"""반려견 요청·응답 모델(13.2, 13.4, 15.3 DogOut, 15.5).

Spring의 DTO + Bean Validation. 형식·범위 검사는 여기서 하고(422 VALIDATION_ERROR),
업무 규칙(기준 회차 등)은 services가 본다.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator

from app.core.dates import today_local
from app.models.enums import FocusLimb, Sex, SizeClass
from app.schemas.common import OutModel, UtcDateTime, Weight

Name50 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Memo = Annotated[str, StringConstraints(max_length=1000)]
BIRTH_YEAR_MIN = 1990


def _check_birth_year(value: int | None) -> int | None:
    if value is not None and not (BIRTH_YEAR_MIN <= value <= today_local().year):
        raise ValueError(f"{BIRTH_YEAR_MIN}년부터 올해까지만 됩니다")
    return value


def _check_rehab_start_date(value: date | None) -> date | None:
    if value is not None and value > today_local():
        raise ValueError("오늘 이전 날짜여야 합니다")
    return value


class DogCreate(BaseModel):
    """POST /dogs 요청(15.5). baseline_session_id는 등록 때 받지 않는다."""

    name: Name50
    breed: Name50
    weight_kg: Weight
    size_class: SizeClass | None = None
    birth_year: int | None = None
    sex: Sex | None = None
    rehab_start_date: date | None = None
    focus_limb: FocusLimb | None = None
    memo: Memo | None = None

    @field_validator("birth_year")
    @classmethod
    def birth_year_range(cls, value: int | None) -> int | None:
        return _check_birth_year(value)

    @field_validator("rehab_start_date")
    @classmethod
    def rehab_start_not_future(cls, value: date | None) -> date | None:
        return _check_rehab_start_date(value)


class DogUpdate(BaseModel):
    """PATCH /dogs/{dog_id} 요청. 보낸 필드만 바꾼다. 값을 비우려면 null. name·breed·weight_kg은 비울 수 없다(13.2)."""

    name: Name50 | None = None
    breed: Name50 | None = None
    weight_kg: Weight | None = None
    size_class: SizeClass | None = None
    birth_year: int | None = None
    sex: Sex | None = None
    rehab_start_date: date | None = None
    focus_limb: FocusLimb | None = None
    baseline_session_id: uuid.UUID | None = None
    memo: Memo | None = None

    @field_validator("name", "breed", "weight_kg", mode="before")
    @classmethod
    def required_fields_cannot_be_null(cls, value: object) -> object:
        # 보내지 않은 필드에는 검증기가 돌지 않으므로, 여기 None은 "null을 보낸 것"이다
        if value is None:
            raise ValueError("비울 수 없습니다")
        return value

    @field_validator("birth_year")
    @classmethod
    def birth_year_range(cls, value: int | None) -> int | None:
        return _check_birth_year(value)

    @field_validator("rehab_start_date")
    @classmethod
    def rehab_start_not_future(cls, value: date | None) -> date | None:
        return _check_rehab_start_date(value)


class DogOut(OutModel):
    """반려견(15.3). 목록과 상세가 같은 모양이다. weight_kg는 JSON 숫자로 보낸다(15.1)."""

    id: uuid.UUID
    name: str
    breed: str
    weight_kg: float
    size_class: str
    size_class_manual: bool
    birth_year: int | None
    sex: str | None
    rehab_start_date: date | None
    focus_limb: str | None
    baseline_session_id: uuid.UUID | None
    memo: str | None
    session_count: int = 0
    last_measured_on: date | None = None
    open_session_id: uuid.UUID | None = None
    created_at: UtcDateTime
    updated_at: UtcDateTime


class DogListOut(BaseModel):
    """페이지 목록(11.5): items, total, page, size."""

    items: list[DogOut]
    total: int
    page: int
    size: int
