"""차트 자료 요청·응답 모델(13.9, 15.3 VitalOut·DogHistoryOut·NoteOut, 15.11): 바이탈, 진단 이력, 메모·진료 기록, 사진.

schemas/sessions.py가 VitalIn을 쓰므로(회차 시작의 vital) 이 파일은 sessions를 import하지 않는다.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, ValidationInfo, field_validator

from app.core.dates import today_local
from app.models.enums import DogStage, HistoryKind, HistorySite, NoteCategory
from app.schemas.common import OutModel, StaffBriefOut, UtcDateTime, Weight

# 13.9. 범위는 통합본에 없어 제안한 값이다(병원 의견을 받으면 고친다)
TempC = Annotated[Decimal, Field(ge=Decimal("30.0"), le=Decimal("45.0"), decimal_places=1)]
Text50 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Text100 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
NoteBody = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


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


class DogHistoryCreate(BaseModel):
    """POST /dogs/{dog_id}/history 요청(13.9). stage를 보내면 반려견의 단계를 함께 바꾼다."""

    occurred_on: date
    kind: HistoryKind
    title: Text100
    site: HistorySite | None = None
    clinician: Text50 | None = None
    stage: DogStage | None = None

    @field_validator("occurred_on")
    @classmethod
    def not_future(cls, value: date) -> date:
        if value > today_local():
            raise ValueError("오늘 이전 날짜여야 합니다")
        return value


class DogHistoryOut(OutModel):
    """진단 이력 한 줄(15.3). staff는 적은 담당자다."""

    id: uuid.UUID
    occurred_on: date
    kind: str
    title: str
    site: str | None
    clinician: str | None
    staff: StaffBriefOut
    created_at: UtcDateTime


class DogHistoryListOut(BaseModel):
    """GET /dogs/{dog_id}/history: 전부, 오래된 것부터(15.11)."""

    items: list[DogHistoryOut]


class NoteItemIn(BaseModel):
    """메모·진료 기록 한 건의 내용(13.9)."""

    category: NoteCategory
    body: NoteBody
    important: bool = False


class NoteCreate(NoteItemIn):
    """POST /dogs/{dog_id}/notes 요청. session_id는 같은 반려견의 회차(선택)."""

    session_id: uuid.UUID | None = None


class NoteBatchCreate(BaseModel):
    """POST /dogs/{dog_id}/notes/batch 요청: 1~8건을 같은 시각으로 쓴다. 같은 분류가 두 번 있으면 422(13.9)."""

    session_id: uuid.UUID | None = None
    notes: list[NoteItemIn] = Field(min_length=1, max_length=8)

    @field_validator("notes")
    @classmethod
    def categories_are_distinct(cls, value: list[NoteItemIn]) -> list[NoteItemIn]:
        categories = [item.category for item in value]
        if len(set(categories)) != len(categories):
            raise ValueError("같은 분류를 두 번 보낼 수 없습니다")
        return value


class NoteUpdate(BaseModel):
    """PATCH /notes/{note_id} 요청. 보낸 것만 바꾼다. 셋 다 null은 안 된다(13.9)."""

    body: NoteBody | None = None
    category: NoteCategory | None = None
    important: bool | None = None

    @field_validator("body", "category", "important", mode="before")
    @classmethod
    def cannot_be_null(cls, value: object) -> object:
        # 보내지 않은 필드에는 검증기가 돌지 않으므로, 여기 None은 "null을 보낸 것"이다
        if value is None:
            raise ValueError("비울 수 없습니다")
        return value


class NoteOut(OutModel):
    """메모·진료 기록 한 건(15.3). staff는 지금 내용을 쓴 담당자, revision_count는 고친 횟수다."""

    id: uuid.UUID
    dog_id: uuid.UUID
    session_id: uuid.UUID | None
    category: str
    body: str
    important: bool
    staff: StaffBriefOut
    revision_count: int = 0
    created_at: UtcDateTime
    updated_at: UtcDateTime


class NoteListOut(BaseModel):
    """페이지 목록(11.5): items, total, page, size."""

    items: list[NoteOut]
    total: int
    page: int
    size: int


class NoteBatchOut(BaseModel):
    """묶음으로 쓴 것들(보낸 순서)."""

    items: list[NoteOut]


class NoteRevisionOut(OutModel):
    """고치기 전 내용 한 줄(15.11). staff는 그 내용을 쓴 담당자, revised_at은 그 내용이 바뀐 시각."""

    id: uuid.UUID
    body: str
    category: str
    important: bool
    staff: StaffBriefOut
    revised_at: UtcDateTime


class NoteRevisionListOut(BaseModel):
    items: list[NoteRevisionOut]


class ImageOut(BaseModel):
    """반려견 사진 하나(15.11). file_url은 서명 URL이고 url_expires_at까지 쓸 수 있다.

    masked_faces는 올릴 때 가린 얼굴 수다. 0보다 크면 사진의 일부가 모자이크되어 있다.
    """

    id: uuid.UUID
    taken_on: date
    kind: str
    caption: str | None
    width: int
    height: int
    masked_faces: int
    staff: StaffBriefOut
    created_at: UtcDateTime
    file_url: str
    url_expires_at: UtcDateTime


class ImageListOut(BaseModel):
    items: list[ImageOut]
