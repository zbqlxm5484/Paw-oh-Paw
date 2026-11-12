"""담당자 스냅샷 캐시(11.6 인증 캐시, 17.2 BE-23 캐시 줄). 다른 테스트는 TTL 0으로 캐시를 끄고 돈다(conftest)."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, update
from sqlalchemy.orm import Session

from app.core import auth_cache as cache_module
from app.core.auth_cache import AuthCache, AuthStaff, auth_cache
from app.core.config import get_settings
from app.core.dates import today_local
from app.models import Staff
from tests.conftest import GOOD_PASSWORD, bearer

WHOAMI = "/api/v1/_test/whoami"
ME = "/api/v1/auth/me"
LOGIN = "/api/v1/auth/login"
PASSWORD = "/api/v1/auth/password"


def _snapshot(**overrides: object) -> AuthStaff:
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "institution_id": uuid.uuid4(),
        "login_id": "kim01",
        "name": "김담당",
        "email": None,
        "role": "CLIENT",
        "is_active": True,
        "institution_code": "INST-1",
        "institution_name": "병원",
        "contract_ends_at": None,
    }
    values.update(overrides)
    return AuthStaff(**values)  # type: ignore[arg-type]


@pytest.fixture
def cache_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """TTL 60초로 캐시를 켠다. 끝나면 비우고 설정도 되돌린다."""
    monkeypatch.setenv("AUTH_CACHE_TTL_SEC", "60")
    get_settings.cache_clear()
    auth_cache.clear()
    yield
    auth_cache.clear()
    get_settings.cache_clear()


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> dict[str, float]:
    """캐시 모듈의 시계를 손으로 돌린다."""
    state = {"t": 1000.0}
    monkeypatch.setattr(cache_module, "_now", lambda: state["t"])
    return state


# ---- AuthStaff 계산값 (11.6) ----


@pytest.mark.parametrize(
    ("role", "days_ago", "status", "effective"),
    [
        ("CLIENT", 1, "EXPIRED", "GUEST"),
        ("CLIENT", 0, "ACTIVE", "CLIENT"),  # 당일은 통과
        ("CLIENT", None, "ACTIVE", "CLIENT"),  # 기한 없음
        ("ADMIN", 1, "EXPIRED", "ADMIN"),  # 크림오프 쪽은 계약을 보지 않는다
        ("STAFF", 1, "EXPIRED", "STAFF"),
    ],
)
def test_effective_role_and_contract_status(role: str, days_ago, status: str, effective: str) -> None:
    ends_at = None if days_ago is None else today_local() - timedelta(days=days_ago)
    snapshot = _snapshot(role=role, contract_ends_at=ends_at)
    assert (snapshot.contract_status, snapshot.effective_role) == (status, effective)


# ---- 캐시 자체 ----


def test_cache_is_off_when_ttl_is_zero() -> None:
    cache = AuthCache()
    snapshot = _snapshot()
    cache.put(snapshot)
    assert len(cache) == 0
    assert cache.get(snapshot.id) is None


def test_put_get_and_expire(cache_on: None, clock: dict[str, float]) -> None:
    cache = AuthCache()
    snapshot = _snapshot()
    cache.put(snapshot)
    assert cache.get(snapshot.id) is snapshot
    clock["t"] += 59
    assert cache.get(snapshot.id) is snapshot
    clock["t"] += 2
    assert cache.get(snapshot.id) is None
    assert len(cache) == 0  # 지난 항목은 조회 때 버린다


def test_invalidate_one_and_whole_institution(cache_on: None) -> None:
    cache = AuthCache()
    inst_x, inst_y = uuid.uuid4(), uuid.uuid4()
    a, b, c = _snapshot(institution_id=inst_x), _snapshot(institution_id=inst_y), _snapshot(institution_id=inst_x)
    for snapshot in (a, b, c):
        cache.put(snapshot)

    cache.invalidate(a.id)
    assert cache.get(a.id) is None
    assert cache.get(b.id) is b and cache.get(c.id) is c

    cache.invalidate_institution(inst_x)
    assert cache.get(c.id) is None
    assert cache.get(b.id) is b


def test_full_cache_drops_expired_entries_on_put(
    cache_on: None, clock: dict[str, float], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cache_module, "MAX_ENTRIES", 2)
    cache = AuthCache()
    first, second, third = _snapshot(), _snapshot(), _snapshot()
    cache.put(first)
    cache.put(second)
    clock["t"] += 61  # 둘 다 지났다
    cache.put(third)
    assert len(cache) == 1
    assert cache.get(third.id) is third


# ---- API에서 (17.2 BE-23 캐시 줄) ----


@contextmanager
def _staff_selects(engine: Engine) -> Iterator[dict[str, int]]:
    """staff 테이블을 읽는 SELECT 수를 센다."""
    counter = {"n": 0}

    def before(conn, cursor, statement, parameters, context, executemany) -> None:  # noqa: ANN001
        if statement.lstrip().upper().startswith("SELECT") and "FROM staff" in statement:
            counter["n"] += 1

    event.listen(engine, "before_cursor_execute", before)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", before)


def test_second_request_skips_the_staff_query(
    cache_on: None, client: TestClient, db: Session, engine: Engine, staff
) -> None:
    headers = bearer(staff)
    db.expunge_all()  # 픽스처가 세션에 올려 둔 행을 비워, 조회가 실제로 DB까지 가게 한다
    with _staff_selects(engine) as counter:
        assert client.get(WHOAMI, headers=headers).status_code == 200
        assert counter["n"] == 1
        assert client.get(WHOAMI, headers=headers).status_code == 200
        assert counter["n"] == 1  # 캐시에서 꺼냈다


def test_disabled_account_passes_until_invalidated(cache_on: None, client: TestClient, db: Session, staff) -> None:
    headers = bearer(staff)
    assert client.get(WHOAMI, headers=headers).status_code == 200  # 캐시에 들어간다

    db.execute(update(Staff).where(Staff.id == staff.id).values(is_active=False))
    db.expire_all()
    assert client.get(WHOAMI, headers=headers).status_code == 200  # 최대 TTL 동안은 옛 스냅샷(11.6 대가)

    auth_cache.invalidate(staff.id)  # 관리자 API가 계정을 중지하면 부르는 것
    blocked = client.get(WHOAMI, headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "ACCOUNT_DISABLED"


def test_ttl_expiry_reloads_from_db(
    cache_on: None, clock: dict[str, float], client: TestClient, db: Session, staff
) -> None:
    headers = bearer(staff)
    assert client.get(WHOAMI, headers=headers).status_code == 200
    db.execute(update(Staff).where(Staff.id == staff.id).values(is_active=False))
    db.expire_all()
    clock["t"] += 61
    assert client.get(WHOAMI, headers=headers).status_code == 403


def test_password_change_cuts_tokens_at_once_in_the_same_process(
    cache_on: None, client: TestClient, db: Session, staff
) -> None:
    """v1.48(11.6 대가): 비밀번호를 바꾼 요청을 받은 프로세스는 캐시를 지워, 옛 토큰을 바로 끊는다."""
    login = client.post(LOGIN, json={"login_id": "staff1", "password": GOOD_PASSWORD})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get(WHOAMI, headers=headers).status_code == 200
    assert auth_cache.get(staff.id) is not None

    changed = client.patch(
        PASSWORD, json={"current_password": GOOD_PASSWORD, "new_password": "new-pass-5678"}, headers=headers
    )
    assert changed.status_code == 200
    cut = client.get(WHOAMI, headers=headers)
    assert cut.status_code == 401
    assert cut.json()["error"]["code"] == "AUTH_EXPIRED"


def test_password_changed_in_another_process_shows_up_after_the_ttl(
    cache_on: None, clock: dict[str, float], client: TestClient, db: Session, staff
) -> None:
    """다른 프로세스에서 바꾼 비밀번호는 이 프로세스의 캐시가 지날 때까지(최대 TTL) 옛 토큰을 막지 못한다."""
    headers = bearer(staff)
    assert client.get(WHOAMI, headers=headers).status_code == 200  # 캐시에 들어간다

    later = datetime.now(UTC) + timedelta(seconds=1)  # 이 토큰보다 뒤에 바꿨다
    db.execute(update(Staff).where(Staff.id == staff.id).values(password_changed_at=later))
    db.expire_all()
    assert client.get(WHOAMI, headers=headers).status_code == 200  # 옛 스냅샷

    clock["t"] += 61
    cut = client.get(WHOAMI, headers=headers)
    assert cut.status_code == 401
    assert cut.json()["error"]["code"] == "AUTH_EXPIRED"


def test_me_reads_db_and_refreshes_cache(cache_on: None, client: TestClient, db: Session, staff) -> None:
    headers = bearer(staff)
    assert client.get(WHOAMI, headers=headers).status_code == 200
    db.execute(update(Staff).where(Staff.id == staff.id).values(name="바뀐 이름"))
    db.expire_all()

    me = client.get(ME, headers=headers)
    assert me.status_code == 200
    assert me.json()["name"] == "바뀐 이름"
    cached = auth_cache.get(staff.id)
    assert cached is not None and cached.name == "바뀐 이름"
