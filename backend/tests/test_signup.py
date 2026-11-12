"""디바이스 코드 확인·회원가입(11.6, 12.5, 13.5, 15.4 verify·signup, 17.2 BE-22)."""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.dates import today_local
from app.models import DeviceCode, Staff
from app.services import signup as signup_service
from app.services.device_codes import CODE_ALPHABET, format_code, generate_code, normalize_code
from tests.conftest import GOOD_PASSWORD

VERIFY = "/api/v1/auth/device-codes/verify"
SIGNUP = "/api/v1/auth/signup"
ME = "/api/v1/auth/me"
CODE = "ABCDEFGHJKMNPQRSTUVW"  # 20자, 모두 코드 글자
PRETTY = "ABCDE-FGHJK-MNPQR-STUVW"
TERMS = {"version": "2026-11-01", "service": True, "privacy": True, "device_location": True}
MISSING = object()  # _signup에 이 값을 주면 그 키를 빼고 보낸다
UNKNOWN = "ZZZZZ-ZZZZZ-ZZZZZ-ZZZZZ"


@pytest.fixture
def device_code(db: Session, staff) -> DeviceCode:
    """staff 기관(T01, 계약 기한 없음)의 코드."""
    row = DeviceCode(institution_id=staff.institution_id, code=CODE, note="1호기")
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
        "terms": TERMS,
    }
    body.update(overrides)
    return client.post(SIGNUP, json={key: value for key, value in body.items() if value is not MISSING})


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


def test_verify_returns_the_institution_only(client: TestClient, device_code: DeviceCode) -> None:
    response = client.post(VERIFY, json={"code": " abcde-fghjk mnpqr-STUVW"})
    assert response.status_code == 200
    # 남은 자리 수는 없다(v1.32: 계정 수 상한 삭제)
    assert response.json() == {"institution": {"id": str(device_code.institution_id), "name": "테스트 병원"}}


def test_contract_ending_today_is_still_usable(client: TestClient, db: Session, device_code: DeviceCode) -> None:
    device_code.institution.contract_ends_at = today_local()
    db.flush()
    assert client.post(VERIFY, json={"code": PRETTY}).status_code == 200


UNUSABLE_CASES = ["unknown", "revoked", "expired", "nineteen_chars", "letter_o"]


def _unusable_code(db: Session, device_code: DeviceCode, case: str) -> str:
    """쓸 수 없는 코드의 다섯 경우를 만들고, 요청에 넣을 코드 글자를 돌려준다."""
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
    return code


@pytest.mark.parametrize("case", UNUSABLE_CASES)
def test_unusable_codes_are_404_with_identical_body(
    client: TestClient, db: Session, device_code: DeviceCode, case: str
) -> None:
    """없음·회수됨·기관 계약 만료·형식 오류는 모두 404 DEVICE_CODE_INVALID이고 본문이 같다. 가입도 같은 답이다."""
    code = _unusable_code(db, device_code, case)

    verify = client.post(VERIFY, json={"code": code})
    assert verify.status_code == 404
    assert verify.json()["error"]["code"] == "DEVICE_CODE_INVALID"
    assert verify.json() == client.post(VERIFY, json={"code": UNKNOWN}).json()

    signup = _signup(client, code=code)
    assert signup.status_code == 404
    assert signup.json() == verify.json()
    assert _count(db, "kim01") == 0


@pytest.mark.parametrize("case", UNUSABLE_CASES)
def test_unusable_code_is_refused_before_bcrypt(
    client: TestClient, db: Session, device_code: DeviceCode, case: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """v1.48(15.4): 쓸 수 없는 코드로 온 가입 요청은 비밀번호 해시를 계산하지 않는다(서버 CPU를 쓰게 하지 못한다)."""
    code = _unusable_code(db, device_code, case)
    hashed: list[str] = []
    monkeypatch.setattr(signup_service, "hash_password", lambda password: hashed.append(password) or "x" * 60)

    response = _signup(client, code=code)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DEVICE_CODE_INVALID"
    assert hashed == []


def test_usable_code_is_hashed_once_and_checked_again_after_the_hash(
    client: TestClient, db: Session, device_code: DeviceCode, monkeypatch: pytest.MonkeyPatch
) -> None:
    """해시를 계산하는 사이에 회수된 코드로는 가입되지 않는다(해시 뒤에 코드를 다시 확인한다, 15.4)."""
    real_hash = signup_service.hash_password
    code_id = device_code.id
    hashed: list[str] = []

    def hash_then_revoke(password: str) -> str:
        hashed.append(password)
        db.execute(update(DeviceCode).where(DeviceCode.id == code_id).values(revoked_at=datetime.now(UTC)))
        return real_hash(password)

    monkeypatch.setattr(signup_service, "hash_password", hash_then_revoke)
    db.expunge_all()  # 실제 요청처럼 코드 행이 세션에 올라 있지 않게 한다(올라 있으면 먼저 읽은 값을 본다)
    response = _signup(client)
    assert response.status_code == 404
    assert hashed == [GOOD_PASSWORD]
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
    body = {"code": PRETTY, "login_id": "kim01", "password": GOOD_PASSWORD, "name": "김담당", "terms": TERMS}
    response = client.post(SIGNUP, json=body)
    assert response.status_code == 422
    assert response.json()["error"]["detail"]["fields"] == [{"field": "email", "type": "missing"}]


def test_input_rules_are_checked_before_the_code(client: TestClient, device_code: DeviceCode) -> None:
    """15.4 순서: 입력 규칙(422) → 코드 검사(404)."""
    response = _signup(client, code=UNKNOWN, password="short")
    assert response.status_code == 422


def test_one_code_has_no_account_limit(client: TestClient, db: Session, device_code: DeviceCode) -> None:
    """v1.32: 코드 하나로 몇 명이든 가입된다. 예전 기본 상한 3을 넘겨 본다."""
    for number in range(1, 6):
        response = _signup(client, login_id=f"kim0{number}", email=f"k{number}@x.kr")
        assert response.status_code == 201, response.text
    joined = db.scalar(select(func.count()).select_from(Staff).where(Staff.device_code_id == device_code.id))
    assert joined == 5
    assert client.post(VERIFY, json={"code": PRETTY}).status_code == 200


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


# ---- 약관 동의 기록 (13.5, 15.4) ----


def test_signup_records_the_agreed_terms(client: TestClient, db: Session, device_code: DeviceCode) -> None:
    before = datetime.now(UTC) - timedelta(minutes=1)
    response = _signup(client, terms={**TERMS, "version": " 2026-11-01 ", "marketing": True})
    assert response.status_code == 201, response.text
    assert "terms" not in response.json()["staff"]  # 응답 모양은 그대로다
    row = db.scalars(select(Staff).where(Staff.login_id == "kim01")).one()
    assert (row.terms_version, row.marketing_agreed) == ("2026-11-01", True)
    assert before <= row.terms_agreed_at <= datetime.now(UTC) + timedelta(minutes=1)


def test_marketing_is_optional_and_defaults_to_false(client: TestClient, db: Session, device_code: DeviceCode) -> None:
    assert _signup(client, terms=TERMS).status_code == 201
    row = db.scalars(select(Staff).where(Staff.login_id == "kim01")).one()
    assert (row.terms_version, row.marketing_agreed) == ("2026-11-01", False)
    assert row.terms_agreed_at is not None


@pytest.mark.parametrize("terms", [MISSING, None])
def test_signup_without_terms_is_422_and_nothing_is_created(
    client: TestClient, db: Session, device_code: DeviceCode, terms: object
) -> None:
    """약관 동의는 필수다(15.4, v1.58). 키가 없거나 null이면 가입시키지 않는다. 웹과 앱은 11-06부터 보낸다."""
    response = _signup(client, terms=terms)
    assert response.status_code == 422, response.text
    assert [item["field"] for item in response.json()["error"]["detail"]["fields"]] == ["terms"]
    assert _count(db, "kim01") == 0


@pytest.mark.parametrize(
    ("terms", "field"),
    [
        ({**TERMS, "service": False}, "terms.service"),
        ({**TERMS, "privacy": False}, "terms.privacy"),
        ({**TERMS, "device_location": False}, "terms.device_location"),
        ({"version": "2026-11-01", "service": True, "privacy": True}, "terms.device_location"),  # 빠짐
        ({**TERMS, "version": "  "}, "terms.version"),
        ({**TERMS, "version": "v" * 21}, "terms.version"),
        ({"service": True, "privacy": True, "device_location": True}, "terms.version"),
        ({**TERMS, "marketing": "아마도"}, "terms.marketing"),
    ],
)
def test_terms_rules_are_422_and_nothing_is_created(
    client: TestClient, db: Session, device_code: DeviceCode, terms: dict, field: str
) -> None:
    response = _signup(client, terms=terms)
    assert response.status_code == 422, response.text
    assert [item["field"] for item in response.json()["error"]["detail"]["fields"]] == [field]
    assert _count(db, "kim01") == 0
