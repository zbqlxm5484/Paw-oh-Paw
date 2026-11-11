"""비밀번호를 바꾸면 그전에 받은 토큰을 끊는다(v1.48).

명세 11.6 요청마다 하는 검사, 12.5 비밀번호를 바꾼 시각, 15.4, 17.2 BE-26.
재설정으로 바꿨을 때는 tests/test_password_reset.py, 인증 캐시와 함께는 tests/test_auth_cache.py에 있다.
"""

import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, decode_access_token
from tests.conftest import GOOD_PASSWORD

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
DOGS = "/api/v1/dogs"
PASSWORD = "/api/v1/auth/password"
NEW_PASSWORD = "new-pass-5678"


def _login_headers(client: TestClient, password: str) -> dict[str, str]:
    response = client.post(LOGIN, json={"login_id": "staff1", "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _headers_issued_at(staff, at: datetime) -> dict[str, str]:
    token, _ = create_access_token(staff_id=staff.id, institution_id=staff.institution_id, role=staff.role, now=at)
    return {"Authorization": f"Bearer {token}"}


def _assert_cut(client: TestClient, headers: dict[str, str]) -> None:
    for url in (ME, DOGS):
        response = client.get(url, headers=headers)
        assert response.status_code == 401, url
        assert response.json()["error"]["code"] == "AUTH_EXPIRED"


def test_password_change_cuts_every_token_issued_before(client: TestClient, db: Session, staff) -> None:
    other_device = _login_headers(client, GOOD_PASSWORD)
    this_device = _login_headers(client, GOOD_PASSWORD)
    assert staff.password_changed_at is None
    staff_out_fields = set(client.get(ME, headers=other_device).json())

    before = datetime.now(UTC)
    changed = client.patch(
        PASSWORD, json={"current_password": GOOD_PASSWORD, "new_password": NEW_PASSWORD}, headers=this_device
    )
    assert changed.status_code == 200
    # 응답 모양은 그대로다(StaffOut). 새 토큰을 주지 않는다
    assert set(changed.json()) == staff_out_fields
    assert "access_token" not in changed.json()
    assert before <= staff.password_changed_at <= datetime.now(UTC)

    # 다른 기기의 토큰도, 바꾼 요청에 쓴 토큰도 끊긴다(바꾼 본인도 다시 로그인한다)
    _assert_cut(client, other_device)
    _assert_cut(client, this_device)
    # 새 비밀번호로 받은 토큰은 쓴다
    fresh = _login_headers(client, NEW_PASSWORD)
    assert client.get(ME, headers=fresh).status_code == 200
    assert client.get(DOGS, headers=fresh).status_code == 200


def test_failed_password_change_cuts_nothing(client: TestClient, db: Session, staff) -> None:
    headers = _login_headers(client, GOOD_PASSWORD)
    wrong = client.patch(
        PASSWORD, json={"current_password": "wrong-pass", "new_password": NEW_PASSWORD}, headers=headers
    )
    assert wrong.status_code == 400
    assert staff.password_changed_at is None
    assert client.get(ME, headers=headers).status_code == 200


def test_tokens_are_compared_below_one_second(client: TestClient, db: Session, staff) -> None:
    """같은 초 안에서도 바꾸기 전에 받은 토큰은 끊기고 뒤에 받은 토큰은 쓴다(iat를 소수점 아래까지 적는다, 11.6)."""
    changed_at = (datetime.now(UTC) - timedelta(seconds=5)).replace(microsecond=500_000)
    staff.password_changed_at = changed_at
    db.flush()
    step = timedelta(milliseconds=1)
    _assert_cut(client, _headers_issued_at(staff, changed_at - step))
    assert client.get(ME, headers=_headers_issued_at(staff, changed_at)).status_code == 200
    assert client.get(ME, headers=_headers_issued_at(staff, changed_at + step)).status_code == 200


def test_iat_keeps_microseconds() -> None:
    """토큰의 iat가 마이크로초까지 그대로 돌아온다. 만료 시각은 전처럼 초 단위다(15.4 expires_at)."""
    issued = (datetime.now(UTC) - timedelta(seconds=5)).replace(microsecond=678_901)
    token, expires_at = create_access_token(
        staff_id=uuid.uuid4(), institution_id=uuid.uuid4(), role="CLIENT", now=issued
    )
    assert decode_access_token(token).issued_at == issued
    assert expires_at.microsecond == 0


def test_tokens_from_before_this_version_work_until_the_password_changes(
    client: TestClient, db: Session, staff
) -> None:
    """v1.47까지 나간 토큰(iat가 정수 초)과 iat가 없는 토큰: 비밀번호를 바꾸기 전에는 쓰고, 바꾸면 끊긴다."""
    secret = get_settings().JWT_SECRET.get_secret_value()
    base = {
        "sub": str(staff.id),
        "inst": str(staff.institution_id),
        "role": "CLIENT",
        "exp": int(time.time()) + 3600,
    }
    tokens = [
        jwt.encode({**base, "iat": int(time.time()) - 10}, secret, algorithm="HS256"),
        jwt.encode(base, secret, algorithm="HS256"),
    ]
    for token in tokens:
        assert client.get(ME, headers={"Authorization": f"Bearer {token}"}).status_code == 200

    staff.password_changed_at = datetime.now(UTC)
    db.flush()
    for token in tokens:
        _assert_cut(client, {"Authorization": f"Bearer {token}"})


def test_cut_token_is_401_before_the_account_state_is_told(client: TestClient, db: Session, staff) -> None:
    """끊긴 토큰은 계정이 중지됐는지도 알려 주지 않는다: 403 ACCOUNT_DISABLED가 아니라 401이다."""
    headers = _headers_issued_at(staff, datetime.now(UTC) - timedelta(minutes=1))
    staff.password_changed_at = datetime.now(UTC)
    staff.is_active = False
    db.flush()
    _assert_cut(client, headers)


def test_password_change_is_logged_with_the_id_only(
    client: TestClient, staff, caplog: pytest.LogCaptureFixture
) -> None:
    headers = _login_headers(client, GOOD_PASSWORD)
    with caplog.at_level(logging.DEBUG):
        changed = client.patch(
            PASSWORD, json={"current_password": GOOD_PASSWORD, "new_password": NEW_PASSWORD}, headers=headers
        )
    assert changed.status_code == 200
    assert f"password changed staff={staff.id}" in caplog.text
    for typed in (GOOD_PASSWORD, NEW_PASSWORD, "staff1"):
        assert typed not in caplog.text
