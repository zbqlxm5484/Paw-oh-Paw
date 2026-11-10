"""자료 파기(BE-19, 명세 7절 보관과 파기, 12.5 삭제 순서, 15.9, 17.6·17.7, S15P31A404-199).

반려견(DOG)·기관(INSTITUTION)·전체(ALL) 단위로 파일과 DB 행을 지우고 purge_log에 1행을 남긴다(파기 확인서 D-13의 근거).

- 순서는 12.5: 파일 → walk_pass → shot → session_metric → report → 차트 자료(dog_note_revision → dog_note →
  dog_vital → dog_history) → dog.baseline_session_id NULL → measure_session → dog.
  파일을 먼저 지우는 이유는 DB에 키가 없는 파일이 남으면 다음 파기에서 빠지기 때문이다. S3는 지우기 오류가 하나라도
  있으면 예외를 내 DB 행을 지우기 전에 멈춘다(11.11).
- dry_run이면 세기만 한다(stat_prefix, count). 어느 쪽이든 대상에 SUBMITTED·ANALYZING 촬영이 있으면 409
  SHOT_IN_PROGRESS.
- 실제로 지울 때는 두 단계다(12.4 잠금, 199 리뷰 박규원).
  1. 잠금 밖: 진행 중 촬영을 미리 보고, 분석 API 사본을 작업마다 지운다. HTTP라 오래 걸릴 수 있어 회차 행을 잠근 채
     부르지 않는다. 잠근 채 기다리면 업로드·측정 종료와 워커의 주 반복이 같은 행에서 멈춘다.
  2. 잠금 안: (INSTITUTION이면 기관 행 →) 반려견 행 → 회차 행을 FOR UPDATE로 잠그고, 진행 중 촬영을 다시 보고,
     1단계 뒤에 생긴 작업만 마저 지운 다음 파일 → 행을 지운다. 보통 마저 지울 작업은 없다.
- 반려견 행을 잠그는 이유: 복원(휴지통에서 꺼내기)과 회차 시작이 같은 행을 잠그므로, 파기가 먼저면 둘은 commit을
  기다렸다가 404이고, 둘이 먼저면 파기는 그 결과를 보고 판단한다. DOG는 처음부터(1단계 전부터) 반려견 행을 쥔다.
  분석 사본만 지워진 채 복원되는 일을 막기 위해서다. 한 마리라 다른 요청을 막지 않는다. INSTITUTION은 2단계에서만
  잠근다. 기관의 반려견을 모두 쥔 채 HTTP를 기다리면 그 기관의 요청이 다 멈추기 때문이다. 대신 기관 행을 잠가
  2단계 동안 새 반려견이 생기지 않게 한다(dog가 기관을 가리키는 FK 때문에 새 행이 기다린다).
- 회차 행을 잠그는 이유: 워커가 UPLOADED 촬영을 가져갈 때 같은 행을 잠그므로, 확인과 삭제 사이에 촬영이 분석 API로
  나가는 틈이 없다(199 리뷰, 조유진). dry_run은 지우지 않으니 잠그지 않는다.
- 분석 API를 파일보다 먼저 부르는 이유: 가장 흔한 실패(분석 API 무응답)에서 팀 서비스 쪽을 하나도 지우지 않은 채
  멈추기 위해서다. 실패하면 503 ANALYSIS_UNAVAILABLE이고 행에 job_id가 남아 다시 부르면 이어서 끝난다(이미 지운
  작업은 404라 성공). 분석 중이라는 409는 SHOT_IN_PROGRESS로 돌려준다. ALL은 작업마다 부르지 않고 분석 API의 전체
  파기 명령으로 나눈다.
- INSTITUTION·ALL은 반려견과 그 아래 자료만 지우고 기관·담당자 계정·디바이스 코드는 남긴다(15.9). ALL은 API로 열지 않고
  scripts/purge.py만 부른다.
- 휴지통(12.5): 담당자의 삭제는 휴지통에 넣기일 뿐이고, 영구 삭제와 30일 뒤 자동 비우기가 이 파기를 DOG로 부른다
  (services/trash.py). 휴지통에 있는 반려견도 DOG·INSTITUTION·ALL 파기 대상이다.
- 계약 종료 뒤 자동 파기(12.5, services/retention.py)는 INSTITUTION을 include_accounts로 부른다. 그때만 그 기관의
  가입 계정(CLIENT)까지 지운다. 기관과 디바이스 코드는 어느 경우에도 지우지 않는다.
- 로그에는 개수만 남긴다(11.8: 반려견 이름·파일 경로 금지).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, replace

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClient
from app.core.auth_cache import auth_cache
from app.core.errors import AppError, ErrorCode
from app.models import (
    Dog,
    DogHistory,
    DogImage,
    DogNote,
    DogNoteRevision,
    DogVital,
    Institution,
    MeasureSession,
    PurgeLog,
    Report,
    SessionMetric,
    Shot,
    Staff,
    WalkPass,
)
from app.models.enums import PurgeScope, StaffRole
from app.schemas.admin import PurgeOut
from app.services.analysis_copies import delete_copies
from app.services.dogs import get_dog
from app.services.sessions import IN_PROGRESS_STATUSES
from app.storage.base import StorageService
from app.storage.keys import dog_prefix, institution_prefix

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SweepResult:
    """워커의 자동 파기 한 차례(services/trash.py, services/retention.py). out_of_time이면 시간 상한에 닿아 남겼다."""

    purged: int
    failed: int
    out_of_time: bool = False


@dataclass(frozen=True)
class _Target:
    scope: str
    target_id: uuid.UUID | None  # purge_log.target_id: DOG면 반려견, INSTITUTION이면 기관, ALL이면 None
    dog_ids: list[uuid.UUID]
    prefixes: list[str]  # 지울(셀) 파일 접두어(7절 형식)


def _resolve(
    db: Session, scope: str, *, institution_id: uuid.UUID | None, target_id: uuid.UUID | None, lock_dog: bool
) -> _Target:
    """대상을 찾는다. lock_dog면 DOG의 반려견 행을 FOR UPDATE로 잠근다(실제로 지울 때)."""
    if scope == PurgeScope.DOG:
        if institution_id is None or target_id is None:
            raise ValueError("DOG 파기에는 기관 ID와 반려견 ID가 필요합니다")
        # 다른 기관·없는 반려견은 404(15.1). 휴지통에 있는 반려견도 지운다
        dog = get_dog(db, institution_id, target_id, include_trashed=True, for_update=lock_dog)
        return _Target(scope, dog.id, [dog.id], [dog_prefix(institution_id, dog.id)])
    if scope == PurgeScope.INSTITUTION:
        if institution_id is None:
            raise ValueError("INSTITUTION 파기에는 기관 ID가 필요합니다")
        if db.get(Institution, institution_id) is None:  # 관리자가 지정한 기관이 없으면 404(15.9)
            raise AppError(ErrorCode.NOT_FOUND)
        dog_ids = list(db.scalars(select(Dog.id).where(Dog.institution_id == institution_id)))
        return _Target(scope, institution_id, dog_ids, [institution_prefix(institution_id)])
    if scope == PurgeScope.ALL:
        institution_ids = list(db.scalars(select(Institution.id)))
        dog_ids = list(db.scalars(select(Dog.id)))
        return _Target(scope, None, dog_ids, [institution_prefix(value) for value in institution_ids])
    raise ValueError(f"모르는 파기 범위입니다: {scope!r}")


def _sessions_of(dog_ids: list[uuid.UUID]):
    return select(MeasureSession.id).where(MeasureSession.dog_id.in_(dog_ids))


def _lock_sessions(db: Session, dog_ids: list[uuid.UUID]) -> int:
    """대상 회차 행을 모두 FOR UPDATE로 잠근다(12.4 잠금. 워커 claim_uploaded와 같은 행). 잠근 행 수를 돌려준다."""
    if not dog_ids:
        return 0
    rows = db.execute(select(MeasureSession.id).where(MeasureSession.dog_id.in_(dog_ids)).with_for_update()).all()
    return len(rows)


def _lock_target(db: Session, target: _Target) -> _Target:
    """2단계의 잠금: (기관 행 →) 반려견 행 → 회차 행 순서로 FOR UPDATE. 잠근 뒤의 반려견 목록으로 대상을 돌려준다.

    순서는 늘 같다(기관 → 반려견 → 회차). 회차 시작은 반려견 → 회차 순서이고 나머지는 회차만 잠그므로 서로 엇갈려
    기다리지 않는다. DOG의 반려견 행은 _resolve가 이미 잠갔다.
    """
    if target.scope == PurgeScope.INSTITUTION:
        db.execute(select(Institution.id).where(Institution.id == target.target_id).with_for_update())
        dog_ids = list(db.scalars(select(Dog.id).where(Dog.institution_id == target.target_id).with_for_update()))
        target = replace(target, dog_ids=dog_ids)
    elif target.scope == PurgeScope.ALL:
        target = replace(target, dog_ids=list(db.scalars(select(Dog.id).with_for_update())))
    _lock_sessions(db, target.dog_ids)
    return target


def has_shot_in_progress(db: Session, dog_ids: list[uuid.UUID]) -> bool:
    if not dog_ids:
        return False
    found = db.scalar(
        select(Shot.id)
        .where(Shot.session_id.in_(_sessions_of(dog_ids)), Shot.status.in_(IN_PROGRESS_STATUSES))
        .limit(1)
    )
    return found is not None


def _job_ids(db: Session, target: _Target) -> list[str]:
    """분석 API에서 지울 작업 ID. 아직 제출하지 않은 촬영은 없고, ALL은 작업마다 부르지 않는다(15.9)."""
    if target.scope == PurgeScope.ALL or not target.dog_ids:
        return []
    query = select(Shot.job_id).where(Shot.session_id.in_(_sessions_of(target.dog_ids)), Shot.job_id.is_not(None))
    return [job_id for job_id in db.scalars(query) if job_id]


def _count_rows(db: Session, dog_ids: list[uuid.UUID]) -> int:
    """dry_run: 지울 행 수. 반려견 + 회차 + 촬영 + 통과 + 수치 + 보고서 + 차트 자료(15.9 rows)."""
    if not dog_ids:
        return 0
    sessions = _sessions_of(dog_ids)
    shots = select(Shot.id).where(Shot.session_id.in_(sessions))

    notes = select(DogNote.id).where(DogNote.dog_id.in_(dog_ids))

    def count(model, condition) -> int:
        return db.scalar(select(func.count()).select_from(model).where(condition)) or 0

    return (
        len(dog_ids)
        + count(MeasureSession, MeasureSession.dog_id.in_(dog_ids))
        + count(Shot, Shot.session_id.in_(sessions))
        + count(WalkPass, WalkPass.shot_id.in_(shots))
        + count(SessionMetric, SessionMetric.session_id.in_(sessions))
        + count(Report, Report.session_id.in_(sessions))
        + count(DogNoteRevision, DogNoteRevision.note_id.in_(notes))
        + count(DogNote, DogNote.dog_id.in_(dog_ids))
        + count(DogVital, DogVital.dog_id.in_(dog_ids))
        + count(DogHistory, DogHistory.dog_id.in_(dog_ids))
        + count(DogImage, DogImage.dog_id.in_(dog_ids))
    )


def _delete_rows(db: Session, dog_ids: list[uuid.UUID]) -> int:
    """12.5 삭제 순서로 지우고 지운 행 수를 돌려준다. DB 연쇄 삭제는 쓰지 않는다."""
    if not dog_ids:
        return 0
    sessions = _sessions_of(dog_ids)
    shots = select(Shot.id).where(Shot.session_id.in_(sessions))
    deleted = 0
    deleted += db.execute(delete(WalkPass).where(WalkPass.shot_id.in_(shots))).rowcount
    deleted += db.execute(delete(Shot).where(Shot.session_id.in_(sessions))).rowcount
    deleted += db.execute(delete(SessionMetric).where(SessionMetric.session_id.in_(sessions))).rowcount
    deleted += db.execute(delete(Report).where(Report.session_id.in_(sessions))).rowcount
    # 차트 자료(v1.36). 회차와 담당자를 가리키므로 회차·계정보다 먼저 지운다
    notes = select(DogNote.id).where(DogNote.dog_id.in_(dog_ids))
    deleted += db.execute(delete(DogNoteRevision).where(DogNoteRevision.note_id.in_(notes))).rowcount
    deleted += db.execute(delete(DogNote).where(DogNote.dog_id.in_(dog_ids))).rowcount
    deleted += db.execute(delete(DogVital).where(DogVital.dog_id.in_(dog_ids))).rowcount
    deleted += db.execute(delete(DogHistory).where(DogHistory.dog_id.in_(dog_ids))).rowcount
    # 사진(v1.40). 파일은 반려견 접두어 삭제에 이미 지워졌다
    deleted += db.execute(delete(DogImage).where(DogImage.dog_id.in_(dog_ids))).rowcount
    db.execute(update(Dog).where(Dog.baseline_session_id.in_(sessions)).values(baseline_session_id=None))
    deleted += db.execute(delete(MeasureSession).where(MeasureSession.dog_id.in_(dog_ids))).rowcount
    deleted += db.execute(delete(Dog).where(Dog.id.in_(dog_ids))).rowcount
    db.expire_all()  # 지운 행을 들고 있던 ORM 객체가 다시 읽히지 않게
    return deleted


def _delete_client_accounts(db: Session, institution_id: uuid.UUID) -> int:
    """기관의 가입 계정(CLIENT)을 지우고 지운 수를 돌려준다(12.5 계약 종료 뒤 자동 파기).

    회차가 담당자를 가리키므로(fk_session_staff) 회차를 지운 뒤에 부른다. 크림오프 계정(ADMIN·STAFF)은 지우지 않는다.
    """
    deleted = db.execute(
        delete(Staff).where(Staff.institution_id == institution_id, Staff.role == StaffRole.CLIENT.value)
    ).rowcount
    db.expire_all()
    auth_cache.invalidate_institution(institution_id)
    return deleted


def purge(
    db: Session,
    storage: StorageService,
    scope: str,
    *,
    institution_id: uuid.UUID | None = None,
    target_id: uuid.UUID | None = None,
    dry_run: bool = True,
    executed_by: uuid.UUID | None = None,
    analysis: AnalysisClient | None = None,
    include_accounts: bool = False,
    deadline: float | None = None,
) -> PurgeOut:
    """파기 또는 dry_run 집계(15.9). institution_id는 지울 자료의 기관(ALL이면 없음), executed_by는 부른 담당자 ID.

    기관은 관리자가 지정할 수 있어 부른 담당자의 기관과 다를 수 있다. 없는 기관, 그 기관에 없는 반려견은 404다.

    analysis는 분석 API 사본을 지울 클라이언트다. 지울 작업이 없으면(ALL, 세기만 할 때) 쓰지 않는다.
    include_accounts는 INSTITUTION을 실제로 지울 때만 뜻이 있다: 그 기관의 가입 계정(CLIENT)도 지우고 rows에 더한다.
    계약 종료 뒤 자동 파기만 쓴다(관리자 API는 계정을 남긴다).
    deadline(time.monotonic() 기준)은 워커의 자동 파기만 넘긴다. 1단계에서 넘기면 OutOfTime을 낸다. 그때까지 지운
    분석 사본은 다시 부르면 404라, 다음 차례에 이어서 끝난다.
    """
    if include_accounts and scope != PurgeScope.INSTITUTION:  # 무엇이든 지우기 전에 본다(199 리뷰)
        raise ValueError("계정까지 지우는 파기는 INSTITUTION에서만 합니다")
    target = _resolve(db, scope, institution_id=institution_id, target_id=target_id, lock_dog=not dry_run)
    # 잠그기 전에 미리 본다. dry_run은 이 검사가 전부이고, 실제 파기는 2단계에서 잠근 뒤 다시 본다
    if has_shot_in_progress(db, target.dog_ids):
        raise AppError(ErrorCode.SHOT_IN_PROGRESS)

    job_ids = _job_ids(db, target)
    files = total_bytes = 0
    if dry_run:
        for prefix in target.prefixes:
            count, size = storage.stat_prefix(prefix)
            files, total_bytes = files + count, total_bytes + size
        rows = _count_rows(db, target.dog_ids)
        logger.info(
            "purge dry run scope=%s rows=%d files=%d bytes=%d analysis_jobs=%d",
            target.scope,
            rows,
            files,
            total_bytes,
            len(job_ids),
        )
        return PurgeOut(
            scope=target.scope,
            target_id=target.target_id,
            dry_run=True,
            rows=rows,
            files=files,
            bytes=total_bytes,
            analysis_jobs=len(job_ids),
        )

    # 1단계(회차 잠금 밖): 분석 API 사본. 파일·행보다 먼저라 실패하면 팀 서비스 쪽은 그대로다
    delete_copies(analysis, job_ids, deadline=deadline)

    # 2단계(잠금 안): 다시 확인하고, 그사이 생긴 작업만 마저 지운 뒤 파일 → 행
    target = _lock_target(db, target)
    if has_shot_in_progress(db, target.dog_ids):
        raise AppError(ErrorCode.SHOT_IN_PROGRESS)
    already = set(job_ids)
    late = [job_id for job_id in _job_ids(db, target) if job_id not in already]
    delete_copies(analysis, late)
    analysis_jobs = len(job_ids) + len(late)

    for prefix in target.prefixes:
        count, size = storage.delete_prefix(prefix)
        files, total_bytes = files + count, total_bytes + size
    rows = _delete_rows(db, target.dog_ids)
    accounts = 0
    if include_accounts and target.target_id is not None:
        accounts = _delete_client_accounts(db, target.target_id)
        rows += accounts
    log = PurgeLog(
        scope=target.scope,
        target_id=target.target_id,
        rows_deleted=rows,
        files_deleted=files,
        bytes_deleted=total_bytes,
        analysis_jobs_deleted=analysis_jobs,
        executed_by=executed_by,
    )
    db.add(log)
    db.flush()
    logger.info(
        "purge done scope=%s rows=%d files=%d bytes=%d analysis_jobs=%d accounts=%d purge_log=%s",
        target.scope,
        rows,
        files,
        total_bytes,
        analysis_jobs,
        accounts,
        log.id,
    )
    return PurgeOut(
        scope=target.scope,
        target_id=target.target_id,
        dry_run=False,
        rows=rows,
        files=files,
        bytes=total_bytes,
        analysis_jobs=analysis_jobs,
        purge_log_id=log.id,
    )
