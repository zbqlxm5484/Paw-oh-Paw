"""인증 요청·응답 모델(15.3 StaffOut, 15.4)."""

import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.schemas.common import OutModel, UtcDateTime


class LoginIn(BaseModel):
    """13.4: 아이디 1~50자. 비밀번호 길이는 로그인에서 검사하지 않는다.

    institution_code가 와도 무시한다(v1.11까지의 화면이 보내던 값).
    """

    login_id: str = Field(min_length=1, max_length=50)
    password: str


class InstitutionOut(OutModel):
    """담당자의 기관(15.3). contract_status는 저장값이 아니라 오늘 기준 계산값이다(11.6)."""

    id: uuid.UUID
    code: str
    name: str
    contract_ends_at: date | None
    contract_status: str


class StaffOut(OutModel):
    """로그인한 담당자(15.3). 화면은 role이 아니라 effective_role(ADMIN·STAFF·CLIENT·GUEST)로 분기한다."""

    id: uuid.UUID
    login_id: str
    name: str
    email: str | None
    role: str
    effective_role: str
    institution: InstitutionOut


class TokenOut(BaseModel):
    """POST /auth/login 응답(15.4)."""

    access_token: str
    token_type: str = "bearer"
    expires_at: UtcDateTime
    staff: StaffOut
