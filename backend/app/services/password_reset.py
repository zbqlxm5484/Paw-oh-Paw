"""비밀번호 재설정(11.6 메일, 12.5 재설정 토큰, 13.8, 15.4 password-reset 둘, BE-27).

토큰은 secrets.token_urlsafe(32)로 만들어 메일로만 보내고, DB에는 SHA-256 해시와 만료 시각(30분)만 둔다. 계정당 하나라
새로 요청하면 이전 토큰은 덮어써서 무효가 된다. 쓰면 지운다. 토큰·이메일은 로그에 남기지 않는다(11.8).
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import mail
from app.core.auth_cache import auth_cache
from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode, message_for
from app.models import Staff
from app.services.auth import set_new_password

logger = logging.getLogger(__name__)

# 15.4: 발급 30분 뒤 만료(코드 상수)
PASSWORD_RESET_TTL_MIN = 30
# messages/ko.yaml의 메일 문구 키(11.6)
MAIL_SUBJECT_KEY = "mail.password_reset.subject"
MAIL_BODY_KEY = "mail.password_reset.body"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def reset_link(token: str) -> str:
    """{FRONTEND_BASE_URL}/reset-password?token={토큰}(15.4)."""
    return f"{get_settings().FRONTEND_BASE_URL.rstrip('/')}/reset-password?token={token}"


def request_reset(db: Session, login_id: str) -> None:
    """재설정 링크 메일(15.4). 계정이 있든 없든 응답은 같다(204). SMTP가 없으면 계정과 상관없이 503.

    계정이 있고 활성이고 이메일이 있을 때만 토큰을 저장하고 메일을 보낸다. GUEST(계약 만료)도 보낸다.
    응답 시간으로 계정 유무를 알 수 없게, 토큰은 계정을 찾기 전에 만든다. 발송이 실패하면 저장한 토큰을 지우고 503.
    """
    if not mail.is_configured():
        raise AppError(ErrorCode.MAIL_UNAVAILABLE)
    token = secrets.token_urlsafe(32)
    token_hash = _hash(token)
    staff = db.scalars(select(Staff).where(Staff.login_id == login_id)).one_or_none()
    if staff is None or not staff.is_active or not staff.email:
        return
    staff.password_reset_hash = token_hash
    staff.password_reset_expires_at = datetime.now(UTC) + timedelta(minutes=PASSWORD_RESET_TTL_MIN)
    db.flush()
    detail = {"name": staff.name, "link": reset_link(token), "ttl_min": PASSWORD_RESET_TTL_MIN}
    try:
        mail.send_mail(staff.email, message_for(MAIL_SUBJECT_KEY), message_for(MAIL_BODY_KEY, detail))
    except mail.MailUnavailable:
        staff.password_reset_hash = None
        staff.password_reset_expires_at = None
        db.flush()
        raise AppError(ErrorCode.MAIL_UNAVAILABLE) from None


def confirm_reset(db: Session, token: str, new_password: str) -> None:
    """토큰으로 비밀번호 바꾸기(15.4). 해시가 맞고 만료 전인 활성 계정이 없으면 400 RESET_TOKEN_INVALID.

    새 비밀번호 규칙(13.4)은 PasswordResetConfirmIn이 422로 본다. 바꾸면 두 칸을 NULL로 하고 캐시에서 지운다.
    그전에 받은 로그인 토큰이 끊기고 로그인 잠금이 풀린다(v1.48, services/auth.set_new_password).
    로그에는 담당자 ID만 남긴다(토큰·이메일은 남기지 않는다, 11.8).
    """
    now = datetime.now(UTC)
    staff = db.scalars(
        select(Staff).where(Staff.password_reset_hash == _hash(token), Staff.is_active.is_(True))
    ).one_or_none()
    if staff is None or staff.password_reset_expires_at is None or staff.password_reset_expires_at <= now:
        raise AppError(ErrorCode.RESET_TOKEN_INVALID)
    set_new_password(db, staff, new_password)
    staff.password_reset_hash = None
    staff.password_reset_expires_at = None
    db.flush()
    auth_cache.invalidate(staff.id)
    logger.info("password reset staff=%s", staff.id)
