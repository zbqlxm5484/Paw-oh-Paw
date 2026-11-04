"""회차 비교(BE-18, 명세 5절 비교 규칙, 15.8, S15P31A404-198).

두 회차의 session_metric 행을 모아 report/judge.py의 판정 함수 하나를 부른다(보고서의 직전 회차 비교와 같은 함수).
오차 범위는 services/tolerance.py가 읽은 config/tolerance.yaml이고, 통과 수 조건(그 수치·그 다리의 n_passes 8 이상)은
judge.usable_tolerance가 본다.

- items는 두 회차 어느 쪽에라도 있는 (gait_type, limb, metric_code)의 합집합이다. 보행 유형이 키에 들어 있으므로 평보와
  속보는 서로 비교되지 않는다(PR-F08-14).
- 정렬은 보행 유형(15.7 순서), 다리(반려견의 focus_limb 먼저, 나머지는 LF·RF·LH·RH·NONE), 12.3 표 순서다.
- "좋아짐·나빠짐" 같은 평가 단어는 내지 않는다(5절). 방향(INCREASE·DECREASE)과 사유 코드만 낸다.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.models import Dog, MeasureSession, SessionMetric
from app.models.enums import GaitType, Limb, SessionStatus
from app.report.judge import judge, usable_tolerance
from app.schemas.common import reason_out
from app.schemas.history import CompareBaseOut, CompareItemOut, CompareOut, CompareTargetOut
from app.services.aggregation import AGGREGATED_GAITS
from app.services.dogs import get_dog
from app.services.history import baseline_session_id, done_sessions, previous_session
from app.services.session_results import METRIC_ORDER
from app.services.tolerance import get_tolerance

# base 쿼리의 종류(15.8 kind)
BASELINE = "BASELINE"
PREVIOUS = "PREVIOUS"
SESSION = "SESSION"

# 400 COMPARE_INVALID의 detail.reason(15.8)
NO_DONE_SESSION = "NO_DONE_SESSION"
SAME_SESSION = "SAME_SESSION"
NO_PREVIOUS = "NO_PREVIOUS"
NOT_DONE = "NOT_DONE"

GAIT_ORDER = {gait: position for position, gait in enumerate(AGGREGATED_GAITS)}
DEFAULT_LIMB_ORDER = (Limb.LF.value, Limb.RF.value, Limb.LH.value, Limb.RH.value, Limb.NONE.value)

MetricKey = tuple[str, str, str]  # (gait_type, limb, metric_code)


def _invalid(reason: str) -> AppError:
    return AppError(ErrorCode.COMPARE_INVALID, {"reason": reason})


def limb_order(focus_limb: str | None) -> dict[str, int]:
    """다리 정렬 순서: 관심 다리가 먼저, 나머지는 LF·RF·LH·RH·NONE(15.8). 추이의 series도 같은 순서를 쓴다."""
    limbs = [limb for limb in DEFAULT_LIMB_ORDER if limb != focus_limb]
    if focus_limb is not None:
        limbs.insert(0, focus_limb)
    return {limb: position for position, limb in enumerate(limbs)}


def _session_of_dog(db: Session, dog: Dog, session_id: uuid.UUID, done: list[MeasureSession]) -> MeasureSession:
    """쿼리로 받은 회차 ID는 이 반려견 안에서만 찾는다(15.1). 없으면 404, 있는데 DONE이 아니면 400 NOT_DONE."""
    for session in done:
        if session.id == session_id:
            return session
    session = db.scalars(
        select(MeasureSession)
        .where(MeasureSession.id == session_id, MeasureSession.dog_id == dog.id)
        .options(selectinload(MeasureSession.metrics))
    ).one_or_none()
    if session is None:
        raise AppError(ErrorCode.NOT_FOUND)
    if session.status != SessionStatus.DONE:
        raise _invalid(NOT_DONE)
    return session


def parse_base(raw: str) -> tuple[str, uuid.UUID | None]:
    """base 쿼리 → (kind, 회차 ID). 형식은 라우터가 BASE_QUERY_PATTERN으로 먼저 거른다."""
    if raw in (BASELINE, PREVIOUS):
        return raw, None
    return SESSION, uuid.UUID(raw)


def _value(row: SessionMetric | None) -> float | None:
    return None if row is None or row.value is None else float(row.value)


def _rows(session: MeasureSession, gait_type: str | None) -> dict[MetricKey, SessionMetric]:
    return {
        (row.gait_type, row.limb, row.metric_code): row
        for row in session.metrics
        if gait_type is None or row.gait_type == gait_type
    }


def compare_rows(
    base_rows: dict[MetricKey, SessionMetric],
    target_rows: dict[MetricKey, SessionMetric],
    *,
    tolerance: dict[str, float],
    model_changed: bool,
    focus_limb: str | None,
) -> list[CompareItemOut]:
    """두 회차의 행을 키로 맞춰 항목마다 판정한다. 행이 한쪽에만 있으면 judge가 NOT_COMPARABLE·NO_DATA를 낸다."""
    limbs = limb_order(focus_limb)
    items: list[CompareItemOut] = []
    for key in sorted(
        set(base_rows) | set(target_rows),
        key=lambda key: (
            GAIT_ORDER.get(key[0], len(GAIT_ORDER)),
            limbs.get(key[1], len(limbs)),
            METRIC_ORDER.get(key[2], len(METRIC_ORDER)),
            key[2],
        ),
    ):
        gait_type, limb, code = key
        base, target = base_rows.get(key), target_rows.get(key)
        # 오차 범위는 두 회차 모두 그 수치·그 다리의 n_passes가 8 이상일 때만 견준다(15.8, 박규원 MR 86 답변)
        usable = usable_tolerance(
            tolerance.get(code), base.n_passes if base else None, target.n_passes if target else None
        )
        verdict = judge(
            _value(base),
            _value(target),
            usable,
            model_changed=model_changed,
            base_reason=base.unmeasurable_reason if base else None,
            target_reason=target.unmeasurable_reason if target else None,
        )
        items.append(
            CompareItemOut(
                metric_code=code,
                limb=limb,
                gait_type=gait_type,
                unit=(base or target).unit,
                base_value=_value(base),
                target_value=_value(target),
                diff=verdict.diff,
                judgement=verdict.judgement,
                note=reason_out(verdict.note),
            )
        )
    return items


def compare_sessions(
    db: Session,
    institution_id: uuid.UUID,
    dog_id: uuid.UUID,
    *,
    target_id: uuid.UUID | None,
    base: str,
    gait_type: GaitType | None,
) -> CompareOut:
    """GET /dogs/{dog_id}/compare(BE-18). 비교할 수 없는 요청은 400 COMPARE_INVALID + detail.reason(15.8)."""
    dog = get_dog(db, institution_id, dog_id)
    done = done_sessions(db, dog.id)
    if not done:
        raise _invalid(NO_DONE_SESSION)
    target = done[-1] if target_id is None else _session_of_dog(db, dog, target_id, done)

    kind, base_id = parse_base(base)
    if kind == PREVIOUS:
        base_session = previous_session(done, target)
        if base_session is None:
            raise _invalid(NO_PREVIOUS)
    else:
        if kind == BASELINE:
            base_id = baseline_session_id(dog, done)
        assert base_id is not None  # DONE 회차가 있으니 기준 회차도 있다
        base_session = _session_of_dog(db, dog, base_id, done)
    if base_session.id == target.id:
        raise _invalid(SAME_SESSION)

    gait = None if gait_type is None else gait_type.value
    model_changed = base_session.model_version != target.model_version
    items = compare_rows(
        _rows(base_session, gait),
        _rows(target, gait),
        tolerance=get_tolerance(get_settings().TOLERANCE_FILE),
        model_changed=model_changed,
        focus_limb=dog.focus_limb,
    )
    return CompareOut(
        dog_id=dog.id,
        base=CompareBaseOut(
            session_id=base_session.id,
            measured_on=base_session.measured_on,
            model_version=base_session.model_version,
            kind=kind,
        ),
        target=CompareTargetOut(
            session_id=target.id, measured_on=target.measured_on, model_version=target.model_version
        ),
        model_changed=model_changed,
        items=items,
    )
