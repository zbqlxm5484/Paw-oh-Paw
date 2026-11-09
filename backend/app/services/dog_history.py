"""진단 이력(BE-29, 12.5 차트 자료, 13.9, 15.11): 진단·수술·재활. 측정 이력(services/history.py)과는 다른 것이다.

반려견은 services/dogs.in_institution으로 거른다(다른 기관·휴지통은 404). flush()까지만 한다.
제목과 수의사 이름은 로그에 남기지 않는다(11.8). 고치거나 지운 것은 누가 했는지 로그에 ID만 남긴다(v1.41).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError, ErrorCode
from app.models import Dog, DogHistory
from app.schemas.chart import DogHistoryCreate, DogHistoryOut, DogHistoryUpdate
from app.services.dogs import get_dog, in_institution, set_stage

logger = logging.getLogger(__name__)


def list_history(db: Session, institution_id: uuid.UUID, dog_id: uuid.UUID) -> list[DogHistoryOut]:
    """그 반려견의 진단 이력 전부. 일어난 날 오름차순(오래된 것부터), 같으면 적은 순서(15.11)."""
    dog = get_dog(db, institution_id, dog_id)
    rows = db.scalars(
        select(DogHistory)
        .options(joinedload(DogHistory.staff))
        .where(DogHistory.dog_id == dog.id)
        .order_by(DogHistory.occurred_on, DogHistory.created_at, DogHistory.id)
    ).all()
    return [DogHistoryOut.model_validate(row) for row in rows]


def add_history(
    db: Session, *, institution_id: uuid.UUID, staff_id: uuid.UUID, dog_id: uuid.UUID, data: DogHistoryCreate
) -> DogHistoryOut:
    """한 줄을 더한다. stage를 보내면 반려견의 단계도 함께 바꾼다(값이 다를 때만. 그때 반려견의 version이 1 는다).

    단계를 바꿀 때는 반려견 행을 잠근다. 잠그지 않으면 다른 담당자의 수정과 겹쳐 version이 어긋날 수 있다.
    """
    query = select(Dog).where(Dog.id == dog_id, in_institution(institution_id))
    if data.stage is not None:
        query = query.with_for_update()
    dog = db.scalars(query).one_or_none()
    if dog is None:
        raise AppError(ErrorCode.NOT_FOUND)
    row = DogHistory(
        dog_id=dog.id,
        occurred_on=data.occurred_on,
        kind=data.kind.value,
        title=data.title,
        site=data.site.value if data.site is not None else None,
        clinician=data.clinician,
        staff_id=staff_id,
        created_at=datetime.now(UTC),  # 같은 트랜잭션에서 둘을 적어도 순서가 남게 DB 기본값을 쓰지 않는다
    )
    db.add(row)
    if data.stage is not None:
        set_stage(dog, data.stage.value)
    db.flush()
    db.refresh(row)
    return DogHistoryOut.model_validate(row)


def _get_row(db: Session, institution_id: uuid.UUID, dog_id: uuid.UUID, history_id: uuid.UUID) -> DogHistory:
    """그 반려견의 이력 한 줄을 잠그고 읽는다. 없거나 다른 반려견·다른 기관·휴지통의 것이면 똑같이 404(15.1)."""
    row = db.scalars(
        select(DogHistory)
        .join(Dog, DogHistory.dog_id == Dog.id)
        .where(DogHistory.id == history_id, DogHistory.dog_id == dog_id, in_institution(institution_id))
        .with_for_update(of=DogHistory)
    ).one_or_none()
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND)
    return row


def update_history(
    db: Session,
    *,
    institution_id: uuid.UUID,
    staff_id: uuid.UUID,
    dog_id: uuid.UUID,
    history_id: uuid.UUID,
    data: DogHistoryUpdate,
) -> DogHistoryOut:
    """보낸 것만 바꾼다(13.9). 적은 담당자(staff)와 적은 시각은 그대로 둔다. 반려견의 단계는 바꾸지 않는다."""
    row = _get_row(db, institution_id, dog_id, history_id)
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(row, field, value.value if hasattr(value, "value") else value)
    db.flush()
    db.refresh(row)
    logger.info("dog history updated history=%s staff=%s fields=%s", row.id, staff_id, ",".join(sorted(changes)))
    return DogHistoryOut.model_validate(row)


def delete_history(
    db: Session, *, institution_id: uuid.UUID, staff_id: uuid.UUID, dog_id: uuid.UUID, history_id: uuid.UUID
) -> None:
    """한 줄을 지운다. 반려견의 단계는 되돌리지 않는다(이력을 더할 때 함께 바꾼 단계도 그대로 남는다)."""
    row = _get_row(db, institution_id, dog_id, history_id)
    db.delete(row)
    db.flush()
    logger.info("dog history deleted history=%s staff=%s", history_id, staff_id)
