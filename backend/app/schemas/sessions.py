"""회차 요청·응답 모델(13.3, 15.3 SessionOut, 15.6)."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, field_validator

from app.core.dates import today_local
from app.schemas.common import OutModel, ReasonOut, UtcDateTime, Weight
from app.schemas.shots import ShotOut


class SessionCreate(BaseModel):
    """POST /dogs/{dog_id}/sessions 요청. 둘 다 선택이다. measured_on 기본값은 오늘(한국 날짜), 미래 날짜 불가(13.3)."""

    measured_on: date | None = None
    weight_kg: Weight | None = None

    @field_validator("measured_on")
    @classmethod
    def not_future(cls, value: date | None) -> date | None:
        if value is not None and value > today_local():
            raise ValueError("미래 날짜는 쓸 수 없습니다")
        return value


class StaffBriefOut(OutModel):
    id: uuid.UUID
    name: str


class DogBriefOut(OutModel):
    id: uuid.UUID
    name: str
    breed: str
    weight_kg: float
    size_class: str


class SideProgressOut(BaseModel):
    valid_passes: int
    recommended: int


class ProgressOut(BaseModel):
    """camera_side별 유효 통과 수와 권장 수(15.6)."""

    LEFT: SideProgressOut
    RIGHT: SideProgressOut


class SessionOut(BaseModel):
    """회차(15.3)."""

    id: uuid.UUID
    dog_id: uuid.UUID
    staff: StaffBriefOut
    measured_on: date
    weight_kg: float | None
    status: str
    fail_reason: ReasonOut | None
    model_name: str | None
    model_version: str | None
    completed_at: UtcDateTime | None
    aggregated_at: UtcDateTime | None
    created_at: UtcDateTime


class SessionDetailOut(SessionOut):
    """GET /sessions/{id}: SessionOut + 반려견 요약, 진행, 안내, 촬영 목록(seq_no 내림차순)."""

    dog: DogBriefOut
    progress: ProgressOut
    notices: list[ReasonOut]
    shots: list[ShotOut]
