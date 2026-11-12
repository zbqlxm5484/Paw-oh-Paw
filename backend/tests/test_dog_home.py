"""홈 배지·최근 변동·가장 최근 대칭 점수(BE-32, 명세 12.5 홈 배지·변동, 15.3, 15.5)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.dates import local_zone, today_local
from app.models import DogHistory, DogNote
from tests.conftest import bearer
from tests.history_fixtures import add_metric, add_shot, another_dog, make_session

DOGS = "/api/v1/dogs"
NOTE_BODY = "오른쪽 뒷다리를 만지면 싫어함"


def _ago(days: int) -> date:
    return today_local() - timedelta(days=days)


def _items(client: TestClient, headers: dict, **params) -> list[dict]:
    response = client.get(DOGS, headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _one(client: TestClient, headers: dict, dog, **params) -> dict:
    return next(item for item in _items(client, headers, **params) if item["id"] == str(dog.id))


def _codes(item: dict) -> list[str]:
    return [change["code"] for change in item["changes"]]


def _history(db: Session, dog, staff, kind: str, title: str, on: date, *, site: str | None = "RH") -> DogHistory:
    row = DogHistory(dog_id=dog.id, occurred_on=on, kind=kind, title=title, site=site, staff_id=staff.id)
    db.add(row)
    db.flush()
    return row


def _note(db: Session, dog, staff, on: date, *, important: bool = True, category: str = "CAUTION") -> DogNote:
    """그 날짜(한국 날짜)의 낮 12시에 쓴 메모."""
    written = datetime.combine(on, datetime.min.time(), tzinfo=local_zone()) + timedelta(hours=12)
    row = DogNote(
        dog_id=dog.id,
        category=category,
        body=NOTE_BODY,
        important=important,
        staff_id=staff.id,
        created_at=written.astimezone(UTC),
        updated_at=written.astimezone(UTC),
    )
    db.add(row)
    db.flush()
    return row


def _scored(db: Session, dog, staff, on: date, right: float, *, seq: int = 0, valid: int = 8):
    """무릎 가동 범위 왼쪽 50, 오른쪽 right인 DONE 회차. 유효 통과가 있는 촬영 하나를 붙인다."""
    session = make_session(db, dog, staff, on, seq=seq)
    add_metric(db, session, "rom_stifle", "LH", 50.0)
    add_metric(db, session, "rom_stifle", "RH", right)
    add_shot(db, session, 1, passes={"LEFT": (valid, 0), "RIGHT": (valid, 0)})
    return session


# 왼쪽 50일 때 오른쪽 값 → 대칭 점수: 50 → 100, 55.26 → 90, 57 → 87, 58 → 85
RIGHT_FOR = {100: 50.0, 90: 55.26, 88: 56.38, 87: 56.95, 85: 58.1}


# ---- 배지 ----


def test_new_dog_has_no_badges_changes_or_score(client: TestClient, dog, auth_headers) -> None:
    item = _one(client, auth_headers, dog)
    assert (item["badges"], item["changes"], item["last_symmetry"]) == ([], [], None)


def test_latest_surgery_is_the_badge_and_hides_the_diagnosis(client, db: Session, dog, staff, auth_headers) -> None:
    _history(db, dog, staff, "DIAGNOSIS", "앞십자인대 파열", _ago(100))
    _history(db, dog, staff, "SURGERY", "TPLO", _ago(90), site="LH")
    _history(db, dog, staff, "SURGERY", "TPLO 재수술", _ago(71))
    _history(db, dog, staff, "REHAB", "재활 시작", _ago(60))
    assert _one(client, auth_headers, dog)["badges"] == [
        {"code": "SURGERY", "title": "TPLO 재수술", "site": "RH", "on": _ago(71).isoformat()}
    ]


def test_diagnosis_is_the_badge_only_without_a_surgery(client, db: Session, dog, staff, auth_headers) -> None:
    _history(db, dog, staff, "DIAGNOSIS", "슬개골 탈구", _ago(40), site=None)
    _history(db, dog, staff, "DIAGNOSIS", "앞십자인대 파열", _ago(10))
    _history(db, dog, staff, "REHAB", "재활 시작", _ago(5))
    assert _one(client, auth_headers, dog)["badges"] == [
        {"code": "DIAGNOSIS", "title": "앞십자인대 파열", "site": "RH", "on": _ago(10).isoformat()}
    ]


def test_last_surgery_and_last_diagnosis_come_together(client, db: Session, dog, staff, auth_headers) -> None:
    """배지는 수술 하나만 주지만 last_surgery·last_diagnosis는 둘 다 준다(v1.41)."""
    assert (_one(client, auth_headers, dog)["last_surgery"], _one(client, auth_headers, dog)["last_diagnosis"]) == (
        None,
        None,
    )
    _history(db, dog, staff, "DIAGNOSIS", "슬개골 탈구", _ago(120), site=None)
    _history(db, dog, staff, "DIAGNOSIS", "앞십자인대 파열", _ago(100))
    _history(db, dog, staff, "SURGERY", "TPLO", _ago(90), site="LH")
    _history(db, dog, staff, "REHAB", "재활 시작", _ago(60))

    item = _one(client, auth_headers, dog)
    assert item["last_surgery"] == {"occurred_on": _ago(90).isoformat(), "title": "TPLO", "site": "LH"}
    assert item["last_diagnosis"] == {"occurred_on": _ago(100).isoformat(), "title": "앞십자인대 파열", "site": "RH"}
    assert [badge["code"] for badge in item["badges"]] == ["SURGERY"]  # 배지 규칙은 그대로다
    detail = client.get(f"{DOGS}/{dog.id}", headers=auth_headers).json()
    assert (detail["last_surgery"], detail["last_diagnosis"]) == (item["last_surgery"], item["last_diagnosis"])


def test_search_finds_dogs_by_history_title(client, db: Session, dog, staff, other_staff, auth_headers) -> None:
    """q는 병명·수술명으로도 찾는다(15.5, v1.41). 다른 기관의 이력으로는 찾지 않는다."""
    from decimal import Decimal

    from app.models import Dog

    _history(db, dog, staff, "SURGERY", "TPLO (경골 고원 수평화 절골술)", _ago(90))
    _history(db, dog, staff, "DIAGNOSIS", "앞십자인대 파열", _ago(100))
    plain = Dog(
        institution_id=staff.institution_id, name="두부", breed="말티즈", weight_kg=Decimal("3.2"), size_class="SMALL"
    )
    foreign = Dog(
        institution_id=other_staff.institution_id,
        name="콩이",
        breed="말티즈",
        weight_kg=Decimal("3.2"),
        size_class="SMALL",
    )
    db.add_all([plain, foreign])
    db.flush()
    _history(db, foreign, other_staff, "SURGERY", "TPLO", _ago(10))

    def names(q: str) -> list[str]:
        body = client.get(DOGS, params={"q": q}, headers=auth_headers).json()
        assert body["total"] == len(body["items"])
        return [item["name"] for item in body["items"]]

    assert names("tplo") == ["보리"]  # 대소문자 무시, 한 반려견은 한 번만
    assert names("인대") == ["보리"]
    assert names("두부") == ["두부"]  # 이름 검색은 그대로
    assert names("100%") == []  # %는 글자 그대로 찾는다


def test_important_note_badge_has_the_date_but_never_the_body(client, db: Session, dog, staff, auth_headers) -> None:
    _note(db, dog, staff, _ago(200))
    _note(db, dog, staff, _ago(30), category="A")
    _note(db, dog, staff, _ago(1), important=False)
    _history(db, dog, staff, "SURGERY", "TPLO", _ago(71))
    response = client.get(DOGS, headers=auth_headers)
    item = next(row for row in response.json()["items"] if row["id"] == str(dog.id))
    assert item["badges"] == [
        {"code": "SURGERY", "title": "TPLO", "site": "RH", "on": _ago(71).isoformat()},
        {"code": "IMPORTANT_NOTE", "title": None, "site": None, "on": _ago(30).isoformat()},
    ]
    assert NOTE_BODY not in response.text
    # 30일 전 메모는 배지에는 있지만 최근 변동은 아니다
    assert item["changes"] == []


# ---- 변동: 수술, 중요 메모 ----


@pytest.mark.parametrize(("days_ago", "expected"), [(0, True), (7, True), (8, False)])
def test_surgery_within_the_window_is_a_change(
    client, db: Session, dog, staff, auth_headers, days_ago: int, expected: bool
) -> None:
    _history(db, dog, staff, "SURGERY", "TPLO", _ago(days_ago))
    changes = _one(client, auth_headers, dog)["changes"]
    wanted = [{"code": "SURGERY_ADDED", "on": _ago(days_ago).isoformat(), "delta": None}] if expected else []
    assert changes == wanted


def test_diagnosis_and_rehab_are_not_changes(client, db: Session, dog, staff, auth_headers) -> None:
    _history(db, dog, staff, "DIAGNOSIS", "앞십자인대 파열", _ago(1))
    _history(db, dog, staff, "REHAB", "재활 시작", _ago(0))
    assert _one(client, auth_headers, dog)["changes"] == []


@pytest.mark.parametrize(("days_ago", "expected"), [(0, True), (7, True), (8, False)])
def test_important_note_within_the_window_is_a_change(
    client, db: Session, dog, staff, auth_headers, days_ago: int, expected: bool
) -> None:
    _note(db, dog, staff, _ago(days_ago))
    _note(db, dog, staff, _ago(0), important=False)
    assert _codes(_one(client, auth_headers, dog)) == (["IMPORTANT_NOTE"] if expected else [])


# ---- 변동: 재촬영 ----


def test_failed_latest_session_needs_a_reshoot(client, db: Session, dog, staff, auth_headers) -> None:
    make_session(db, dog, staff, _ago(2), status="FAILED", model_version=None)
    assert _one(client, auth_headers, dog)["changes"] == [
        {"code": "RESHOOT_NEEDED", "on": _ago(2).isoformat(), "delta": None}
    ]


def test_done_session_without_valid_passes_needs_a_reshoot(client, db: Session, dog, staff, auth_headers) -> None:
    session = make_session(db, dog, staff, _ago(1))
    add_shot(db, session, 1, passes={"LEFT": (0, 3)})
    assert _codes(_one(client, auth_headers, dog)) == ["RESHOOT_NEEDED"]


def test_done_session_with_an_invalid_shot_needs_a_reshoot(client, db: Session, dog, staff, auth_headers) -> None:
    session = _scored(db, dog, staff, _ago(1), RIGHT_FOR[90])
    bad = add_shot(db, session, 2, passes={"LEFT": (0, 2)})
    bad.validity = "INVALID"
    db.flush()
    item = _one(client, auth_headers, dog)
    assert _codes(item) == ["RESHOOT_NEEDED"]
    assert item["last_symmetry"] == 90


def test_clean_done_session_is_not_a_change(client, db: Session, dog, staff, auth_headers) -> None:
    _scored(db, dog, staff, _ago(1), RIGHT_FOR[90])
    assert _one(client, auth_headers, dog)["changes"] == []


def test_only_the_latest_finished_session_counts(client, db: Session, dog, staff, auth_headers) -> None:
    make_session(db, dog, staff, _ago(3), status="FAILED", model_version=None)
    _scored(db, dog, staff, _ago(1), RIGHT_FOR[90])
    # 그 뒤에 연 측정 중 회차는 끝난 회차가 아니라서 보지 않는다
    make_session(db, dog, staff, _ago(0), status="MEASURING", model_version=None)
    assert _one(client, auth_headers, dog)["changes"] == []


def test_same_day_sessions_follow_created_at(client, db: Session, dog, staff, auth_headers) -> None:
    _scored(db, dog, staff, _ago(1), RIGHT_FOR[90], seq=0)
    make_session(db, dog, staff, _ago(1), status="FAILED", model_version=None, seq=1)
    assert _codes(_one(client, auth_headers, dog)) == ["RESHOOT_NEEDED"]


def test_latest_session_outside_the_window_gives_nothing(client, db: Session, dog, staff, auth_headers) -> None:
    make_session(db, dog, staff, _ago(8), status="FAILED", model_version=None)
    assert _one(client, auth_headers, dog)["changes"] == []
    assert _codes(_one(client, auth_headers, dog, changed_within_days=8)) == ["RESHOOT_NEEDED"]


# ---- 변동: 보행 ----


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        (87, 90, [{"code": "GAIT_BETTER", "delta": 3}]),
        (90, 87, [{"code": "GAIT_WORSE", "delta": -3}]),
        (100, 85, [{"code": "GAIT_WORSE", "delta": -15}]),
        (88, 90, []),
        (90, 88, []),
        (90, 90, []),
    ],
)
def test_gait_change_needs_three_points(
    client, db: Session, dog, staff, auth_headers, before: int, after: int, expected: list[dict]
) -> None:
    _scored(db, dog, staff, _ago(30), RIGHT_FOR[before])
    _scored(db, dog, staff, _ago(2), RIGHT_FOR[after])
    item = _one(client, auth_headers, dog)
    assert item["last_symmetry"] == after
    assert item["changes"] == [{**change, "on": _ago(2).isoformat()} for change in expected]


def test_gait_compares_with_the_previous_session_that_has_a_score(
    client, db: Session, dog, staff, auth_headers
) -> None:
    _scored(db, dog, staff, _ago(40), RIGHT_FOR[100])
    _scored(db, dog, staff, _ago(30), RIGHT_FOR[85])
    make_session(db, dog, staff, _ago(20), status="FAILED", model_version=None)
    unscored = make_session(db, dog, staff, _ago(10))
    add_shot(db, unscored, 1, passes={"LEFT": (4, 0)})
    add_metric(db, unscored, "rom_stifle", "LH", 50.0)
    _scored(db, dog, staff, _ago(1), RIGHT_FOR[90])
    assert _one(client, auth_headers, dog)["changes"] == [
        {"code": "GAIT_BETTER", "on": _ago(1).isoformat(), "delta": 5}
    ]


def test_first_scored_session_has_no_gait_change(client, db: Session, dog, staff, auth_headers) -> None:
    _scored(db, dog, staff, _ago(1), RIGHT_FOR[85])
    item = _one(client, auth_headers, dog)
    assert (item["changes"], item["last_symmetry"]) == ([], 85)


def test_no_gait_change_when_the_latest_session_has_no_score(client, db: Session, dog, staff, auth_headers) -> None:
    _scored(db, dog, staff, _ago(30), RIGHT_FOR[100])
    _scored(db, dog, staff, _ago(20), RIGHT_FOR[85])
    make_session(db, dog, staff, _ago(1), status="FAILED", model_version=None)
    item = _one(client, auth_headers, dog)
    assert _codes(item) == ["RESHOOT_NEEDED"]
    # 가장 최근 점수는 점수가 있는 마지막 회차의 것이다
    assert item["last_symmetry"] == 85


def test_changes_are_newest_first_then_in_code_order(client, db: Session, dog, staff, auth_headers) -> None:
    _scored(db, dog, staff, _ago(30), RIGHT_FOR[100])
    session = _scored(db, dog, staff, _ago(3), RIGHT_FOR[85])
    bad = add_shot(db, session, 2, passes={"RIGHT": (0, 1)})
    bad.validity = "INVALID"
    _history(db, dog, staff, "SURGERY", "TPLO", _ago(3))
    _note(db, dog, staff, _ago(1))
    assert [(change["code"], change["on"]) for change in _one(client, auth_headers, dog)["changes"]] == [
        ("IMPORTANT_NOTE", _ago(1).isoformat()),
        ("RESHOOT_NEEDED", _ago(3).isoformat()),
        ("GAIT_WORSE", _ago(3).isoformat()),
        ("SURGERY_ADDED", _ago(3).isoformat()),
    ]


# ---- 거르기 ----


def test_changed_within_days_keeps_only_dogs_with_changes(client, db: Session, dog, staff, auth_headers) -> None:
    quiet = another_dog(db, staff.institution_id, "콩이")
    _scored(db, quiet, staff, _ago(1), RIGHT_FOR[90])
    old = another_dog(db, staff.institution_id, "두부")
    _history(db, old, staff, "SURGERY", "TPLO", _ago(20))
    noted = another_dog(db, staff.institution_id, "초코")
    _note(db, noted, staff, _ago(2))
    _history(db, dog, staff, "SURGERY", "TPLO", _ago(5))

    response = client.get(DOGS, headers=auth_headers, params={"changed_within_days": 7})
    body = response.json()
    assert {item["name"] for item in body["items"]} == {"보리", "초코"}
    assert body["total"] == 2
    assert all(item["changes"] for item in body["items"])
    # 기간을 늘리면 20일 전 수술도 들어온다. changes도 그 기간으로 계산한다
    wide = client.get(DOGS, headers=auth_headers, params={"changed_within_days": 30}).json()
    assert {item["name"] for item in wide["items"]} == {"보리", "초코", "두부"}
    assert wide["total"] == 3
    # 거르지 않으면 모두 나오고 changes는 7일 기준이다
    everyone = {item["name"]: item for item in _items(client, auth_headers)}
    assert set(everyone) == {"보리", "콩이", "두부", "초코"}
    assert everyone["두부"]["changes"] == [] and everyone["두부"]["badges"][0]["code"] == "SURGERY"


def test_filter_works_with_search_and_paging(client, db: Session, dog, staff, auth_headers) -> None:
    for name in ("콩이", "콩순이", "두부"):
        other = another_dog(db, staff.institution_id, name)
        _history(db, other, staff, "SURGERY", "TPLO", _ago(1))
    found = client.get(DOGS, headers=auth_headers, params={"changed_within_days": 7, "q": "콩"}).json()
    assert {item["name"] for item in found["items"]} == {"콩이", "콩순이"}
    assert found["total"] == 2
    page = client.get(DOGS, headers=auth_headers, params={"changed_within_days": 7, "size": 2, "page": 2}).json()
    assert (len(page["items"]), page["total"]) == (1, 3)


def test_filter_with_no_changed_dog_is_an_empty_page(client, dog, auth_headers) -> None:
    body = client.get(DOGS, headers=auth_headers, params={"changed_within_days": 7}).json()
    assert (body["items"], body["total"]) == ([], 0)


def test_other_institutions_dogs_never_show(client, db: Session, dog, staff, other_staff, auth_headers) -> None:
    theirs = another_dog(db, other_staff.institution_id, "남의 개")
    _history(db, theirs, other_staff, "SURGERY", "TPLO", _ago(1))
    assert _items(client, auth_headers, changed_within_days=7) == []
    mine = _items(client, bearer(other_staff), changed_within_days=7)
    assert [item["name"] for item in mine] == ["남의 개"]


@pytest.mark.parametrize("value", ["0", "31", "-1", "abc", "1.5"])
def test_changed_within_days_must_be_1_to_30(client: TestClient, auth_headers, value: str) -> None:
    response = client.get(DOGS, headers=auth_headers, params={"changed_within_days": value})
    assert response.status_code == 422
    assert response.json()["error"]["detail"]["fields"][0]["field"] == "changed_within_days"


def test_trash_list_has_no_badges_and_ignores_the_filter(client, db: Session, dog, staff, auth_headers) -> None:
    _history(db, dog, staff, "SURGERY", "TPLO", _ago(1))
    assert client.delete(f"{DOGS}/{dog.id}", headers=auth_headers).status_code == 204
    assert _items(client, auth_headers, changed_within_days=7) == []
    for params in ({"trash": "true"}, {"trash": "true", "changed_within_days": 7}):
        (item,) = _items(client, auth_headers, **params)
        assert (item["badges"], item["changes"], item["last_symmetry"]) == ([], [], None)
        assert (item["last_surgery"], item["last_diagnosis"]) == (None, None)


def test_detail_carries_the_same_values_as_the_list(client, db: Session, dog, staff, auth_headers) -> None:
    _scored(db, dog, staff, _ago(30), RIGHT_FOR[100])
    _scored(db, dog, staff, _ago(2), RIGHT_FOR[85])
    _history(db, dog, staff, "SURGERY", "TPLO", _ago(2))
    _note(db, dog, staff, _ago(0))
    listed = _one(client, auth_headers, dog)
    detail = client.get(f"{DOGS}/{dog.id}", headers=auth_headers).json()
    assert len(listed["changes"]) == 3
    for key in ("badges", "changes", "last_symmetry"):
        assert detail[key] == listed[key]


# ---- 쿼리 수 ----


def _statements(db: Session, call) -> int:
    seen: list[str] = []
    connection = db.connection()

    def record(_conn, _cursor, statement: str, _parameters, _context, _many) -> None:
        seen.append(statement)

    event.listen(connection, "before_cursor_execute", record)
    try:
        call()
    finally:
        event.remove(connection, "before_cursor_execute", record)
    return len(seen)


def _busy_dog(db: Session, staff, name: str) -> uuid.UUID:
    other = another_dog(db, staff.institution_id, name)
    _history(db, other, staff, "DIAGNOSIS", "앞십자인대 파열", _ago(50))
    _history(db, other, staff, "SURGERY", "TPLO", _ago(3))
    _note(db, other, staff, _ago(2))
    _scored(db, other, staff, _ago(20), RIGHT_FOR[100])
    _scored(db, other, staff, _ago(1), RIGHT_FOR[85])
    return other.id


@pytest.mark.parametrize("params", [{}, {"changed_within_days": 7}])
def test_query_count_does_not_grow_with_dogs(client, db: Session, dog, staff, auth_headers, params: dict) -> None:
    _busy_dog(db, staff, "하나")
    client.get(DOGS, headers=auth_headers, params=params)  # 로그인 확인 캐시를 채운다
    few = _statements(db, lambda: client.get(DOGS, headers=auth_headers, params=params))
    for index in range(6):
        _busy_dog(db, staff, f"개{index}")
    body: dict = {}
    many = _statements(db, lambda: body.update(client.get(DOGS, headers=auth_headers, params=params).json()))
    assert body["total"] >= 7
    assert many == few
