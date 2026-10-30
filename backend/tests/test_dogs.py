"""반려견 API·체급 분류(12.5, 13.2, 15.5, 17.2 BE-02·03)와 기관 분리(17.1)."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dates import today_local
from app.models import Dog, MeasureSession
from app.services.size_class import BreedListError, classify_size, get_breeds, load_breeds
from tests.conftest import bearer

DOGS = "/api/v1/dogs"


def _patch(client: TestClient, url: str, *, json: dict, headers: dict):
    """지금 저장된 version을 읽어 같이 보낸다(15.5 BE-25). 잠금 자체는 test_patch_version_is_checked가 본다."""
    version = client.get(url, headers=headers).json()["version"]
    return client.patch(url, json={"version": version, **json}, headers=headers)


BASE = {
    "name": "보리",
    "breed": "골든 리트리버",
    "weight_kg": 28.4,
    "birth_year": 2019,
    "sex": "FEMALE_SPAYED",
    "rehab_start_date": "2026-10-01",
    "focus_limb": "RH",
    "memo": None,
}
DOG_OUT_KEYS = {
    "version",
    "id",
    "name",
    "breed",
    "weight_kg",
    "size_class",
    "size_class_manual",
    "birth_year",
    "sex",
    "rehab_start_date",
    "focus_limb",
    "baseline_session_id",
    "memo",
    "session_count",
    "last_measured_on",
    "open_session_id",
    "created_at",
    "updated_at",
}


def _post(client: TestClient, headers: dict, **overrides):
    return client.post(DOGS, json={**BASE, **overrides}, headers=headers)


def _fields(response) -> list[str]:
    return [f["field"] for f in response.json()["error"]["detail"]["fields"]]


def _session(db: Session, dog: Dog, staff, measured_on: date, status: str = "DONE") -> MeasureSession:
    row = MeasureSession(
        dog_id=dog.id, staff_id=staff.id, measured_on=measured_on, size_class=dog.size_class, status=status
    )
    db.add(row)
    db.flush()
    return row


# ---- classify_size (12.5, BE-02): 체중만 본다. 경계값은 위 구간에 든다 ----


@pytest.mark.parametrize(
    ("weight", "expected"),
    [
        ("0.50", "SMALL"),
        ("9.99", "SMALL"),
        ("10.00", "MEDIUM"),
        ("24.99", "MEDIUM"),
        ("25.00", "LARGE"),
        ("100.00", "LARGE"),
    ],
)
def test_weight_boundaries(weight: str, expected: str) -> None:
    assert classify_size(Decimal(weight)) == expected


def test_thresholds_come_from_caller() -> None:
    assert classify_size(Decimal("12"), small_max_kg=Decimal("15"), medium_max_kg=Decimal("30")) == "SMALL"
    assert classify_size(Decimal("30"), small_max_kg=Decimal("15"), medium_max_kg=Decimal("30")) == "LARGE"


def test_breed_list_loads_and_is_cached() -> None:
    path = get_settings().BREEDS_FILE
    names = load_breeds(path)
    assert "골든 리트리버" in names and "말티즈" in names
    assert len(names) == len(set(names))
    assert get_breeds(path) is get_breeds(path)


def test_bad_breed_list_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "breeds.yaml"
    bad.write_text("- name: 푸들\n  size_class: SMALL\n", encoding="utf-8")  # 옛 견종표 모양은 거부
    with pytest.raises(BreedListError):
        load_breeds(bad)


# ---- 등록 (BE-02) ----


def test_create_dog_classifies_by_weight(client: TestClient, auth_headers: dict) -> None:
    response = _post(client, auth_headers)  # 28.4 kg → LARGE
    assert response.status_code == 201
    body = response.json()
    assert set(body) == DOG_OUT_KEYS
    assert body["size_class"] == "LARGE"
    assert body["size_class_manual"] is False
    assert body["weight_kg"] == 28.4
    assert body["rehab_start_date"] == "2026-10-01"
    assert body["memo"] is None and body["baseline_session_id"] is None
    assert body["session_count"] == 0 and body["last_measured_on"] is None and body["open_session_id"] is None
    assert body["created_at"].endswith("Z") and body["updated_at"].endswith("Z")


@pytest.mark.parametrize(
    ("breed", "weight", "expected"),
    [
        ("믹스", 9.99, "SMALL"),
        ("골든 리트리버", 9.99, "SMALL"),  # 견종은 체급에 영향을 주지 않는다
        ("말티즈", 10, "MEDIUM"),
        ("믹스", 24.99, "MEDIUM"),
        ("말티즈", 25, "LARGE"),
    ],
)
def test_create_dog_size_follows_weight_not_breed(
    client: TestClient, auth_headers: dict, breed, weight, expected
) -> None:
    response = _post(client, auth_headers, breed=breed, weight_kg=weight)
    assert response.status_code == 201
    assert response.json()["size_class"] == expected
    assert response.json()["size_class_manual"] is False


def test_create_dog_with_manual_size_class(client: TestClient, auth_headers: dict) -> None:
    response = _post(client, auth_headers, size_class="SMALL")
    assert response.status_code == 201
    assert response.json()["size_class"] == "SMALL"
    assert response.json()["size_class_manual"] is True


def test_create_dog_strips_name_and_ignores_baseline(client: TestClient, auth_headers: dict) -> None:
    response = _post(client, auth_headers, name="  보리  ", baseline_session_id=str(uuid.uuid4()))
    assert response.status_code == 201
    assert response.json()["name"] == "보리"
    assert response.json()["baseline_session_id"] is None


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"name": "   "}, "name"),
        ({"name": "가" * 51}, "name"),
        ({"breed": ""}, "breed"),
        ({"weight_kg": 0.4}, "weight_kg"),
        ({"weight_kg": 100.01}, "weight_kg"),
        ({"weight_kg": 28.456}, "weight_kg"),
        ({"size_class": "HUGE"}, "size_class"),
        ({"birth_year": 1989}, "birth_year"),
        ({"sex": "DOG"}, "sex"),
        ({"focus_limb": "TAIL"}, "focus_limb"),
        ({"memo": "메" * 1001}, "memo"),
    ],
)
def test_create_dog_input_rules(client: TestClient, auth_headers: dict, overrides: dict, field: str) -> None:
    response = _post(client, auth_headers, **overrides)
    assert response.status_code == 422
    assert field in _fields(response)


def test_create_dog_date_rules_follow_local_today(client: TestClient, auth_headers: dict) -> None:
    today = today_local()
    assert _post(client, auth_headers, birth_year=today.year + 1).status_code == 422
    assert _post(client, auth_headers, rehab_start_date=str(today + timedelta(days=1))).status_code == 422
    assert _post(client, auth_headers, birth_year=today.year, rehab_start_date=str(today)).status_code == 201


def test_create_dog_needs_token(client: TestClient) -> None:
    response = client.post(DOGS, json=BASE)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


# ---- 목록·검색 (BE-03) ----


def test_list_sorts_by_last_measured_on_desc_with_unmeasured_last(
    client: TestClient, db: Session, staff, auth_headers: dict
) -> None:
    dog_a = db.get(Dog, _post(client, auth_headers, name="A").json()["id"])
    dog_b = db.get(Dog, _post(client, auth_headers, name="B").json()["id"])
    _post(client, auth_headers, name="C")
    _session(db, dog_b, staff, date(2026, 10, 15))
    _session(db, dog_a, staff, date(2026, 10, 10))
    open_session = _session(db, dog_a, staff, date(2026, 10, 20), status="MEASURING")

    response = client.get(DOGS, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["page"], body["size"]) == (3, 1, 20)
    assert [item["name"] for item in body["items"]] == ["A", "B", "C"]
    first = body["items"][0]
    assert first["session_count"] == 2
    assert first["last_measured_on"] == "2026-10-20"
    assert first["open_session_id"] == str(open_session.id)
    assert body["items"][2]["session_count"] == 0
    assert body["items"][2]["last_measured_on"] is None


def test_list_search_by_name_part_and_escapes_wildcards(client: TestClient, auth_headers: dict) -> None:
    for name in ("보리", "보라", "100%", "Max"):
        _post(client, auth_headers, name=name)

    # 한 트랜잭션 안에서는 created_at이 모두 같아(now()는 트랜잭션 시작 시각) 순서는 test_list_paging이 본다.
    assert {d["name"] for d in client.get(DOGS, params={"q": "보"}, headers=auth_headers).json()["items"]} == {
        "보라",
        "보리",
    }
    assert [d["name"] for d in client.get(DOGS, params={"q": "%"}, headers=auth_headers).json()["items"]] == ["100%"]
    assert [d["name"] for d in client.get(DOGS, params={"q": "max"}, headers=auth_headers).json()["items"]] == ["Max"]
    assert client.get(DOGS, params={"q": "없는이름"}, headers=auth_headers).json()["total"] == 0


def test_list_paging(client: TestClient, db: Session, auth_headers: dict) -> None:
    # 한 트랜잭션 안에서는 now()가 같아 created_at이 모두 같으므로, 등록 시각을 직접 달리 둔다
    for minutes, name in enumerate(("A", "B", "C")):
        dog_id = _create(client, auth_headers, name=name)
        db.execute(update(Dog).where(Dog.id == dog_id).values(created_at=datetime(2026, 10, 1, 9, minutes, tzinfo=UTC)))
    page1 = client.get(DOGS, params={"page": 1, "size": 2}, headers=auth_headers).json()
    page2 = client.get(DOGS, params={"page": 2, "size": 2}, headers=auth_headers).json()
    page3 = client.get(DOGS, params={"page": 3, "size": 2}, headers=auth_headers).json()
    assert (len(page1["items"]), page1["total"], page1["size"]) == (2, 3, 2)
    assert (len(page2["items"]), page2["page"]) == (1, 2)
    assert (len(page3["items"]), page3["total"]) == (0, 3)
    # 등록 순 내림차순(측정이 없으면 created_at 내림차순)
    assert [d["name"] for d in page1["items"] + page2["items"]] == ["C", "B", "A"]


@pytest.mark.parametrize("params", [{"page": 0}, {"size": 0}, {"size": 101}, {"q": "가" * 51}])
def test_list_query_rules(client: TestClient, auth_headers: dict, params: dict) -> None:
    response = client.get(DOGS, params=params, headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# ---- 상세·기관 분리 (17.1) ----


def test_other_institution_dog_is_404_identical_to_missing(client: TestClient, auth_headers: dict, other_staff) -> None:
    mine = _post(client, auth_headers).json()["id"]
    theirs = _post(client, bearer(other_staff), name="남의개").json()["id"]

    assert client.get(f"{DOGS}/{mine}", headers=auth_headers).status_code == 200
    other = client.get(f"{DOGS}/{theirs}", headers=auth_headers)
    missing = client.get(f"{DOGS}/{uuid.uuid4()}", headers=auth_headers)
    assert other.status_code == missing.status_code == 404
    assert other.json() == missing.json()
    assert client.get(f"{DOGS}/not-a-uuid", headers=auth_headers).status_code == 404

    names = [d["name"] for d in client.get(DOGS, headers=auth_headers).json()["items"]]
    assert "남의개" not in names
    assert client.patch(f"{DOGS}/{theirs}", json={"version": 0, "memo": "x"}, headers=auth_headers).status_code == 404


# ---- 수정 (BE-02) ----


def _create(client: TestClient, headers: dict, **overrides) -> str:
    return _post(client, headers, **overrides).json()["id"]


def test_patch_weight_reclassifies_when_not_manual(client: TestClient, auth_headers: dict) -> None:
    dog_id = _create(client, auth_headers, breed="믹스", weight_kg=9.0)  # SMALL
    response = _patch(client, f"{DOGS}/{dog_id}", json={"weight_kg": 30.0}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["weight_kg"] == 30.0
    assert (response.json()["size_class"], response.json()["size_class_manual"]) == ("LARGE", False)
    again = _patch(client, f"{DOGS}/{dog_id}", json={"weight_kg": 24.99}, headers=auth_headers).json()
    assert again["size_class"] == "MEDIUM"


def test_patch_breed_does_not_change_size_class(client: TestClient, auth_headers: dict) -> None:
    dog_id = _create(client, auth_headers, breed="믹스", weight_kg=9.0)  # SMALL
    response = _patch(client, f"{DOGS}/{dog_id}", json={"breed": "골든 리트리버"}, headers=auth_headers)
    assert response.json()["breed"] == "골든 리트리버"
    assert response.json()["size_class"] == "SMALL"
    assert response.json()["size_class_manual"] is False


def test_patch_manual_size_class_sticks_until_null(client: TestClient, auth_headers: dict) -> None:
    dog_id = _create(client, auth_headers, breed="말티즈", weight_kg=3.0)  # SMALL
    manual = _patch(client, f"{DOGS}/{dog_id}", json={"size_class": "LARGE"}, headers=auth_headers).json()
    assert (manual["size_class"], manual["size_class_manual"]) == ("LARGE", True)

    after_weight = _patch(client, f"{DOGS}/{dog_id}", json={"weight_kg": 3.5}, headers=auth_headers).json()
    assert after_weight["size_class"] == "LARGE"  # 직접 고친 체급은 체중을 바꿔도 그대로

    auto = _patch(client, f"{DOGS}/{dog_id}", json={"size_class": None}, headers=auth_headers).json()
    assert (auto["size_class"], auto["size_class_manual"]) == ("SMALL", False)  # 저장된 체중 3.5 kg으로 다시 분류


def test_patch_size_class_null_uses_stored_weight(client: TestClient, auth_headers: dict) -> None:
    dog_id = _create(client, auth_headers, breed="믹스", weight_kg=30.0, size_class="SMALL")
    auto = _patch(client, f"{DOGS}/{dog_id}", json={"size_class": None}, headers=auth_headers).json()
    assert auto["size_class"] == "LARGE"


def test_patch_weight_and_size_class_together_size_class_wins(client: TestClient, auth_headers: dict) -> None:
    dog_id = _create(client, auth_headers, breed="믹스", weight_kg=9.0)
    body = {"weight_kg": 30.0, "size_class": "MEDIUM"}
    response = _patch(client, f"{DOGS}/{dog_id}", json=body, headers=auth_headers).json()
    assert response["weight_kg"] == 30.0
    assert (response["size_class"], response["size_class_manual"]) == ("MEDIUM", True)


def test_patch_null_on_required_fields_is_422(client: TestClient, auth_headers: dict) -> None:
    dog_id = _create(client, auth_headers)
    for field in ("name", "breed", "weight_kg"):
        response = _patch(client, f"{DOGS}/{dog_id}", json={field: None}, headers=auth_headers)
        assert response.status_code == 422
        assert _fields(response) == [field]


def test_patch_optional_fields_can_be_cleared_and_empty_patch_is_noop(client: TestClient, auth_headers: dict) -> None:
    dog_id = _create(client, auth_headers, memo="메모")
    cleared = _patch(client, f"{DOGS}/{dog_id}", json={"memo": None, "focus_limb": None}, headers=auth_headers).json()
    assert cleared["memo"] is None and cleared["focus_limb"] is None
    untouched = _patch(client, f"{DOGS}/{dog_id}", json={}, headers=auth_headers)
    assert untouched.status_code == 200
    assert untouched.json()["name"] == "보리"


def test_patch_baseline_session_rules(client: TestClient, db: Session, staff, auth_headers: dict) -> None:
    dog = db.get(Dog, _create(client, auth_headers))
    other_dog = db.get(Dog, _create(client, auth_headers, name="다른개"))
    done = _session(db, dog, staff, date(2026, 10, 10), status="DONE")
    measuring = _session(db, dog, staff, date(2026, 10, 11), status="MEASURING")
    other_done = _session(db, other_dog, staff, date(2026, 10, 12), status="DONE")

    for bad in (measuring.id, other_done.id, uuid.uuid4()):
        response = _patch(client, f"{DOGS}/{dog.id}", json={"baseline_session_id": str(bad)}, headers=auth_headers)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "BASELINE_INVALID"

    ok = _patch(client, f"{DOGS}/{dog.id}", json={"baseline_session_id": str(done.id)}, headers=auth_headers)
    assert ok.status_code == 200
    assert ok.json()["baseline_session_id"] == str(done.id)

    cleared = _patch(client, f"{DOGS}/{dog.id}", json={"baseline_session_id": None}, headers=auth_headers)
    assert cleared.json()["baseline_session_id"] is None


# ---- 낙관적 잠금 (BE-25, 12.5, 15.5) ----


def test_patch_version_is_checked(client: TestClient, auth_headers: dict) -> None:
    created = client.post(DOGS, json={"name": "보리", "breed": "말티즈", "weight_kg": 3.0}, headers=auth_headers).json()
    assert created["version"] == 0
    url = f"{DOGS}/{created['id']}"

    first = client.patch(url, json={"version": 0, "memo": "첫 수정"}, headers=auth_headers)
    assert first.status_code == 200
    assert first.json()["version"] == 1

    stale = client.patch(url, json={"version": 0, "memo": "늦은 수정"}, headers=auth_headers)
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "DOG_MODIFIED"
    current = client.get(url, headers=auth_headers).json()
    assert (current["memo"], current["version"]) == ("첫 수정", 1)

    missing = client.patch(url, json={"memo": "x"}, headers=auth_headers)
    assert missing.status_code == 422
    assert missing.json()["error"]["detail"]["fields"] == [{"field": "version", "type": "missing"}]

    noop = client.patch(url, json={"version": 1}, headers=auth_headers)
    assert noop.status_code == 200 and noop.json()["version"] == 1  # 바꾼 것이 없으면 번호도 그대로
