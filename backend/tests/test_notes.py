"""메모·진료 기록과 수정 이력(12.5 차트 자료, 13.9, 15.11, 17.2 BE-30, v1.36). 방문일과 지우기는 v1.46이다."""

import logging
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.core.dates import today_local
from app.models import DogNote, DogNoteRevision, Staff
from app.services.purge import purge
from app.storage.base import get_storage
from tests.conftest import GOOD_PASSWORD, bearer, password_hash_for
from tests.history_fixtures import another_dog, make_session

API = "/api/v1"
MEMO = {"category": "CAUTION", "body": "입질 있음. 입마개 필요", "important": True}


def _post(client: TestClient, dog, headers: dict, **overrides):
    return client.post(f"{API}/dogs/{dog.id}/notes", json={**MEMO, **overrides}, headers=headers)


def _batch(client: TestClient, dog, headers: dict, notes: list[dict], **extra):
    return client.post(f"{API}/dogs/{dog.id}/notes/batch", json={"notes": notes, **extra}, headers=headers)


def _list(client: TestClient, dog, headers: dict, **params) -> dict:
    response = client.get(f"{API}/dogs/{dog.id}/notes", params=params, headers=headers)
    assert response.status_code == 200
    return response.json()


def _patch(client: TestClient, note_id: str, headers: dict, **changes):
    return client.patch(f"{API}/notes/{note_id}", json=changes, headers=headers)


def _revisions(client: TestClient, note_id: str, headers: dict) -> list[dict]:
    response = client.get(f"{API}/notes/{note_id}/revisions", headers=headers)
    assert response.status_code == 200
    return response.json()["items"]


def _fields(response) -> list[str]:
    return [f["field"] for f in response.json()["error"]["detail"]["fields"]]


def _count(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


@pytest.fixture
def colleague(db: Session, staff) -> Staff:
    """staff와 같은 기관의 다른 담당자."""
    row = Staff(
        institution_id=staff.institution_id,
        login_id="staff9",
        password_hash=password_hash_for(GOOD_PASSWORD),
        name="동료",
        role="CLIENT",
    )
    db.add(row)
    db.flush()
    return row


# ---- 쓰기 ----


def test_post_writes_a_note_by_the_caller(client: TestClient, dog, staff, auth_headers: dict) -> None:
    response = _post(client, dog, auth_headers, body="  입질 있음. 입마개 필요  ")
    assert response.status_code == 201
    body = response.json()
    assert {key: body[key] for key in MEMO} == MEMO  # 앞뒤 공백은 지운다
    assert body["dog_id"] == str(dog.id) and body["session_id"] is None
    assert body["staff"] == {"id": str(staff.id), "name": "담당자"}
    assert body["revision_count"] == 0
    assert body["created_at"] == body["updated_at"]
    assert body["visited_on"] == today_local().isoformat()  # 방문일을 빼면 오늘이다(v1.46)
    assert set(body) == {
        *MEMO,
        "id",
        "dog_id",
        "session_id",
        "visited_on",
        "staff",
        "revision_count",
        "created_at",
        "updated_at",
    }


def test_writer_cannot_be_sent_in_the_request(client: TestClient, dog, staff, colleague, auth_headers: dict) -> None:
    body = _post(client, dog, auth_headers, staff_id=str(colleague.id), staff={"name": "남의 이름"}).json()
    assert body["staff"]["id"] == str(staff.id)


def test_important_defaults_to_false(client: TestClient, dog, auth_headers: dict) -> None:
    response = client.post(
        f"{API}/dogs/{dog.id}/notes", json={"category": "S", "body": "산책 뒤 절뚝임"}, headers=auth_headers
    )
    assert response.status_code == 201 and response.json()["important"] is False


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"category": "MEMO"}, "category"),
        ({"category": None}, "category"),
        ({"body": "   "}, "body"),
        ({"body": "가" * 2001}, "body"),
        ({"body": None}, "body"),
        ({"session_id": "회차아님"}, "session_id"),
    ],
)
def test_input_rules(client: TestClient, db: Session, dog, auth_headers: dict, overrides: dict, field: str) -> None:
    response = _post(client, dog, auth_headers, **overrides)
    assert response.status_code == 422
    assert _fields(response) == [field]
    assert _count(db, DogNote) == 0


def test_body_of_2000_characters_is_accepted(client: TestClient, dog, auth_headers: dict) -> None:
    assert _post(client, dog, auth_headers, body="가" * 2000).status_code == 201


def test_session_id_must_be_a_session_of_the_same_dog(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    mine = make_session(db, dog, staff, date(2026, 10, 20))
    other_dog = another_dog(db, staff.institution_id)
    theirs = make_session(db, other_dog, staff, date(2026, 10, 20))

    ok = _post(client, dog, auth_headers, session_id=str(mine.id))
    assert ok.status_code == 201 and ok.json()["session_id"] == str(mine.id)
    for wrong in (theirs.id, uuid.uuid4()):
        response = _post(client, dog, auth_headers, session_id=str(wrong))
        assert response.status_code == 422 and _fields(response) == ["session_id"]
    assert _count(db, DogNote) == 1


# ---- 묶음 ----


def test_batch_writes_all_with_the_same_time_in_the_sent_order(client: TestClient, dog, auth_headers: dict) -> None:
    soap = [
        {"category": "S", "body": "산책 뒤 오른뒤 절뚝임"},
        {"category": "A", "body": "CCL 부분 파열 의심", "important": True},
        {"category": "P", "body": "2주 뒤 재측정"},
    ]
    response = _batch(client, dog, auth_headers, soap)
    assert response.status_code == 201
    items = response.json()["items"]
    assert [item["category"] for item in items] == ["S", "A", "P"]
    assert len({item["created_at"] for item in items}) == 1
    assert [item["important"] for item in items] == [False, True, False]
    assert len({item["id"] for item in items}) == 3


@pytest.mark.parametrize(
    "notes",
    [
        [],
        [{"category": "S", "body": "하나"}, {"category": "S", "body": "둘"}],  # 같은 분류 두 번
        [{"category": "S", "body": "하나"}, {"category": "O", "body": "   "}],  # 하나가 어긋남
        [{"category": c, "body": "가"} for c in ("S", "O", "A", "P", "CAUTION", "GUARDIAN", "BOOKING", "OTHER", "S")],
    ],
)
def test_batch_saves_nothing_when_any_item_is_wrong(client: TestClient, db: Session, dog, auth_headers, notes) -> None:
    assert _batch(client, dog, auth_headers, notes).status_code == 422
    assert _count(db, DogNote) == 0


def test_batch_takes_one_session_for_all(client: TestClient, db: Session, dog, staff, auth_headers) -> None:
    session = make_session(db, dog, staff, date(2026, 10, 20))
    items = _batch(
        client,
        dog,
        auth_headers,
        [{"category": "S", "body": "가"}, {"category": "O", "body": "나"}],
        session_id=str(session.id),
    ).json()["items"]
    assert {item["session_id"] for item in items} == {str(session.id)}

    wrong = _batch(client, dog, auth_headers, [{"category": "S", "body": "가"}], session_id=str(uuid.uuid4()))
    assert wrong.status_code == 422 and _fields(wrong) == ["session_id"]


# ---- 목록 ----


def test_list_is_newest_first_with_paging(client: TestClient, dog, auth_headers: dict) -> None:
    for index in range(5):
        _post(client, dog, auth_headers, body=f"메모 {index}", category="OTHER")

    first = _list(client, dog, auth_headers, size=2)
    assert [item["body"] for item in first["items"]] == ["메모 4", "메모 3"]
    assert (first["total"], first["page"], first["size"]) == (5, 1, 2)
    last = _list(client, dog, auth_headers, size=2, page=3)
    assert [item["body"] for item in last["items"]] == ["메모 0"]
    assert _list(client, dog, auth_headers)["size"] == 50  # 기본값


def test_list_filters_by_kind_and_session(client: TestClient, db: Session, dog, staff, auth_headers) -> None:
    session = make_session(db, dog, staff, date(2026, 10, 20))
    _post(client, dog, auth_headers, category="CAUTION", body="주의")
    _post(client, dog, auth_headers, category="BOOKING", body="예약")
    _batch(
        client,
        dog,
        auth_headers,
        [{"category": "S", "body": "S"}, {"category": "P", "body": "P"}],
        session_id=str(session.id),
    )

    def bodies(**params) -> set[str]:
        return {item["body"] for item in _list(client, dog, auth_headers, **params)["items"]}

    assert bodies(kind="memo") == {"주의", "예약"}
    assert bodies(kind="chart") == {"S", "P"}
    assert bodies() == {"주의", "예약", "S", "P"}
    assert bodies(session_id=str(session.id)) == {"S", "P"}
    assert bodies(session_id=str(session.id), kind="memo") == set()
    assert _list(client, dog, auth_headers, session_id=str(uuid.uuid4()))["total"] == 0  # 모르는 회차는 빈 목록
    assert _list(client, dog, auth_headers, kind="memo")["total"] == 2  # 개수도 같은 조건


@pytest.mark.parametrize("params", [{"kind": "soap"}, {"size": 0}, {"size": 201}, {"page": 0}, {"session_id": "x"}])
def test_list_query_rules(client: TestClient, dog, auth_headers: dict, params: dict) -> None:
    response = client.get(f"{API}/dogs/{dog.id}/notes", params=params, headers=auth_headers)
    assert response.status_code == 422
    assert _fields(response) == [next(iter(params))]


def test_list_counts_revisions_without_a_query_per_note(client: TestClient, db: Session, dog, auth_headers) -> None:
    """메모 수가 늘어도 목록의 쿼리 수가 같다(15.1 N+1 금지)."""

    def add_edited_note(body: str) -> None:
        note_id = _post(client, dog, auth_headers, body=body).json()["id"]
        _patch(client, note_id, auth_headers, body=body + " (고침)")

    def count_queries() -> int:
        statements: list[str] = []

        def record(conn, cursor, statement, parameters, context, executemany) -> None:
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", record)
        try:
            listed = _list(client, dog, auth_headers)
        finally:
            event.remove(engine, "before_cursor_execute", record)
        assert all(item["revision_count"] == 1 for item in listed["items"])
        return len(statements)

    add_edited_note("하나")
    count_queries()  # 첫 요청은 세션에 없는 행을 읽는 쿼리가 더 있을 수 있다
    one = count_queries()
    for body in ("둘", "셋", "넷"):
        add_edited_note(body)
    assert count_queries() == one


# ---- 고치기와 수정 이력 ----


def test_patch_keeps_the_previous_content_as_a_revision(
    client: TestClient, dog, staff, colleague, auth_headers
) -> None:
    note = _post(client, dog, auth_headers).json()

    edited = _patch(client, note["id"], bearer(colleague), body="입질 있음. 뒷다리 만질 때 특히", important=False)
    assert edited.status_code == 200
    body = edited.json()
    assert body["body"] == "입질 있음. 뒷다리 만질 때 특히" and body["important"] is False
    assert body["category"] == "CAUTION"  # 보내지 않은 것은 그대로
    assert body["revision_count"] == 1
    assert body["staff"]["name"] == "동료"  # 지금 내용을 쓴 사람
    assert body["created_at"] == note["created_at"] and body["updated_at"] >= note["updated_at"]

    (revision,) = _revisions(client, note["id"], auth_headers)
    assert revision["body"] == MEMO["body"] and revision["important"] is True and revision["category"] == "CAUTION"
    assert revision["staff"] == {"id": str(staff.id), "name": "담당자"}  # 그 내용을 쓴 사람(처음 쓴 사람)
    assert set(revision) == {"id", "body", "category", "important", "staff", "revised_at"}


def test_revisions_are_newest_first(client: TestClient, dog, auth_headers: dict) -> None:
    note_id = _post(client, dog, auth_headers, body="첫째").json()["id"]
    _patch(client, note_id, auth_headers, body="둘째")
    last = _patch(client, note_id, auth_headers, body="셋째").json()
    assert last["revision_count"] == 2
    assert [item["body"] for item in _revisions(client, note_id, auth_headers)] == ["둘째", "첫째"]
    assert _list(client, dog, auth_headers)["items"][0]["body"] == "셋째"


def test_patch_without_a_real_change_adds_no_revision(
    client: TestClient, db: Session, dog, colleague, auth_headers
) -> None:
    note = _post(client, dog, auth_headers).json()
    for changes in ({}, {"body": MEMO["body"]}, {"important": True, "category": "CAUTION"}):
        same = _patch(client, note["id"], bearer(colleague), **changes)
        assert same.status_code == 200
        assert same.json()["revision_count"] == 0
        assert same.json()["staff"]["name"] == "담당자"  # 고친 것이 없으니 쓴 사람도 그대로
    assert _count(db, DogNoteRevision) == 0
    assert _revisions(client, note["id"], auth_headers) == []


def test_category_changes_only_within_the_same_kind(client: TestClient, db: Session, dog, auth_headers) -> None:
    memo_id = _post(client, dog, auth_headers, category="CAUTION").json()["id"]
    chart_id = _post(client, dog, auth_headers, category="S").json()["id"]

    assert _patch(client, memo_id, auth_headers, category="GUARDIAN").json()["category"] == "GUARDIAN"
    assert _patch(client, chart_id, auth_headers, category="O").json()["category"] == "O"
    for note_id, category in ((memo_id, "S"), (chart_id, "OTHER")):
        response = _patch(client, note_id, auth_headers, category=category, body="바꾸려던 내용")
        assert response.status_code == 422 and _fields(response) == ["category"]
    assert _count(db, DogNoteRevision) == 2  # 막힌 요청은 이력도 본문도 남기지 않았다
    assert "바꾸려던 내용" not in {item["body"] for item in _list(client, dog, auth_headers)["items"]}


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"body": None}, "body"),
        ({"body": "  "}, "body"),
        ({"body": "가" * 2001}, "body"),
        ({"category": None}, "category"),
        ({"category": "X"}, "category"),
        ({"important": None}, "important"),
    ],
)
def test_patch_input_rules(client: TestClient, dog, auth_headers: dict, changes: dict, field: str) -> None:
    note_id = _post(client, dog, auth_headers).json()["id"]
    response = _patch(client, note_id, auth_headers, **changes)
    assert response.status_code == 422 and _fields(response) == [field]


def test_session_id_cannot_be_changed(client: TestClient, db: Session, dog, staff, auth_headers) -> None:
    session = make_session(db, dog, staff, date(2026, 10, 20))
    note_id = _post(client, dog, auth_headers).json()["id"]
    body = _patch(client, note_id, auth_headers, session_id=str(session.id)).json()
    assert body["session_id"] is None and body["revision_count"] == 0


# ---- 방문일(v1.46) ----


def test_visit_date_can_be_a_past_day_and_orders_the_list(client: TestClient, dog, auth_headers: dict) -> None:
    """지난 날짜로 쓰면 목록에서 그 날짜 자리에 온다. 순서는 방문일 → 쓴 시각이다."""
    today = today_local()
    _post(client, dog, auth_headers, body="오늘 첫 메모", category="OTHER")
    past = _post(
        client, dog, auth_headers, body="지난주 방문", category="S", visited_on=(today - timedelta(days=7)).isoformat()
    )
    assert past.status_code == 201 and past.json()["visited_on"] == (today - timedelta(days=7)).isoformat()
    yesterday = (today - timedelta(days=1)).isoformat()
    _post(client, dog, auth_headers, body="어제 방문", category="S", visited_on=yesterday)
    _post(client, dog, auth_headers, body="오늘 둘째 메모", category="OTHER", visited_on=today.isoformat())
    _post(client, dog, auth_headers, body="날짜 없이", category="OTHER", visited_on=None)

    listed = [item["body"] for item in _list(client, dog, auth_headers)["items"]]
    assert listed == ["날짜 없이", "오늘 둘째 메모", "오늘 첫 메모", "어제 방문", "지난주 방문"]


def test_future_visit_date_is_422(client: TestClient, db: Session, dog, auth_headers: dict) -> None:
    tomorrow = (today_local() + timedelta(days=1)).isoformat()
    single = _post(client, dog, auth_headers, visited_on=tomorrow)
    assert single.status_code == 422 and _fields(single) == ["visited_on"]
    batch = _batch(client, dog, auth_headers, [{"category": "S", "body": "가"}], visited_on=tomorrow)
    assert batch.status_code == 422 and _fields(batch) == ["visited_on"]
    assert _post(client, dog, auth_headers, visited_on="지난주").status_code == 422
    assert _count(db, DogNote) == 0


@pytest.mark.parametrize(
    "value", [0, 86400, -86400, "0", "2026-11-01T00:00:00Z", "2026-11-01T00:00:00", "20261101", ""]
)
def test_visit_date_takes_only_a_plain_date(client: TestClient, db: Session, dog, auth_headers, value) -> None:
    """숫자(1970년부터의 초로 읽힌다)나 시각이 붙은 값은 날짜로 받지 않는다(13.9)."""
    single = _post(client, dog, auth_headers, visited_on=value)
    assert single.status_code == 422 and _fields(single) == ["visited_on"]
    batch = _batch(client, dog, auth_headers, [{"category": "S", "body": "가"}], visited_on=value)
    assert batch.status_code == 422 and _fields(batch) == ["visited_on"]
    assert _count(db, DogNote) == 0


def test_today_is_the_korean_date(client: TestClient, dog, auth_headers, monkeypatch: pytest.MonkeyPatch) -> None:
    """UTC로는 11-10 15:30이어도 한국은 11-11 00:30이다. 기본값과 미래 검사가 한국 날짜를 쓴다."""

    class _Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 10, 15, 30, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr("app.core.dates.datetime", _Clock)
    assert _post(client, dog, auth_headers).json()["visited_on"] == "2026-11-11"
    assert _post(client, dog, auth_headers, visited_on="2026-11-11").status_code == 201
    assert _post(client, dog, auth_headers, visited_on="2026-11-12").status_code == 422


def test_batch_takes_one_visit_date_for_all(client: TestClient, dog, auth_headers: dict) -> None:
    day = (today_local() - timedelta(days=3)).isoformat()
    soap = [{"category": "S", "body": "가", "visited_on": "2020-01-01"}, {"category": "O", "body": "나"}]
    response = _batch(client, dog, auth_headers, soap, visited_on=day)
    assert response.status_code == 201
    assert [item["visited_on"] for item in response.json()["items"]] == [day, day]  # 건마다 보낸 날짜는 보지 않는다
    today_batch = _batch(client, dog, auth_headers, [{"category": "A", "body": "다"}]).json()["items"]
    assert today_batch[0]["visited_on"] == today_local().isoformat()


def test_visit_date_cannot_be_changed(client: TestClient, dog, auth_headers: dict) -> None:
    day = (today_local() - timedelta(days=3)).isoformat()
    note_id = _post(client, dog, auth_headers, visited_on=day).json()["id"]
    body = _patch(client, note_id, auth_headers, visited_on="2020-01-01").json()
    assert body["visited_on"] == day and body["revision_count"] == 0
    edited = _patch(client, note_id, auth_headers, body="고친 내용", visited_on="2020-01-01").json()
    assert edited["visited_on"] == day and edited["revision_count"] == 1


# ---- 지우기(v1.46) ----


def _delete(client: TestClient, note_id: str, headers: dict):
    return client.delete(f"{API}/notes/{note_id}", headers=headers)


def test_delete_removes_the_note_and_its_revisions(client: TestClient, db: Session, dog, auth_headers) -> None:
    kept_id = _post(client, dog, auth_headers, body="남길 메모").json()["id"]
    _patch(client, kept_id, auth_headers, body="남길 메모 (고침)")
    note_id = _post(client, dog, auth_headers, body="잘못 쓴 메모").json()["id"]
    _patch(client, note_id, auth_headers, body="잘못 쓴 메모 (고침)")
    _patch(client, note_id, auth_headers, important=False)
    assert (_count(db, DogNote), _count(db, DogNoteRevision)) == (2, 3)

    response = _delete(client, note_id, auth_headers)
    assert response.status_code == 204 and response.content == b""
    assert (_count(db, DogNote), _count(db, DogNoteRevision)) == (1, 1)  # 다른 메모와 그 이력은 그대로다
    assert [item["id"] for item in _list(client, dog, auth_headers)["items"]] == [kept_id]
    assert len(_revisions(client, kept_id, auth_headers)) == 1

    assert _delete(client, note_id, auth_headers).status_code == 404  # 이미 없다
    assert _patch(client, note_id, auth_headers, body="지운 뒤 고치기").status_code == 404
    assert client.get(f"{API}/notes/{note_id}/revisions", headers=auth_headers).status_code == 404


def _locks_and_deletes(db: Session, call) -> list[str]:
    """call이 도는 동안 나간 SQL 중 잠금(FOR UPDATE)과 DELETE·INSERT가 건드린 테이블을 순서대로 돌려준다."""
    seen: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany) -> None:
        text = " ".join(statement.split())
        if "FOR UPDATE" in text:
            seen.append("lock " + text.split(" FROM ")[1].split()[0])
        elif text.startswith("DELETE FROM "):
            seen.append("delete " + text.split()[2])
        elif text.startswith("INSERT INTO "):
            seen.append("insert " + text.split()[2])

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        call()
    finally:
        event.remove(engine, "before_cursor_execute", record)
    return seen


def test_edit_and_delete_lock_the_dog_before_the_note(client: TestClient, db: Session, dog, auth_headers) -> None:
    """자료 파기와 같은 순서로 잠근다(12.4: 반려견 → 그 아래). 메모 행만 잠그면 파기와 서로 기다리다 멈춘다."""
    note_id = _post(client, dog, auth_headers).json()["id"]
    edited = _locks_and_deletes(db, lambda: _patch(client, note_id, auth_headers, body="고친 내용"))
    assert edited == ["lock dog", "lock dog_note", "insert dog_note_revision"]
    deleted = _locks_and_deletes(db, lambda: _delete(client, note_id, auth_headers))
    assert deleted == ["lock dog", "lock dog_note", "delete dog_note_revision", "delete dog_note"]


def test_delete_takes_one_of_a_batch(client: TestClient, dog, auth_headers: dict) -> None:
    soap = [{"category": "S", "body": "가"}, {"category": "O", "body": "나"}, {"category": "P", "body": "다"}]
    items = _batch(client, dog, auth_headers, soap).json()["items"]
    assert _delete(client, items[1]["id"], auth_headers).status_code == 204
    assert sorted(item["category"] for item in _list(client, dog, auth_headers)["items"]) == ["P", "S"]


def test_deleting_the_important_note_drops_the_home_badge(client: TestClient, dog, auth_headers: dict) -> None:
    note_id = _post(client, dog, auth_headers).json()["id"]  # MEMO는 중요 표시가 켜져 있다
    codes = [badge["code"] for badge in client.get(f"{API}/dogs/{dog.id}", headers=auth_headers).json()["badges"]]
    assert codes == ["IMPORTANT_NOTE"]

    assert _delete(client, note_id, auth_headers).status_code == 204
    detail = client.get(f"{API}/dogs/{dog.id}", headers=auth_headers).json()
    assert detail["badges"] == [] and detail["changes"] == []


def test_delete_is_404_for_others_and_logs_no_body(
    client: TestClient, db: Session, dog, staff, auth_headers, other_staff, caplog
) -> None:
    note_id = _post(client, dog, auth_headers, body="약 알레르기 있음").json()["id"]
    assert _delete(client, note_id, bearer(other_staff)).status_code == 404
    assert _delete(client, str(uuid.uuid4()), auth_headers).status_code == 404
    assert client.delete(f"{API}/notes/{note_id}").status_code == 401
    assert client.delete(f"{API}/dogs/{dog.id}", headers=auth_headers).status_code == 204  # 휴지통
    assert _delete(client, note_id, auth_headers).status_code == 404
    assert _count(db, DogNote) == 1

    assert client.post(f"{API}/dogs/{dog.id}/restore", headers=auth_headers).status_code == 200
    with caplog.at_level(logging.DEBUG):
        assert _delete(client, note_id, auth_headers).status_code == 204
    logged = [record.getMessage() for record in caplog.records]
    assert f"dog note deleted note={note_id} staff={staff.id}" in logged
    assert "알레르기" not in "\n".join(logged)
    assert _count(db, DogNote) == 0


# ---- 기관 분리, 휴지통, 로그 ----


def test_other_institution_sees_404_everywhere(client: TestClient, db: Session, dog, auth_headers, other_staff) -> None:
    note_id = _post(client, dog, auth_headers).json()["id"]
    _patch(client, note_id, auth_headers, body="고친 내용")
    other = bearer(other_staff)

    assert client.get(f"{API}/dogs/{dog.id}/notes", headers=other).status_code == 404
    assert _post(client, dog, other).status_code == 404
    assert _batch(client, dog, other, [{"category": "S", "body": "가"}]).status_code == 404
    assert _patch(client, note_id, other, body="남의 것 고치기").status_code == 404
    assert client.get(f"{API}/notes/{note_id}/revisions", headers=other).status_code == 404
    assert _patch(client, str(uuid.uuid4()), auth_headers, body="없는 메모").status_code == 404
    assert client.get(f"{API}/notes/{uuid.uuid4()}/revisions", headers=auth_headers).status_code == 404

    assert _count(db, DogNote) == 1 and _count(db, DogNoteRevision) == 1
    assert _list(client, dog, auth_headers)["items"][0]["body"] == "고친 내용"


def test_notes_of_a_trashed_dog_are_404(client: TestClient, dog, auth_headers: dict) -> None:
    note_id = _post(client, dog, auth_headers).json()["id"]
    assert client.delete(f"{API}/dogs/{dog.id}", headers=auth_headers).status_code == 204

    assert client.get(f"{API}/dogs/{dog.id}/notes", headers=auth_headers).status_code == 404
    assert _post(client, dog, auth_headers).status_code == 404
    assert _patch(client, note_id, auth_headers, body="휴지통에서 고치기").status_code == 404
    assert client.get(f"{API}/notes/{note_id}/revisions", headers=auth_headers).status_code == 404

    assert client.post(f"{API}/dogs/{dog.id}/restore", headers=auth_headers).status_code == 200
    assert _list(client, dog, auth_headers)["total"] == 1  # 복원하면 그대로 돌아온다


def test_notes_need_a_token(client: TestClient, dog) -> None:
    assert client.get(f"{API}/dogs/{dog.id}/notes").status_code == 401
    assert client.post(f"{API}/dogs/{dog.id}/notes", json=MEMO).status_code == 401
    assert client.patch(f"{API}/notes/{uuid.uuid4()}", json={"body": "가"}).status_code == 401
    assert client.get(f"{API}/notes/{uuid.uuid4()}/revisions").status_code == 401


def test_note_bodies_are_not_in_the_log(client: TestClient, dog, auth_headers, caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        note_id = _post(client, dog, auth_headers, body="약 알레르기 있음").json()["id"]
        _patch(client, note_id, auth_headers, body="페니실린 알레르기")
        _batch(client, dog, auth_headers, [{"category": "A", "body": "슬개골 탈구 의심"}])
        _list(client, dog, auth_headers)
        _revisions(client, note_id, auth_headers)
    logged = "\n".join(record.getMessage() for record in caplog.records)
    for secret in ("알레르기", "페니실린", "슬개골"):
        assert secret not in logged


# ---- 측정 취소와 파기(12.5 삭제 순서) ----


def test_cancelling_the_session_keeps_the_note_and_drops_the_link(client: TestClient, dog, auth_headers: dict) -> None:
    session = client.post(f"{API}/dogs/{dog.id}/sessions", json={}, headers=auth_headers).json()
    note = _post(client, dog, auth_headers, category="S", body="측정 전 문진", session_id=session["id"]).json()
    assert client.delete(f"{API}/sessions/{session['id']}", headers=auth_headers).status_code == 204

    (kept,) = _list(client, dog, auth_headers)["items"]
    assert kept["id"] == note["id"] and kept["session_id"] is None
    assert kept["updated_at"] == note["updated_at"] and kept["revision_count"] == 0  # 고친 것이 아니다


def test_purge_counts_and_deletes_notes_and_revisions(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    session = make_session(db, dog, staff, date(2026, 10, 20))
    note_id = _post(client, dog, auth_headers, session_id=str(session.id)).json()["id"]
    _patch(client, note_id, auth_headers, body="고친 내용")
    _post(client, dog, auth_headers, category="OTHER", body="다른 메모")
    expected = 1 + 1 + 2 + 1  # 반려견 + 회차 + 메모 둘 + 수정 이력 하나

    counted = purge(db, get_storage(), "DOG", institution_id=dog.institution_id, target_id=dog.id)
    assert counted.rows == expected
    done = purge(db, get_storage(), "DOG", institution_id=dog.institution_id, target_id=dog.id, dry_run=False)
    assert done.rows == expected
    assert _count(db, DogNote) == 0 and _count(db, DogNoteRevision) == 0
