"""자료 파기(BE-19, 명세 7절 보관과 파기, 12.5 삭제 순서, 15.9, 17.6·17.7, S15P31A404-199).

반려견(DOG)·기관(INSTITUTION)·전체(ALL) 단위로 파일과 DB 행을 지우고 purge_log에 1행을 남긴다(파기 확인서 D-13의 근거).

- 순서는 12.5: 파일 → walk_pass → shot → session_metric → report → 차트 자료(dog_vital → dog_history)
  → dog.baseline_session_id NULL → measure_session → dog.
  파일을 먼저 지우는 이유는 DB에 키가 없는 파일이 남으면 다음 파기에서 빠지기 때문이다. S3는 지우기 오류가 하나라도
  있으면 예외를 내 DB 행을 지우기 전에 멈춘다(11.11).
- dry_run이면 세기만 한다(stat_prefix, count). 어느 쪽이든 대상에 SUBMITTED·ANALYZING 촬영이 있으면 409
  SHOT_IN_PROGRESS.
- 실제로 지울 때는 그 검사 전에 대상 회차 행을 모두 FOR UPDATE로 잠근다(12.4 잠금). 워커가 UPLOADED 촬영을 가져갈 때
  같은 행을 잠그므로, 확인과 삭제 사이에 촬영이 분석 API로 나가는 틈이 없다(199 리뷰, 조유진). 워커가 먼저 잠갔으면
  파기는 기다렸다가 SUBMITTED를 보고 409, 파기가 먼저면 워커는 commit 뒤 지워진 행을 보고 건너뛴다. 잠금은 파일을
  지우는 동안도 쥐고 있다(파일 → 행 순서가 한 트랜잭션 안이어야 하므로). dry_run은 지우지 않으니 잠그지 않는다.
- 분석 API도 작업마다 영상·결과·관절점 사본을 들고 있어 DOG·INSTITUTION은 파일보다 먼저 작업마다 지운다. 가장 흔한
  실패(분석 API 무응답)에서 팀 서비스 쪽을 하나도 지우지 않은 채 멈추기 위해서다. 실패하면 503
  ANALYSIS_UNAVAILABLE이고 행에 job_id가 남아 다시 부르면 이어서 끝난다(이미 지운 작업은 404라 성공). 분석 중이라는
  409는 SHOT_IN_PROGRESS로 돌려준다. ALL은 작업마다 부르지 않고 분석 API의 전체 파기 명령으로 나눈다.
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
from dataclasses import dataclass

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClient, AnalysisClientError
from app.core.auth_cache import auth_cache
from app.core.errors import AppError, ErrorCode
from app.models import (
    Dog,
    DogHistory,
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
from app.services.dogs import get_dog
from app.services.sessions import IN_PROGRESS_STATUSES
from app.storage.base import StorageService
from app.storage.keys import dog_prefix, institution_prefix

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Target:
    scope: str
    target_id: uuid.UUID | None  # purge_log.target_id: DOG면 반려견, INSTITUTION이면 기관, ALL이면 None
    dog_ids: list[uuid.UUID]
    prefixes: list[str]  # 지울(셀) 파일 접두어(7절 형식)


def _resolve(db: Session, scope: str, *, institution_id: uuid.UUID | None, target_id: uuid.UUID | None) -> _Target:
    if scope == PurgeScope.DOG:
        if institution_id is None or target_id is None:
            raise ValueError("DOG 파기에는 기관 ID와 반려견 ID가 필요합니다")
        # 다른 기관·없는 반려견은 404(15.1). 휴지통에 있는 반려견도 지운다
        dog = get_dog(db, institution_id, target_id, include_trashed=True)
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


def _delete_analysis_copies(analysis: AnalysisClient | None, job_ids: list[str]) -> None:
    """분석 API 사본을 지운다. 처음 실패한 곳에서 멈춘다. 지운 것은 다시 부르면 404라 이어서 끝난다."""
    if not job_ids:
        return
    if analysis is None:
        raise ValueError("분석 작업이 있는 파기에는 분석 클라이언트가 필요합니다")
    for done, job_id in enumerate(job_ids):
        try:
            analysis.delete(job_id)
        except AnalysisClientError as error:
            logger.warning(
                "purge stopped: analysis delete failed status=%s done=%d/%d", error.status_code, done, len(job_ids)
            )
            raise AppError(
                ErrorCode.SHOT_IN_PROGRESS if error.job_in_progress else ErrorCode.ANALYSIS_UNAVAILABLE
            ) from None


def _count_rows(db: Session, dog_ids: list[uuid.UUID]) -> int:
    """dry_run: 지울 행 수. 반려견 + 회차 + 촬영 + 통과 + 수치 + 보고서 + 차트 자료(15.9 rows)."""
    if not dog_ids:
        return 0
    sessions = _sessions_of(dog_ids)
    shots = select(Shot.id).where(Shot.session_id.in_(sessions))

    def count(model, condition) -> int:
        return db.scalar(select(func.count()).select_from(model).where(condition)) or 0

    return (
        len(dog_ids)
        + count(MeasureSession, MeasureSession.dog_id.in_(dog_ids))
        + count(Shot, Shot.session_id.in_(sessions))
        + count(WalkPass, WalkPass.shot_id.in_(shots))
        + count(SessionMetric, SessionMetric.session_id.in_(sessions))
        + count(Report, Report.session_id.in_(sessions))
        + count(DogVital, DogVital.dog_id.in_(dog_ids))
        + count(DogHistory, DogHistory.dog_id.in_(dog_ids))
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
    deleted += db.execute(delete(DogVital).where(DogVital.dog_id.in_(dog_ids))).rowcount
    deleted += db.execute(delete(DogHistory).where(DogHistory.dog_id.in_(dog_ids))).rowcount
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
) -> PurgeOut:
    """파기 또는 dry_run 집계(15.9). institution_id는 지울 자료의 기관(ALL이면 없음), executed_by는 부른 담당자 ID.

    기관은 관리자가 지정할 수 있어 부른 담당자의 기관과 다를 수 있다. 없는 기관, 그 기관에 없는 반려견은 404다.

    analysis는 분석 API 사본을 지울 클라이언트다. 지울 작업이 없으면(ALL, 세기만 할 때) 쓰지 않는다.
    include_accounts는 INSTITUTION을 실제로 지울 때만 뜻이 있다: 그 기관의 가입 계정(CLIENT)도 지우고 rows에 더한다.
    계약 종료 뒤 자동 파기만 쓴다(관리자 API는 계정을 남긴다).
    """
    target = _resolve(db, scope, institution_id=institution_id, target_id=target_id)
    if not dry_run:
        _lock_sessions(db, target.dog_ids)  # 잠근 뒤 확인한다(12.4). 세기만 하는 dry_run은 잠그지 않는다
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

    _delete_analysis_copies(analysis, job_ids)  # 파일·행보다 먼저. 실패하면 팀 서비스 쪽은 그대로다
    for prefix in target.prefixes:
        count, size = storage.delete_prefix(prefix)
        files, total_bytes = files + count, total_bytes + size
    rows = _delete_rows(db, target.dog_ids)
    accounts = 0
    if include_accounts:
        if target.scope != PurgeScope.INSTITUTION or target.target_id is None:
            raise ValueError("계정까지 지우는 파기는 INSTITUTION에서만 합니다")
        accounts = _delete_client_accounts(db, target.target_id)
        rows += accounts
    log = PurgeLog(
        scope=target.scope,
        target_id=target.target_id,
        rows_deleted=rows,
        files_deleted=files,
        bytes_deleted=total_bytes,
        analysis_jobs_deleted=len(job_ids),
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
        len(job_ids),
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
        analysis_jobs=len(job_ids),
        purge_log_id=log.id,
    )
