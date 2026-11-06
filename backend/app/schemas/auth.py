"""인증 요청·응답 모델(13.4, 13.5, 15.3 StaffOut, 15.4).

Spring의 DTO + Bean Validation. 형식 검사는 여기서 하고(422 VALIDATION_ERROR), 코드·아이디 중복 같은 업무 규칙은
services가 본다.
"""

import uuid
from datetime import date
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, StringConstraints, ValidationInfo, field_validator

from app.core.security import PasswordRuleError, check_password_rule
from app.schemas.common import OutModel, UtcDateTime

# 13.5 아이디: 4~50자, 영문 소문자·숫자·.·_·-만. 대문자는 422(로그인의 '입력 그대로 비교'와 부딪히지 않게)
LOGIN_ID_PATTERN = r"^[a-z0-9._-]{4,50}$"
LoginId = Annotated[str, StringConstraints(pattern=LOGIN_ID_PATTERN)]
# 13.5 이름: 1~50자, 앞뒤 공백은 지운다
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
# 13.5 이메일: 앞뒤 공백을 지우고 소문자로, 5~254자, @가 하나이고 그 뒤에 .이 있다(정규식, 라이브러리 없음)
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, min_length=5, max_length=254, pattern=EMAIL_PATTERN),
]


def _password_rule(value: str) -> str:
    """13.4 규칙(8자 이상, UTF-8 72바이트 이하)을 422로. 계정을 만들거나 비밀번호를 바꿀 때만 검사한다."""
    try:
        check_password_rule(value)
    except PasswordRuleError as error:
        raise ValueError(str(error)) from None
    return value


NewPassword = Annotated[str, AfterValidator(_password_rule)]


class LoginIn(BaseModel):
    """13.4: 아이디 1~50자. 비밀번호 길이는 로그인에서 검사하지 않는다.

    institution_code가 와도 무시한다(v1.11까지의 화면이 보내던 값).
    """

    login_id: str = Field(min_length=1, max_length=50)
    password: str


class DeviceCodeVerifyIn(BaseModel):
    """POST /auth/device-codes/verify 요청(15.4). 하이픈·공백·소문자는 서비스가 정리한다(13.5)."""

    code: str = Field(min_length=1, max_length=40)


class InstitutionBriefOut(OutModel):
    """verify 응답의 기관(15.4): 가입 화면에 보여 줄 이름만."""

    id: uuid.UUID
    name: str


class DeviceCodeVerifyOut(BaseModel):
    """POST /auth/device-codes/verify 응답(15.4)."""

    institution: InstitutionBriefOut


# 13.5 약관 버전: 1~20자, 앞뒤 공백은 지운다
TermsVersion = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]


class TermsIn(BaseModel):
    """가입 때의 약관 동의(13.5, 15.4). 필수 셋은 true여야 하고(아니면 422) marketing만 선택이다."""

    version: TermsVersion
    service: bool
    privacy: bool
    device_location: bool
    marketing: bool = False

    @field_validator("service", "privacy", "device_location")
    @classmethod
    def required_terms_are_agreed(cls, value: bool) -> bool:
        if not value:
            raise ValueError("필수 약관에 동의해야 합니다")
        return value


class SignupIn(BaseModel):
    """POST /auth/signup 요청(13.5, 15.4). 가입 계정은 모두 CLIENT이고 이메일은 필수다(인증 메일은 없다).

    terms는 약관 동의다. 화면이 아직 보내지 않아 없어도 가입되고 그때는 기록을 남기지 않는다(15.4).
    """

    code: str = Field(min_length=1, max_length=40)
    login_id: LoginId
    password: NewPassword
    name: PersonName
    email: Email
    terms: TermsIn | None = None


class PasswordChangeIn(BaseModel):
    """PATCH /auth/password 요청(13.7). 현재 비밀번호는 길이를 검사하지 않는다(로그인과 같다)."""

    current_password: str
    new_password: NewPassword

    @field_validator("new_password")
    @classmethod
    def differs_from_current(cls, value: str, info: ValidationInfo) -> str:
        if value == info.data.get("current_password"):
            raise ValueError("현재 비밀번호와 같습니다")
        return value


class MeUpdate(BaseModel):
    """PATCH /auth/me 요청(13.7): 이름·이메일, 보낸 필드만. null은 받지 않는다."""

    name: PersonName | None = None
    email: Email | None = None

    @field_validator("name", "email")
    @classmethod
    def not_null(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("비울 수 없습니다")
        return value


class PasswordResetRequestIn(BaseModel):
    """POST /auth/password-reset/request 요청(13.8). 없는 아이디여도 204."""

    login_id: str = Field(min_length=1, max_length=50)


class PasswordResetConfirmIn(BaseModel):
    """POST /auth/password-reset/confirm 요청(13.8)."""

    token: str = Field(min_length=1, max_length=100)
    new_password: NewPassword


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
