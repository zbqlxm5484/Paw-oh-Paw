"""크림오프 관리자 API(11.6 역할 검사·무효화, 13.6, 15.9, 17.2 BE-23·BE-24)."""

import logging
import uuid
from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_cache import auth_cache
from app.core.config import get_settings
from app.core.dates import today_local
from app.models import DeviceCode, Institution, Staff
from app.services.device_codes import CODE_ALPHABET
from tests.conftest import GOOD_PASSWORD, bearer, password_hash_for

ADMIN = "/api/v1/admin"
INSTITUTIONS = f"{ADMIN}/institutions"
LOGIN = "/api/v1/auth/login"
VERIFY = "/api/v1/auth/device-codes/verify"
SIGNUP = "/api/v1/auth/signup"
DOGS = "/api/v1/dogs"


@pytest.fixture
def creamoff(db: Session) -> dict[str, Staff]:
    """크림오프 자체 기관(계약 기한 없음)의 ADMIN(boss)과 STAFF(temp1)."""
    institution = Institution(code="CREAMOFF", name="크림오프")
    db.add(institution)
    db.flush()
    rows = {
        "admin": Staff(
            institution_id=institution.id,
            login_id="boss",
            password_hash=password_hash_for(GOOD_PASSWORD),
            name="사장",
            role="ADMIN",
        ),
        "worker": Staff(
            institution_id=institution.id,
            login_id="temp1",
            password_hash=password_hash_for(GOOD_PASSWORD),
            name="임시 스태프",
            role="STAFF",
        ),
    }
    db.add_all(rows.values())
    db.flush()
    for row in rows.values():
        db.refresh(row)
    return rows


@pytest.fixture
def admin_headers(creamoff: dict[str, Staff]) -> dict[str, str]:
    return bearer(creamoff["admin"])


@pytest.fixture
def worker_headers(creamoff: dict[str, Staff]) -> dict[str, str]:
    return bearer(creamoff["worker"])


@pytest.fixture
def cache_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """인증 캐시를 켠다(conftest는 0). 무효화(11.6)를 보는 테스트만 쓴다."""
    monkeypatch.setenv("AUTH_CACHE_TTL_SEC", "60")
    get_settings.cache_clear()
    auth_cache.clear()
    yield
    auth_cache.clear()
    get_settings.cache_clear()


def _login(client: TestClient, login_id: str, password: str = GOOD_PASSWORD):
    return client.post(LOGIN, json={"login_id": login_id, "password": password})


def _signup(client: TestClient, code: str, login_id: str):
    body = {
        "code": code,
        "login_id": login_id,
        "password": GOOD_PASSWORD,
        "name": "담당자",
        "email": f"{login_id}@x.kr",
    }
    return client.post(SIGNUP, json=body)


# ---- 역할 검사 (11.6) ----


@pytest.mark.parametrize(
    ("who", "get_status", "post_status"),
    [("client", 403, 403), ("worker", 200, 403), ("admin", 200, 201)],
)
def test_reads_need_creamoff_and_writes_need_admin(
    client: TestClient, creamoff: dict[str, Staff], auth_headers: dict, who: str, get_status: int, post_status: int
) -> None:
    headers = auth_headers if who == "client" else bearer(creamoff[who])
    assert client.get(INSTITUTIONS, headers=headers).status_code == get_status
    response = client.post(INSTITUTIONS, json={"name": "새 병원"}, headers=headers)
    assert response.status_code == post_status
    if post_status == 403:
        assert response.json()["error"]["code"] == "FORBIDDEN"


# ---- BE-24 흐름 ----


def test_admin_flow(client: TestClient, db: Session, admin_headers: dict) -> None:
    """기관 만들기 → 코드 발급 → 가입 → 계약일 수정 → 회수 → 계정 중지(17.2 BE-24)."""
    created = client.post(
        INSTITUTIONS,
        json={"code": None, "name": "크림 재활센터", "contract_ends_at": "2027-10-30"},
        headers=admin_headers,
    )
    assert created.status_code == 201
    institution = created.json()
    assert institution["code"].startswith("INST-")
    assert len(institution["code"]) == 11
    assert set(institution["code"][5:]) <= set(CODE_ALPHABET)
    assert (institution["contract_ends_at"], institution["contract_status"]) == ("2027-10-30", "ACTIVE")
    assert (institution["staff_count"], institution["device_code_count"]) == (0, 0)
    assert institution["created_at"].endswith("Z")
    inst_id = institution["id"]

    issued = client.post(f"{INSTITUTIONS}/{inst_id}/device-codes", headers=admin_headers)
    assert issued.status_code == 201
    code = issued.json()
    assert len(code["code"]) == 23
    assert code["code"].count("-") == 3
    assert (code["active_accounts"], code["revoked_at"], code["note"]) == (0, None, None)
    assert "max_accounts" not in code  # 계정 수 상한은 없다(v1.32)
    assert code["institution_id"] == inst_id
    listed = client.get(f"{INSTITUTIONS}/{inst_id}/device-codes", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json()["items"] == [code]

    signup = _signup(client, code["code"], "kim01")
    assert signup.status_code == 201
    client_headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    assert client.get(DOGS, headers=client_headers).status_code == 200

    staff_list = client.get(f"{INSTITUTIONS}/{inst_id}/staff", headers=admin_headers)
    assert staff_list.status_code == 200
    [member] = staff_list.json()["items"]
    assert (member["login_id"], member["role"], member["is_active"], member["device_code_id"]) == (
        "kim01",
        "CLIENT",
        True,
        code["id"],
    )
    assert member["email"] == "kim01@x.kr"
    assert "password" not in str(member)
    found = next(
        item for item in client.get(INSTITUTIONS, headers=admin_headers).json()["items"] if item["id"] == inst_id
    )
    assert (found["staff_count"], found["device_code_count"]) == (1, 1)
    assert (
        client.get(f"{INSTITUTIONS}/{inst_id}/device-codes", headers=admin_headers).json()["items"][0][
            "active_accounts"
        ]
        == 1
    )

    # 계약 종료일을 어제로 → 그 기관 CLIENT는 GUEST, 코드도 못 쓴다
    yesterday = (today_local() - timedelta(days=1)).isoformat()
    expired = client.patch(f"{INSTITUTIONS}/{inst_id}", json={"contract_ends_at": yesterday}, headers=admin_headers)
    assert expired.status_code == 200
    assert expired.json()["contract_status"] == "EXPIRED"
    blocked = client.get(DOGS, headers=client_headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "CONTRACT_EXPIRED"
    assert client.post(VERIFY, json={"code": code["code"]}).status_code == 404
    # null = 기한 없음
    restored = client.patch(f"{INSTITUTIONS}/{inst_id}", json={"contract_ends_at": None}, headers=admin_headers)
    assert (restored.json()["contract_ends_at"], restored.json()["contract_status"]) == (None, "ACTIVE")
    assert client.get(DOGS, headers=client_headers).status_code == 200

    # 회수(멱등): 코드로는 더 못 가입하고 기존 계정은 그대로
    revoked = client.post(f"{ADMIN}/device-codes/{code['id']}/revoke", headers=admin_headers)
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None
    again = client.post(f"{ADMIN}/device-codes/{code['id']}/revoke", headers=admin_headers)
    assert again.status_code == 200
    assert again.json()["revoked_at"] == revoked.json()["revoked_at"]
    assert client.post(VERIFY, json={"code": code["code"]}).status_code == 404
    assert _signup(client, code["code"], "kim02").status_code == 404
    assert _login(client, "kim01").status_code == 200
    assert client.get(f"{INSTITUTIONS}/{inst_id}/device-codes", headers=admin_headers).json()["items"][0]["revoked_at"]

    # 계정 중지 → 로그인 403, 재개 → 200
    disabled = client.patch(f"{ADMIN}/staff/{member['id']}", json={"is_active": False}, headers=admin_headers)
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False
    login = _login(client, "kim01")
    assert login.status_code == 403
    assert login.json()["error"]["code"] == "ACCOUNT_DISABLED"
    enabled = client.patch(f"{ADMIN}/staff/{member['id']}", json={"is_active": True}, headers=admin_headers)
    assert enabled.json()["is_active"] is True
    assert _login(client, "kim01").status_code == 200


# ---- 기관 (13.6) ----


def test_institution_code_rules(client: TestClient, admin_headers: dict) -> None:
    given = client.post(INSTITUTIONS, json={"code": " ABC ", "name": "병원"}, headers=admin_headers)
    assert given.status_code == 201
    assert given.json()["code"] == "ABC"

    duplicate = client.post(INSTITUTIONS, json={"code": "ABC", "name": "다른 병원"}, headers=admin_headers)
    assert duplicate.status_code == 422
    assert duplicate.json()["error"]["code"] == "VALIDATION_ERROR"
    assert duplicate.json()["error"]["detail"]["fields"] == [{"field": "code", "type": "duplicate"}]

    too_long = client.post(INSTITUTIONS, json={"code": "C" * 21, "name": "병원"}, headers=admin_headers)
    assert too_long.status_code == 422
    assert [item["field"] for item in too_long.json()["error"]["detail"]["fields"]] == ["code"]

    no_name = client.post(INSTITUTIONS, json={"code": "DEF"}, headers=admin_headers)
    assert no_name.status_code == 422
    assert no_name.json()["error"]["detail"]["fields"] == [{"field": "name", "type": "missing"}]

    # 과거 날짜도 받는다(즉시 만료). 90일보다 더 지난 날짜만 막는다(13.6, tests/test_retention.py)
    yesterday = (today_local() - timedelta(days=1)).isoformat()
    past = client.post(INSTITUTIONS, json={"name": "끝난 병원", "contract_ends_at": yesterday}, headers=admin_headers)
    assert past.status_code == 201
    assert past.json()["contract_status"] == "EXPIRED"


def test_institutions_are_listed_by_name(client: TestClient, admin_headers: dict, staff) -> None:
    for name in ("B 병원", "A 재활센터"):
        assert client.post(INSTITUTIONS, json={"name": name}, headers=admin_headers).status_code == 201
    names = [item["name"] for item in client.get(INSTITUTIONS, headers=admin_headers).json()["items"]]
    assert names.index("A 재활센터") < names.index("B 병원")
    assert {"크림오프", "테스트 병원"} <= set(names)


def test_update_institution(client: TestClient, admin_headers: dict, staff) -> None:
    url = f"{INSTITUTIONS}/{staff.institution_id}"
    renamed = client.patch(url, json={"name": " 새 이름 "}, headers=admin_headers)
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "새 이름"
    assert renamed.json()["staff_count"] == 1

    null_name = client.patch(url, json={"name": None}, headers=admin_headers)
    assert null_name.status_code == 422
    assert [item["field"] for item in null_name.json()["error"]["detail"]["fields"]] == ["name"]

    nothing = client.patch(url, json={}, headers=admin_headers)
    assert nothing.status_code == 200
    assert nothing.json()["name"] == "새 이름"


# ---- 디바이스 코드 (13.6) ----


def test_device_code_rules(client: TestClient, admin_headers: dict, staff) -> None:
    base = f"{INSTITUTIONS}/{staff.institution_id}/device-codes"
    too_long = client.post(base, json={"note": "메" * 101}, headers=admin_headers)
    assert too_long.status_code == 422
    assert [item["field"] for item in too_long.json()["error"]["detail"]["fields"]] == ["note"]

    issued = client.post(base, json={"note": "2호기"}, headers=admin_headers)
    assert issued.status_code == 201
    assert issued.json()["note"] == "2호기"
    code_url = f"{ADMIN}/device-codes/{issued.json()['id']}"

    cleared = client.patch(code_url, json={"note": None}, headers=admin_headers)
    assert (cleared.status_code, cleared.json()["note"]) == (200, None)
    # 예전 화면이 상한을 보내도 무시한다(칸이 없다). 422가 아니다
    ignored = client.patch(code_url, json={"max_accounts": 1, "note": "새 메모"}, headers=admin_headers)
    assert (ignored.status_code, ignored.json()["note"]) == (200, "새 메모")
    assert "max_accounts" not in ignored.json()

    # 계정 수 상한이 없다(v1.32): 몇 명이든 가입되고 목록에는 활성 계정 수만 보인다
    for login_id in ("kim01", "kim02", "kim03", "kim04"):
        assert _signup(client, issued.json()["code"], login_id).status_code == 201
    listed = client.get(base, headers=admin_headers).json()["items"]
    assert [item["active_accounts"] for item in listed] == [4]
    assert client.post(VERIFY, json={"code": issued.json()["code"]}).status_code == 200
    assert _login(client, "kim04").status_code == 200


def test_one_usable_code_per_institution(client: TestClient, admin_headers: dict, staff, other_staff) -> None:
    """v1.32: 회수하지 않은 코드는 기관마다 하나다. 회수하면 새로 발급할 수 있고 회수한 코드는 목록에 남는다."""
    base = f"{INSTITUTIONS}/{staff.institution_id}/device-codes"
    first = client.post(base, headers=admin_headers)
    assert first.status_code == 201
    again = client.post(base, json={"note": "둘째"}, headers=admin_headers)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "DEVICE_CODE_EXISTS"
    # 다른 기관은 따로 센다
    other = client.post(f"{INSTITUTIONS}/{other_staff.institution_id}/device-codes", headers=admin_headers)
    assert other.status_code == 201

    assert _signup(client, first.json()["code"], "kim01").status_code == 201
    revoked = client.post(f"{ADMIN}/device-codes/{first.json()['id']}/revoke", headers=admin_headers)
    assert revoked.status_code == 200
    second = client.post(base, json={"note": "둘째"}, headers=admin_headers)
    assert second.status_code == 201
    items = client.get(base, headers=admin_headers).json()["items"]
    assert {item["id"]: item["revoked_at"] is None for item in items} == {
        first.json()["id"]: False,
        second.json()["id"]: True,
    }
    # 회수한 코드로는 가입이 안 되고, 그 코드로 가입한 계정은 그대로 쓴다
    assert _signup(client, first.json()["code"], "kim02").status_code == 404
    assert _signup(client, second.json()["code"], "kim02").status_code == 201
    assert _login(client, "kim01").status_code == 200


def test_code_list_is_masked_for_staff_and_full_for_admin(
    client: TestClient, admin_headers: dict, worker_headers: dict, staff
) -> None:
    """v1.48(15.9): 코드 전체는 ADMIN만 본다. 조회만 하는 STAFF의 목록에는 가운데 두 묶음을 가린 값이 온다."""
    base = f"{INSTITUTIONS}/{staff.institution_id}/device-codes"
    issued = client.post(base, json={"note": "1호기"}, headers=admin_headers).json()
    full = issued["code"]
    masked = f"{full[:5]}-*****-*****-{full[-5:]}"

    assert client.get(base, headers=admin_headers).json()["items"] == [issued]
    for_worker = client.get(base, headers=worker_headers)
    assert for_worker.status_code == 200
    # code만 다르고 나머지 칸과 모양은 같다
    assert for_worker.json()["items"] == [{**issued, "code": masked}]
    assert full not in for_worker.text
    assert full.replace("-", "") not in for_worker.text

    # 회수한 코드도 가린다
    assert client.post(f"{ADMIN}/device-codes/{issued['id']}/revoke", headers=admin_headers).status_code == 200
    [revoked] = client.get(base, headers=worker_headers).json()["items"]
    assert revoked["code"] == masked and revoked["revoked_at"] is not None
    assert client.get(base, headers=admin_headers).json()["items"][0]["code"] == full


def test_issue_and_revoke_are_logged_with_ids_only(
    client: TestClient, creamoff: dict[str, Staff], admin_headers: dict, staff, caplog: pytest.LogCaptureFixture
) -> None:
    """11.8(v1.48): 코드 발급·회수는 누가 했는지 ID로 남고, 코드 값은 로그에 없다.

    이미 회수한 코드를 다시 회수해도(멱등) 로그를 또 남기지 않는다.
    """
    base = f"{INSTITUTIONS}/{staff.institution_id}/device-codes"
    with caplog.at_level(logging.DEBUG):
        issued = client.post(base, json={"note": "비밀 메모"}, headers=admin_headers).json()
        revoke_url = f"{ADMIN}/device-codes/{issued['id']}/revoke"
        assert client.post(revoke_url, headers=admin_headers).status_code == 200
        assert client.post(revoke_url, headers=admin_headers).status_code == 200
    who = f"institution={staff.institution_id} by={creamoff['admin'].id}"
    assert f"device code issued code={issued['id']} {who}" in caplog.text
    assert caplog.text.count(f"device code revoked code={issued['id']} {who}") == 1
    for secret in (issued["code"], issued["code"].replace("-", ""), "비밀 메모", "boss"):
        assert secret not in caplog.text


def test_the_index_stops_a_second_usable_code(db: Session, staff) -> None:
    """발급 API의 확인을 지나쳐도(동시 발급) uq_device_code_active가 막는다."""
    db.add(DeviceCode(institution_id=staff.institution_id, code="A" * 20))
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(DeviceCode(institution_id=staff.institution_id, code="B" * 20))
        db.flush()


def test_self_disable_is_409(client: TestClient, creamoff: dict[str, Staff], admin_headers: dict) -> None:
    url = f"{ADMIN}/staff/{creamoff['admin'].id}"
    response = client.patch(url, json={"is_active": False}, headers=admin_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SELF_DISABLE"
    assert client.patch(url, json={"is_active": True}, headers=admin_headers).status_code == 200
    # 다른 크림오프 계정은 중지할 수 있다
    other = client.patch(f"{ADMIN}/staff/{creamoff['worker'].id}", json={"is_active": False}, headers=admin_headers)
    assert other.status_code == 200


def test_changes_invalidate_the_auth_cache(
    cache_on: None, client: TestClient, db: Session, staff, auth_headers: dict, admin_headers: dict
) -> None:
    """BE-23: 캐시를 켜도 관리자 API로 계정을 중지하거나 계약을 끝내면 같은 프로세스에서 즉시 막힌다(11.6 무효화)."""
    assert client.get(DOGS, headers=auth_headers).status_code == 200
    assert len(auth_cache) >= 1

    assert (
        client.patch(f"{ADMIN}/staff/{staff.id}", json={"is_active": False}, headers=admin_headers).status_code == 200
    )
    blocked = client.get(DOGS, headers=auth_headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "ACCOUNT_DISABLED"

    assert client.patch(f"{ADMIN}/staff/{staff.id}", json={"is_active": True}, headers=admin_headers).status_code == 200
    assert client.get(DOGS, headers=auth_headers).status_code == 200

    yesterday = (today_local() - timedelta(days=1)).isoformat()
    url = f"{INSTITUTIONS}/{staff.institution_id}"
    assert client.patch(url, json={"contract_ends_at": yesterday}, headers=admin_headers).status_code == 200
    expired = client.get(DOGS, headers=auth_headers)
    assert expired.status_code == 403
    assert expired.json()["error"]["code"] == "CONTRACT_EXPIRED"


def test_unknown_ids_are_404(client: TestClient, admin_headers: dict) -> None:
    missing = uuid.uuid4()
    calls = [
        ("patch", f"{INSTITUTIONS}/{missing}", {"name": "x"}),
        ("get", f"{INSTITUTIONS}/{missing}/device-codes", None),
        ("post", f"{INSTITUTIONS}/{missing}/device-codes", {}),
        ("patch", f"{ADMIN}/device-codes/{missing}", {"note": "x"}),
        ("post", f"{ADMIN}/device-codes/{missing}/revoke", None),
        ("get", f"{INSTITUTIONS}/{missing}/staff", None),
        ("patch", f"{ADMIN}/staff/{missing}", {"is_active": False}),
    ]
    for method, url, body in calls:
        response = client.request(method.upper(), url, json=body, headers=admin_headers)
        assert response.status_code == 404, (method, url)
        assert response.json()["error"]["code"] == "NOT_FOUND"
