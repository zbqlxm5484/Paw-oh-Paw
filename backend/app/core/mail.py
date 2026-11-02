"""재설정 메일 보내기(11.6 메일). 파이썬 표준 smtplib(STARTTLS)만 쓰고 라이브러리를 더하지 않는다(D-11).

SMTP_HOST가 비어 있으면 보내지 않고 MailUnavailable을 낸다(API는 503 MAIL_UNAVAILABLE).
받는 주소는 로그에 남기지 않는다(11.8). Spring에 빗대면 JavaMailSender를 아주 얇게 둔 것이다.
테스트는 _deliver를 가짜로 바꿔 끼운다.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)
SMTP_TIMEOUT_SEC = 10


class MailUnavailable(Exception):
    """SMTP가 설정되지 않았거나 발송에 실패했다."""


def is_configured() -> bool:
    return bool(get_settings().SMTP_HOST)


def send_mail(to: str, subject: str, body: str) -> None:
    """평문 메일 한 통. 실패 원인은 예외 종류만 로그에 남긴다(주소·본문은 남기지 않는다)."""
    settings = get_settings()
    if not settings.SMTP_HOST:
        raise MailUnavailable("SMTP_HOST is empty")
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        _deliver(message)
    except (smtplib.SMTPException, OSError) as error:
        logger.error("mail delivery failed: %s", type(error).__name__)
        raise MailUnavailable("delivery failed") from error


def _deliver(message: EmailMessage) -> None:
    """실제 발송: 접속 → STARTTLS → (계정이 있으면) 로그인 → 전송."""
    settings = get_settings()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=SMTP_TIMEOUT_SEC) as smtp:
        smtp.starttls()
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD.get_secret_value())
        smtp.send_message(message)
