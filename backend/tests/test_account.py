"""비밀번호 변경·내 정보 수정(13.7, 15.4 PATCH /auth/password·/auth/me, 17.2 BE-26)."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.dates import today_local
from tests.conftest import GOOD_PASSWORD

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
PASSWORD = "/api/v1/auth/password"
NEW_PASSWORD = "new-pass-5678"


def _login(client: TestClient, password: str):
    return client.post(LOGIN, json={"login_id": "staff1", "password": password})


def test_change_password(client: TestClient, staff, auth_headers: dict) -> None:
    wrong = client.patch(
        PASSWORD, json={"current_password": "wrong-pass", "new_password": NEW_PASSWORD}, headers=auth_headers
    )
    assert wrong.status_code == 400
    assert wrong.json()["error"]["code"] == "PASSWORD_MISMATCH"

    same = client.patch(
        PASSWORD, json={"current_password": GOOD_PASSWORD, "new_password": GOOD_PASSWORD}, headers=auth_headers
    )
    assert same.status_code == 422
    assert [item["field"] for item in same.json()["error"]["detail"]["fields"]] == ["new_password"]

    short = client.patch(
        PASSWORD, json={"current_password": GOOD_PASSWORD, "new_password": "short7!"}, headers=auth_headers
    )
    assert short.status_code == 422
    assert [item["field"] for item in short.json()["error"]["detail"]["fields"]] == ["new_password"]

    changed = client.patch(
        PASSWORD, json={"current_password": GOOD_PASSWORD, "new_password": NEW_PASSWORD}, headers=auth_headers
    )
    assert changed.status_code == 200
    assert changed.json()["id"] == str(staff.id)
    assert _login(client, GOOD_PASSWORD).status_code == 401
    assert _login(client, NEW_PASSWORD).status_code == 200
    # 이미 받은 토큰은 그대로 쓴다(토큰 무효화는 없다, 15.4)
    assert client.get(ME, headers=auth_headers).status_code == 200


def test_update_me(client: TestClient, staff, auth_headers: dict) -> None:
    email = client.patch(ME, json={"email": " New@Example.com "}, headers=auth_headers)
    assert email.status_code == 200
    assert email.json()["email"] == "new@example.com"
    assert client.get(ME, headers=auth_headers).json()["email"] == "new@example.com"

    name = client.patch(ME, json={"name": " 새 이름 "}, headers=auth_headers)
    assert name.status_code == 200
    assert (name.json()["name"], name.json()["email"]) == ("새 이름", "new@example.com")

    nothing = client.patch(ME, json={}, headers=auth_headers)
    assert nothing.status_code == 200
    assert nothing.json()["name"] == "새 이름"


@pytest.mark.parametrize(
    ("body", "field"),
    [({"email": None}, "email"), ({"email": "bad"}, "email"), ({"name": "   "}, "name"), ({"name": None}, "name")],
)
def test_update_me_rules_are_422(client: TestClient, staff, auth_headers: dict, body: dict, field: str) -> None:
    response = client.patch(ME, json=body, headers=auth_headers)
    assert response.status_code == 422
    assert [item["field"] for item in response.json()["error"]["detail"]["fields"]] == [field]


def test_guest_cannot_change_password_or_me(client: TestClient, db: Session, staff, auth_headers: dict) -> None:
    staff.institution.contract_ends_at = today_local() - timedelta(days=1)
    db.flush()
    for url, body in (
        (PASSWORD, {"current_password": GOOD_PASSWORD, "new_password": NEW_PASSWORD}),
        (ME, {"name": "x"}),
    ):
        response = client.patch(url, json=body, headers=auth_headers)
        assert response.status_code == 403, url
        assert response.json()["error"]["code"] == "CONTRACT_EXPIRED"
    assert client.get(ME, headers=auth_headers).status_code == 200
