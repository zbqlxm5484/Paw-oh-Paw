"""회차 결과 조회(BE-14·21, 명세 12.3, 15.1, 15.7). 값은 session_metric 행 그대로 보낸다(PR-F09-05).

좌우 차이와 대칭 지수는 저장하지 않고 여기서 계산한다(12.3). 판단 단어를 넣지 않는다(5절).
"""

from __future__ import annotations

import uuid
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.errors import AppError, ErrorCode, JudgeReason, NoticeCode
from app.models import MeasureSession, SessionMetric, Shot
from app.models.enums import Limb, SessionStatus, ShotStatus, Validity
from app.schemas.common import ReasonOut, reason_out
from app.schemas.sessions import (
    ExcludeSummaryOut,
    GaitResultOut,
    LimbCompareOut,
    MetricOut,
    PassCountsOut,
    SessionResultOut,
    ShotCountsOut,
)
from app.services.aggregation import AGGREGATED_GAITS, METRICS
from app.services.sessions import session_query, side_counts, to_session_out

METRIC_ORDER = {metric.code: position for position, metric in enumerate(METRICS)}
LIMB_ORDER = {limb.value: position for position, limb in enumerate(Limb)}
# 앞다리 쌍이 뒷다리 쌍보다 앞이다(15.7 정렬)
COMPARE_PAIRS = (("FORE", Limb.LF.value, Limb.RF.value), ("HIND", Limb.LH.value, Limb.RH.value))
DIFF_PLACES = Decimal("0.0001")
SYMMETRY_PLACES = Decimal("0.01")


def _metric_out(row: SessionMetric) -> MetricOut:
    return MetricOut(
        metric_code=row.metric_code,
        limb=row.limb,
        value=None if row.value is None else float(row.value),
        unit=row.unit,
        measurable=row.measurable,
        unmeasurable_reason=reason_out(row.unmeasurable_reason),
        n_passes=row.n_passes,
    )


def _compare_one(pair: str, code: str, left: SessionMetric | None, right: SessionMetric | None) -> LimbCompareOut:
    """한 수치의 좌우 비교(15.7). 계산은 float가 아니라 Decimal로 한다(15.1)."""
    left_value = left.value if left else None
    right_value = right.value if right else None
    reason: ReasonOut | None = None
    if left is None or right is None:
        reason = reason_out(NoticeCode.NO_DATA.value)
    elif left_value is None:
        reason = reason_out(left.unmeasurable_reason)
    elif right_value is None:
        reason = reason_out(right.unmeasurable_reason)
    comparable = left_value is not None and right_value is not None
    diff: Decimal | None = None
    symmetry: Decimal | None = None
    if comparable:
        diff = (left_value - right_value).quantize(DIFF_PLACES, rounding=ROUND_HALF_UP)
        total = left_value + right_value
        if total != 0:
            symmetry = (abs(left_value - right_value) / (total / 2) * 100).quantize(
                SYMMETRY_PLACES, rounding=ROUND_HALF_UP
            )
    return LimbCompareOut(
        pair=pair,
        metric_code=code,
        unit=(left or right).unit,
        left=None if left_value is None else float(left_value),
        right=None if right_value is None else float(right_value),
        diff=None if diff is None else float(diff),
        symmetry_index=None if symmetry is None else float(symmetry),
        comparable=comparable,
        reason=None if comparable else reason,
    )


def _compare_rank(entry: LimbCompareOut) -> tuple[int, float]:
    """대칭 지수가 있는 항목을 큰 순서로 → 지수만 없는 비교 가능 항목 → 비교할 수 없는 항목(15.7)."""
    if entry.symmetry_index is not None:
        return (0, -entry.symmetry_index)
    return (1, 0.0) if entry.comparable else (2, 0.0)


def limb_compare(rows: list[SessionMetric]) -> list[LimbCompareOut]:
    """다리 비교 요약(BE-21). 같은 값끼리는 sorted가 넣은 순서(12.3 표, FORE → HIND)를 지킨다."""
    by_key = {(row.metric_code, row.limb): row for row in rows}
    codes = sorted(
        {row.metric_code for row in rows if row.limb != Limb.NONE.value},
        key=lambda code: (METRIC_ORDER.get(code, len(METRIC_ORDER)), code),
    )
    entries: list[LimbCompareOut] = []
    for code in codes:
        for pair, left_limb, right_limb in COMPARE_PAIRS:
            left, right = by_key.get((code, left_limb)), by_key.get((code, right_limb))
            if left is not None or right is not None:
                entries.append(_compare_one(pair, code, left, right))
    return sorted(entries, key=_compare_rank)


def _gaits(metrics: list[SessionMetric]) -> list[GaitResultOut]:
    gaits: list[GaitResultOut] = []
    for gait_type in AGGREGATED_GAITS:
        rows = [row for row in metrics if row.gait_type == gait_type]
        if not rows:
            continue
        rows.sort(
            key=lambda row: (
                METRIC_ORDER.get(row.metric_code, len(METRIC_ORDER)),
                row.metric_code,
                LIMB_ORDER.get(row.limb, len(LIMB_ORDER)),
            )
        )
        gaits.append(
            GaitResultOut(
                gait_type=gait_type, metrics=[_metric_out(row) for row in rows], limb_compare=limb_compare(rows)
            )
        )
    return gaits


def _exclude_summary(shots: list[Shot]) -> list[ExcludeSummaryOut]:
    """제외된 통과를 사유별로 센다. 많은 순서, 같으면 코드 순서."""
    counts = Counter(
        walk_pass.exclude_reason or JudgeReason.UNKNOWN_REASON.value
        for shot in shots
        for walk_pass in shot.passes
        if not walk_pass.is_valid
    )
    return [
        ExcludeSummaryOut(**reason_out(code).model_dump(), count=count)
        for code, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def session_result(
    db: Session, institution_id: uuid.UUID, session_id: uuid.UUID, *, include_trashed: bool = False
) -> SessionResultOut:
    """GET /sessions/{id}/result. 없거나 다른 기관이면 404, DONE이 아니면 409 SESSION_NOT_DONE.

    include_trashed는 워커의 보고서 생성만 쓴다. 휴지통에 들어간 뒤에도 보고서를 끝까지 만들어 두어야 복원했을 때
    결과가 있다(12.5).
    """
    session = (
        db.scalars(
            session_query(institution_id, session_id, include_trashed=include_trashed)
            .options(
                joinedload(MeasureSession.staff),
                selectinload(MeasureSession.shots).selectinload(Shot.passes),
                selectinload(MeasureSession.metrics),
            )
            .execution_options(populate_existing=True)
        )
        .unique()
        .one_or_none()
    )
    if session is None:
        raise AppError(ErrorCode.NOT_FOUND)
    if session.status != SessionStatus.DONE:
        raise AppError(ErrorCode.SESSION_NOT_DONE)

    passes = [walk_pass for shot in session.shots for walk_pass in shot.passes]
    used = sum(1 for walk_pass in passes if walk_pass.is_valid)
    left, right = side_counts(session.shots)
    notices = [reason_out(NoticeCode.ONE_SIDE_ONLY.value)] if (left > 0) != (right > 0) else []
    return SessionResultOut(
        **to_session_out(session).model_dump(),
        pass_counts=PassCountsOut(measured=len(passes), used=used, excluded=len(passes) - used),
        shot_counts=ShotCountsOut(
            total=len(session.shots),
            failed=sum(1 for shot in session.shots if shot.status == ShotStatus.FAILED),
            invalid=sum(1 for shot in session.shots if shot.validity == Validity.INVALID),
        ),
        exclude_summary=_exclude_summary(session.shots),
        notices=notices,
        gaits=_gaits(session.metrics),
    )
