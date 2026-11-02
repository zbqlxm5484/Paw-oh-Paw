"""회차 집계(BE-13, 명세 6절, 12.3, 12.4, 12.5).

측정 종료 뒤 워커가 부른다. 회차의 DONE 촬영마다 analysis.json을 읽어 유효 통과의 수치를 보행 유형별·다리별로 묶고,
session_metric 행과 회차 DONE, 보고서 PENDING 행을 한 트랜잭션에 넣는다(12.4). commit은 워커가 한다.

묶는 규칙(12.3 "회차 값"):
- 다리는 통과의 camera_side 쪽이다. RIGHT 통과는 RF·RH, LEFT 통과는 LF·LH의 값이다.
- 회차 값은 측정된 통과들의 중앙값이고 n_passes는 그 수다. gait_cycles만 합이다.
- stifle_cv는 모든 통과의 보행 주기별 무릎 가동 범위를 모아 표본 표준편차 ÷ 평균 × 100으로 계산한다.
- 잴 유효 통과가 없는 다리는 NO_PASS_FOR_LIMB, 통과들이 모두 측정 불가면 가장 많은 사유로 측정 불가 행을 넣는다.
  통과들이 그 수치를 아예 보내지 않았으면 행을 넣지 않는다(결과 조회에서 NO_DATA).
- 집계는 WALK·TROT만 한다(15.7). 유효 통과가 하나도 없는 회차도 오류가 아니라 수치 행 없는 DONE이다.
"""

from __future__ import annotations

import json
import logging
import math
import statistics
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.clients.analysis import map_reason
from app.core.errors import JudgeReason
from app.models import MeasureSession, Report, SessionMetric, Shot
from app.models.enums import CameraSide, GaitType, Limb, ReportEdition, SessionStatus, ShotStatus
from app.report import TEMPLATE_VERSION
from app.services.analysis_results import ResultFormatError, parse_result
from app.storage.base import StorageError, StorageService

logger = logging.getLogger(__name__)

AGGREGATED_GAITS = (GaitType.WALK.value, GaitType.TROT.value)
FORE_LIMBS = (Limb.LF.value, Limb.RF.value)
HIND_LIMBS = (Limb.LH.value, Limb.RH.value)
ALL_LIMBS = FORE_LIMBS + HIND_LIMBS
WHOLE_BODY = (Limb.NONE.value,)
LIMBS_OF_SIDE = {
    CameraSide.LEFT.value: (Limb.LF.value, Limb.LH.value),
    CameraSide.RIGHT.value: (Limb.RF.value, Limb.RH.value),
}
# session_metric.value는 NUMERIC(10,4)다(12.2). 넘는 값을 DB까지 보내면 저장 중 오류가 난다
VALUE_LIMIT = Decimal("1000000")
STIFLE_CV = "stifle_cv"
GAIT_CYCLES = "gait_cycles"
# 분석 결과에서 stifle_cv의 재료가 들어 있는 키. {"values": [주기마다 가동 범위], "unit": "deg"}
STIFLE_CYCLE_ROM = "stifle_cycle_rom"


class AggregationError(Exception):
    """analysis.json을 읽을 수 없어 수치를 계산하지 못할 때. 워커는 회차를 FAILED(AGGREGATION_FAILED)로 둔다."""


@dataclass(frozen=True)
class MetricDef:
    code: str
    unit: str
    limbs: tuple[str, ...]


# 12.3 표 순서. 결과 조회의 정렬도 이 순서를 쓴다(15.7)
METRICS: tuple[MetricDef, ...] = (
    MetricDef("rom_shoulder", "deg", FORE_LIMBS),
    MetricDef("rom_elbow", "deg", FORE_LIMBS),
    MetricDef("rom_carpus", "deg", FORE_LIMBS),
    MetricDef("rom_hip", "deg", HIND_LIMBS),
    MetricDef("rom_stifle", "deg", HIND_LIMBS),
    MetricDef("rom_tarsus", "deg", HIND_LIMBS),
    MetricDef("angle_median_shoulder", "deg", FORE_LIMBS),
    MetricDef("angle_median_elbow", "deg", FORE_LIMBS),
    MetricDef("angle_median_carpus", "deg", FORE_LIMBS),
    MetricDef("angle_median_hip", "deg", HIND_LIMBS),
    MetricDef("angle_median_stifle", "deg", HIND_LIMBS),
    MetricDef("angle_median_tarsus", "deg", HIND_LIMBS),
    MetricDef(STIFLE_CV, "pct", HIND_LIMBS),
    MetricDef("paw_lift", "pct_body", ALL_LIMBS),
    MetricDef("paw_excursion", "pct_body", ALL_LIMBS),
    MetricDef("stride_length", "pct_body", ALL_LIMBS),
    MetricDef("stance_ratio", "pct", ALL_LIMBS),
    MetricDef("walk_speed", "body_per_sec", WHOLE_BODY),
    MetricDef(GAIT_CYCLES, "count", WHOLE_BODY),
)


@dataclass(frozen=True)
class PassMetrics:
    """유효 통과 하나의 수치(analysis.json의 passes[].metrics)."""

    shot_id: uuid.UUID
    gait_type: str
    camera_side: str
    metrics: dict[str, Any]

    def covers(self, limb: str) -> bool:
        return limb == Limb.NONE.value or limb in LIMBS_OF_SIDE[self.camera_side]


@dataclass(frozen=True)
class MetricRow:
    """session_metric 한 행(12.2)."""

    gait_type: str
    limb: str
    metric_code: str
    value: Decimal | None
    unit: str
    measurable: bool
    unmeasurable_reason: str | None
    n_passes: int


def _json_key(metric: MetricDef, limb: str) -> str:
    """분석 결과의 키. 앞·뒷다리 값을 한 통과에 함께 보내는 수치만 _front·_hind가 붙는다(6절 계약)."""
    if metric.limbs != ALL_LIMBS:
        return metric.code
    return f"{metric.code}_front" if limb in FORE_LIMBS else f"{metric.code}_hind"


def _decimal(raw: Any) -> Decimal | None:
    """JSON 숫자 → Decimal. float의 이진 오차가 DB에 들어가지 않게 문자열을 거친다. 숫자가 아니거나 범위 밖이면 None."""
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        return None
    if isinstance(raw, float) and not math.isfinite(raw):
        return None
    number = Decimal(str(raw))
    return number if abs(number) < VALUE_LIMIT else None


def _read_value(item: PassMetrics, key: str) -> tuple[Decimal | None, str | None]:
    """통과 하나의 값. (값, None) 또는 (None, 측정 불가 사유)."""
    entry = item.metrics[key]
    raw = entry.get("value") if isinstance(entry, dict) else None
    if raw is None:
        reason = entry.get("reason") if isinstance(entry, dict) else None
        return None, map_reason(reason, shot_id=item.shot_id, where=f"metrics.{key}")
    number = _decimal(raw)
    if number is None:
        logger.warning("unusable metric value in metrics.%s shot=%s", key, item.shot_id)
        return None, JudgeReason.UNKNOWN_REASON.value
    return number, None


def _row(
    gait_type: str,
    metric: MetricDef,
    limb: str,
    *,
    value: Decimal | None = None,
    reason: str | None = None,
    n_passes: int,
) -> MetricRow:
    return MetricRow(
        gait_type=gait_type,
        limb=limb,
        metric_code=metric.code,
        value=value,
        unit=metric.unit,
        measurable=value is not None,
        unmeasurable_reason=reason,
        n_passes=n_passes,
    )


def _most_common(reasons: list[str]) -> str:
    return Counter(reasons).most_common(1)[0][0]


def _stifle_cv_row(gait_type: str, metric: MetricDef, limb: str, passes: list[PassMetrics]) -> MetricRow | None:
    cycles: list[Decimal] = []
    reasons: list[str] = []
    used = 0
    for item in passes:
        if STIFLE_CYCLE_ROM not in item.metrics:
            continue
        entry = item.metrics[STIFLE_CYCLE_ROM]
        raw_values = entry.get("values") if isinstance(entry, dict) else None
        numbers = [_decimal(raw) for raw in raw_values] if isinstance(raw_values, list) else []
        numbers = [number for number in numbers if number is not None]
        if numbers:
            cycles.extend(numbers)
            used += 1
            continue
        reason = entry.get("reason") if isinstance(entry, dict) else None
        reasons.append(
            JudgeReason.NOT_ENOUGH_CYCLES.value
            if reason is None
            else map_reason(reason, shot_id=item.shot_id, where=f"metrics.{STIFLE_CYCLE_ROM}")
        )
    if not used and not reasons:
        return None
    if not used:
        return _row(gait_type, metric, limb, reason=_most_common(reasons), n_passes=len(reasons))
    not_enough = _row(gait_type, metric, limb, reason=JudgeReason.NOT_ENOUGH_CYCLES.value, n_passes=used)
    if len(cycles) < 2:
        return not_enough
    mean = statistics.mean(cycles)
    if mean == 0:
        return not_enough
    value = statistics.stdev(cycles) / mean * 100
    return _row(gait_type, metric, limb, value=value, n_passes=used) if abs(value) < VALUE_LIMIT else not_enough


def _metric_row(gait_type: str, metric: MetricDef, limb: str, passes: list[PassMetrics]) -> MetricRow | None:
    if not passes:
        return _row(gait_type, metric, limb, reason=JudgeReason.NO_PASS_FOR_LIMB.value, n_passes=0)
    if metric.code == STIFLE_CV:
        return _stifle_cv_row(gait_type, metric, limb, passes)
    key = _json_key(metric, limb)
    values: list[Decimal] = []
    reasons: list[str] = []
    for item in passes:
        if key not in item.metrics:
            continue
        number, reason = _read_value(item, key)
        if number is not None:
            values.append(number)
        else:
            reasons.append(reason)
    if values:
        value = sum(values) if metric.code == GAIT_CYCLES else statistics.median(values)
        return _row(gait_type, metric, limb, value=value, n_passes=len(values))
    if reasons:
        return _row(gait_type, metric, limb, reason=_most_common(reasons), n_passes=len(reasons))
    return None


def build_metric_rows(passes: list[PassMetrics]) -> list[MetricRow]:
    """유효 통과들 → session_metric 행. 유형별로, 12.3 표 순서로."""
    rows: list[MetricRow] = []
    for gait_type in AGGREGATED_GAITS:
        gait_passes = [item for item in passes if item.gait_type == gait_type]
        if not gait_passes:
            continue
        for metric in METRICS:
            for limb in metric.limbs:
                row = _metric_row(gait_type, metric, limb, [item for item in gait_passes if item.covers(limb)])
                if row is not None:
                    rows.append(row)
    return rows


def load_passes(storage: StorageService, shots: list[Shot]) -> list[PassMetrics]:
    """DONE 촬영의 analysis.json에서 유효 통과를 읽는다(6절: 통과별 수치는 JSON에만 있다)."""
    passes: list[PassMetrics] = []
    for shot in shots:
        if shot.status != ShotStatus.DONE:
            continue
        if shot.analysis_key is None:
            raise AggregationError(f"shot={shot.id} has no analysis.json")
        try:
            result = json.loads(storage.read_bytes(shot.analysis_key))
            parsed = parse_result(result, shot_id=shot.id)
        except (StorageError, OSError, ValueError) as e:
            # str(e)에는 파일 경로가 섞일 수 있어 종류만 남긴다(11.8)
            raise AggregationError(f"shot={shot.id} analysis.json unreadable: {type(e).__name__}") from e
        except ResultFormatError as e:
            raise AggregationError(f"shot={shot.id} analysis.json format: {e}") from e
        # parse_result는 받은 순서를 지키므로 raw와 짝이 맞는다
        for row, raw in zip(parsed.passes, result["passes"], strict=True):
            if not row.is_valid:
                continue
            if row.gait_type not in AGGREGATED_GAITS:
                logger.warning("valid pass %d has gait %s shot=%s; left out", row.pass_no, row.gait_type, shot.id)
                continue
            metrics = raw.get("metrics")
            passes.append(
                PassMetrics(
                    shot_id=shot.id,
                    gait_type=row.gait_type,
                    camera_side=row.camera_side,
                    metrics=metrics if isinstance(metrics, dict) else {},
                )
            )
    return passes


def aggregate_session(db: Session, storage: StorageService, session_id: uuid.UUID, *, now: datetime) -> bool:
    """AGGREGATING 회차를 잠그고 수치 행·DONE·보고서 PENDING 행을 넣는다(flush까지, 12.4).

    그사이 지워졌거나 상태가 바뀌었으면 아무것도 쓰지 않고 False다. 파일을 읽을 수 없으면 AggregationError.
    """
    locked = db.execute(
        select(MeasureSession.id)
        .where(MeasureSession.id == session_id, MeasureSession.status == SessionStatus.AGGREGATING.value)
        .with_for_update()
    ).first()
    if locked is None:
        return False
    # populate_existing: 같은 세션의 상태 조회가 읽어 둔 촬영이 있어도 DB에서 다시 채운다
    shots = list(
        db.scalars(
            select(Shot)
            .where(Shot.session_id == session_id)
            .order_by(Shot.seq_no)
            .execution_options(populate_existing=True)
        )
    )
    rows = build_metric_rows(load_passes(storage, shots))
    done_shots = [shot for shot in shots if shot.status == ShotStatus.DONE]
    versions = {shot.model_version for shot in done_shots}
    if len(versions) > 1:
        logger.warning("session %s mixes model versions; keeping the last shot's", session_id)
    last = done_shots[-1] if done_shots else None
    db.execute(
        update(MeasureSession)
        .where(MeasureSession.id == session_id, MeasureSession.status == SessionStatus.AGGREGATING.value)
        .values(
            status=SessionStatus.DONE.value,
            aggregated_at=now,
            fail_reason=None,
            model_name=last.model_name if last else None,
            model_version=last.model_version if last else None,
        )
    )
    db.add_all(SessionMetric(session_id=session_id, **asdict(row)) for row in rows)
    db.add_all(
        Report(session_id=session_id, edition=edition.value, template_version=TEMPLATE_VERSION)
        for edition in ReportEdition
    )
    db.flush()
    return True
