"""인증 요청·응답 모델(15.3 StaffOut, 15.4)."""

import uuid

from pydantic import BaseModel, Field

from app.schemas.common import OutModel, UtcDateTime


class LoginIn(BaseModel):
    """13.4: 기관 코드 1~20자, 아이디 1~50자. 비밀번호 길이는 로그인에서 검사하지 않는다."""

    institution_code: str = Field(min_length=1, max_length=20)
    login_id: str = Field(min_length=1, max_length=50)
    password: str


class InstitutionOut(OutModel):
    id: uuid.UUID
    code: str
    name: str


class StaffOut(OutModel):
    """로그인한 담당자(15.3)."""

    id: uuid.UUID
    login_id: str
    name: str
    role: str
    institution: InstitutionOut


class TokenOut(BaseModel):
    """POST /auth/login 응답(15.4)."""

    access_token: str
    token_type: str = "bearer"
    expires_at: UtcDateTime
    staff: StaffOut
