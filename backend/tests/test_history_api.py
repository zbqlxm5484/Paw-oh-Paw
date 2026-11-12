"""측정 이력 API(명세 15.8의 8번, 12.5 기준 회차, BE-17, 17.5, S15P31A404-198)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import bearer
from tests.history_fixtures import add_report, add_shot, make_session

HISTORY = "/api/v1/dogs/{}/sessions"


def _items(client: TestClient, headers: dict, dog, **params) -> list[dict]:
    response = client.get(HISTORY.format(dog.id), params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_history_is_newest_first_and_same_day_sessions_by_created_at(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    first = make_session(db, dog, staff, date(2026, 10, 1), weight=Decimal("28.10"))
    second = make_session(db, dog, staff, date(2026, 10, 20), seq=0)
    third = make_session(db, dog, staff, date(2026, 10, 20), seq=1, status="MEASURING", model_version=None)

    body = client.get(HISTORY.format(dog.id), headers=auth_headers).json()
    assert [item["id"] for item in body["items"]] == [str(third.id), str(second.id), str(first.id)]
    assert (body["total"], body["page"], body["size"]) == (3, 1, 20)
    assert body["items"][2] == {
        "id": str(first.id),
        "measured_on": "2026-10-01",
        "weight_kg": 28.1,
        "status": "DONE",
        "is_baseline": True,
        "valid_passes": {"LEFT": 0, "RIGHT": 0},
        "model_version": "v1",
        "symmetry_score": None,
        "reports": {"OWNER": None, "VET": None},
    }
    # 측정 중인 회차는 체중·모델 버전이 비어 있어도 키는 남는다(11.5)
    newest = body["items"][0]
    assert newest["status"] == "MEASURING" and newest["weight_kg"] is None and newest["model_version"] is None


def test_exactly_one_item_is_baseline_and_it_is_the_earliest_done_session(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    make_session(db, dog, staff, date(2026, 9, 30), status="FAILED")  # 더 이르지만 DONE이 아니다
    make_session(db, dog, staff, date(2026, 10, 1))
    make_session(db, dog, staff, date(2026, 10, 2))
    items = _items(client, auth_headers, dog)
    assert [(item["measured_on"], item["is_baseline"]) for item in items] == [
        ("2026-10-02", False),
        ("2026-10-01", True),
        ("2026-09-30", False),
    ]


def test_baseline_follows_the_dog_setting_when_it_is_set(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    make_session(db, dog, staff, date(2026, 10, 1))
    later = make_session(db, dog, staff, date(2026, 10, 2))
    dog.baseline_session_id = later.id
    db.flush()
    items = _items(client, auth_headers, dog)
    assert [item["is_baseline"] for item in items] == [True, False]
    assert sum(item["is_baseline"] for item in items) == 1


def test_valid_passes_count_done_shots_only_and_reports_are_per_edition(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    session = make_session(db, dog, staff, date(2026, 10, 1))
    add_shot(db, session, 1, passes={"LEFT": (3, 1), "RIGHT": (2, 0)})
    add_shot(db, session, 2, status="FAILED", passes={"LEFT": (5, 0)})  # 실패한 촬영의 통과는 세지 않는다(15.6)
    add_report(db, session, "VET", "FAILED")
    add_report(db, session, "OWNER", "DONE")
    (item,) = _items(client, auth_headers, dog)
    assert item["valid_passes"] == {"LEFT": 3, "RIGHT": 2}
    assert item["reports"] == {"OWNER": "DONE", "VET": "FAILED"}


def test_history_paging(client: TestClient, db: Session, dog, staff, auth_headers) -> None:
    for day in (1, 2, 3):
        make_session(db, dog, staff, date(2026, 10, day))
    page1 = client.get(HISTORY.format(dog.id), params={"page": 1, "size": 2}, headers=auth_headers).json()
    page2 = client.get(HISTORY.format(dog.id), params={"page": 2, "size": 2}, headers=auth_headers).json()
    assert (len(page1["items"]), page1["total"], page1["size"]) == (2, 3, 2)
    assert (len(page2["items"]), page2["page"], page2["total"]) == (1, 2, 3)
    assert [item["measured_on"] for item in page1["items"] + page2["items"]] == [
        "2026-10-03",
        "2026-10-02",
        "2026-10-01",
    ]


@pytest.mark.parametrize("params", [{"page": 0}, {"size": 0}, {"size": 101}])
def test_history_query_rules(client: TestClient, dog, auth_headers, params: dict) -> None:
    response = client.get(HISTORY.format(dog.id), params=params, headers=auth_headers)
    assert response.status_code == 422 and response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_other_institution_dog_and_unknown_dog_are_404(client: TestClient, dog, auth_headers, other_staff) -> None:
    assert client.get(HISTORY.format(dog.id), headers=bearer(other_staff)).status_code == 404
    assert client.get(HISTORY.format(uuid.uuid4()), headers=auth_headers).status_code == 404
    assert client.get(HISTORY.format("not-a-uuid"), headers=auth_headers).status_code == 404


def test_history_needs_token(client: TestClient, dog) -> None:
    assert client.get(HISTORY.format(dog.id)).status_code == 401
