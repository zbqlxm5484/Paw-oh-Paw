"""수치 추이 API(명세 5절, 15.8의 23번, BE-18, S15P31A404-198)."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import bearer
from tests.history_fixtures import add_metric, make_session

TRENDS = "/api/v1/dogs/{}/trends"


def _get(client: TestClient, headers: dict, dog, **params):
    params.setdefault("gait_type", "TROT")
    return client.get(TRENDS.format(dog.id), params=params, headers=headers)


def _body(client: TestClient, headers: dict, dog, **params) -> dict:
    response = _get(client, headers, dog, **params)
    assert response.status_code == 200, response.text
    return response.json()


def _stifle_sessions(db: Session, dog, staff) -> tuple:
    first = make_session(db, dog, staff, date(2026, 10, 1))
    add_metric(db, first, "rom_stifle", "LH", 38.2)
    add_metric(db, first, "rom_stifle", "RH", 45.4)
    second = make_session(db, dog, staff, date(2026, 10, 20), seq=0, model_version="v2")
    add_metric(db, second, "rom_stifle", "LH", None, reason="LOW_CONFIDENCE")
    add_metric(db, second, "rom_stifle", "RH", 42.0)
    third = make_session(db, dog, staff, date(2026, 10, 20), seq=1, model_version="v2")
    add_metric(db, third, "rom_stifle", "RH", 43.0)
    failed = make_session(db, dog, staff, date(2026, 10, 10), status="FAILED")
    add_metric(db, failed, "rom_stifle", "RH", 99.0)  # DONE이 아니라 빠진다
    make_session(db, dog, staff, date(2026, 10, 25), status="MEASURING", model_version=None)
    return first, second, third


def test_series_follow_done_sessions_in_order_with_focus_limb_first(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    dog.focus_limb = "RH"
    db.flush()
    first, second, third = _stifle_sessions(db, dog, staff)

    body = _body(client, auth_headers, dog, metric_code="rom_stifle")
    assert (body["dog_id"], body["metric_code"], body["unit"], body["gait_type"]) == (
        str(dog.id),
        "rom_stifle",
        "deg",
        "TROT",
    )
    assert [series["limb"] for series in body["series"]] == ["RH", "LH"]
    right, left = body["series"]
    assert right["points"] == [
        {
            "session_id": str(first.id),
            "measured_on": "2026-10-01",
            "value": 45.4,
            "measurable": True,
            "unmeasurable_reason": None,
            "model_version": "v1",
        },
        {
            "session_id": str(second.id),
            "measured_on": "2026-10-20",
            "value": 42.0,
            "measurable": True,
            "unmeasurable_reason": None,
            "model_version": "v2",
        },
        {
            "session_id": str(third.id),
            "measured_on": "2026-10-20",
            "value": 43.0,
            "measurable": True,
            "unmeasurable_reason": None,
            "model_version": "v2",
        },
    ]
    # 행이 없는 회차(third)는 점이 없고, 측정 불가(second)는 value가 null인 점이다
    assert [(point["session_id"], point["value"]) for point in left["points"]] == [
        (str(first.id), 38.2),
        (str(second.id), None),
    ]
    assert left["points"][1]["measurable"] is False
    assert left["points"][1]["unmeasurable_reason"]["code"] == "LOW_CONFIDENCE"
    # 좌우 차이는 양쪽이 다 측정된 첫 회차만. diff = 왼쪽 − 오른쪽, 대칭 지수는 12.3 식(Decimal, 둘째 자리)
    assert body["lr_diff"] == [
        {
            "pair": "HIND",
            "points": [
                {"session_id": str(first.id), "measured_on": "2026-10-01", "diff": -7.2, "symmetry_index": 17.22}
            ],
        }
    ]


def test_limb_filter_keeps_one_series_and_only_its_pair(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    _stifle_sessions(db, dog, staff)
    body = _body(client, auth_headers, dog, metric_code="rom_stifle", limb="LH")
    assert [series["limb"] for series in body["series"]] == ["LH"]
    assert [series["pair"] for series in body["lr_diff"]] == ["HIND"]
    # 그 수치에 없는 다리를 주면 비어 있다(앞다리에는 무릎이 없다)
    body = _body(client, auth_headers, dog, metric_code="rom_stifle", limb="LF")
    assert body["series"] == [] and body["lr_diff"] == []


def test_whole_body_metric_has_one_series_and_no_lr_diff(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    session = make_session(db, dog, staff, date(2026, 10, 1))
    add_metric(db, session, "walk_speed", "NONE", 1.25)
    body = _body(client, auth_headers, dog, metric_code="walk_speed")
    assert body["unit"] == "body_per_sec"
    assert [(series["limb"], len(series["points"])) for series in body["series"]] == [("NONE", 1)]
    assert body["lr_diff"] == []


@pytest.mark.parametrize(
    ("focus_limb", "limbs", "pairs"),
    [(None, ["LF", "RF", "LH", "RH"], ["FORE", "HIND"]), ("LH", ["LH", "LF", "RF", "RH"], ["HIND", "FORE"])],
)
def test_four_limb_metric_lists_every_limb_with_the_focus_pair_first(
    client: TestClient, db: Session, dog, staff, auth_headers, focus_limb: str | None, limbs: list, pairs: list
) -> None:
    dog.focus_limb = focus_limb
    db.flush()
    session = make_session(db, dog, staff, date(2026, 10, 1))
    add_metric(db, session, "paw_lift", "LF", 10.0)
    add_metric(db, session, "paw_lift", "RF", 10.0)  # 왼쪽과 같으면 diff 0, 대칭 지수 0
    add_metric(db, session, "paw_lift", "LH", 12.0)
    body = _body(client, auth_headers, dog, metric_code="paw_lift")
    assert [series["limb"] for series in body["series"]] == limbs
    assert {series["limb"]: len(series["points"]) for series in body["series"]} == {"LF": 1, "RF": 1, "LH": 1, "RH": 0}
    assert [series["pair"] for series in body["lr_diff"]] == pairs
    by_pair = {series["pair"]: series["points"] for series in body["lr_diff"]}
    assert by_pair["FORE"][0]["diff"] == 0.0 and by_pair["FORE"][0]["symmetry_index"] == 0.0
    assert by_pair["HIND"] == []  # 오른뒤가 없어 좌우 차이를 낼 수 없다


def test_date_range_is_inclusive(client: TestClient, db: Session, dog, staff, auth_headers) -> None:
    first, second, third = _stifle_sessions(db, dog, staff)
    ids = lambda body: [point["session_id"] for point in body["series"][1]["points"]]  # noqa: E731 (RH 계열)
    assert ids(_body(client, auth_headers, dog, metric_code="rom_stifle")) == [
        str(s.id) for s in (first, second, third)
    ]
    body = _body(client, auth_headers, dog, metric_code="rom_stifle", **{"from": "2026-10-20"})
    assert ids(body) == [str(second.id), str(third.id)]
    body = _body(client, auth_headers, dog, metric_code="rom_stifle", to="2026-10-01")
    assert ids(body) == [str(first.id)]
    body = _body(client, auth_headers, dog, metric_code="rom_stifle", **{"from": "2026-10-02", "to": "2026-10-19"})
    assert ids(body) == [] and body["lr_diff"][0]["points"] == []


def test_gait_types_are_kept_apart(client: TestClient, db: Session, dog, staff, auth_headers) -> None:
    session = make_session(db, dog, staff, date(2026, 10, 1))
    add_metric(db, session, "rom_stifle", "RH", 40.0, gait="WALK")
    add_metric(db, session, "rom_stifle", "RH", 50.0, gait="TROT")
    trot = _body(client, auth_headers, dog, metric_code="rom_stifle", gait_type="TROT")
    walk = _body(client, auth_headers, dog, metric_code="rom_stifle", gait_type="WALK")
    assert [point["value"] for point in trot["series"][1]["points"]] == [50.0]
    assert [point["value"] for point in walk["series"][1]["points"]] == [40.0]


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"metric_code": "rom_knee", "gait_type": "TROT"}, "metric_code"),  # 12.3 표에 없는 코드
        ({"gait_type": "TROT"}, "metric_code"),
        ({"metric_code": "rom_stifle", "gait_type": "JOG"}, "gait_type"),
        ({"metric_code": "rom_stifle", "gait_type": "TROT", "limb": "LEFT"}, "limb"),
        ({"metric_code": "rom_stifle", "gait_type": "TROT", "from": "2026-13-01"}, "from"),
    ],
)
def test_bad_query_values_are_422_and_name_the_field(
    client: TestClient, dog, auth_headers, params: dict, field: str
) -> None:
    response = client.get(TRENDS.format(dog.id), params=params, headers=auth_headers)
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["detail"]["fields"][0]["field"] == field


def test_missing_gait_type_is_422(client: TestClient, dog, auth_headers) -> None:
    response = client.get(TRENDS.format(dog.id), params={"metric_code": "rom_stifle"}, headers=auth_headers)
    assert response.status_code == 422 and response.json()["error"]["detail"]["fields"][0]["field"] == "gait_type"


def test_other_institution_dog_is_404_and_token_is_required(client: TestClient, dog, auth_headers, other_staff) -> None:
    assert _get(client, bearer(other_staff), dog, metric_code="rom_stifle").status_code == 404
    assert (
        client.get(TRENDS.format(dog.id), params={"metric_code": "rom_stifle", "gait_type": "TROT"}).status_code == 401
    )
