"""반려견 휴지통(12.5, 15.5, S15P31A404-199).

담당자가 삭제를 누르면 반려견을 지우지 않고 휴지통에 넣는다(dog.deleted_at). 휴지통의 반려견은 목록·상세·회차·촬영·
보고서 어디에서도 보이지 않고(services/dogs.in_institution), 복원하면 그대로 돌아온다. 완전히 지우는 길은 셋이다.

- 담당자의 영구 삭제(휴지통에 있는 것만)
- 워커의 자동 비우기: 휴지통에 넣고 TRASH_RETENTION_DAYS(30일)가 지난 것
- 관리자 파기(POST /admin/purge)

셋 다 자료 파기(services/purge.py)의 DOG를 불러 순서·오류·purge_log가 같다. Spring에 빗대면 soft delete다.

넣기·복원·영구 삭제는 반려견 행을 FOR UPDATE로 잠근 뒤 본다(12.4 잠금, 199 리뷰 박규원). 파기도 같은 행을 잠그므로
둘 중 하나만 먼저 간다. 파기가 먼저면 복원은 commit을 기다렸다가 404이고, 복원이 먼저면 자동 비우기는 잠근 뒤
휴지통에 없는 것을 보고 건너뛴다. 잠그지 않으면 "복원했다"고 답한 반려견이 지워질 수 있다.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClient
from app.core.errors import AppError, ErrorCode
from app.models import Dog
from app.models.enums import PurgeScope
from app.services.analysis_copies import Cleared, OutOfTime
from app.services.dogs import TRASH_RETENTION_DAYS, get_dog
from app.services.purge import SweepResult, has_shot_in_progress, purge
from app.storage.base import StorageService

logger = logging.getLogger(__name__)

# 자동 비우기가 한 번에 보는 반려견 수. 남은 것은 다음 차례에 본다
SWEEP_BATCH = 20


def _trashed_dog(db: Session, institution_id: uuid.UUID, dog_id: uuid.UUID) -> Dog:
    """휴지통에 있는 자기 기관의 반려견을 잠가서 돌려준다. 없거나 휴지통에 없으면 404 NOT_FOUND(15.1)."""
    dog = db.scalars(
        select(Dog)
        .where(Dog.id == dog_id, Dog.institution_id == institution_id, Dog.deleted_at.is_not(None))
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()
    if dog is None:
        raise AppError(ErrorCode.NOT_FOUND)
    return dog


def move_to_trash(db: Session, institution_id: uuid.UUID, dog_id: uuid.UUID) -> None:
    """휴지통에 넣는다. 파일·행은 그대로다. 분석 중인 촬영이 있으면 409 SHOT_IN_PROGRESS(파기와 같다)."""
    dog = get_dog(db, institution_id, dog_id, for_update=True)  # 이미 휴지통에 있으면 404
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
    _trashed_dog(db, institution_id, dog_id)  # 잠근 채 파기로 넘어간다. 그사이 복원할 수 없다
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
    deadline: float | None = None,
    cleared: Cleared | None = None,
) -> SweepResult:
    """휴지통에 넣은 지 30일이 지난 반려견을 영구 삭제한다(워커). 지운 수, 못 지운 수, 시간 상한에 닿았는지를 돌려준다.

    한 마리씩 savepoint 안에서 지우고 지울 때마다 commit해 잠금을 바로 푼다. 하나가 실패해도 앞에서 지운 것은 남는다.
    후보를 읽은 뒤 복원했을 수 있으므로, 반려견 행을 잠근 뒤 아직 휴지통에 있고 기한이 지났는지 다시 본다.
    분석 API가 응답하지 않으면 남은 것도 같은 이유로 실패할 테니 거기서 멈춘다(작업마다 시간 한도를 기다리지 않게).
    deadline(time.monotonic() 기준)을 넘기면 남은 것을 다음 차례로 미룬다. 주 반복과 같은 스레드에서 돌기 때문이다
    (12.4). 못 지운 것은 다음 차례에 다시 한다. purge_log.executed_by는 NULL이다(사람이 누른 것이 아니다).
    cleared는 분석 API 사본을 끝낸 촬영을 적어 두는 곳이다. 워커가 차례마다 같은 것을 넘겨, 이어서 할 때 끝낸
    촬영을 다시 부르지 않는다(services/analysis_copies.py).
    """
    cutoff = (now or datetime.now(UTC)) - timedelta(days=TRASH_RETENTION_DAYS)
    expired = (Dog.deleted_at.is_not(None), Dog.deleted_at <= cutoff)
    rows = db.execute(
        select(Dog.id, Dog.institution_id).where(*expired).order_by(Dog.deleted_at, Dog.id).limit(limit)
    ).all()
    purged = failed = 0
    for index, (dog_id, institution_id) in enumerate(rows):
        if deadline is not None and time.monotonic() >= deadline:
            return SweepResult(purged, failed, out_of_time=True)
        try:
            with db.begin_nested():
                still_expired = db.scalar(select(Dog.id).where(Dog.id == dog_id, *expired).with_for_update())
                if still_expired is None:
                    continue  # 그사이 복원했거나 다른 길로 이미 지웠다
                purge(
                    db,
                    storage,
                    PurgeScope.DOG,
                    analysis=analysis,
                    institution_id=institution_id,
                    target_id=dog_id,
                    dry_run=False,
                    executed_by=None,
                    deadline=deadline,
                    cleared=cleared,
                )
            db.commit()  # 한 마리 지울 때마다 잠금을 푼다
            purged += 1
        except OutOfTime:
            return SweepResult(purged, failed, out_of_time=True)
        except AppError as error:
            failed += 1
            logger.warning("trash sweep could not purge a dog code=%s", error.code.value)
            if error.code == ErrorCode.ANALYSIS_UNAVAILABLE:
                failed += len(rows) - index - 1  # 남은 것도 못 지운 것으로 센다
                break
    return SweepResult(purged, failed)
