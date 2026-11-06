"""차트 자료 요청·응답 모델(13.9, 15.3 VitalOut, 15.11): 바이탈.

schemas/sessions.py가 VitalIn을 쓰므로(회차 시작의 vital) 이 파일은 sessions를 import하지 않는다.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from app.schemas.common import OutModel, StaffBriefOut, UtcDateTime, Weight

# 13.9. 범위는 통합본에 없어 제안한 값이다(병원 의견을 받으면 고친다)
TempC = Annotated[Decimal, Field(ge=Decimal("30.0"), le=Decimal("45.0"), decimal_places=1)]


class VitalIn(BaseModel):
    """바이탈 하루치. 다섯 값 모두 필수다(13.9). PUT /dogs/{dog_id}/vitals/{measured_on}과 회차 시작의 vital이 쓴다."""

    weight_kg: Weight
    temp_c: TempC
    heart_rate: int = Field(ge=20, le=300)
    sbp: int = Field(ge=30, le=300)
    dbp: int = Field(ge=10, le=250)

    @field_validator("dbp")
    @classmethod
    def dbp_below_sbp(cls, value: int, info: ValidationInfo) -> int:
        # sbp가 앞에 선언돼 있어 여기서 읽을 수 있다. sbp 자체가 틀렸으면 그 오류만 낸다
        sbp = info.data.get("sbp")
        if sbp is not None and value >= sbp:
            raise ValueError("이완기 혈압은 수축기 혈압보다 작아야 합니다")
        return value


class VitalOut(OutModel):
    """바이탈 하루치(15.3). staff는 마지막으로 저장한 담당자다."""

    id: uuid.UUID
    measured_on: date
    weight_kg: float
    temp_c: float
    heart_rate: int
    sbp: int
    dbp: int
    staff: StaffBriefOut
    session_id: uuid.UUID | None
    created_at: UtcDateTime
    updated_at: UtcDateTime


class VitalListOut(BaseModel):
    """GET /dogs/{dog_id}/vitals: 전부, 최신이 앞(15.11)."""

    items: list[VitalOut]
