"""반려견 차트 칸: 동물번호·보호자·단계(12.5 차트 자료, 13.2, 15.3 DogOut, 15.5, 17.2 BE-02·03, v1.36)."""

import json
import logging
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.dates import today_local
from app.services.dogs import phone_last4
from app.services.report_input import build_report_input
from tests.conftest import bearer
from tests.history_fixtures import add_report, make_session

DOGS = "/api/v1/dogs"
BASE = {"name": "보리", "breed": "골든 리트리버", "weight_kg": 28.4}
CHART = {"chart_no": "A-1024", "owner_name": "김보호", "owner_phone": "010-1234-5678", "stage": "PRE"}


def _post(client: TestClient, headers: dict, **overrides):
    return client.post(DOGS, json={**BASE, **overrides}, headers=headers)


def _patch(client: TestClient, dog_id: str, headers: dict, **changes):
    version = client.get(f"{DOGS}/{dog_id}", headers=headers).json()["version"]
    return client.patch(f"{DOGS}/{dog_id}", json={"version": version, **changes}, headers=headers)


def _fields(response) -> list[str]:
    return [f["field"] for f in response.json()["error"]["detail"]["fields"]]


def test_create_stores_chart_fields_and_detail_shows_the_full_phone(client: TestClient, auth_headers: dict) -> None:
    created = _post(client, auth_headers, **{**CHART, "chart_no": "  A-1024 "})
    assert created.status_code == 201
    body = created.json()
    assert {key: body[key] for key in CHART} == CHART  # 앞뒤 공백은 지운다
    assert body["owner_phone_last4"] == "5678"
    assert body["stage_changed_on"] is None  # 등록은 단계가 바뀐 것이 아니다

    detail = client.get(f"{DOGS}/{body['id']}", headers=auth_headers).json()
    assert detail["owner_phone"] == "010-1234-5678"


def test_chart_fields_are_optional_and_stage_defaults_to_rehab(client: TestClient, auth_headers: dict) -> None:
    body = _post(client, auth_headers).json()
    assert body["chart_no"] is None and body["owner_name"] is None
    assert body["owner_phone"] is None and body["owner_phone_last4"] is None
    assert body["stage"] == "REHAB" and body["stage_changed_on"] is None


def test_list_hides_the_phone_except_the_last_four_digits(client: TestClient, auth_headers: dict) -> None:
    _post(client, auth_headers, **CHART)
    item = client.get(DOGS, headers=auth_headers).json()["items"][0]
    assert item["owner_phone"] is None
    assert item["owner_phone_last4"] == "5678"
    assert item["owner_name"] == "김보호" and item["chart_no"] == "A-1024"


@pytest.mark.parametrize(
    ("phone", "expected"),
    [("010-1234-5678", "5678"), ("+82 10 1234 5678", "5678"), ("02-123", "2123"), ("1234567", "4567"), (None, None)],
)
def test_phone_last4_takes_digits_only(phone: str | None, expected: str | None) -> None:
    assert phone_last4(phone) == expected


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"chart_no": ""}, "chart_no"),
        ({"chart_no": "1" * 31}, "chart_no"),
        ({"owner_name": "   "}, "owner_name"),
        ({"owner_name": "가" * 51}, "owner_name"),
        ({"owner_phone": "123456"}, "owner_phone"),  # 7자보다 짧다
        ({"owner_phone": "010-1234-5678-9012-3456"}, "owner_phone"),  # 20자를 넘는다
        ({"owner_phone": "010.1234.5678"}, "owner_phone"),  # 숫자와 - + 공백만
        ({"stage": "ACTIVE"}, "stage"),
        ({"stage": None}, "stage"),
    ],
)
def test_chart_field_input_rules(client: TestClient, auth_headers: dict, overrides: dict, field: str) -> None:
    response = _post(client, auth_headers, **overrides)
    assert response.status_code == 422
    assert _fields(response) == [field]


def test_stage_changed_on_is_not_taken_from_the_request(client: TestClient, auth_headers: dict) -> None:
    body = _post(client, auth_headers, stage="DONE", stage_changed_on="2020-01-01").json()
    assert body["stage"] == "DONE" and body["stage_changed_on"] is None
    patched = _patch(client, body["id"], auth_headers, stage_changed_on="2020-01-01").json()
    assert patched["stage_changed_on"] is None


def test_patch_stage_sets_the_changed_date_only_when_the_value_changes(client: TestClient, auth_headers: dict) -> None:
    dog_id = _post(client, auth_headers).json()["id"]

    same = _patch(client, dog_id, auth_headers, stage="REHAB").json()
    assert same["stage_changed_on"] is None

    changed = _patch(client, dog_id, auth_headers, stage="DONE").json()
    assert changed["stage"] == "DONE"
    assert changed["stage_changed_on"] == today_local().isoformat()

    null = _patch(client, dog_id, auth_headers, stage=None)
    assert null.status_code == 422 and _fields(null) == ["stage"]


def test_patch_changes_and_clears_chart_fields(client: TestClient, auth_headers: dict) -> None:
    dog_id = _post(client, auth_headers, **CHART).json()["id"]
    changed = _patch(client, dog_id, auth_headers, owner_phone="02-555-0101", chart_no=None).json()
    assert changed["owner_phone"] == "02-555-0101" and changed["owner_phone_last4"] == "0101"
    assert changed["chart_no"] is None
    assert changed["owner_name"] == "김보호"  # 보내지 않은 것은 그대로


def test_search_finds_chart_no_and_owner_name_but_not_the_phone(client: TestClient, auth_headers: dict) -> None:
    _post(client, auth_headers, name="보리", chart_no="A-1024", owner_name="김보호", owner_phone="010-1234-5678")
    _post(client, auth_headers, name="콩이", chart_no="B-0007", owner_name="이주인", owner_phone="010-9999-0000")
    _post(client, auth_headers, name="초코")

    def names(q: str) -> set[str]:
        return {d["name"] for d in client.get(DOGS, params={"q": q}, headers=auth_headers).json()["items"]}

    assert names("a-10") == {"보리"}  # 동물번호, 대소문자 무시
    assert names("주인") == {"콩이"}  # 보호자 이름
    assert names("초") == {"초코"}  # 이름은 그대로 찾는다
    assert names("1234") == set()  # 연락처로는 찾지 않는다
    assert client.get(DOGS, params={"q": "0"}, headers=auth_headers).json()["total"] == 2  # 개수도 같은 조건


def test_other_institution_cannot_find_by_owner(client: TestClient, auth_headers: dict, other_staff) -> None:
    _post(client, auth_headers, **CHART)
    other = client.get(DOGS, params={"q": "김보호"}, headers=bearer(other_staff)).json()
    assert other["total"] == 0


def test_owner_info_is_not_in_the_log(client: TestClient, auth_headers: dict, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        dog_id = _post(client, auth_headers, **CHART).json()["id"]
        _patch(client, dog_id, auth_headers, owner_name="박보호", owner_phone="010-0000-1111")
        client.get(DOGS, params={"q": "박보호"}, headers=auth_headers)
        _post(client, auth_headers, owner_phone="전화번호아님")  # 422도 값을 남기지 않는다
    logged = "\n".join(record.getMessage() for record in caplog.records)
    for secret in ("김보호", "박보호", "010-1234-5678", "010-0000-1111", "전화번호아님"):
        assert secret not in logged


def test_owner_info_is_not_in_the_report_input(db: Session, staff, dog) -> None:
    """보호자 정보는 보호자용·수의사용 보고서 어디에도 넣지 않는다(4절 BE-02)."""
    dog.chart_no, dog.owner_name, dog.owner_phone = "A-1024", "김보호", "010-1234-5678"
    session = make_session(db, dog, staff, date(2026, 10, 20))
    for edition in ("OWNER", "VET"):
        report = add_report(db, session, edition, "PENDING")
        dumped = json.dumps(build_report_input(db, report), ensure_ascii=False)
        assert "김보호" not in dumped and "5678" not in dumped and "A-1024" not in dumped
