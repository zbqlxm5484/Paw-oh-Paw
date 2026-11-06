"""회원 탈퇴와 알림 설정(명세 13.7, 15.4 DELETE /auth/me·PATCH /auth/me, 17.2 BE-26, S15P31A404-192)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dates import today_local
from app.models import Dog, Institution, Staff
from tests.conftest import GOOD_PASSWORD, bearer, password_hash_for

ME = "/api/v1/auth/me"
LOGIN = "/api/v1/auth/login"
ADMIN = "/api/v1/admin"


def _colleague(db: Session, staff: Staff, login_id: str = "second01", *, role: str = "CLIENT", active: bool = True):
    row = Staff(
        institution_id=staff.institution_id,
        login_id=login_id,
        password_hash=password_hash_for(GOOD_PASSWORD),
        name="동료",
        role=role,
        is_active=active,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


def _withdraw(client: TestClient, headers: dict[str, str], password: str = GOOD_PASSWORD):
    return client.request("DELETE", ME, json={"password": password}, headers=headers)


def test_withdraw_stops_the_account_and_keeps_the_data(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    _colleague(db, staff)
    response = _withdraw(client, auth_headers)
    assert response.status_code == 204, response.text
    assert response.content == b""

    db.refresh(staff)
    assert staff.is_active is False
    assert datetime.now(UTC) - timedelta(minutes=1) <= staff.withdrawn_at <= datetime.now(UTC) + timedelta(minutes=1)
    # 지우지 않고 중지한다: 행도, 기관의 자료도 그대로다
    assert db.get(Dog, dog.id) is not None
    # 받은 토큰도, 다시 로그인도 막힌다(중지한 계정과 같은 403)
    again = client.get(ME, headers=auth_headers)
    assert again.status_code == 403 and again.json()["error"]["code"] == "ACCOUNT_DISABLED"
    login = client.post(LOGIN, json={"login_id": staff.login_id, "password": GOOD_PASSWORD})
    assert login.status_code == 403 and login.json()["error"]["code"] == "ACCOUNT_DISABLED"


def test_a_wrong_password_changes_nothing(client: TestClient, db: Session, staff, auth_headers) -> None:
    _colleague(db, staff)
    response = _withdraw(client, auth_headers, password="wrong-password")
    assert response.status_code == 400 and response.json()["error"]["code"] == "PASSWORD_MISMATCH"
    db.refresh(staff)
    assert (staff.is_active, staff.withdrawn_at) == (True, None)
    assert client.request("DELETE", ME, json={}, headers=auth_headers).status_code == 422
    assert client.request("DELETE", ME, json={"password": GOOD_PASSWORD}).status_code == 401


def test_the_last_active_account_cannot_withdraw(
    client: TestClient, db: Session, staff, auth_headers, other_staff
) -> None:
    """기관이 통째로 잠기지 않게 막는다. 중지한 동료와 다른 기관의 계정은 세지 않는다."""
    _colleague(db, staff, "stopped01", active=False)
    response = _withdraw(client, auth_headers)
    assert response.status_code == 409 and response.json()["error"]["code"] == "LAST_ACCOUNT"
    db.refresh(staff)
    assert (staff.is_active, staff.withdrawn_at) == (True, None)

    second = _colleague(db, staff, "second01")
    assert _withdraw(client, auth_headers).status_code == 204
    # 이제 남은 한 명이 마지막이다
    last = _withdraw(client, bearer(second))
    assert last.status_code == 409 and last.json()["error"]["code"] == "LAST_ACCOUNT"


def test_a_guest_can_still_withdraw(client: TestClient, db: Session, staff, auth_headers) -> None:
    """계약이 끝난 기관의 담당자(GUEST)도 탈퇴할 수 있다."""
    _colleague(db, staff)
    db.get(Institution, staff.institution_id).contract_ends_at = today_local() - timedelta(days=1)
    db.flush()
    assert _withdraw(client, auth_headers).status_code == 204


def test_admin_can_bring_a_withdrawn_account_back(client: TestClient, db: Session, staff, auth_headers) -> None:
    _colleague(db, staff)
    boss = _colleague(db, staff, "boss01", role="ADMIN")
    assert _withdraw(client, auth_headers).status_code == 204
    listed = client.get(f"{ADMIN}/institutions/{staff.institution_id}/staff", headers=bearer(boss)).json()["items"]
    mine = next(item for item in listed if item["id"] == str(staff.id))
    assert mine["is_active"] is False and mine["withdrawn_at"] is not None

    back = client.patch(f"{ADMIN}/staff/{staff.id}", json={"is_active": True}, headers=bearer(boss))
    assert back.status_code == 200, back.text
    assert (back.json()["is_active"], back.json()["withdrawn_at"]) == (True, None)
    assert client.post(LOGIN, json={"login_id": staff.login_id, "password": GOOD_PASSWORD}).status_code == 200


def test_notif_on_is_saved_and_returned(client: TestClient, db: Session, staff, auth_headers) -> None:
    assert client.get(ME, headers=auth_headers).json()["notif_on"] is True  # 기본은 켜짐

    off = client.patch(ME, json={"notif_on": False}, headers=auth_headers)
    assert off.status_code == 200, off.text
    assert off.json()["notif_on"] is False
    assert client.get(ME, headers=auth_headers).json()["notif_on"] is False
    assert db.scalar(select(Staff.notif_on).where(Staff.id == staff.id)) is False
    # 다른 필드만 보내면 그대로다
    renamed = client.patch(ME, json={"name": "새 이름"}, headers=auth_headers)
    assert (renamed.json()["name"], renamed.json()["notif_on"]) == ("새 이름", False)
    # 로그인 응답의 staff에도 들어 있다
    login = client.post(LOGIN, json={"login_id": staff.login_id, "password": GOOD_PASSWORD})
    assert login.json()["staff"]["notif_on"] is False


def test_notif_on_is_per_account(client: TestClient, db: Session, staff, auth_headers) -> None:
    second = _colleague(db, staff)
    assert client.patch(ME, json={"notif_on": False}, headers=auth_headers).status_code == 200
    assert client.get(ME, headers=bearer(second)).json()["notif_on"] is True


@pytest.mark.parametrize("value", [None, "가끔", 3])
def test_notif_on_must_be_a_boolean(client: TestClient, auth_headers, value: object) -> None:
    response = client.patch(ME, json={"notif_on": value}, headers=auth_headers)
    assert response.status_code == 422, response.text
    assert [item["field"] for item in response.json()["error"]["detail"]["fields"]] == ["notif_on"]
