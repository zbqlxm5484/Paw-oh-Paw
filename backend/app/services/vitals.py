"""바이탈(BE-28, 12.5 차트 자료, 13.9, 15.11). 반려견마다 하루 한 줄이고 같은 날 다시 보내면 보낸 값만 바꾼다.

반려견은 services/dogs.in_institution으로 거른다(다른 기관·휴지통은 404). flush()까지만 한다.
체중을 적은 날이 체중이 적힌 날 중 가장 최근이면 반려견의 등록 체중도 그 값으로 바꾼다(12.5, v1.41).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, joinedload

from app.core.dates import today_local
from app.core.errors import AppError, ErrorCode
from app.models import Dog, DogVital
from app.schemas.chart import VitalOut, VitalPut
from app.services.dogs import classify, get_dog, in_institution

_KEEP = object()  # save_vital의 session_id 기본값: 이미 있는 값을 그대로 둔다
VITAL_FIELDS = ("weight_kg", "temp_c", "heart_rate", "sbp", "dbp")


def _invalid(field: str, kind: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, {"fields": [{"field": field, "type": kind}]})


def _check(values: dict[str, object]) -> None:
    """저장된 값과 합친 그날 줄의 규칙(13.9): 값이 하나는 있고, 혈압은 둘이 함께 있으며 이완기가 수축기보다 작다."""
    if all(values[name] is None for name in VITAL_FIELDS):
        raise _invalid("body", "vital_empty")
    sbp, dbp = values["sbp"], values["dbp"]
    if (sbp is None) != (dbp is None):
        raise _invalid("dbp" if dbp is None else "sbp", "blood_pressure_pair")
    if sbp is not None and dbp >= sbp:  # type: ignore[operator]
        raise _invalid("dbp", "dbp_not_below_sbp")


def _sync_dog_weight(db: Session, dog: Dog, measured_on: date, weight: Decimal) -> None:
    """체중을 적은 날보다 뒤에 체중이 적힌 줄이 없으면 반려견의 등록 체중을 그 값으로 바꾼다(12.5).

    지난 날짜의 값을 뒤늦게 적어도 지금 체중이 옛값으로 돌아가지 않는다. 체급을 직접 지정하지 않았으면 다시 분류한다.
    값이 실제로 바뀌면 반려견의 version이 1 는다. 부르는 쪽이 반려견 행을 잠근 뒤라 겹치지 않는다.
    """
    later = db.scalar(
        select(
            exists().where(
                DogVital.dog_id == dog.id, DogVital.measured_on > measured_on, DogVital.weight_kg.is_not(None)
            )
        )
    )
    if later or dog.weight_kg == weight:
        return
    dog.weight_kg = weight
    if not dog.size_class_manual:
        dog.size_class = classify(weight)


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
    values: dict[str, object],
    staff_id: uuid.UUID,
    session_id: uuid.UUID | None | object = _KEEP,
) -> DogVital:
    """그날 줄을 만들거나 바꾼다(12.5). 부르는 쪽이 반려견 행을 잠근 뒤에 불러야 같은 날 두 줄이 생기지 않는다.

    values에 있는 값만 바꾸고(None이면 비운다) 없는 값은 그대로 둔다. staff_id는 늘 바꾼다. session_id는 주었을 때만
    바꾼다(회차 시작만 준다). 합친 줄이 규칙에 어긋나면 아무것도 바꾸지 않고 422다.
    """
    vital = db.scalars(
        select(DogVital).where(DogVital.dog_id == dog.id, DogVital.measured_on == measured_on)
    ).one_or_none()
    merged = {name: getattr(vital, name) if vital is not None else None for name in VITAL_FIELDS} | values
    _check(merged)
    if vital is None:
        vital = DogVital(dog_id=dog.id, measured_on=measured_on)
        db.add(vital)
    for name in VITAL_FIELDS:
        setattr(vital, name, merged[name])
    vital.staff_id = staff_id
    if session_id is not _KEEP:
        vital.session_id = session_id  # type: ignore[assignment]
    weight = values.get("weight_kg")
    if weight is not None:
        _sync_dog_weight(db, dog, measured_on, weight)  # type: ignore[arg-type]
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
    data: VitalPut,
) -> VitalOut:
    """PUT /dogs/{dog_id}/vitals/{measured_on}. 보낸 값만 바꾼다. 미래 날짜는 422다(13.9)."""
    if measured_on > today_local():
        raise AppError(ErrorCode.VALIDATION_ERROR, {"fields": [{"field": "measured_on", "type": "date_future"}]})
    dog = db.scalars(
        select(Dog).where(Dog.id == dog_id, in_institution(institution_id)).with_for_update()
    ).one_or_none()
    if dog is None:
        raise AppError(ErrorCode.NOT_FOUND)
    vital = save_vital(
        db, dog=dog, measured_on=measured_on, values=data.model_dump(exclude_unset=True), staff_id=staff_id
    )
    return VitalOut.model_validate(vital)
