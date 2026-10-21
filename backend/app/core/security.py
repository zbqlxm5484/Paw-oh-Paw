"""비밀번호 해시(13.4), JWT(11.6), 서명 URL(11.6). 명세 11.2 security.py.

Spring에 빗대면 PasswordEncoder + JwtTokenProvider + 서명 URL 도우미를 한 파일에 둔 것이다.
HTTP 오류로 바꾸는 일은 api/deps.py가 한다. 이 파일은 TokenError 같은 자기 예외만 낸다.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings

PASSWORD_MIN_CHARS = 8
# bcrypt 5.0은 72바이트를 넘는 비밀번호를 받으면 오류를 낸다. 한글 한 글자는 UTF-8로 3바이트다.
PASSWORD_MAX_BYTES = 72

JWT_ALGORITHM = "HS256"


# ---- 비밀번호 (13.4) ----


class PasswordRuleError(ValueError):
    """비밀번호가 13.4 규칙에 맞지 않을 때."""


def check_password_rule(password: str) -> None:
    """계정을 만들 때만 검사한다. 로그인에서는 길이를 검사하지 않는다(13.4)."""
    if len(password) < PASSWORD_MIN_CHARS:
        raise PasswordRuleError(f"비밀번호는 {PASSWORD_MIN_CHARS}자 이상이어야 합니다")
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise PasswordRuleError(
            f"비밀번호는 UTF-8로 {PASSWORD_MAX_BYTES}바이트 이하여야 합니다(한글 한 글자는 3바이트)"
        )


def hash_password(password: str) -> str:
    """규칙을 검사한 뒤 bcrypt 해시를 돌려준다. DB에는 이 값만 저장한다."""
    check_password_rule(password)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """비밀번호가 해시와 맞으면 True. 72바이트를 넘으면 bcrypt를 부르지 않고 False다(13.4)."""
    data = password.encode("utf-8")
    if len(data) > PASSWORD_MAX_BYTES:
        return False
    return bcrypt.checkpw(data, password_hash.encode("ascii"))


# ---- JWT (11.6) ----


class TokenError(Exception):
    """토큰이 없거나 잘못되었다. deps.py가 401 AUTH_REQUIRED로 바꾼다."""


class TokenExpiredError(TokenError):
    """토큰이 만료되었다. deps.py가 401 AUTH_EXPIRED로 바꾼다."""


@dataclass(frozen=True)
class TokenClaims:
    """토큰 안의 값(11.6): sub(담당자 ID), inst(기관 ID), role, exp."""

    staff_id: uuid.UUID
    institution_id: uuid.UUID
    role: str
    expires_at: datetime


def create_access_token(
    *, staff_id: uuid.UUID, institution_id: uuid.UUID, role: str, now: datetime | None = None
) -> tuple[str, datetime]:
    """로그인 토큰과 만료 시각. 만료는 JWT_EXPIRE_HOURS(기본 12시간) 뒤이고, 새로 받는 기능은 없다(16절)."""
    settings = get_settings()
    now = now or datetime.now(UTC)
    expires_at = (now + timedelta(hours=settings.JWT_EXPIRE_HOURS)).replace(microsecond=0)
    payload = {
        "sub": str(staff_id),
        "inst": str(institution_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET.get_secret_value(), algorithm=JWT_ALGORITHM)
    return token, expires_at


def decode_access_token(token: str) -> TokenClaims:
    """토큰을 검증해 값을 꺼낸다. 만료면 TokenExpiredError, 그 밖의 문제는 TokenError."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "inst", "role", "exp"]},
        )
    except jwt.ExpiredSignatureError as error:
        raise TokenExpiredError("token expired") from error
    except jwt.InvalidTokenError as error:
        raise TokenError("invalid token") from error
    try:
        return TokenClaims(
            staff_id=uuid.UUID(str(payload["sub"])),
            institution_id=uuid.UUID(str(payload["inst"])),
            role=str(payload["role"]),
            expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=UTC),
        )
    except (KeyError, ValueError, TypeError) as error:
        raise TokenError("invalid claims") from error


# ---- 서명 URL (11.6) ----


def _signature(secret: str, path: str, exp: int) -> str:
    """서명할 문자열은 경로 + 줄바꿈 + exp. HMAC-SHA256의 소문자 16진수 64자."""
    message = f"{path}\n{exp}".encode()
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def make_signed_url(path: str, *, now: datetime | None = None) -> tuple[str, datetime]:
    """FILE_URL_TTL_SEC(기본 300초) 동안 열리는 주소와 만료 시각.

    path는 /api/v1부터 쓴 전체 경로이고 쿼리는 넣지 않는다. download는 서명에 들어가지 않는다(11.6).
    """
    settings = get_settings()
    now = now or datetime.now(UTC)
    expires_at = now.replace(microsecond=0) + timedelta(seconds=settings.FILE_URL_TTL_SEC)
    exp = int(expires_at.timestamp())
    sig = _signature(settings.FILE_URL_SECRET.get_secret_value(), path, exp)
    return f"{path}?exp={exp}&sig={sig}", expires_at


def verify_signed_url(path: str, exp: int, sig: str, *, now: datetime | None = None) -> bool:
    """서명이 맞고 아직 만료되지 않았으면 True. 비교는 hmac.compare_digest로 한다(11.6)."""
    settings = get_settings()
    now = now or datetime.now(UTC)
    if now.timestamp() >= exp:
        return False
    expected = _signature(settings.FILE_URL_SECRET.get_secret_value(), path, exp)
    return hmac.compare_digest(expected, sig)
