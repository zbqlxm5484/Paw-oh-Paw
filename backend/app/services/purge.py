"""자료 파기(BE-19, 명세 7절 보관과 파기, 12.5 삭제 순서, 15.9, 17.6·17.7, S15P31A404-199).

반려견(DOG)·기관(INSTITUTION)·전체(ALL) 단위로 파일과 DB 행을 지우고 purge_log에 1행을 남긴다(파기 확인서 D-13의 근거).

- 순서는 12.5: 파일 → walk_pass → shot → session_metric → report → dog.baseline_session_id NULL → measure_session → dog.
  파일을 먼저 지우는 이유는 DB에 키가 없는 파일이 남으면 다음 파기에서 빠지기 때문이다. S3는 지우기 오류가 하나라도
  있으면 예외를 내 DB 행을 지우기 전에 멈춘다(11.11).
- dry_run이면 세기만 한다(stat_prefix, count). 어느 쪽이든 대상에 SUBMITTED·ANALYZING 촬영이 있으면 409
  SHOT_IN_PROGRESS.
- 실제로 지울 때는 그 검사 전에 대상 회차 행을 모두 FOR UPDATE로 잠근다(12.4 잠금). 워커가 UPLOADED 촬영을 가져갈 때
  같은 행을 잠그므로, 확인과 삭제 사이에 촬영이 분석 API로 나가는 틈이 없다(199 리뷰, 조유진). 워커가 먼저 잠갔으면
  파기는 기다렸다가 SUBMITTED를 보고 409, 파기가 먼저면 워커는 commit 뒤 지워진 행을 보고 건너뛴다. 잠금은 파일을
  지우는 동안도 쥐고 있다(파일 → 행 순서가 한 트랜잭션 안이어야 하므로). dry_run은 지우지 않으니 잠그지 않는다.
- INSTITUTION·ALL은 반려견과 그 아래 자료만 지우고 기관·담당자 계정·디바이스 코드는 남긴다(15.9). ALL은 API로 열지 않고
  scripts/purge.py만 부른다.
- 로그에는 개수만 남긴다(11.8: 반려견 이름·파일 경로 금지).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.models import Dog, Institution, MeasureSession, PurgeLog, Report, SessionMetric, Shot, WalkPass
from app.models.enums import PurgeScope
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
        dog = get_dog(db, institution_id, target_id)  # 다른 기관·없는 반려견은 404(15.1)
        return _Target(scope, dog.id, [dog.id], [dog_prefix(institution_id, dog.id)])
    if scope == PurgeScope.INSTITUTION:
        if institution_id is None:
            raise ValueError("INSTITUTION 파기에는 기관 ID가 필요합니다")
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


def _has_shot_in_progress(db: Session, dog_ids: list[uuid.UUID]) -> bool:
    if not dog_ids:
        return False
    found = db.scalar(
        select(Shot.id)
        .where(Shot.session_id.in_(_sessions_of(dog_ids)), Shot.status.in_(IN_PROGRESS_STATUSES))
        .limit(1)
    )
    return found is not None


def _count_rows(db: Session, dog_ids: list[uuid.UUID]) -> int:
    """dry_run: 지울 행 수. 반려견 + 회차 + 촬영 + 통과 + 수치 + 보고서."""
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
    db.execute(update(Dog).where(Dog.baseline_session_id.in_(sessions)).values(baseline_session_id=None))
    deleted += db.execute(delete(MeasureSession).where(MeasureSession.dog_id.in_(dog_ids))).rowcount
    deleted += db.execute(delete(Dog).where(Dog.id.in_(dog_ids))).rowcount
    db.expire_all()  # 지운 행을 들고 있던 ORM 객체가 다시 읽히지 않게
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
) -> PurgeOut:
    """파기 또는 dry_run 집계(15.9). institution_id는 부른 담당자의 기관(ALL이면 없음), executed_by는 담당자 ID."""
    target = _resolve(db, scope, institution_id=institution_id, target_id=target_id)
    if not dry_run:
        _lock_sessions(db, target.dog_ids)  # 잠근 뒤 확인한다(12.4). 세기만 하는 dry_run은 잠그지 않는다
    if _has_shot_in_progress(db, target.dog_ids):
        raise AppError(ErrorCode.SHOT_IN_PROGRESS)

    files = total_bytes = 0
    if dry_run:
        for prefix in target.prefixes:
            count, size = storage.stat_prefix(prefix)
            files, total_bytes = files + count, total_bytes + size
        rows = _count_rows(db, target.dog_ids)
        logger.info("purge dry run scope=%s rows=%d files=%d bytes=%d", target.scope, rows, files, total_bytes)
        return PurgeOut(
            scope=target.scope, target_id=target.target_id, dry_run=True, rows=rows, files=files, bytes=total_bytes
        )

    for prefix in target.prefixes:
        count, size = storage.delete_prefix(prefix)
        files, total_bytes = files + count, total_bytes + size
    rows = _delete_rows(db, target.dog_ids)
    log = PurgeLog(
        scope=target.scope,
        target_id=target.target_id,
        rows_deleted=rows,
        files_deleted=files,
        bytes_deleted=total_bytes,
        executed_by=executed_by,
    )
    db.add(log)
    db.flush()
    logger.info(
        "purge done scope=%s rows=%d files=%d bytes=%d purge_log=%s", target.scope, rows, files, total_bytes, log.id
    )
    return PurgeOut(
        scope=target.scope,
        target_id=target.target_id,
        dry_run=False,
        rows=rows,
        files=files,
        bytes=total_bytes,
        purge_log_id=log.id,
    )
