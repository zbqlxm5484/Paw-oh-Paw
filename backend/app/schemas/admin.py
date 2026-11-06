"""크림오프 관리자 API 요청·응답 모델(13.6, 15.3 InstitutionAdminOut·DeviceCodeOut, 15.9).

Spring의 DTO + Bean Validation. 형식·범위 검사는 여기서 하고(422), 기관 코드 중복·자기 계정 중지 같은 업무 규칙은
services/admin.py가 본다.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, ValidationInfo, field_validator

from app.schemas.common import OutModel, UtcDateTime

# 13.6 기관 코드 1~20자(비우면 서버가 만든다), 기관 이름 1~100자, 코드 메모 최대 100자
InstitutionCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
InstitutionName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Note = Annotated[str, StringConstraints(max_length=100)]


def _not_null(value: object) -> object:
    """PATCH에서 "필드": null을 막는다(보내지 않은 것과 구분한다)."""
    if value is None:
        raise ValueError("비울 수 없습니다")
    return value


# ---- 기관 ----


class InstitutionAdminOut(BaseModel):
    """기관(15.3). contract_status·staff_count·device_code_count는 계산값이다."""

    id: uuid.UUID
    code: str
    name: str
    contract_ends_at: date | None
    contract_status: str
    staff_count: int
    device_code_count: int
    created_at: UtcDateTime


class InstitutionListOut(BaseModel):
    items: list[InstitutionAdminOut]


class InstitutionCreate(BaseModel):
    """POST /admin/institutions(15.9). code가 null이면 서버가 INST- + 6자로 만든다(13.6)."""

    code: InstitutionCode | None = None
    name: InstitutionName
    contract_ends_at: date | None = None


class InstitutionUpdate(BaseModel):
    """PATCH /admin/institutions/{id}: 보낸 필드만. contract_ends_at의 null은 기한 없음, name은 비울 수 없다."""

    name: InstitutionName | None = None
    contract_ends_at: date | None = None

    @field_validator("name")
    @classmethod
    def name_not_null(cls, value: str | None) -> str | None:
        return _not_null(value)  # type: ignore[return-value]


# ---- 디바이스 코드 ----


class DeviceCodeOut(BaseModel):
    """디바이스 코드(15.3). code는 화면 모양(XXXXX-XXXXX-XXXXX-XXXXX). 코드 전체가 든 자리는 발급 응답과 목록뿐이다."""

    id: uuid.UUID
    code: str
    institution_id: uuid.UUID
    active_accounts: int
    revoked_at: UtcDateTime | None
    note: str | None
    created_at: UtcDateTime


class DeviceCodeListOut(BaseModel):
    items: list[DeviceCodeOut]


class DeviceCodeCreate(BaseModel):
    """POST /admin/institutions/{id}/device-codes(15.9). 본문을 비우면 메모 없음. 계정 수 상한은 없다(v1.32)."""

    note: Note | None = None


class DeviceCodeUpdate(BaseModel):
    """PATCH /admin/device-codes/{id}: 보낸 필드만. note의 null은 메모 지우기다."""

    note: Note | None = None


# ---- 계정 ----


class StaffAdminOut(OutModel):
    """기관의 계정 목록 항목(15.9). 비밀번호·토큰은 어디에도 없다."""

    id: uuid.UUID
    login_id: str
    name: str
    email: str | None
    role: str
    is_active: bool
    device_code_id: uuid.UUID | None
    created_at: UtcDateTime


class StaffListOut(BaseModel):
    items: list[StaffAdminOut]


class StaffUpdate(BaseModel):
    """PATCH /admin/staff/{id}(15.9): 중지·재개만. 역할·비밀번호를 바꾸는 필드는 없다."""

    is_active: bool


# ---- 자료 파기(15.9, BE-19) ----


class PurgeRequest(BaseModel):
    """POST /admin/purge 요청. DOG는 target_id(반려견 ID) 필수, INSTITUTION은 기관 전체라 target_id가 없다.

    institution_id는 지울 자료가 있는 기관이다. 생략하면 부른 관리자의 기관이다(15.9).
    여러 기관을 지우는 ALL은 API로 열지 않는다(scripts/purge.py). dry_run 기본값은 true: 세기만 하고 지우지 않는다.
    """

    scope: Literal["DOG", "INSTITUTION"]
    target_id: uuid.UUID | None = Field(default=None, validate_default=True)
    institution_id: uuid.UUID | None = None
    dry_run: bool = True

    @field_validator("target_id")
    @classmethod
    def target_matches_scope(cls, value: uuid.UUID | None, info: ValidationInfo) -> uuid.UUID | None:
        scope = info.data.get("scope")
        if scope == "DOG" and value is None:
            raise ValueError("scope가 DOG면 반려견 ID가 필요합니다")
        if scope == "INSTITUTION" and value is not None:
            raise ValueError("scope가 INSTITUTION이면 target_id를 보내지 않습니다(기관 전체)")
        return value


class PurgeOut(BaseModel):
    """파기 결과 또는 dry_run 집계(15.9). rows는 반려견·회차·촬영·통과·수치·보고서 행 수의 합.

    analysis_jobs는 분석 API에서 지운(또는 지울) 작업 수이고 이미 없던 작업도 센다. ALL은 작업마다 부르지 않아 0이다.
    """

    scope: str
    target_id: uuid.UUID | None
    dry_run: bool
    rows: int
    files: int
    bytes: int
    analysis_jobs: int = 0
    purge_log_id: uuid.UUID | None = None
