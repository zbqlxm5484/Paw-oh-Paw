"""진단 이력(12.5 차트 자료, 13.9, 15.11, 17.2 BE-29, v1.36). 측정 이력(test_history_api.py)과는 다른 것이다."""

import logging
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dates import today_local
from app.models import DogHistory
from app.services.purge import purge
from app.storage.base import get_storage
from tests.conftest import bearer

DOGS = "/api/v1/dogs"
SURGERY = {"occurred_on": "2026-08-27", "kind": "SURGERY", "title": "TPLO", "site": "RH", "clinician": "박수의"}


def _post(client: TestClient, dog, headers: dict, **overrides):
    return client.post(f"{DOGS}/{dog.id}/history", json={**SURGERY, **overrides}, headers=headers)


def _list(client: TestClient, dog, headers: dict) -> list[dict]:
    response = client.get(f"{DOGS}/{dog.id}/history", headers=headers)
    assert response.status_code == 200
    return response.json()["items"]


def _fields(response) -> list[str]:
    return [f["field"] for f in response.json()["error"]["detail"]["fields"]]


def _dog(client: TestClient, dog, headers: dict) -> dict:
    return client.get(f"{DOGS}/{dog.id}", headers=headers).json()


def test_post_adds_a_row_written_by_the_caller(client: TestClient, dog, staff, auth_headers: dict) -> None:
    response = _post(client, dog, auth_headers, title="  TPLO ")
    assert response.status_code == 201
    body = response.json()
    assert {key: body[key] for key in SURGERY} == SURGERY  # 앞뒤 공백은 지운다
    assert body["staff"] == {"id": str(staff.id), "name": "담당자"}
    assert set(body) == {*SURGERY, "id", "staff", "created_at"}


def test_site_and_clinician_are_optional(client: TestClient, dog, auth_headers: dict) -> None:
    body = client.post(
        f"{DOGS}/{dog.id}/history",
        json={"occurred_on": "2026-08-20", "kind": "DIAGNOSIS", "title": "앞십자인대 파열"},
        headers=auth_headers,
    ).json()
    assert body["site"] is None and body["clinician"] is None


def test_list_is_oldest_first_and_same_day_keeps_the_writing_order(client: TestClient, dog, auth_headers: dict) -> None:
    _post(client, dog, auth_headers, occurred_on="2026-09-10", kind="REHAB", title="수중 러닝 시작")
    _post(client, dog, auth_headers, occurred_on="2026-08-27", kind="DIAGNOSIS", title="앞십자인대 파열")
    _post(client, dog, auth_headers, occurred_on="2026-08-27", kind="SURGERY", title="TPLO")
    assert [item["title"] for item in _list(client, dog, auth_headers)] == ["앞십자인대 파열", "TPLO", "수중 러닝 시작"]


def test_list_is_empty_without_rows(client: TestClient, dog, auth_headers: dict) -> None:
    assert _list(client, dog, auth_headers) == []


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"kind": "CHECKUP"}, "kind"),
        ({"title": "   "}, "title"),
        ({"title": "가" * 101}, "title"),
        ({"site": "TAIL"}, "site"),
        ({"clinician": "가" * 51}, "clinician"),
        ({"clinician": ""}, "clinician"),
        ({"stage": "ACTIVE"}, "stage"),
        ({"occurred_on": "어제"}, "occurred_on"),
        ({"occurred_on": None}, "occurred_on"),
    ],
)
def test_input_rules(client: TestClient, db: Session, dog, auth_headers: dict, overrides: dict, field: str) -> None:
    response = _post(client, dog, auth_headers, **overrides)
    assert response.status_code == 422
    assert _fields(response) == [field]
    assert db.scalar(select(func.count()).select_from(DogHistory)) == 0


def test_spine_site_and_today_are_accepted_but_not_a_future_date(client: TestClient, dog, auth_headers: dict) -> None:
    today = today_local()
    assert _post(client, dog, auth_headers, site="SP", occurred_on=today.isoformat()).status_code == 201
    future = _post(client, dog, auth_headers, occurred_on=(today + timedelta(days=1)).isoformat())
    assert future.status_code == 422 and _fields(future) == ["occurred_on"]


def test_stage_changes_the_dog_and_bumps_its_version(client: TestClient, dog, auth_headers: dict) -> None:
    before = _dog(client, dog, auth_headers)
    assert before["stage"] == "REHAB" and before["stage_changed_on"] is None

    assert _post(client, dog, auth_headers, stage="DONE").status_code == 201
    after = _dog(client, dog, auth_headers)
    assert after["stage"] == "DONE"
    assert after["stage_changed_on"] == today_local().isoformat()  # 일어난 날이 아니라 적은 날
    assert after["version"] == before["version"] + 1


def test_same_stage_or_no_stage_leaves_the_dog_alone(client: TestClient, dog, auth_headers: dict) -> None:
    before = _dog(client, dog, auth_headers)
    assert _post(client, dog, auth_headers, stage="REHAB").status_code == 201
    assert _post(client, dog, auth_headers).status_code == 201
    after = _dog(client, dog, auth_headers)
    assert after["version"] == before["version"] and after["stage_changed_on"] is None


def test_other_institution_and_trashed_dog_are_404(
    client: TestClient, db: Session, dog, auth_headers, other_staff
) -> None:
    _post(client, dog, auth_headers)
    other = bearer(other_staff)
    assert client.get(f"{DOGS}/{dog.id}/history", headers=other).status_code == 404
    assert _post(client, dog, other, stage="DONE").status_code == 404
    assert client.get(f"{DOGS}/{uuid.uuid4()}/history", headers=auth_headers).status_code == 404
    assert db.scalar(select(func.count()).select_from(DogHistory)) == 1
    assert _dog(client, dog, auth_headers)["stage"] == "REHAB"  # 다른 기관의 요청은 단계를 바꾸지 못했다

    assert client.delete(f"{DOGS}/{dog.id}", headers=auth_headers).status_code == 204  # 휴지통
    assert client.get(f"{DOGS}/{dog.id}/history", headers=auth_headers).status_code == 404
    assert _post(client, dog, auth_headers).status_code == 404


def test_history_needs_a_token(client: TestClient, dog) -> None:
    assert client.get(f"{DOGS}/{dog.id}/history").status_code == 401
    assert client.post(f"{DOGS}/{dog.id}/history", json=SURGERY).status_code == 401


def test_title_and_clinician_are_not_in_the_log(client: TestClient, dog, auth_headers, caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        _post(client, dog, auth_headers, title="슬개골 탈구 3기", clinician="최집도")
        _list(client, dog, auth_headers)
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "슬개골" not in logged and "최집도" not in logged


def test_purge_counts_and_deletes_history(client: TestClient, db: Session, dog, auth_headers) -> None:
    _post(client, dog, auth_headers)
    _post(client, dog, auth_headers, kind="REHAB", title="재활 시작")

    counted = purge(db, get_storage(), "DOG", institution_id=dog.institution_id, target_id=dog.id)
    assert counted.rows == 1 + 2  # 반려견 + 진단 이력 둘
    done = purge(db, get_storage(), "DOG", institution_id=dog.institution_id, target_id=dog.id, dry_run=False)
    assert done.rows == 1 + 2
    assert db.scalar(select(func.count()).select_from(DogHistory)) == 0
