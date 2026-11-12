"""비밀번호 재설정(11.6 메일, 12.5 재설정 토큰, 13.8, 15.4, 17.2 BE-27)과 core/mail.py."""

import hashlib
import logging
import re
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import mail
from app.core.config import get_settings
from app.core.dates import today_local
from app.services.auth import LOGIN_MAX_FAILURES
from app.services.password_reset import PASSWORD_RESET_TTL_MIN
from tests.conftest import GOOD_PASSWORD

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
REQUEST = "/api/v1/auth/password-reset/request"
CONFIRM = "/api/v1/auth/password-reset/confirm"
NEW_PASSWORD = "reset-pass-9012"
EMAIL = "staff1@example.com"


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> list[EmailMessage]:
    """SMTP를 켜고(가짜 호스트) 실제 발송 대신 보낸 메일을 모은다."""
    sent: list[EmailMessage] = []
    settings = get_settings()
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(settings, "SMTP_FROM", "no-reply@test")
    monkeypatch.setattr(mail, "_deliver", sent.append)
    return sent


@pytest.fixture
def mailable(db: Session, staff):
    """이메일이 있는 활성 담당자."""
    staff.email = EMAIL
    db.flush()
    return staff


def _request(client: TestClient, login_id: str = "staff1"):
    return client.post(REQUEST, json={"login_id": login_id})


def _token_in(message: EmailMessage) -> str:
    match = re.search(r"/reset-password\?token=([A-Za-z0-9_-]+)", message.get_content())
    assert match is not None
    return match.group(1)


def _login(client: TestClient, password: str):
    return client.post(LOGIN, json={"login_id": "staff1", "password": password})


# ---- 요청 (BE-27) ----


def test_request_stores_hash_and_sends_one_mail(client: TestClient, db: Session, mailable, outbox: list) -> None:
    response = _request(client)
    assert response.status_code == 204
    assert response.content == b""
    [message] = outbox
    assert (message["From"], message["To"]) == ("no-reply@test", EMAIL)
    assert message["Subject"]
    body = message.get_content()
    assert "담당자" in body  # 이름
    assert f"{PASSWORD_RESET_TTL_MIN}분" in body
    token = _token_in(message)
    assert body.count(get_settings().FRONTEND_BASE_URL) == 1
    # DB에는 해시와 만료 시각만 있다
    db.refresh(mailable)
    assert mailable.password_reset_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in (mailable.password_reset_hash or "")
    remaining = mailable.password_reset_expires_at - datetime.now(UTC)
    assert timedelta(minutes=PASSWORD_RESET_TTL_MIN - 1) < remaining <= timedelta(minutes=PASSWORD_RESET_TTL_MIN)


@pytest.mark.parametrize("case", ["unknown", "no_email", "disabled"])
def test_request_is_204_without_mail_for_unknown_disabled_or_no_email(
    client: TestClient, db: Session, staff, outbox: list, case: str
) -> None:
    login_id = "staff1"
    if case == "unknown":
        login_id = "nobody"
    elif case == "disabled":
        staff.email = EMAIL
        staff.is_active = False
    db.flush()
    response = _request(client, login_id)
    assert response.status_code == 204
    assert response.content == b""
    assert outbox == []
    db.refresh(staff)
    assert staff.password_reset_hash is None


def test_request_is_503_without_smtp(client: TestClient, db: Session, mailable) -> None:
    """SMTP_HOST가 비어 있으면 계정과 상관없이 503이고 토큰을 저장하지 않는다."""
    assert get_settings().SMTP_HOST == ""
    for login_id in ("staff1", "nobody"):
        response = _request(client, login_id)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "MAIL_UNAVAILABLE"
    db.refresh(mailable)
    assert mailable.password_reset_hash is None


def test_delivery_failure_is_503_and_clears_token(
    client: TestClient, db: Session, mailable, outbox: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(message: EmailMessage) -> None:
        raise smtplib.SMTPServerDisconnected("gone")

    monkeypatch.setattr(mail, "_deliver", fail)
    response = _request(client)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MAIL_UNAVAILABLE"
    db.refresh(mailable)
    assert (mailable.password_reset_hash, mailable.password_reset_expires_at) == (None, None)


def test_guest_can_request_reset(client: TestClient, db: Session, mailable, outbox: list) -> None:
    mailable.institution.contract_ends_at = today_local() - timedelta(days=1)
    db.flush()
    assert _request(client).status_code == 204
    assert len(outbox) == 1


def test_request_input_rules(client: TestClient, outbox: list) -> None:
    assert client.post(REQUEST, json={"login_id": ""}).status_code == 422
    assert client.post(REQUEST, json={"login_id": "a" * 51}).status_code == 422
    assert client.post(REQUEST, json={}).status_code == 422


# ---- 확인 (BE-27) ----


def test_confirm_changes_password_and_token_works_once(client: TestClient, db: Session, mailable, outbox: list) -> None:
    _request(client)
    token = _token_in(outbox[0])

    done = client.post(CONFIRM, json={"token": token, "new_password": NEW_PASSWORD})
    assert done.status_code == 204
    assert done.content == b""
    assert _login(client, NEW_PASSWORD).status_code == 200
    assert _login(client, GOOD_PASSWORD).status_code == 401
    db.refresh(mailable)
    assert (mailable.password_reset_hash, mailable.password_reset_expires_at) == (None, None)

    again = client.post(CONFIRM, json={"token": token, "new_password": "another-pass-1"})
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "RESET_TOKEN_INVALID"
    assert _login(client, NEW_PASSWORD).status_code == 200


def test_confirm_rejects_expired_wrong_or_disabled(client: TestClient, db: Session, mailable, outbox: list) -> None:
    _request(client)
    token = _token_in(outbox[0])

    wrong = client.post(
        CONFIRM, json={"token": token[:-1] + ("A" if token[-1] != "A" else "B"), "new_password": NEW_PASSWORD}
    )
    assert wrong.status_code == 400
    assert wrong.json()["error"]["code"] == "RESET_TOKEN_INVALID"

    short = client.post(CONFIRM, json={"token": token, "new_password": "short7!"})
    assert short.status_code == 422
    assert [item["field"] for item in short.json()["error"]["detail"]["fields"]] == ["new_password"]

    mailable.password_reset_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()
    expired = client.post(CONFIRM, json={"token": token, "new_password": NEW_PASSWORD})
    assert expired.status_code == 400
    assert expired.json()["error"]["code"] == "RESET_TOKEN_INVALID"
    assert _login(client, GOOD_PASSWORD).status_code == 200


def test_confirm_cuts_tokens_issued_before_and_unlocks(
    client: TestClient, db: Session, mailable, outbox: list, caplog
) -> None:
    """v1.48(12.5): 재설정하면 그전에 받은 로그인 토큰이 끊기고 로그인 잠금이 풀린다. 로그에는 담당자 ID만 남는다."""
    old = _login(client, GOOD_PASSWORD)
    old_headers = {"Authorization": f"Bearer {old.json()['access_token']}"}
    # 누가 이 아이디로 다섯 번 틀려 잠긴 상태
    mailable.login_fail_count = LOGIN_MAX_FAILURES
    mailable.login_locked_until = datetime.now(UTC) + timedelta(minutes=20)
    db.flush()
    assert _login(client, GOOD_PASSWORD).status_code == 401
    assert client.get(ME, headers=old_headers).status_code == 200  # 잠겨도 받은 토큰은 쓴다

    _request(client)
    with caplog.at_level(logging.DEBUG):
        done = client.post(CONFIRM, json={"token": _token_in(outbox[0]), "new_password": NEW_PASSWORD})
    assert done.status_code == 204
    assert (mailable.login_fail_count, mailable.login_locked_until) == (0, None)
    assert mailable.password_changed_at is not None

    cut = client.get(ME, headers=old_headers)
    assert cut.status_code == 401
    assert cut.json()["error"]["code"] == "AUTH_EXPIRED"
    fresh = _login(client, NEW_PASSWORD)
    assert fresh.status_code == 200
    assert client.get(ME, headers={"Authorization": f"Bearer {fresh.json()['access_token']}"}).status_code == 200
    assert f"password reset staff={mailable.id}" in caplog.text
    assert NEW_PASSWORD not in caplog.text and EMAIL not in caplog.text


def test_failed_confirm_keeps_tokens_and_lock(client: TestClient, db: Session, mailable, outbox: list) -> None:
    headers = {"Authorization": f"Bearer {_login(client, GOOD_PASSWORD).json()['access_token']}"}
    mailable.login_fail_count = 3
    db.flush()
    wrong = client.post(CONFIRM, json={"token": "not-the-token", "new_password": NEW_PASSWORD})
    assert wrong.status_code == 400
    db.expire_all()
    assert (mailable.login_fail_count, mailable.password_changed_at) == (3, None)
    assert client.get(ME, headers=headers).status_code == 200


def test_new_request_replaces_the_old_token(client: TestClient, mailable, outbox: list) -> None:
    _request(client)
    _request(client)
    first, second = (_token_in(message) for message in outbox)
    assert first != second
    assert client.post(CONFIRM, json={"token": first, "new_password": NEW_PASSWORD}).status_code == 400
    assert client.post(CONFIRM, json={"token": second, "new_password": NEW_PASSWORD}).status_code == 204


def test_logs_do_not_contain_token_or_email(
    client: TestClient, mailable, outbox: list, monkeypatch: pytest.MonkeyPatch, caplog
) -> None:
    with caplog.at_level(logging.DEBUG):
        _request(client)
        token = _token_in(outbox[0])
        monkeypatch.setattr(mail, "_deliver", lambda message: (_ for _ in ()).throw(OSError("down")))
        assert _request(client).status_code == 503
        client.post(CONFIRM, json={"token": token, "new_password": NEW_PASSWORD})
    assert EMAIL not in caplog.text
    assert token not in caplog.text
    assert "mail delivery failed: OSError" in caplog.text


# ---- core/mail.py ----


class _FakeSmtp:
    calls: list = []
    instances: list = []

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.args = (host, port, timeout)
        _FakeSmtp.instances.append(self)

    def __enter__(self) -> "_FakeSmtp":
        return self

    def __exit__(self, *exc: object) -> None:
        _FakeSmtp.calls.append(("quit",))

    def starttls(self) -> None:
        _FakeSmtp.calls.append(("starttls",))

    def login(self, user: str, password: str) -> None:
        _FakeSmtp.calls.append(("login", user, password))

    def send_message(self, message: EmailMessage) -> None:
        _FakeSmtp.calls.append(("send", message["From"], message["To"], message["Subject"], message.get_content()))


def test_deliver_uses_starttls_and_login(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import SecretStr

    settings = get_settings()
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 2525)
    monkeypatch.setattr(settings, "SMTP_USER", "sender")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", SecretStr("smtp-secret"))
    monkeypatch.setattr(settings, "SMTP_FROM", "no-reply@example.com")
    _FakeSmtp.calls, _FakeSmtp.instances = [], []
    monkeypatch.setattr(mail.smtplib, "SMTP", _FakeSmtp)

    mail.send_mail("to@example.com", "제목", "본문\n")

    assert _FakeSmtp.instances[0].args == ("smtp.example.com", 2525, mail.SMTP_TIMEOUT_SEC)
    assert _FakeSmtp.calls == [
        ("starttls",),
        ("login", "sender", "smtp-secret"),
        ("send", "no-reply@example.com", "to@example.com", "제목", "본문\n"),
        ("quit",),
    ]


def test_deliver_skips_login_without_user(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_FROM", "no-reply@example.com")
    _FakeSmtp.calls, _FakeSmtp.instances = [], []
    monkeypatch.setattr(mail.smtplib, "SMTP", _FakeSmtp)
    mail.send_mail("to@example.com", "s", "b")
    assert [call[0] for call in _FakeSmtp.calls] == ["starttls", "send", "quit"]


def test_send_mail_without_host_raises() -> None:
    assert mail.is_configured() is False
    with pytest.raises(mail.MailUnavailable):
        mail.send_mail("to@example.com", "s", "b")
