"""회차 비교 API(명세 5절 비교 규칙, 15.8의 22번, BE-18, 17.5, S15P31A404-198).

판정 함수 자체(report/judge.py)는 test_report_judge.py가 본다. 여기서는 두 회차의 행을 모아 판정하고 정렬하는 것,
기준·직전·지정 회차 고르기, 비교할 수 없는 요청의 400을 본다.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services import tolerance as tolerance_module
from tests.conftest import bearer
from tests.history_fixtures import add_metric, another_dog, make_session

COMPARE = "/api/v1/dogs/{}/compare"
JUDGEMENTS = {"INCREASE", "DECREASE", "WITHIN_RANGE", "UNKNOWN", "NOT_COMPARABLE"}
# 5절: 백엔드는 평가 단어를 내지 않는다
EVALUATION_WORDS = ("좋아", "나빠", "개선", "악화", "호전", "better", "worse", "improv")


@pytest.fixture
def tolerance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[dict[str, float]], None]:
    """테스트용 오차 범위 파일을 쓰고 설정이 그것을 보게 한다. 끝나면 캐시를 비워 실제 파일로 돌아간다."""

    def _set(values: dict[str, float]) -> None:
        file = tmp_path / "tolerance.yaml"
        body = "".join(f"{code}: {value}\n" for code, value in values.items()) or "# 아직 값이 없다\n"
        file.write_text(body, encoding="utf-8")
        monkeypatch.setattr(get_settings(), "TOLERANCE_FILE", str(file))
        tolerance_module._cached.cache_clear()

    yield _set
    tolerance_module._cached.cache_clear()


def _get(client: TestClient, headers: dict, dog, **params):
    return client.get(COMPARE.format(dog.id), params=params, headers=headers)


def _by_key(body: dict) -> dict[tuple[str, str, str], dict]:
    return {(item["gait_type"], item["limb"], item["metric_code"]): item for item in body["items"]}


def _error(response) -> tuple[int, str, dict | None]:
    error = response.json()["error"]
    return response.status_code, error["code"], error["detail"]


# ---- 판정 ----


def test_default_compares_baseline_to_latest_and_covers_every_judgement(
    client: TestClient, db: Session, dog, staff, auth_headers, tolerance
) -> None:
    tolerance({"rom_stifle": 3.0, "rom_hip": 5.0, "stance_ratio": 5.0})
    base = make_session(db, dog, staff, date(2026, 10, 1))
    target = make_session(db, dog, staff, date(2026, 10, 20))
    add_metric(db, base, "rom_stifle", "LH", 30.2), add_metric(db, target, "rom_stifle", "LH", 33.2)  # BE-18
    add_metric(db, base, "rom_stifle", "RH", 38.2), add_metric(db, target, "rom_stifle", "RH", 42.0)
    add_metric(db, base, "rom_hip", "RH", 50.0), add_metric(db, target, "rom_hip", "RH", 44.0)
    add_metric(db, base, "rom_elbow", "LF", 10.0), add_metric(db, target, "rom_elbow", "LF", 20.0)  # 범위 없음
    add_metric(db, base, "stance_ratio", "LF", 60.0, n_passes=7), add_metric(db, target, "stance_ratio", "LF", 61.0)
    add_metric(db, target, "rom_tarsus", "LH", 20.0)  # target에만 있다
    add_metric(db, base, "rom_hip", "LH", None, reason="LOW_CONFIDENCE"), add_metric(db, target, "rom_hip", "LH", 40.0)

    response = _get(client, auth_headers, dog)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dog_id"] == str(dog.id) and body["model_changed"] is False
    assert body["base"] == {
        "session_id": str(base.id),
        "measured_on": "2026-10-01",
        "model_version": "v1",
        "kind": "BASELINE",
    }
    assert body["target"] == {"session_id": str(target.id), "measured_on": "2026-10-20", "model_version": "v1"}

    items = _by_key(body)
    assert len(items) == 7 and all(
        set(item)
        == {"metric_code", "limb", "gait_type", "unit", "base_value", "target_value", "diff", "judgement", "note"}
        for item in body["items"]
    )
    within = items[("TROT", "LH", "rom_stifle")]
    assert (within["judgement"], within["note"], within["diff"]) == ("WITHIN_RANGE", None, 3.0)
    increase = items[("TROT", "RH", "rom_stifle")]
    assert (increase["judgement"], increase["diff"], increase["unit"]) == ("INCREASE", 3.8, "deg")
    decrease = items[("TROT", "RH", "rom_hip")]
    assert (decrease["judgement"], decrease["diff"]) == ("DECREASE", -6.0)
    no_range = items[("TROT", "LF", "rom_elbow")]
    assert (no_range["judgement"], no_range["diff"]) == ("UNKNOWN", 10.0)
    assert no_range["note"] == {"code": "RANGE_NOT_SET", "message": "변화 판단 기준이 아직 정해지지 않았습니다."}
    few_passes = items[("TROT", "LF", "stance_ratio")]
    assert (few_passes["judgement"], few_passes["note"]["code"], few_passes["unit"]) == (
        "UNKNOWN",
        "RANGE_NOT_SET",
        "pct",
    )
    missing = items[("TROT", "LH", "rom_tarsus")]
    assert (missing["judgement"], missing["note"]["code"], missing["diff"]) == ("NOT_COMPARABLE", "NO_DATA", None)
    assert (missing["base_value"], missing["target_value"]) == (None, 20.0)
    unmeasurable = items[("TROT", "LH", "rom_hip")]
    assert (unmeasurable["judgement"], unmeasurable["note"]["code"]) == ("NOT_COMPARABLE", "LOW_CONFIDENCE")
    assert (unmeasurable["base_value"], unmeasurable["target_value"], unmeasurable["diff"]) == (None, 40.0, None)


def test_pass_count_rule_holds_for_either_side_and_starts_at_eight(
    client: TestClient, db: Session, dog, staff, auth_headers, tolerance
) -> None:
    """오차 범위와 견주는 조건(5절, 197): 두 회차 모두 그 수치·그 다리의 n_passes가 8 이상. 어느 쪽이든 7이면 값만."""
    tolerance({"rom_stifle": 3.0, "rom_hip": 5.0})
    base = make_session(db, dog, staff, date(2026, 10, 1))
    target = make_session(db, dog, staff, date(2026, 10, 20))
    add_metric(db, base, "rom_stifle", "LH", 30.0, n_passes=8)  # target 쪽이 7
    add_metric(db, target, "rom_stifle", "LH", 36.0, n_passes=7)
    add_metric(db, base, "rom_stifle", "RH", 30.0, n_passes=7)  # base 쪽이 7
    add_metric(db, target, "rom_stifle", "RH", 36.0, n_passes=8)
    add_metric(db, base, "rom_hip", "LH", 40.0, n_passes=8)  # 경계: 둘 다 8이면 판정한다
    add_metric(db, target, "rom_hip", "LH", 46.0, n_passes=8)
    add_metric(db, base, "rom_hip", "RH", 40.0, n_passes=8)  # 8과 9
    add_metric(db, target, "rom_hip", "RH", 42.0, n_passes=9)

    items = _by_key(_get(client, auth_headers, dog).json())
    for limb in ("LH", "RH"):
        few = items[("TROT", limb, "rom_stifle")]
        assert (few["judgement"], few["note"]["code"], few["diff"]) == ("UNKNOWN", "RANGE_NOT_SET", 6.0)
    assert items[("TROT", "LH", "rom_hip")]["judgement"] == "INCREASE"
    assert items[("TROT", "RH", "rom_hip")]["judgement"] == "WITHIN_RANGE"


def test_compare_reads_metric_rows_of_the_two_chosen_sessions_only(
    client: TestClient, db: Session, dog, staff, auth_headers, tolerance
) -> None:
    """회차가 늘어도 비교는 고른 두 회차의 수치 행만 읽는다(198 리뷰). 사이 회차의 행은 쿼리에 들어가지 않는다."""
    tolerance({"rom_stifle": 3.0})
    base = make_session(db, dog, staff, date(2026, 10, 1))
    middle = make_session(db, dog, staff, date(2026, 10, 10))
    target = make_session(db, dog, staff, date(2026, 10, 20))
    for session, value in ((base, 30.0), (middle, 50.0), (target, 31.0)):
        add_metric(db, session, "rom_stifle", "LH", value)
    seen: list[str] = []
    connection = db.connection()

    def record(_conn, _cursor, statement: str, parameters, _context, _many) -> None:
        if "FROM session_metric" in statement:
            seen.append(repr(parameters))

    event.listen(connection, "before_cursor_execute", record)
    try:
        response = _get(client, auth_headers, dog)
    finally:
        event.remove(connection, "before_cursor_execute", record)

    assert response.status_code == 200, response.text
    assert _by_key(response.json())[("TROT", "LH", "rom_stifle")]["diff"] == 1.0
    (parameters,) = seen  # 수치 행을 읽는 쿼리는 하나뿐이다
    assert str(base.id) in parameters and str(target.id) in parameters
    assert str(middle.id) not in parameters


def test_empty_tolerance_file_makes_every_comparable_item_unknown(
    client: TestClient, db: Session, dog, staff, auth_headers, tolerance
) -> None:
    tolerance({})
    base = make_session(db, dog, staff, date(2026, 10, 1))
    target = make_session(db, dog, staff, date(2026, 10, 20))
    add_metric(db, base, "rom_stifle", "RH", 38.2), add_metric(db, target, "rom_stifle", "RH", 42.0)
    add_metric(db, base, "rom_hip", "RH", 50.0), add_metric(db, target, "rom_hip", "RH", 44.0)
    add_metric(db, target, "rom_tarsus", "LH", 20.0)
    items = _by_key(_get(client, auth_headers, dog).json())
    assert {(item["judgement"], item["note"]["code"]) for key, item in items.items() if key[2] != "rom_tarsus"} == {
        ("UNKNOWN", "RANGE_NOT_SET")
    }
    assert items[("TROT", "RH", "rom_stifle")]["diff"] == 3.8
    assert items[("TROT", "LH", "rom_tarsus")]["judgement"] == "NOT_COMPARABLE"


def test_a_changed_model_is_unknown_even_with_a_tolerance(
    client: TestClient, db: Session, dog, staff, auth_headers, tolerance
) -> None:
    tolerance({"rom_stifle": 3.0})
    base = make_session(db, dog, staff, date(2026, 10, 1), model_version="v1")
    target = make_session(db, dog, staff, date(2026, 10, 20), model_version="v2")
    add_metric(db, base, "rom_stifle", "RH", 38.2), add_metric(db, target, "rom_stifle", "RH", 42.0)
    body = _get(client, auth_headers, dog).json()
    assert body["model_changed"] is True
    (item,) = body["items"]
    assert (item["judgement"], item["note"]["code"], item["diff"]) == ("UNKNOWN", "MODEL_CHANGED", 3.8)


def test_gait_types_are_never_compared_with_each_other_and_can_be_filtered(
    client: TestClient, db: Session, dog, staff, auth_headers, tolerance
) -> None:
    tolerance({"rom_stifle": 3.0})
    base = make_session(db, dog, staff, date(2026, 10, 1))
    target = make_session(db, dog, staff, date(2026, 10, 20))
    add_metric(db, base, "rom_stifle", "RH", 30.0, gait="WALK")
    add_metric(db, target, "rom_stifle", "RH", 40.0, gait="TROT")

    body = _get(client, auth_headers, dog).json()
    assert [(item["gait_type"], item["judgement"], item["note"]["code"]) for item in body["items"]] == [
        ("WALK", "NOT_COMPARABLE", "NO_DATA"),
        ("TROT", "NOT_COMPARABLE", "NO_DATA"),
    ]
    assert [item["gait_type"] for item in _get(client, auth_headers, dog, gait_type="TROT").json()["items"]] == ["TROT"]
    assert _get(client, auth_headers, dog, gait_type="PACE").json()["items"] == []
    assert _get(client, auth_headers, dog, gait_type="JOG").status_code == 422


def test_no_evaluation_words_anywhere_in_the_response(
    client: TestClient, db: Session, dog, staff, auth_headers, tolerance
) -> None:
    tolerance({"rom_stifle": 3.0, "rom_hip": 3.0})
    base = make_session(db, dog, staff, date(2026, 10, 1))
    target = make_session(db, dog, staff, date(2026, 10, 20))
    add_metric(db, base, "rom_stifle", "RH", 38.2), add_metric(db, target, "rom_stifle", "RH", 42.0)
    add_metric(db, base, "rom_hip", "RH", 50.0), add_metric(db, target, "rom_hip", "RH", 44.0)
    add_metric(db, base, "rom_elbow", "LF", 10.0), add_metric(db, target, "rom_elbow", "LF", 10.5)
    (
        add_metric(db, base, "rom_tarsus", "LH", None, reason="NOT_ENOUGH_CYCLES"),
        add_metric(db, target, "rom_tarsus", "LH", 1.0),
    )
    body = _get(client, auth_headers, dog).json()
    text = json.dumps(body, ensure_ascii=False).lower()
    assert not any(word in text for word in EVALUATION_WORDS)
    assert {item["judgement"] for item in body["items"]} == {"INCREASE", "DECREASE", "UNKNOWN", "NOT_COMPARABLE"}
    assert {item["judgement"] for item in body["items"]} <= JUDGEMENTS


def test_items_are_sorted_by_gait_then_focus_limb_then_metric_table_order(
    client: TestClient, db: Session, dog, staff, auth_headers, tolerance
) -> None:
    tolerance({})
    dog.focus_limb = "RH"
    db.flush()
    base = make_session(db, dog, staff, date(2026, 10, 1))
    target = make_session(db, dog, staff, date(2026, 10, 20))
    for session in (base, target):
        add_metric(db, session, "rom_stifle", "LH", 1.0)
        add_metric(db, session, "rom_stifle", "RH", 1.0)
        add_metric(db, session, "rom_hip", "RH", 1.0)
        add_metric(db, session, "walk_speed", "NONE", 1.0)
        add_metric(db, session, "paw_lift", "LF", 1.0)
        add_metric(db, session, "rom_stifle", "RH", 1.0, gait="WALK")
    body = _get(client, auth_headers, dog).json()
    assert [(item["gait_type"], item["limb"], item["metric_code"]) for item in body["items"]] == [
        ("WALK", "RH", "rom_stifle"),
        ("TROT", "RH", "rom_hip"),
        ("TROT", "RH", "rom_stifle"),
        ("TROT", "LF", "paw_lift"),
        ("TROT", "LH", "rom_stifle"),
        ("TROT", "NONE", "walk_speed"),
    ]


# ---- 기준·직전·지정 회차 ----


def test_previous_base_is_the_session_right_before_target_in_12_5_order(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    first = make_session(db, dog, staff, date(2026, 10, 1))
    second = make_session(db, dog, staff, date(2026, 10, 20), seq=0)
    third = make_session(db, dog, staff, date(2026, 10, 20), seq=1)  # 같은 날, 나중에 만든 회차

    body = _get(client, auth_headers, dog, base="PREVIOUS").json()
    assert (body["target"]["session_id"], body["base"]["session_id"], body["base"]["kind"]) == (
        str(third.id),
        str(second.id),
        "PREVIOUS",
    )
    body = _get(client, auth_headers, dog, base="PREVIOUS", target=str(second.id)).json()
    assert body["base"]["session_id"] == str(first.id)
    response = _get(client, auth_headers, dog, base="PREVIOUS", target=str(first.id))
    assert _error(response) == (400, "COMPARE_INVALID", {"reason": "NO_PREVIOUS"})


def test_base_can_be_a_session_id_and_baseline_follows_the_dog_setting(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    make_session(db, dog, staff, date(2026, 10, 1))
    second = make_session(db, dog, staff, date(2026, 10, 10))
    third = make_session(db, dog, staff, date(2026, 10, 20))

    body = _get(client, auth_headers, dog, base=str(second.id), target=str(third.id)).json()
    assert (body["base"]["session_id"], body["base"]["kind"]) == (str(second.id), "SESSION")

    dog.baseline_session_id = second.id
    db.flush()
    body = _get(client, auth_headers, dog).json()
    assert (body["base"]["session_id"], body["base"]["kind"], body["target"]["session_id"]) == (
        str(second.id),
        "BASELINE",
        str(third.id),
    )


def test_a_single_done_session_is_same_session(client: TestClient, db: Session, dog, staff, auth_headers) -> None:
    only = make_session(db, dog, staff, date(2026, 10, 1))
    assert _error(_get(client, auth_headers, dog)) == (400, "COMPARE_INVALID", {"reason": "SAME_SESSION"})
    response = _get(client, auth_headers, dog, base=str(only.id), target=str(only.id))
    assert _error(response) == (400, "COMPARE_INVALID", {"reason": "SAME_SESSION"})


def test_no_done_session_is_reported_before_anything_else(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    assert _error(_get(client, auth_headers, dog)) == (400, "COMPARE_INVALID", {"reason": "NO_DONE_SESSION"})
    measuring = make_session(db, dog, staff, date(2026, 10, 1), status="MEASURING", model_version=None)
    response = _get(client, auth_headers, dog, target=str(measuring.id))
    assert _error(response) == (400, "COMPARE_INVALID", {"reason": "NO_DONE_SESSION"})


def test_a_session_that_is_not_done_cannot_be_target_or_base(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    make_session(db, dog, staff, date(2026, 10, 1))
    done = make_session(db, dog, staff, date(2026, 10, 10))
    aggregating = make_session(db, dog, staff, date(2026, 10, 20), status="AGGREGATING", model_version=None)
    response = _get(client, auth_headers, dog, target=str(aggregating.id))
    assert _error(response) == (400, "COMPARE_INVALID", {"reason": "NOT_DONE"})
    response = _get(client, auth_headers, dog, base=str(aggregating.id), target=str(done.id))
    assert _error(response) == (400, "COMPARE_INVALID", {"reason": "NOT_DONE"})


def test_ids_outside_the_dog_are_404_and_bad_query_values_are_422(
    client: TestClient, db: Session, dog, staff, auth_headers, other_staff
) -> None:
    make_session(db, dog, staff, date(2026, 10, 1))
    make_session(db, dog, staff, date(2026, 10, 10))
    stranger = another_dog(db, staff.institution_id)
    foreign = make_session(db, stranger, staff, date(2026, 10, 10))

    assert _get(client, auth_headers, dog, target=str(foreign.id)).status_code == 404
    assert _get(client, auth_headers, dog, base=str(foreign.id)).status_code == 404
    assert _get(client, auth_headers, dog, base=str(uuid.uuid4())).status_code == 404
    assert _get(client, bearer(other_staff), dog).status_code == 404

    response = _get(client, auth_headers, dog, base="nonsense")
    assert response.status_code == 422
    assert response.json()["error"]["detail"]["fields"][0]["field"] == "base"
    response = _get(client, auth_headers, dog, target="abc")
    assert response.status_code == 422
    assert response.json()["error"]["detail"]["fields"][0]["field"] == "target"


def test_compare_needs_token(client: TestClient, dog) -> None:
    assert client.get(COMPARE.format(dog.id)).status_code == 401
