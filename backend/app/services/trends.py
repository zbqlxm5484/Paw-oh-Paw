"""수치 추이(BE-18, 명세 5절, 15.8, S15P31A404-198). 한 수치·한 보행 유형을 DONE 회차 순서(12.5)로 잇는다.

- series는 그 수치의 다리 전부(12.3 표의 limb)이고 관심 다리가 먼저다. 행이 없는 회차는 점을 넣지 않고,
  측정 불가면 value가 null인 점을 넣는다. 점이 하나도 없는 다리는 빈 배열이다.
- lr_diff는 양쪽이 모두 측정된 회차만 점으로 넣는다. 계산은 결과 조회의 limb_compare(12.3 식, Decimal)를 그대로 쓴다.
  limb를 주면 그 다리가 속한 쌍만, 다리 구분이 없는 수치(walk_speed, gait_cycles)는 빈 배열이다.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.models import MeasureSession, SessionMetric
from app.models.enums import GaitType, Limb
from app.schemas.common import reason_out
from app.schemas.history import LrDiffPointOut, LrDiffSeriesOut, TrendPointOut, TrendSeriesOut, TrendsOut
from app.services.aggregation import METRICS, MetricDef
from app.services.compare import limb_order
from app.services.dogs import get_dog
from app.services.history import done_sessions
from app.services.session_results import COMPARE_PAIRS, limb_compare

METRIC_BY_CODE: dict[str, MetricDef] = {metric.code: metric for metric in METRICS}


def _metric_def(metric_code: str) -> MetricDef:
    """12.3 표에 없는 코드는 422 VALIDATION_ERROR(FastAPI의 입력 검사 오류와 같은 모양)."""
    metric = METRIC_BY_CODE.get(metric_code)
    if metric is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, {"fields": [{"field": "metric_code", "type": "enum"}]})
    return metric


def _rows(session: MeasureSession, gait_type: str, metric_code: str) -> list[SessionMetric]:
    return [row for row in session.metrics if row.gait_type == gait_type and row.metric_code == metric_code]


def _point(session: MeasureSession, row: SessionMetric) -> TrendPointOut:
    return TrendPointOut(
        session_id=session.id,
        measured_on=session.measured_on,
        value=None if row.value is None else float(row.value),
        measurable=row.measurable,
        unmeasurable_reason=reason_out(row.unmeasurable_reason),
        model_version=session.model_version,
    )


def _lr_points(sessions: list[MeasureSession], pair: str, gait_type: str, metric_code: str) -> list[LrDiffPointOut]:
    points: list[LrDiffPointOut] = []
    for session in sessions:
        for entry in limb_compare(_rows(session, gait_type, metric_code)):
            if entry.pair == pair and entry.comparable and entry.diff is not None:
                points.append(
                    LrDiffPointOut(
                        session_id=session.id,
                        measured_on=session.measured_on,
                        diff=entry.diff,
                        symmetry_index=entry.symmetry_index,
                    )
                )
    return points


def trends(
    db: Session,
    institution_id: uuid.UUID,
    dog_id: uuid.UUID,
    *,
    metric_code: str,
    gait_type: GaitType,
    limb: Limb | None,
    date_from: date | None,
    date_to: date | None,
) -> TrendsOut:
    """GET /dogs/{dog_id}/trends(BE-18). DONE 회차만, measured_on 오름차순(같으면 created_at)."""
    metric = _metric_def(metric_code)
    dog = get_dog(db, institution_id, dog_id)
    sessions = done_sessions(db, dog.id, date_from=date_from, date_to=date_to)
    gait = gait_type.value
    order = limb_order(dog.focus_limb)

    limbs = [value for value in metric.limbs if limb is None or value == limb.value]
    limbs.sort(key=lambda value: order.get(value, len(order)))
    series = [
        TrendSeriesOut(
            limb=value,
            points=[
                _point(session, row)
                for session in sessions
                for row in _rows(session, gait, metric.code)
                if row.limb == value
            ],
        )
        for value in limbs
    ]

    pairs = [
        (pair, left, right)
        for pair, left, right in COMPARE_PAIRS
        if left in metric.limbs and right in metric.limbs and (limb is None or limb.value in (left, right))
    ]
    # 관심 다리가 속한 쌍이 먼저, 나머지는 앞다리 → 뒷다리(15.7)
    pairs.sort(key=lambda item: min(order.get(item[1], len(order)), order.get(item[2], len(order))))
    lr_diff = [LrDiffSeriesOut(pair=pair, points=_lr_points(sessions, pair, gait, metric.code)) for pair, _, _ in pairs]
    return TrendsOut(
        dog_id=dog.id, metric_code=metric.code, unit=metric.unit, gait_type=gait, series=series, lr_diff=lr_diff
    )
