"""인증·기관 분리(11.6, 13.4, 15.4, 17.1·17.2 BE-01)와 get_db(11.7)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.core.security import create_access_token, make_signed_url, verify_signed_url
from app.models import Institution
from tests.conftest import GOOD_PASSWORD, bearer

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"


def _login(client: TestClient, **overrides: str):
    body = {"institution_code": "T01", "login_id": "staff1", "password": GOOD_PASSWORD}
    body.update(overrides)
    return client.post(LOGIN, json=body)


# ---- 로그인 (BE-01) ----


def test_login_returns_token_and_staff(client: TestClient, staff) -> None:
    response = _login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["staff"] == {
        "id": str(staff.id),
        "login_id": "staff1",
        "name": "담당자",
        "role": "STAFF",
        "institution": {"id": str(staff.institution_id), "code": "T01", "name": "테스트 병원"},
    }
    # 만료 시각은 UTC·초 단위·Z, 지금부터 JWT_EXPIRE_HOURS 뒤
    assert body["expires_at"].endswith("Z")
    expires_at = datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00"))
    expected = datetime.now(UTC) + timedelta(hours=get_settings().JWT_EXPIRE_HOURS)
    assert abs((expires_at - expected).total_seconds()) < 60


def test_token_from_login_works_on_me(client: TestClient, staff) -> None:
    token = _login(client).json()["access_token"]
    response = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["login_id"] == "staff1"


@pytest.mark.parametrize(
    "overrides",
    [
        {"institution_code": "NOPE"},
        {"login_id": "nobody"},
        {"password": "wrong-pass"},
        {"institution_code": "t01"},  # 대소문자 구분(13.4)
        {"login_id": "STAFF1"},
    ],
)
def test_any_wrong_field_is_401_login_failed_with_identical_body(client: TestClient, staff, overrides: dict) -> None:
    wrong = _login(client, **overrides)
    assert wrong.status_code == 401
    assert wrong.json() == {
        "error": {"code": "LOGIN_FAILED", "message": wrong.json()["error"]["message"], "detail": None}
    }
    # 아이디가 없을 때와 비밀번호가 틀렸을 때의 본문이 같다
    assert wrong.json() == _login(client, password="another-wrong").json()


def test_password_over_72_bytes_is_401_not_500(client: TestClient, staff) -> None:
    response = _login(client, password="가" * 25)  # 75바이트
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "LOGIN_FAILED"


def test_inactive_account_cannot_login_or_use_token(client: TestClient, db: Session, staff) -> None:
    headers = bearer(staff)
    staff.is_active = False
    db.flush()

    login = _login(client)
    assert login.status_code == 403
    assert login.json()["error"]["code"] == "ACCOUNT_DISABLED"

    me = client.get(ME, headers=headers)
    assert me.status_code == 403
    assert me.json()["error"]["code"] == "ACCOUNT_DISABLED"


def test_wrong_password_on_inactive_account_is_still_login_failed(client: TestClient, db: Session, staff) -> None:
    staff.is_active = False
    db.flush()
    response = _login(client, password="wrong-pass")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "LOGIN_FAILED"


def test_login_input_rules_are_422(client: TestClient, staff) -> None:
    response = _login(client, institution_code="C" * 21)
    assert response.status_code == 422
    assert response.json()["error"]["detail"]["fields"] == [{"field": "institution_code", "type": "string_too_long"}]


# ---- 토큰 확인 (17.1 공통) ----


def test_me_returns_staff_out(client: TestClient, staff, auth_headers: dict) -> None:
    response = client.get(ME, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["institution"]["code"] == "T01"


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer "},
        {"Authorization": "Basic abc"},
        {"Authorization": "Bearer not-a-jwt"},
    ],
)
def test_missing_or_bad_token_is_401_auth_required(client: TestClient, staff, headers: dict) -> None:
    response = client.get(ME, headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_expired_token_is_401_auth_expired(client: TestClient, staff) -> None:
    hours = get_settings().JWT_EXPIRE_HOURS
    token, _ = create_access_token(
        staff_id=staff.id,
        institution_id=staff.institution_id,
        role=staff.role,
        now=datetime.now(UTC) - timedelta(hours=hours + 1),
    )
    response = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_EXPIRED"


def test_token_of_deleted_staff_is_401(client: TestClient, staff) -> None:
    token, _ = create_access_token(staff_id=uuid.uuid4(), institution_id=staff.institution_id, role="STAFF")
    response = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_token_signed_with_other_secret_is_rejected(client: TestClient, staff, monkeypatch: pytest.MonkeyPatch) -> None:
    import jwt

    token = jwt.encode(
        {"sub": str(staff.id), "inst": str(staff.institution_id), "role": "STAFF", "exp": 4102444800},
        "another-secret-that-is-long-enough-000",
        algorithm="HS256",
    )
    response = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_admin_only_dependency(client: TestClient, db: Session, staff, auth_headers: dict) -> None:
    forbidden = client.get("/api/v1/_test/admin-only", headers=auth_headers)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    staff.role = "ADMIN"
    db.flush()
    allowed = client.get("/api/v1/_test/admin-only", headers=bearer(staff))
    assert allowed.status_code == 200


# ---- 서명 URL (11.6) ----

VECTOR_SECRET = "example-file-url-secret-000000000000"
VECTOR_PATH = "/api/v1/shots/3f2a9c1e-5b7d-4e8a-9c21-7d4e5f6a8b90/video"
VECTOR_EXP = 1792455600
VECTOR_SIG = "71dc0ee5f533d3459657e501b062aefcaec8867af045a52eaab5b75bb3c98b95"


@pytest.fixture
def vector_secret(monkeypatch: pytest.MonkeyPatch):
    """11.6의 예시 값으로 FILE_URL_SECRET을 바꾼다."""
    monkeypatch.setenv("FILE_URL_SECRET", VECTOR_SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_signed_url_matches_spec_vector(vector_secret: None) -> None:
    ttl = get_settings().FILE_URL_TTL_SEC
    now = datetime.fromtimestamp(VECTOR_EXP - ttl, tz=UTC)
    url, expires_at = make_signed_url(VECTOR_PATH, now=now)
    assert url == f"{VECTOR_PATH}?exp={VECTOR_EXP}&sig={VECTOR_SIG}"
    assert expires_at == datetime.fromtimestamp(VECTOR_EXP, tz=UTC)


def test_verify_signed_url(vector_secret: None) -> None:
    before = datetime.fromtimestamp(VECTOR_EXP - 10, tz=UTC)
    after = datetime.fromtimestamp(VECTOR_EXP + 1, tz=UTC)
    assert verify_signed_url(VECTOR_PATH, VECTOR_EXP, VECTOR_SIG, now=before)
    assert not verify_signed_url(VECTOR_PATH, VECTOR_EXP, VECTOR_SIG, now=after)  # 만료
    assert not verify_signed_url(VECTOR_PATH, VECTOR_EXP, VECTOR_SIG[:-1] + "0", now=before)  # 변조된 서명
    assert not verify_signed_url(VECTOR_PATH + "x", VECTOR_EXP, VECTOR_SIG, now=before)  # 다른 경로
    assert not verify_signed_url(VECTOR_PATH, VECTOR_EXP + 1, VECTOR_SIG, now=before)  # 다른 만료 시각


# ---- get_db (11.7) ----


def test_get_db_commits_on_success_and_rolls_back_on_error(engine: Engine, clean_tables: None) -> None:
    ok = get_db()
    session = next(ok)
    session.add(Institution(code="COMMIT", name="저장됨"))
    with pytest.raises(StopIteration):
        next(ok)  # 정상 종료 → commit

    failing = get_db()
    session = next(failing)
    session.add(Institution(code="ROLLBACK", name="되돌림"))
    session.flush()
    with pytest.raises(RuntimeError):
        failing.throw(RuntimeError("요청 처리 중 오류"))  # 예외 → rollback

    with Session(engine) as check:
        codes = set(check.scalars(select(Institution.code)).all())
    assert codes == {"COMMIT"}
