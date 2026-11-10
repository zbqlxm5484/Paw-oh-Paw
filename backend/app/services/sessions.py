"""회차 시작·조회·측정 종료·취소(12.4, 12.5, 13.3, 15.6). 모든 조회는 기관 ID로 거른다(11.6)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, joinedload, selectinload

from app.clients.analysis import AnalysisClient
from app.core.config import get_settings
from app.core.dates import today_local
from app.core.errors import AppError, ErrorCode, NoticeCode
from app.models import Dog, DogNote, DogVital, MeasureSession, Report, SessionMetric, Shot, WalkPass
from app.models.enums import CameraSide, SessionStatus, ShotStatus
from app.schemas.common import ReasonOut, reason_out
from app.schemas.sessions import (
    DogBriefOut,
    DogNameOut,
    ProgressOut,
    SessionCreate,
    SessionDetailOut,
    SessionListItem,
    SessionOut,
    SideProgressOut,
    StaffBriefOut,
)
from app.services.analysis_copies import ShotJob, delete_shot_copies
from app.services.dogs import classify, in_institution
from app.services.shots import to_shot_out
from app.services.symmetry import session_scores
from app.services.vitals import save_vital
from app.storage.base import get_storage
from app.storage.keys import session_prefix

IN_PROGRESS_STATUSES = (ShotStatus.SUBMITTED.value, ShotStatus.ANALYZING.value)


def to_session_out(session: MeasureSession) -> SessionOut:
    return SessionOut(
        id=session.id,
        dog_id=session.dog_id,
        staff=StaffBriefOut.model_validate(session.staff),
        measured_on=session.measured_on,
        weight_kg=session.weight_kg,
        size_class=session.size_class,
        status=session.status,
        fail_reason=reason_out(session.fail_reason),
        model_name=session.model_name,
        model_version=session.model_version,
        completed_at=session.completed_at,
        aggregated_at=session.aggregated_at,
        created_at=session.created_at,
    )


def start_session(
    db: Session, *, institution_id: uuid.UUID, staff_id: uuid.UUID, dog_id: uuid.UUID, data: SessionCreate
) -> MeasureSession:
    """회차 시작(BE-04). 반려견 행을 잠근 뒤 MEASURING 회차가 있는지 본다(12.4). 있으면 409 SESSION_ALREADY_OPEN.

    회차 체급(12.5): 담당자가 반려견 체급을 직접 지정했으면 그 값, 아니면 그날 체중(없으면 등록 체중)으로 정한다.
    vital을 보내면 그날 바이탈로 저장하고 이 회차와 묶는다(15.6). weight_kg가 없으면 vital의 체중이 회차 체중이고,
    둘이 다르면 422다. vital의 체중은 바이탈 규칙대로 반려견의 등록 체중에도 반영된다(12.5, v1.41).
    """
    weight = data.weight_kg
    if data.vital is not None:
        if weight is not None and weight != data.vital.weight_kg:
            raise AppError(ErrorCode.VALIDATION_ERROR, {"fields": [{"field": "vital.weight_kg", "type": "mismatch"}]})
        weight = data.vital.weight_kg
    dog = db.scalars(
        select(Dog).where(Dog.id == dog_id, in_institution(institution_id)).with_for_update()
    ).one_or_none()
    if dog is None:
        raise AppError(ErrorCode.NOT_FOUND)
    open_id = db.scalar(
        select(MeasureSession.id).where(
            MeasureSession.dog_id == dog.id, MeasureSession.status == SessionStatus.MEASURING.value
        )
    )
    if open_id is not None:
        raise AppError(ErrorCode.SESSION_ALREADY_OPEN, {"session_id": str(open_id)})
    weight_for_size = weight if weight is not None else dog.weight_kg
    session = MeasureSession(
        dog_id=dog.id,
        staff_id=staff_id,
        measured_on=data.measured_on or today_local(),
        weight_kg=weight,
        size_class=dog.size_class if dog.size_class_manual else classify(weight_for_size),
    )
    db.add(session)
    db.flush()
    if data.vital is not None:  # 반려견 행을 잠근 채라 같은 날 두 줄이 생기지 않는다
        save_vital(
            db,
            dog=dog,
            measured_on=session.measured_on,
            values=data.vital.model_dump(),
            staff_id=staff_id,
            session_id=session.id,
        )
    db.refresh(session)
    return session


def session_query(institution_id: uuid.UUID, session_id: uuid.UUID, *, include_trashed: bool = False):
    """기관으로 거른 회차 조회. include_trashed는 워커의 보고서 생성만 쓴다(휴지통의 반려견도 만든다, 12.5)."""
    owner = Dog.institution_id == institution_id if include_trashed else in_institution(institution_id)
    return (
        select(MeasureSession).join(Dog, MeasureSession.dog_id == Dog.id).where(MeasureSession.id == session_id, owner)
    )


def list_sessions(
    db: Session,
    institution_id: uuid.UUID,
    *,
    staff_id: uuid.UUID | None,
    status: str | None,
    page: int,
    size: int,
) -> tuple[list[SessionListItem], int]:
    """GET /sessions(BE-33, 15.6). 기관의 모든 회차를 measured_on 내림차순, 같으면 created_at 내림차순으로.

    휴지통의 반려견은 뺀다. 반려견 이름은 같은 쿼리로, 담당자는 joinedload로, 대칭 점수는 이 페이지의 DONE 회차만
    쿼리 한 번으로 읽는다(15.1 N+1 금지).
    """
    conditions = [in_institution(institution_id)]
    if staff_id is not None:
        conditions.append(MeasureSession.staff_id == staff_id)
    if status is not None:
        conditions.append(MeasureSession.status == status)
    rows = db.execute(
        select(MeasureSession, Dog.name)
        .join(Dog, MeasureSession.dog_id == Dog.id)
        .where(*conditions)
        .options(joinedload(MeasureSession.staff))
        .order_by(MeasureSession.measured_on.desc(), MeasureSession.created_at.desc(), MeasureSession.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .execution_options(populate_existing=True)
    ).all()
    total = (
        db.scalar(
            select(func.count())
            .select_from(MeasureSession)
            .join(Dog, MeasureSession.dog_id == Dog.id)
            .where(*conditions)
        )
        or 0
    )
    scores = session_scores(db, [session.id for session, _ in rows if session.status == SessionStatus.DONE.value])
    items = [
        SessionListItem(
            id=session.id,
            measured_on=session.measured_on,
            status=session.status,
            fail_reason=reason_out(session.fail_reason),
            dog=DogNameOut(id=session.dog_id, name=dog_name),
            staff=StaffBriefOut.model_validate(session.staff),
            weight_kg=session.weight_kg,
            model_version=session.model_version,
            symmetry_score=scores.get(session.id),
            completed_at=session.completed_at,
            created_at=session.created_at,
        )
        for session, dog_name in rows
    ]
    return items, total


def get_session(
    db: Session, institution_id: uuid.UUID, session_id: uuid.UUID, *, for_update: bool = False
) -> MeasureSession:
    """없거나 다른 기관의 회차면 똑같이 404 NOT_FOUND(15.1). for_update면 회차 행을 잠근다(joinedload 없이, 11.7)."""
    query = session_query(institution_id, session_id)
    if for_update:
        query = query.with_for_update(of=MeasureSession)
    session = db.scalars(query).one_or_none()
    if session is None:
        raise AppError(ErrorCode.NOT_FOUND)
    return session


def side_counts(shots: list[Shot]) -> tuple[int, int]:
    """DONE 촬영의 유효 통과를 보행 유형 구분 없이 camera_side별로 센다(왼쪽, 오른쪽). 15.6·15.7이 같은 기준을 쓴다."""
    counts = {CameraSide.LEFT.value: 0, CameraSide.RIGHT.value: 0}
    for shot in shots:
        if shot.status != ShotStatus.DONE:
            continue
        for walk_pass in shot.passes:
            if walk_pass.is_valid and walk_pass.camera_side in counts:
                counts[walk_pass.camera_side] += 1
    return counts[CameraSide.LEFT.value], counts[CameraSide.RIGHT.value]


def session_detail(db: Session, institution_id: uuid.UUID, session_id: uuid.UUID) -> SessionDetailOut:
    """GET /sessions/{id}: 회차·반려견·진행·촬영을 한 번에 준다. 딸린 행은 selectinload로 한 번에 읽는다(15.1)."""
    # populate_existing: 같은 세션이 전에 읽어 둔 촬영 목록이 있어도 DB에서 다시 채운다(2~3초마다 다시 부르는 화면용).
    session = (
        db.scalars(
            session_query(institution_id, session_id)
            .options(
                joinedload(MeasureSession.dog),
                joinedload(MeasureSession.staff),
                selectinload(MeasureSession.shots).selectinload(Shot.passes),
            )
            .execution_options(populate_existing=True)
        )
        .unique()
        .one_or_none()
    )
    if session is None:
        raise AppError(ErrorCode.NOT_FOUND)

    recommended = get_settings().RECOMMENDED_PASSES
    left, right = side_counts(session.shots)

    notices: list[ReasonOut] = []
    if left >= recommended and right >= recommended:
        notices.append(reason_out(NoticeCode.RECOMMENDED_MET.value))
    elif (left > 0) != (right > 0):
        notices.append(reason_out(NoticeCode.ONE_SIDE_ONLY.value))

    shots = sorted(session.shots, key=lambda s: s.seq_no, reverse=True)
    return SessionDetailOut(
        **to_session_out(session).model_dump(),
        dog=DogBriefOut.model_validate(session.dog),
        progress=ProgressOut(
            LEFT=SideProgressOut(valid_passes=left, recommended=recommended),
            RIGHT=SideProgressOut(valid_passes=right, recommended=recommended),
        ),
        notices=notices,
        shots=[to_shot_out(shot) for shot in shots],
    )


def count_in_progress_shots(db: Session, session_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Shot)
            .where(Shot.session_id == session_id, Shot.status.in_(IN_PROGRESS_STATUSES))
        )
        or 0
    )


def delete_session_tree(db: Session, session: MeasureSession, institution_id: uuid.UUID) -> None:
    """12.5 삭제 순서: 파일 → walk_pass → shot → session_metric → report → dog.baseline_session_id NULL
    → measure_session. 차트 자료는 지우지 않고, 이 회차를 가리키던 session_id만 NULL로 돌린다.
    분석 API 사본은 부르는 쪽(cancel_session)이 이보다 먼저 지운다.

    DB 연쇄 삭제(ON DELETE CASCADE)는 쓰지 않는다.
    파일을 먼저 지우는 이유는 DB에 키가 없는 파일이 남으면 파기에서 빠지기 때문이다.
    """
    get_storage().delete_prefix(session_prefix(institution_id, session.dog_id, session.id))
    shot_ids = select(Shot.id).where(Shot.session_id == session.id)
    db.execute(delete(WalkPass).where(WalkPass.shot_id.in_(shot_ids)))
    db.execute(delete(Shot).where(Shot.session_id == session.id))
    db.execute(delete(SessionMetric).where(SessionMetric.session_id == session.id))
    db.execute(delete(Report).where(Report.session_id == session.id))
    db.execute(update(Dog).where(Dog.baseline_session_id == session.id).values(baseline_session_id=None))
    # updated_at을 그대로 두려고 같은 값을 다시 넣는다(onupdate가 지금 시각으로 바꾸지 않게)
    db.execute(
        update(DogVital)
        .where(DogVital.session_id == session.id)
        .values(session_id=None, updated_at=DogVital.updated_at)
    )
    db.execute(
        update(DogNote).where(DogNote.session_id == session.id).values(session_id=None, updated_at=DogNote.updated_at)
    )
    db.execute(delete(MeasureSession).where(MeasureSession.id == session.id))
    db.expunge(session)


def complete_session(db: Session, institution_id: uuid.UUID, session_id: uuid.UUID) -> MeasureSession:
    """측정 종료(BE-13, 13.3): MEASURING이고 촬영이 1건 이상일 때만 AGGREGATING으로. 집계는 워커가 이어서 한다(12.4)."""
    session = get_session(db, institution_id, session_id, for_update=True)
    db.refresh(session)  # 잠근 뒤의 상태로 다시 본다
    if session.status != SessionStatus.MEASURING:
        raise AppError(ErrorCode.SESSION_CLOSED)
    has_shot = db.scalar(select(Shot.id).where(Shot.session_id == session.id).limit(1))
    if has_shot is None:
        raise AppError(ErrorCode.SESSION_EMPTY)
    session.status = SessionStatus.AGGREGATING.value
    session.completed_at = datetime.now(UTC)
    db.flush()
    db.refresh(session)
    return session


def _shot_jobs(db: Session, session_id: uuid.UUID) -> list[ShotJob]:
    """회차의 모든 촬영과 그 작업 ID. 작업 ID가 없는 촬영도 넣는다(분석 API에 모르는 작업이 있을 수 있다)."""
    query = select(Shot.id, Shot.job_id).where(Shot.session_id == session_id).order_by(Shot.seq_no, Shot.id)
    return [(shot_id, job_id or None) for shot_id, job_id in db.execute(query)]


def _require_cancellable(db: Session, session: MeasureSession) -> None:
    if session.status != SessionStatus.MEASURING:
        raise AppError(ErrorCode.SESSION_CLOSED)
    if count_in_progress_shots(db, session.id):
        raise AppError(ErrorCode.SHOT_IN_PROGRESS)


def cancel_session(
    db: Session, institution_id: uuid.UUID, session_id: uuid.UUID, analysis: AnalysisClient | None
) -> None:
    """측정 취소(BE-10, 13.3): MEASURING이고 SUBMITTED·ANALYZING 촬영이 없을 때만. 회차와 딸린 것을 모두 지운다.

    촬영 행을 지우면 분석 API 사본을 다시 찾을 수 없으므로 먼저 지운다(199 리뷰 조유진). 못 지우면 503
    ANALYSIS_UNAVAILABLE이고 회차는 그대로다. 분석 API는 HTTP라 회차 행을 잠그기 전에 부르고(조건은 미리 본다),
    잠근 뒤 조건을 다시 보고 그사이 달라진 촬영(새 촬영, 작업 ID가 바뀐 촬영)만 마저 지운다(12.4 잠금).
    """
    session = get_session(db, institution_id, session_id)
    _require_cancellable(db, session)
    first = _shot_jobs(db, session.id)
    delete_shot_copies(analysis, first)
    session = get_session(db, institution_id, session_id, for_update=True)
    db.refresh(session)  # 잠근 뒤의 상태로 다시 본다
    _require_cancellable(db, session)
    already = set(first)
    delete_shot_copies(analysis, [pair for pair in _shot_jobs(db, session.id) if pair not in already])
    delete_session_tree(db, session, institution_id)
