"""기관의 그날 기록(12.5 그날 기록, 15.11 GET /daily-records, 17.2 BE-35, v1.46)."""

import logging
import re
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.dates import today_local
from tests.conftest import bearer
from tests.history_fixtures import another_dog, make_session

API = "/api/v1"
URL = f"{API}/daily-records"
AUTH_QUERY = re.compile(r"SELECT\s+(institution|staff)\.")


def _get(client: TestClient, headers: dict, **params) -> dict:
    response = client.get(URL, params=params, headers=headers)
    assert response.status_code == 200
    return response.json()


def _by_id(item: dict) -> str:
    return item["id"]


def _vital(client: TestClient, dog, headers: dict, day: date, **values) -> dict:
    response = client.put(f"{API}/dogs/{dog.id}/vitals/{day.isoformat()}", json=values, headers=headers)
    assert response.status_code == 200
    return response.json()


def _note(client: TestClient, dog, headers: dict, body: str, category: str = "OTHER", **extra) -> dict:
    response = client.post(
        f"{API}/dogs/{dog.id}/notes", json={"category": category, "body": body, **extra}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


def test_gives_the_vitals_notes_and_sessions_of_that_day(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    today, yesterday = today_local(), today_local() - timedelta(days=1)
    other = another_dog(db, staff.institution_id)
    # 오늘: 보리 바이탈·메모·회차, 콩이 바이탈·진료 기록·회차. 어제: 보리 바이탈·회차, 콩이의 어제 방문 기록(오늘 씀)
    first_vital = _vital(client, dog, auth_headers, today, heart_rate=90)
    second_vital = _vital(client, other, auth_headers, today, weight_kg=6.0)
    old_vital = _vital(client, dog, auth_headers, yesterday, heart_rate=80)
    first_note = _note(client, dog, auth_headers, "오늘 메모")
    second_note = _note(client, other, auth_headers, "오늘 진료 기록", category="S")
    late_note = _note(
        client, other, auth_headers, "어제 방문을 오늘 적음", category="S", visited_on=yesterday.isoformat()
    )
    done = make_session(db, dog, staff, today)
    measuring = make_session(db, other, staff, today, status="MEASURING", seq=1)
    old_session = make_session(db, dog, staff, yesterday)

    body = _get(client, auth_headers)
    assert set(body) == {"date", "vitals", "notes", "sessions"}
    assert body["date"] == today.isoformat()  # date를 빼면 오늘이다
    # VitalOut 그대로다. 시험은 한 트랜잭션이라 적은 시각이 같아 순서를 보지 않는다
    assert sorted(body["vitals"], key=_by_id) == sorted([first_vital, second_vital], key=_by_id)
    assert {item["dog_id"] for item in body["vitals"]} == {str(dog.id), str(other.id)}
    assert body["notes"] == [first_note, second_note]  # 쓴 순서, NoteOut 그대로
    assert [(item["id"], item["status"]) for item in body["sessions"]] == [
        (str(done.id), "DONE"),
        (str(measuring.id), "MEASURING"),
    ]
    assert body["sessions"][0]["dog"] == {"id": str(dog.id), "name": "보리"}
    assert set(body["sessions"][0]) == {
        "id",
        "measured_on",
        "status",
        "fail_reason",
        "dog",
        "staff",
        "weight_kg",
        "model_version",
        "symmetry_score",
        "completed_at",
        "created_at",
    }

    past = _get(client, auth_headers, date=yesterday.isoformat())
    assert past["date"] == yesterday.isoformat()
    assert past["vitals"] == [old_vital]
    assert past["notes"] == [late_note]  # 방문일로 거른다. 쓴 날이 아니다
    assert [item["id"] for item in past["sessions"]] == [str(old_session.id)]


def test_empty_day_and_future_day_are_empty_lists(client: TestClient, dog, auth_headers: dict) -> None:
    _vital(client, dog, auth_headers, today_local(), heart_rate=90)
    for day in (date(2020, 1, 1), today_local() + timedelta(days=30)):
        body = _get(client, auth_headers, date=day.isoformat())
        assert body == {"date": day.isoformat(), "vitals": [], "notes": [], "sessions": []}


def test_other_institutions_and_trashed_dogs_are_left_out(
    client: TestClient, db: Session, dog, staff, auth_headers, other_staff
) -> None:
    today = today_local()
    theirs = another_dog(db, other_staff.institution_id, name="남의 개")
    other = bearer(other_staff)
    _vital(client, theirs, other, today, heart_rate=70)
    _note(client, theirs, other, "다른 기관의 메모")
    make_session(db, theirs, other_staff, today)
    _vital(client, dog, auth_headers, today, heart_rate=90)
    _note(client, dog, auth_headers, "우리 기관의 메모")
    make_session(db, dog, staff, today)

    mine = _get(client, auth_headers)
    assert [item["dog_id"] for item in mine["vitals"]] == [str(dog.id)]
    assert [item["body"] for item in mine["notes"]] == ["우리 기관의 메모"]
    assert [item["dog"]["name"] for item in mine["sessions"]] == ["보리"]
    their_view = _get(client, other)
    assert [item["dog_id"] for item in their_view["vitals"]] == [str(theirs.id)]
    assert [item["body"] for item in their_view["notes"]] == ["다른 기관의 메모"]
    assert [item["dog"]["name"] for item in their_view["sessions"]] == ["남의 개"]

    assert client.delete(f"{API}/dogs/{dog.id}", headers=auth_headers).status_code == 204  # 휴지통
    assert _get(client, auth_headers) == {"date": today.isoformat(), "vitals": [], "notes": [], "sessions": []}
    assert client.post(f"{API}/dogs/{dog.id}/restore", headers=auth_headers).status_code == 200
    assert len(_get(client, auth_headers)["notes"]) == 1  # 복원하면 돌아온다


def test_deleted_records_disappear(client: TestClient, dog, auth_headers: dict) -> None:
    today = today_local()
    _vital(client, dog, auth_headers, today, heart_rate=90)
    note = _note(client, dog, auth_headers, "지울 메모")
    assert client.delete(f"{API}/dogs/{dog.id}/vitals/{today.isoformat()}", headers=auth_headers).status_code == 204
    assert client.delete(f"{API}/notes/{note['id']}", headers=auth_headers).status_code == 204
    body = _get(client, auth_headers)
    assert body["vitals"] == [] and body["notes"] == []


def test_edited_note_carries_its_revision_count(client: TestClient, dog, auth_headers: dict) -> None:
    note = _note(client, dog, auth_headers, "처음 내용")
    assert (
        client.patch(f"{API}/notes/{note['id']}", json={"body": "고친 내용"}, headers=auth_headers).status_code == 200
    )
    (listed,) = _get(client, auth_headers)["notes"]
    assert (listed["body"], listed["revision_count"]) == ("고친 내용", 1)


def test_query_count_does_not_grow_with_dogs(client: TestClient, db: Session, dog, staff, auth_headers) -> None:
    """반려견·기록이 늘어도 쿼리 수가 같다(15.1 N+1 금지)."""
    today = today_local()

    def fill(target, seq: int) -> None:
        _vital(client, target, auth_headers, today, heart_rate=90)
        note = _note(client, target, auth_headers, "메모")
        client.patch(f"{API}/notes/{note['id']}", json={"body": "메모 (고침)"}, headers=auth_headers)
        make_session(db, target, staff, today, seq=seq)

    def count_queries() -> tuple[int, int]:
        statements: list[str] = []

        def record(conn, cursor, statement, parameters, context, executemany) -> None:
            # 로그인 확인이 기관·담당자를 다시 읽는 쿼리는 이 API의 것이 아니라 세지 않는다
            if statement.lstrip().upper().startswith("SELECT") and not AUTH_QUERY.match(statement.lstrip()):
                statements.append(statement)

        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", record)
        try:
            body = _get(client, auth_headers)
        finally:
            event.remove(engine, "before_cursor_execute", record)
        return len(statements), len(body["notes"])

    fill(dog, 0)
    count_queries()  # 첫 요청은 세션에 없는 행을 읽는 쿼리가 더 있을 수 있다
    one, notes = count_queries()
    assert notes == 1 and one == 5  # 바이탈, 메모, 수정 횟수, 회차, 대칭 점수
    for index in range(3):
        fill(another_dog(db, staff.institution_id, name=f"개 {index}"), index + 1)
    many, notes = count_queries()
    assert notes == 4 and many == one


def test_date_rules_token_and_contract(client: TestClient, db: Session, staff, dog, auth_headers: dict) -> None:
    for bad in ("어제", "2026-13-01", "20261110"):
        response = client.get(URL, params={"date": bad}, headers=auth_headers)
        assert response.status_code == 422, bad
        assert [item["field"] for item in response.json()["error"]["detail"]["fields"]] == ["date"]
    assert client.get(URL).status_code == 401

    staff.institution.contract_ends_at = today_local() - timedelta(days=1)
    db.flush()
    expired = client.get(URL, headers=auth_headers)
    assert expired.status_code == 403 and expired.json()["error"]["code"] == "CONTRACT_EXPIRED"


def test_note_bodies_are_not_in_the_log(client: TestClient, dog, auth_headers, caplog) -> None:
    _note(client, dog, auth_headers, "약 알레르기 있음")
    with caplog.at_level(logging.DEBUG):
        _get(client, auth_headers)
    assert "알레르기" not in "\n".join(record.getMessage() for record in caplog.records)
