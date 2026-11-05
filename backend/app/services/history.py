"""측정 이력(BE-17, 15.8)과 회차 순서 규칙(12.5). 회차 비교(services/compare.py)와 추이(services/trends.py)가 같이 쓴다.

- 회차 순서는 언제나 (measured_on, created_at) 오름차순이다. 가장 이른·가장 최근·바로 앞 회차를 모두 이 순서로 정한다
  (측정일을 직접 고를 수 있고 같은 날 회차가 둘일 수 있어서다).
- 기준 회차는 dog.baseline_session_id가 있으면 그 회차, 없으면 가장 이른 DONE 회차다.
- 모든 조회는 반려견을 기관 ID로 먼저 찾는다(11.6). 없거나 다른 기관이면 404 NOT_FOUND(15.1).
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Dog, MeasureSession, Shot
from app.models.enums import ReportEdition, SessionStatus
from app.schemas.history import ReportStatusesOut, SessionHistoryItem, ValidPassesOut
from app.services.dogs import get_dog
from app.services.sessions import side_counts


def done_sessions(
    db: Session,
    dog_id: uuid.UUID,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    with_metrics: bool = True,
) -> list[MeasureSession]:
    """반려견의 DONE 회차를 12.5 순서로. from·to는 measured_on 기간(날짜 포함).

    with_metrics면 수치 행도 한 번에 읽는다(15.1, 추이가 쓴다). 회차의 순서·기준·직전만 볼 때는 False로 불러 수치 행을
    읽지 않는다(비교는 고른 두 회차의 행만 따로 읽는다. 198 리뷰).
    """
    query = (
        select(MeasureSession)
        .where(MeasureSession.dog_id == dog_id, MeasureSession.status == SessionStatus.DONE.value)
        .order_by(MeasureSession.measured_on, MeasureSession.created_at, MeasureSession.id)
        .execution_options(populate_existing=True)
    )
    if with_metrics:
        query = query.options(selectinload(MeasureSession.metrics))
    if date_from is not None:
        query = query.where(MeasureSession.measured_on >= date_from)
    if date_to is not None:
        query = query.where(MeasureSession.measured_on <= date_to)
    return list(db.scalars(query).all())


def baseline_session_id(dog: Dog, done: list[MeasureSession]) -> uuid.UUID | None:
    """12.5 기준 회차: 지정값이 있으면 그것, 없으면 가장 이른 DONE 회차. DONE 회차가 없고 지정값도 없으면 None."""
    if dog.baseline_session_id is not None:
        return dog.baseline_session_id
    return done[0].id if done else None


def previous_session(done: list[MeasureSession], target: MeasureSession) -> MeasureSession | None:
    """12.5 순서로 target 바로 앞의 DONE 회차. 없으면 None."""
    before = [session for session in done if _order_key(session) < _order_key(target)]
    return before[-1] if before else None


def _order_key(session: MeasureSession) -> tuple:
    return (session.measured_on, session.created_at, session.id)


def _report_statuses(session: MeasureSession) -> ReportStatusesOut:
    by_edition = {report.edition: report.status for report in session.reports}
    return ReportStatusesOut(
        OWNER=by_edition.get(ReportEdition.OWNER.value), VET=by_edition.get(ReportEdition.VET.value)
    )


def _history_item(session: MeasureSession, baseline_id: uuid.UUID | None) -> SessionHistoryItem:
    left, right = side_counts(session.shots)
    return SessionHistoryItem(
        id=session.id,
        measured_on=session.measured_on,
        weight_kg=None if session.weight_kg is None else float(session.weight_kg),
        status=session.status,
        is_baseline=session.id == baseline_id,
        valid_passes=ValidPassesOut(LEFT=left, RIGHT=right),
        model_version=session.model_version,
        reports=_report_statuses(session),
    )


def list_sessions(
    db: Session, institution_id: uuid.UUID, dog_id: uuid.UUID, *, page: int, size: int
) -> tuple[list[SessionHistoryItem], int]:
    """GET /dogs/{dog_id}/sessions(BE-17). 모든 상태의 회차를 measured_on 내림차순, 같으면 created_at 내림차순으로.

    촬영·통과·보고서 행은 selectinload로 한 번에 읽고(N+1 금지), 기준 회차 ID는 쿼리 하나로 정한다.
    """
    dog = get_dog(db, institution_id, dog_id)
    query = (
        select(MeasureSession)
        .where(MeasureSession.dog_id == dog.id)
        .options(
            selectinload(MeasureSession.shots).selectinload(Shot.passes),
            selectinload(MeasureSession.reports),
        )
        .order_by(MeasureSession.measured_on.desc(), MeasureSession.created_at.desc(), MeasureSession.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .execution_options(populate_existing=True)
    )
    sessions = list(db.scalars(query).all())
    total = db.scalar(select(func.count()).select_from(MeasureSession).where(MeasureSession.dog_id == dog.id)) or 0
    baseline_id = dog.baseline_session_id
    if baseline_id is None:
        baseline_id = db.scalar(
            select(MeasureSession.id)
            .where(MeasureSession.dog_id == dog.id, MeasureSession.status == SessionStatus.DONE.value)
            .order_by(MeasureSession.measured_on, MeasureSession.created_at, MeasureSession.id)
            .limit(1)
        )
    return [_history_item(session, baseline_id) for session in sessions], total
