"""바이탈(12.5 차트 자료, 13.9, 15.6 회차 시작의 vital, 15.11, 17.2 BE-28, v1.36)."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.core.dates import today_local
from app.models import DogVital, MeasureSession
from app.services.purge import purge
from app.storage.base import get_storage
from tests.conftest import GOOD_PASSWORD, bearer, password_hash_for

DOGS = "/api/v1/dogs"
VITAL = {"weight_kg": 28.1, "temp_c": 38.6, "heart_rate": 92, "sbp": 132, "dbp": 84}
DAY = "2026-10-20"


def _put(client: TestClient, dog, headers: dict, day: str = DAY, **overrides):
    return client.put(f"{DOGS}/{dog.id}/vitals/{day}", json={**VITAL, **overrides}, headers=headers)


def _list(client: TestClient, dog, headers: dict) -> list[dict]:
    response = client.get(f"{DOGS}/{dog.id}/vitals", headers=headers)
    assert response.status_code == 200
    return response.json()["items"]


def _fields(response) -> list[str]:
    return [f["field"] for f in response.json()["error"]["detail"]["fields"]]


def _count(db: Session, dog) -> int:
    return db.scalar(select(func.count()).select_from(DogVital).where(DogVital.dog_id == dog.id)) or 0


def test_put_creates_the_day_and_returns_the_writer(client: TestClient, dog, staff, auth_headers: dict) -> None:
    response = _put(client, dog, auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert {key: body[key] for key in VITAL} == VITAL  # 숫자는 JSON 숫자로 온다(15.1)
    assert body["measured_on"] == DAY
    assert body["staff"] == {"id": str(staff.id), "name": "담당자"}
    assert body["session_id"] is None
    assert set(body) == {*VITAL, "id", "measured_on", "staff", "session_id", "created_at", "updated_at"}


def test_put_on_the_same_day_replaces_the_values(client: TestClient, db: Session, dog, staff, auth_headers) -> None:
    from app.models import Staff

    first = _put(client, dog, auth_headers).json()
    colleague = Staff(
        institution_id=staff.institution_id,
        login_id="staff9",
        password_hash=password_hash_for(GOOD_PASSWORD),
        name="동료",
        role="CLIENT",
    )
    db.add(colleague)
    db.flush()

    second = _put(client, dog, bearer(colleague), temp_c=39.1, heart_rate=110).json()

    assert second["id"] == first["id"]  # 하루 한 줄(uq_dog_vital_day)
    assert second["temp_c"] == 39.1 and second["heart_rate"] == 110
    assert second["staff"]["name"] == "동료"  # 바꾼 담당자
    assert _count(db, dog) == 1


def test_list_is_newest_first(client: TestClient, dog, auth_headers: dict) -> None:
    for day in ("2026-10-01", "2026-10-20", "2026-09-15"):
        _put(client, dog, auth_headers, day=day)
    assert [item["measured_on"] for item in _list(client, dog, auth_headers)] == [
        "2026-10-20",
        "2026-10-01",
        "2026-09-15",
    ]


def test_list_is_empty_without_vitals(client: TestClient, dog, auth_headers: dict) -> None:
    assert _list(client, dog, auth_headers) == []


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"weight_kg": 0.4}, "weight_kg"),
        ({"weight_kg": 100.1}, "weight_kg"),
        ({"temp_c": 29.9}, "temp_c"),
        ({"temp_c": 45.1}, "temp_c"),
        ({"temp_c": 38.55}, "temp_c"),  # 소수 첫째 자리까지
        ({"heart_rate": 19}, "heart_rate"),
        ({"heart_rate": 301}, "heart_rate"),
        ({"sbp": 29}, "sbp"),
        ({"sbp": 301}, "sbp"),
        ({"dbp": 9}, "dbp"),
        ({"sbp": 120, "dbp": 120}, "dbp"),  # 이완기는 수축기보다 작아야 한다
        ({"sbp": 100, "dbp": 130}, "dbp"),
        ({"temp_c": None}, "temp_c"),  # 다섯 값 모두 필수
    ],
)
def test_input_rules(client: TestClient, dog, auth_headers: dict, overrides: dict, field: str) -> None:
    response = _put(client, dog, auth_headers, **overrides)
    assert response.status_code == 422
    assert _fields(response) == [field]


def test_every_value_is_required(client: TestClient, dog, auth_headers: dict) -> None:
    response = client.put(f"{DOGS}/{dog.id}/vitals/{DAY}", json={"weight_kg": 28.1}, headers=auth_headers)
    assert response.status_code == 422
    assert set(_fields(response)) == {"temp_c", "heart_rate", "sbp", "dbp"}


def test_boundary_values_are_accepted(client: TestClient, dog, auth_headers: dict) -> None:
    low = _put(client, dog, auth_headers, weight_kg=0.5, temp_c=30.0, heart_rate=20, sbp=30, dbp=10)
    high = _put(client, dog, auth_headers, weight_kg=100.0, temp_c=45.0, heart_rate=300, sbp=300, dbp=250)
    assert low.status_code == 200 and high.status_code == 200


def test_future_date_is_422_and_a_bad_date_is_404(client: TestClient, dog, auth_headers: dict) -> None:
    today = today_local()
    assert _put(client, dog, auth_headers, day=today.isoformat()).status_code == 200
    future = _put(client, dog, auth_headers, day=(today + timedelta(days=1)).isoformat())
    assert future.status_code == 422 and _fields(future) == ["measured_on"]
    assert _put(client, dog, auth_headers, day="어제").status_code == 404  # 주소의 값은 ID처럼 404(15.1)


def test_other_institution_and_trashed_dog_are_404(
    client: TestClient, db: Session, dog, auth_headers, other_staff
) -> None:
    _put(client, dog, auth_headers)
    other = bearer(other_staff)
    assert client.get(f"{DOGS}/{dog.id}/vitals", headers=other).status_code == 404
    assert _put(client, dog, other).status_code == 404
    assert client.get(f"{DOGS}/{uuid.uuid4()}/vitals", headers=auth_headers).status_code == 404
    assert _count(db, dog) == 1  # 다른 기관의 요청은 아무것도 바꾸지 않았다

    assert client.delete(f"{DOGS}/{dog.id}", headers=auth_headers).status_code == 204  # 휴지통
    assert client.get(f"{DOGS}/{dog.id}/vitals", headers=auth_headers).status_code == 404
    assert _put(client, dog, auth_headers).status_code == 404


def test_vitals_need_a_token(client: TestClient, dog) -> None:
    assert client.get(f"{DOGS}/{dog.id}/vitals").status_code == 401
    assert client.put(f"{DOGS}/{dog.id}/vitals/{DAY}", json=VITAL).status_code == 401


# ---- DogOut.latest_vital ----


def test_dog_out_carries_the_latest_vital(client: TestClient, dog, auth_headers: dict) -> None:
    assert client.get(f"{DOGS}/{dog.id}", headers=auth_headers).json()["latest_vital"] is None
    _put(client, dog, auth_headers, day="2026-10-20", heart_rate=100)
    _put(client, dog, auth_headers, day="2026-10-01", heart_rate=80)

    detail = client.get(f"{DOGS}/{dog.id}", headers=auth_headers).json()
    assert detail["latest_vital"]["measured_on"] == "2026-10-20"
    assert detail["latest_vital"]["heart_rate"] == 100
    listed = client.get(DOGS, headers=auth_headers).json()["items"][0]
    assert listed["latest_vital"] == detail["latest_vital"]


def test_list_reads_latest_vitals_in_one_query(client: TestClient, db: Session, staff, auth_headers: dict) -> None:
    """반려견 수가 늘어도 목록의 쿼리 수가 같다(15.1 N+1 금지)."""
    from app.models import Dog

    def add_dog_with_vitals(name: str) -> None:
        row = Dog(
            institution_id=staff.institution_id, name=name, breed="말티즈", weight_kg=Decimal("3.2"), size_class="SMALL"
        )
        db.add(row)
        db.flush()
        for day in (date(2026, 10, 1), date(2026, 10, 2)):
            db.add(
                DogVital(dog_id=row.id, measured_on=day, staff_id=staff.id, **{**VITAL, "weight_kg": Decimal("3.2")})
            )
        db.flush()

    def count_queries() -> int:
        statements: list[str] = []

        def record(conn, cursor, statement, parameters, context, executemany) -> None:
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", record)
        try:
            assert client.get(DOGS, headers=auth_headers).status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", record)
        return len(statements)

    add_dog_with_vitals("하나")
    count_queries()  # 첫 요청은 기관 행을 읽는 쿼리가 하나 더 있다(그 뒤로는 세션이 들고 있다)
    one = count_queries()
    for name in ("둘", "셋", "넷"):
        add_dog_with_vitals(name)
    assert count_queries() == one


# ---- 회차 시작의 vital(15.6) ----


def test_session_start_saves_the_vital_and_links_the_session(
    client: TestClient, db: Session, dog, auth_headers
) -> None:
    response = client.post(f"{DOGS}/{dog.id}/sessions", json={"measured_on": DAY, "vital": VITAL}, headers=auth_headers)
    assert response.status_code == 201
    session = response.json()
    assert session["weight_kg"] == 28.1  # weight_kg를 빼면 vital의 체중이 회차 체중이다

    (vital,) = _list(client, dog, auth_headers)
    assert vital["measured_on"] == DAY and vital["session_id"] == session["id"]
    assert {key: vital[key] for key in VITAL} == VITAL


def test_session_start_replaces_the_vital_of_that_day(client: TestClient, db: Session, dog, auth_headers) -> None:
    earlier = _put(client, dog, auth_headers, heart_rate=70).json()
    session = client.post(
        f"{DOGS}/{dog.id}/sessions", json={"measured_on": DAY, "weight_kg": 28.1, "vital": VITAL}, headers=auth_headers
    ).json()
    (vital,) = _list(client, dog, auth_headers)
    assert vital["id"] == earlier["id"] and vital["heart_rate"] == 92 and vital["session_id"] == session["id"]

    # 뒤에 PUT으로 고쳐도 회차 연결은 그대로다
    again = _put(client, dog, auth_headers, heart_rate=95).json()
    assert again["session_id"] == session["id"]


def test_session_start_rejects_two_different_weights(client: TestClient, db: Session, dog, auth_headers) -> None:
    response = client.post(f"{DOGS}/{dog.id}/sessions", json={"weight_kg": 27.0, "vital": VITAL}, headers=auth_headers)
    assert response.status_code == 422 and _fields(response) == ["vital.weight_kg"]
    assert db.scalar(select(func.count()).select_from(MeasureSession)) == 0
    assert _count(db, dog) == 0


def test_session_start_checks_the_vital_values(client: TestClient, dog, auth_headers: dict) -> None:
    response = client.post(f"{DOGS}/{dog.id}/sessions", json={"vital": {**VITAL, "dbp": 140}}, headers=auth_headers)
    assert response.status_code == 422 and _fields(response) == ["vital.dbp"]


def test_session_start_without_vital_is_unchanged(client: TestClient, db: Session, dog, auth_headers) -> None:
    response = client.post(f"{DOGS}/{dog.id}/sessions", json={}, headers=auth_headers)
    assert response.status_code == 201 and response.json()["weight_kg"] is None
    assert _count(db, dog) == 0


def test_cancelling_the_session_keeps_the_vital(client: TestClient, db: Session, dog, auth_headers) -> None:
    session = client.post(
        f"{DOGS}/{dog.id}/sessions", json={"measured_on": DAY, "vital": VITAL}, headers=auth_headers
    ).json()
    assert client.delete(f"/api/v1/sessions/{session['id']}", headers=auth_headers).status_code == 204

    (vital,) = _list(client, dog, auth_headers)
    assert vital["session_id"] is None and vital["heart_rate"] == 92  # 병원은 그날 실제로 쟀다


# ---- 파기(12.5 삭제 순서) ----


def test_purge_counts_and_deletes_vitals(client: TestClient, db: Session, dog, staff, auth_headers) -> None:
    client.post(f"{DOGS}/{dog.id}/sessions", json={"measured_on": DAY, "vital": VITAL}, headers=auth_headers)
    _put(client, dog, auth_headers, day="2026-10-01")
    without = 1 + 1  # 반려견 + 회차

    counted = purge(db, get_storage(), "DOG", institution_id=dog.institution_id, target_id=dog.id)
    assert counted.rows == without + 2
    done = purge(db, get_storage(), "DOG", institution_id=dog.institution_id, target_id=dog.id, dry_run=False)
    assert done.rows == without + 2
    assert db.scalar(select(func.count()).select_from(DogVital)) == 0
