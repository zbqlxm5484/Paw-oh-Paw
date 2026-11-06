"""반려견 휴지통(12.5, 15.5, S15P31A404-199).

담당자가 삭제를 누르면 반려견을 지우지 않고 휴지통에 넣는다(dog.deleted_at). 휴지통의 반려견은 목록·상세·회차·촬영·
보고서 어디에서도 보이지 않고(services/dogs.in_institution), 복원하면 그대로 돌아온다. 완전히 지우는 길은 셋이다.

- 담당자의 영구 삭제(휴지통에 있는 것만)
- 워커의 자동 비우기: 휴지통에 넣고 TRASH_RETENTION_DAYS(30일)가 지난 것
- 관리자 파기(POST /admin/purge)

셋 다 자료 파기(services/purge.py)의 DOG를 불러 순서·오류·purge_log가 같다. Spring에 빗대면 soft delete다.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClient
from app.core.errors import AppError, ErrorCode
from app.models import Dog
from app.models.enums import PurgeScope
from app.services.dogs import TRASH_RETENTION_DAYS, get_dog
from app.services.purge import has_shot_in_progress, purge
from app.storage.base import StorageService

logger = logging.getLogger(__name__)

# 자동 비우기가 한 번에 보는 반려견 수. 남은 것은 다음 차례에 본다
SWEEP_BATCH = 20


def _trashed_dog(db: Session, institution_id: uuid.UUID, dog_id: uuid.UUID) -> Dog:
    """휴지통에 있는 자기 기관의 반려견. 없거나 휴지통에 없으면 404 NOT_FOUND(15.1)."""
    dog = db.scalars(
        select(Dog).where(Dog.id == dog_id, Dog.institution_id == institution_id, Dog.deleted_at.is_not(None))
    ).one_or_none()
    if dog is None:
        raise AppError(ErrorCode.NOT_FOUND)
    return dog


def move_to_trash(db: Session, institution_id: uuid.UUID, dog_id: uuid.UUID) -> None:
    """휴지통에 넣는다. 파일·행은 그대로다. 분석 중인 촬영이 있으면 409 SHOT_IN_PROGRESS(파기와 같다)."""
    dog = get_dog(db, institution_id, dog_id)  # 이미 휴지통에 있으면 404
    if has_shot_in_progress(db, [dog.id]):
        raise AppError(ErrorCode.SHOT_IN_PROGRESS)
    dog.deleted_at = datetime.now(UTC)
    db.flush()
    logger.info("dog moved to trash dog_id=%s", dog.id)


def restore(db: Session, institution_id: uuid.UUID, dog_id: uuid.UUID) -> None:
    """휴지통에서 꺼낸다. 아무것도 지우지 않았으므로 회차·영상·보고서가 그대로 돌아온다."""
    dog = _trashed_dog(db, institution_id, dog_id)
    dog.deleted_at = None
    db.flush()
    logger.info("dog restored from trash dog_id=%s", dog.id)


def delete_permanently(
    db: Session,
    storage: StorageService,
    analysis: AnalysisClient,
    institution_id: uuid.UUID,
    dog_id: uuid.UUID,
    *,
    executed_by: uuid.UUID,
) -> None:
    """휴지통의 반려견을 영구 삭제한다(되돌릴 수 없다). 휴지통에 없는 반려견은 404다."""
    _trashed_dog(db, institution_id, dog_id)
    purge(
        db,
        storage,
        PurgeScope.DOG,
        analysis=analysis,
        institution_id=institution_id,
        target_id=dog_id,
        dry_run=False,
        executed_by=executed_by,
    )


def purge_expired(
    db: Session,
    storage: StorageService,
    analysis: AnalysisClient,
    *,
    now: datetime | None = None,
    limit: int = SWEEP_BATCH,
) -> tuple[int, int]:
    """휴지통에 넣은 지 30일이 지난 반려견을 영구 삭제한다(워커). (지운 수, 못 지운 수)를 돌려준다.

    한 마리씩 savepoint 안에서 지워, 하나가 실패해도 앞에서 지운 것은 남는다. 분석 API가 응답하지 않으면 남은 것도
    같은 이유로 실패할 테니 거기서 멈춘다(작업마다 시간 한도를 기다리지 않게). 못 지운 것은 다음 차례에 다시 한다.
    purge_log.executed_by는 NULL이다(사람이 누른 것이 아니다).
    """
    cutoff = (now or datetime.now(UTC)) - timedelta(days=TRASH_RETENTION_DAYS)
    rows = db.execute(
        select(Dog.id, Dog.institution_id)
        .where(Dog.deleted_at.is_not(None), Dog.deleted_at <= cutoff)
        .order_by(Dog.deleted_at, Dog.id)
        .limit(limit)
    ).all()
    purged = failed = 0
    for dog_id, institution_id in rows:
        try:
            with db.begin_nested():
                purge(
                    db,
                    storage,
                    PurgeScope.DOG,
                    analysis=analysis,
                    institution_id=institution_id,
                    target_id=dog_id,
                    dry_run=False,
                    executed_by=None,
                )
            purged += 1
        except AppError as error:
            failed += 1
            logger.warning("trash sweep could not purge a dog code=%s", error.code.value)
            if error.code == ErrorCode.ANALYSIS_UNAVAILABLE:
                failed += len(rows) - purged - failed
                break
    return purged, failed
