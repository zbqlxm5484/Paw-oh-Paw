"""바이탈(BE-28, 12.5 차트 자료, 13.9, 15.11). 반려견마다 하루 한 줄이고 같은 날 다시 보내면 값을 바꾼다.

반려견은 services/dogs.in_institution으로 거른다(다른 기관·휴지통은 404). flush()까지만 한다.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.dates import today_local
from app.core.errors import AppError, ErrorCode
from app.models import Dog, DogVital
from app.schemas.chart import VitalIn, VitalOut
from app.services.dogs import get_dog, in_institution

_KEEP = object()  # save_vital의 session_id 기본값: 이미 있는 값을 그대로 둔다


def list_vitals(db: Session, institution_id: uuid.UUID, dog_id: uuid.UUID) -> list[VitalOut]:
    """그 반려견의 바이탈 전부, 최신이 앞(15.11)."""
    dog = get_dog(db, institution_id, dog_id)
    rows = db.scalars(
        select(DogVital)
        .options(joinedload(DogVital.staff))
        .where(DogVital.dog_id == dog.id)
        .order_by(DogVital.measured_on.desc())
    ).all()
    return [VitalOut.model_validate(row) for row in rows]


def save_vital(
    db: Session,
    *,
    dog: Dog,
    measured_on: date,
    data: VitalIn,
    staff_id: uuid.UUID,
    session_id: uuid.UUID | None | object = _KEEP,
) -> DogVital:
    """그날 값을 만들거나 바꾼다(12.5). 부르는 쪽이 반려견 행을 잠근 뒤에 불러야 같은 날 두 줄이 생기지 않는다.

    바꿀 때는 다섯 값과 staff_id를 바꾼다. session_id는 주었을 때만 바꾼다(회차 시작만 준다).
    """
    vital = db.scalars(
        select(DogVital).where(DogVital.dog_id == dog.id, DogVital.measured_on == measured_on)
    ).one_or_none()
    if vital is None:
        vital = DogVital(dog_id=dog.id, measured_on=measured_on)
        db.add(vital)
    vital.weight_kg = data.weight_kg
    vital.temp_c = data.temp_c
    vital.heart_rate = data.heart_rate
    vital.sbp = data.sbp
    vital.dbp = data.dbp
    vital.staff_id = staff_id
    if session_id is not _KEEP:
        vital.session_id = session_id  # type: ignore[assignment]
    db.flush()
    db.refresh(vital)
    return vital


def put_vital(
    db: Session,
    *,
    institution_id: uuid.UUID,
    staff_id: uuid.UUID,
    dog_id: uuid.UUID,
    measured_on: date,
    data: VitalIn,
) -> VitalOut:
    """PUT /dogs/{dog_id}/vitals/{measured_on}. 미래 날짜는 422다(13.9)."""
    if measured_on > today_local():
        raise AppError(ErrorCode.VALIDATION_ERROR, {"fields": [{"field": "measured_on", "type": "date_future"}]})
    dog = db.scalars(
        select(Dog).where(Dog.id == dog_id, in_institution(institution_id)).with_for_update()
    ).one_or_none()
    if dog is None:
        raise AppError(ErrorCode.NOT_FOUND)
    vital = save_vital(db, dog=dog, measured_on=measured_on, data=data, staff_id=staff_id)
    return VitalOut.model_validate(vital)
