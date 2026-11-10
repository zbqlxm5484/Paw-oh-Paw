"""기관 회차 목록 GET /sessions(BE-33, 명세 15.6). 최신순, 담당자·상태로 거르기, 기관 분리."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models import Staff
from tests.conftest import GOOD_PASSWORD, bearer, password_hash_for
from tests.history_fixtures import add_metric, another_dog, make_session

SESSIONS = "/api/v1/sessions"


def _get(client: TestClient, headers: dict, **params) -> dict:
    response = client.get(SESSIONS, headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _ids(body: dict) -> list[str]:
    return [item["id"] for item in body["items"]]


def _colleague(db: Session, staff, name: str = "동료") -> Staff:
    row = Staff(
        institution_id=staff.institution_id,
        login_id=f"staff-{uuid.uuid4().hex[:8]}",
        password_hash=password_hash_for(GOOD_PASSWORD),
        name=name,
        role="CLIENT",
    )
    db.add(row)
    db.flush()
    return row


def test_list_is_newest_first_across_dogs_with_dog_and_staff(client, db: Session, dog, staff, auth_headers) -> None:
    other = another_dog(db, staff.institution_id, "콩이")
    colleague = _colleague(db, staff)
    first = make_session(db, dog, staff, date(2026, 10, 1))
    same_day_early = make_session(db, other, colleague, date(2026, 10, 20), seq=0)
    same_day_late = make_session(db, dog, staff, date(2026, 10, 20), seq=1, status="MEASURING", model_version=None)
    add_metric(db, first, "rom_stifle", "LH", 31.0)
    add_metric(db, first, "rom_stifle", "RH", 38.2)

    body = _get(client, auth_headers)
    assert _ids(body) == [str(same_day_late.id), str(same_day_early.id), str(first.id)]
    assert (body["total"], body["page"], body["size"]) == (3, 1, 20)
    assert body["items"][2] == {
        "id": str(first.id),
        "measured_on": "2026-10-01",
        "status": "DONE",
        "fail_reason": None,
        "dog": {"id": str(dog.id), "name": "보리"},
        "staff": {"id": str(staff.id), "name": "담당자"},
        "weight_kg": None,
        "model_version": "v1",
        "symmetry_score": 79,
        "completed_at": "2026-10-01T00:00:00Z",
        "created_at": "2026-10-01T00:00:00Z",
    }
    assert body["items"][1]["dog"] == {"id": str(other.id), "name": "콩이"}
    assert body["items"][1]["staff"] == {"id": str(colleague.id), "name": "동료"}
    # 측정 중인 회차는 점수와 끝난 시각이 비어 있다
    assert (body["items"][0]["symmetry_score"], body["items"][0]["completed_at"]) == (None, None)


def test_filter_by_staff_and_status(client, db: Session, dog, staff, auth_headers) -> None:
    colleague = _colleague(db, staff)
    mine_done = make_session(db, dog, staff, date(2026, 10, 1))
    mine_failed = make_session(db, dog, staff, date(2026, 10, 2), status="FAILED", model_version=None)
    theirs_done = make_session(db, dog, colleague, date(2026, 10, 3))
    theirs_failed = make_session(db, dog, colleague, date(2026, 10, 4), status="FAILED", model_version=None)
    mine_failed.fail_reason = "AGGREGATION_FAILED"
    db.flush()

    by_staff = _get(client, auth_headers, staff_id=str(colleague.id))
    assert _ids(by_staff) == [str(theirs_failed.id), str(theirs_done.id)]
    assert by_staff["total"] == 2
    by_status = _get(client, auth_headers, status="FAILED")
    assert _ids(by_status) == [str(theirs_failed.id), str(mine_failed.id)]
    assert by_status["items"][1]["fail_reason"]["code"] == "AGGREGATION_FAILED"
    both = _get(client, auth_headers, staff_id=str(staff.id), status="DONE")
    assert (_ids(both), both["total"]) == ([str(mine_done.id)], 1)
    assert _get(client, auth_headers, staff_id=str(uuid.uuid4()))["items"] == []


def test_paging(client, db: Session, dog, staff, auth_headers) -> None:
    sessions = [make_session(db, dog, staff, date(2026, 10, day)) for day in range(1, 6)]
    page2 = _get(client, auth_headers, page=2, size=2)
    assert _ids(page2) == [str(sessions[2].id), str(sessions[1].id)]
    assert (page2["total"], page2["page"], page2["size"]) == (5, 2, 2)
    assert _get(client, auth_headers, page=4, size=2)["items"] == []


def test_other_institution_and_trashed_dogs_are_left_out(
    client, db: Session, dog, staff, other_staff, auth_headers
) -> None:
    mine = make_session(db, dog, staff, date(2026, 10, 1))
    theirs_dog = another_dog(db, other_staff.institution_id, "남의 개")
    theirs = make_session(db, theirs_dog, other_staff, date(2026, 10, 2))
    trashed_dog = another_dog(db, staff.institution_id, "휴지통")
    make_session(db, trashed_dog, staff, date(2026, 10, 3))
    trashed_dog.deleted_at = datetime.now(UTC)
    db.flush()

    body = _get(client, auth_headers)
    assert (_ids(body), body["total"]) == ([str(mine.id)], 1)
    # 다른 기관의 담당자 ID로 걸러도 그 기관의 회차는 보이지 않는다
    assert _get(client, auth_headers, staff_id=str(other_staff.id))["items"] == []
    assert _ids(_get(client, bearer(other_staff))) == [str(theirs.id)]


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"staff_id": "abc"}, "staff_id"),
        ({"status": "CANCELLED"}, "status"),
        ({"status": "done"}, "status"),
        ({"page": 0}, "page"),
        ({"size": 101}, "size"),
    ],
)
def test_query_rules(client: TestClient, auth_headers, params: dict, field: str) -> None:
    response = client.get(SESSIONS, headers=auth_headers, params=params)
    assert response.status_code == 422
    assert response.json()["error"]["detail"]["fields"][0]["field"] == field


def test_list_needs_a_token(client: TestClient) -> None:
    assert client.get(SESSIONS).status_code == 401


def test_query_count_does_not_grow_with_sessions(client, db: Session, dog, staff, auth_headers) -> None:
    def count() -> int:
        seen: list[str] = []
        connection = db.connection()

        def record(_conn, _cursor, statement: str, _parameters, _context, _many) -> None:
            seen.append(statement)

        event.listen(connection, "before_cursor_execute", record)
        try:
            assert client.get(SESSIONS, headers=auth_headers).status_code == 200
        finally:
            event.remove(connection, "before_cursor_execute", record)
        return len(seen)

    def add(day: int) -> None:
        other = another_dog(db, staff.institution_id, f"개{day}")
        session = make_session(db, other, _colleague(db, staff, f"동료{day}"), date(2026, 10, day))
        add_metric(db, session, "rom_stifle", "LH", 31.0)
        add_metric(db, session, "rom_stifle", "RH", 38.2)

    add(1)
    client.get(SESSIONS, headers=auth_headers)  # 로그인 확인 캐시를 채운다
    few = count()
    for day in range(2, 9):
        add(day)
    assert count() == few
