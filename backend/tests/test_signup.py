"""디바이스 코드 확인·회원가입(11.6, 12.5, 13.5, 15.4 verify·signup, 17.2 BE-22)."""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dates import today_local
from app.models import DeviceCode, Staff
from app.services.device_codes import CODE_ALPHABET, format_code, generate_code, normalize_code
from tests.conftest import GOOD_PASSWORD

VERIFY = "/api/v1/auth/device-codes/verify"
SIGNUP = "/api/v1/auth/signup"
ME = "/api/v1/auth/me"
CODE = "ABCDEFGHJKMNPQRSTUVW"  # 20자, 모두 코드 글자
PRETTY = "ABCDE-FGHJK-MNPQR-STUVW"
UNKNOWN = "ZZZZZ-ZZZZZ-ZZZZZ-ZZZZZ"


@pytest.fixture
def device_code(db: Session, staff) -> DeviceCode:
    """staff 기관(T01, 계약 기한 없음)의 코드. 계정 2개까지."""
    row = DeviceCode(institution_id=staff.institution_id, code=CODE, max_accounts=2, note="1호기")
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


def _signup(client: TestClient, **overrides: object):
    body: dict[str, object] = {
        "code": PRETTY,
        "login_id": "kim01",
        "password": GOOD_PASSWORD,
        "name": "김담당",
        "email": "Kim01@Example.com",
    }
    body.update(overrides)
    return client.post(SIGNUP, json=body)


def _count(db: Session, login_id: str) -> int:
    return db.scalar(select(func.count()).select_from(Staff).where(Staff.login_id == login_id)) or 0


# ---- 코드 글자·정리 (13.5) ----


@pytest.mark.parametrize("raw", [PRETTY, " abcde fghjk-mnpqr-stuvw ", CODE.lower(), CODE])
def test_normalize_accepts_hyphen_space_and_lowercase(raw: str) -> None:
    assert normalize_code(raw) == CODE


@pytest.mark.parametrize(
    "raw",
    [CODE[:-1], CODE + "A", CODE[:-1] + "0", CODE[:-1] + "O", CODE[:-1] + "I", CODE[:-1] + "L", CODE[:-1] + "1", ""],
)
def test_normalize_rejects_wrong_length_and_confusable_letters(raw: str) -> None:
    assert normalize_code(raw) is None


def test_format_and_generate() -> None:
    assert format_code(CODE) == PRETTY
    first, second = generate_code(), generate_code()
    assert len(first) == 20
    assert set(first) <= set(CODE_ALPHABET)
    assert first != second
    assert normalize_code(format_code(first)) == first


# ---- 코드 확인 (BE-22) ----


def test_verify_returns_institution_and_remaining(client: TestClient, device_code: DeviceCode) -> None:
    response = client.post(VERIFY, json={"code": " abcde-fghjk mnpqr-STUVW"})
    assert response.status_code == 200
    assert response.json() == {
        "institution": {"id": str(device_code.institution_id), "name": "테스트 병원"},
        "remaining_accounts": 2,
    }


def test_verify_counts_only_active_accounts(client: TestClient, db: Session, device_code: DeviceCode, staff) -> None:
    staff.device_code_id = device_code.id
    db.flush()
    assert client.post(VERIFY, json={"code": PRETTY}).json()["remaining_accounts"] == 1
    staff.is_active = False
    db.flush()
    assert client.post(VERIFY, json={"code": PRETTY}).json()["remaining_accounts"] == 2


def test_contract_ending_today_is_still_usable(client: TestClient, db: Session, device_code: DeviceCode) -> None:
    device_code.institution.contract_ends_at = today_local()
    db.flush()
    assert client.post(VERIFY, json={"code": PRETTY}).status_code == 200


@pytest.mark.parametrize("case", ["unknown", "revoked", "expired", "nineteen_chars", "letter_o"])
def test_unusable_codes_are_404_with_identical_body(
    client: TestClient, db: Session, device_code: DeviceCode, case: str
) -> None:
    """없음·회수됨·기관 계약 만료·형식 오류는 모두 404 DEVICE_CODE_INVALID이고 본문이 같다. 가입도 같은 답이다."""
    code = PRETTY
    if case == "unknown":
        code = UNKNOWN
    elif case == "revoked":
        device_code.revoked_at = datetime.now(UTC)
    elif case == "expired":
        device_code.institution.contract_ends_at = today_local() - timedelta(days=1)
    elif case == "nineteen_chars":
        code = PRETTY[:-1]
    elif case == "letter_o":
        code = PRETTY[:-1] + "O"
    db.flush()

    verify = client.post(VERIFY, json={"code": code})
    assert verify.status_code == 404
    assert verify.json()["error"]["code"] == "DEVICE_CODE_INVALID"
    assert verify.json() == client.post(VERIFY, json={"code": UNKNOWN}).json()

    signup = _signup(client, code=code)
    assert signup.status_code == 404
    assert signup.json() == verify.json()
    assert _count(db, "kim01") == 0


# ---- 가입 (BE-22) ----


def test_signup_creates_client_and_logs_in(client: TestClient, db: Session, device_code: DeviceCode, staff) -> None:
    response = _signup(client)
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    out = body["staff"]
    assert (out["login_id"], out["name"], out["email"]) == ("kim01", "김담당", "kim01@example.com")
    assert (out["role"], out["effective_role"]) == ("CLIENT", "CLIENT")
    assert out["institution"]["id"] == str(staff.institution_id)
    row = db.scalars(select(Staff).where(Staff.login_id == "kim01")).one()
    assert row.device_code_id == device_code.id
    assert row.password_hash.startswith("$2b$")
    # 응답의 토큰으로 바로 /auth/me를 부를 수 있다
    me = client.get(ME, headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["id"] == out["id"]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"email": None}, "email"),
        ({"email": "no-at-sign"}, "email"),
        ({"email": "a@b"}, "email"),
        ({"email": "a@@b.kr"}, "email"),
        ({"login_id": "Kim01"}, "login_id"),  # 대문자는 422(13.5)
        ({"login_id": "abc"}, "login_id"),
        ({"login_id": "kim 01"}, "login_id"),
        ({"password": "short7!"}, "password"),
        ({"password": "가" * 25}, "password"),  # 75바이트
        ({"name": "   "}, "name"),
        ({"name": "이" * 51}, "name"),
    ],
)
def test_signup_input_rules_are_422(client: TestClient, device_code: DeviceCode, overrides: dict, field: str) -> None:
    response = _signup(client, **overrides)
    assert response.status_code == 422
    assert [item["field"] for item in response.json()["error"]["detail"]["fields"]] == [field]


def test_signup_without_email_is_422(client: TestClient, device_code: DeviceCode) -> None:
    body = {"code": PRETTY, "login_id": "kim01", "password": GOOD_PASSWORD, "name": "김담당"}
    response = client.post(SIGNUP, json=body)
    assert response.status_code == 422
    assert response.json()["error"]["detail"]["fields"] == [{"field": "email", "type": "missing"}]


def test_input_rules_are_checked_before_the_code(client: TestClient, device_code: DeviceCode) -> None:
    """15.4 순서: 입력 규칙(422) → 코드 검사(404)."""
    response = _signup(client, code=UNKNOWN, password="short")
    assert response.status_code == 422


def test_code_cap_counts_active_accounts_only(client: TestClient, db: Session, device_code: DeviceCode) -> None:
    assert _signup(client, login_id="kim01", email="a@x.kr").status_code == 201
    assert _signup(client, login_id="kim02", email="b@x.kr").status_code == 201
    third = _signup(client, login_id="kim03", email="c@x.kr")
    assert third.status_code == 409
    assert third.json()["error"]["code"] == "DEVICE_CODE_FULL"
    verify = client.post(VERIFY, json={"code": PRETTY})
    assert verify.status_code == 409
    assert verify.json()["error"]["code"] == "DEVICE_CODE_FULL"
    assert _count(db, "kim03") == 0

    # 계정 하나를 중지하면 자리가 돌아와 다시 가입된다(12.5)
    first = db.scalars(select(Staff).where(Staff.login_id == "kim01")).one()
    first.is_active = False
    db.flush()
    assert client.post(VERIFY, json={"code": PRETTY}).json()["remaining_accounts"] == 1
    assert _signup(client, login_id="kim03", email="c@x.kr").status_code == 201


def test_login_id_taken_in_any_institution(
    client: TestClient, db: Session, device_code: DeviceCode, other_staff
) -> None:
    """다른 기관의 아이디와 겹쳐도 409 LOGIN_ID_TAKEN(아이디는 전역 유일, 12.2)."""
    response = _signup(client, login_id="staff2")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LOGIN_ID_TAKEN"
    assert _count(db, "staff2") == 1


def test_logs_do_not_contain_code_or_email(client: TestClient, device_code: DeviceCode, caplog) -> None:
    """11.8: 디바이스 코드·이메일은 로그에 남지 않는다(실패한 요청도)."""
    with caplog.at_level(logging.DEBUG):
        assert _signup(client, code=UNKNOWN, email="secret@example.com").status_code == 404
        assert _signup(client).status_code == 201
    assert "ZZZZZ" not in caplog.text
    assert "secret@example.com" not in caplog.text
    assert "kim01@example.com" not in caplog.text
    assert CODE not in caplog.text
