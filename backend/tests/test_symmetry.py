"""대칭 점수(BE-31, 명세 12.3, 15.7, 15.8). 식은 100 − 평균(대상 쌍의 대칭 지수)이고 100에 가까울수록 좌우가 비슷하다"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.symmetry import SCORE_PAIRS, score_of, session_score, session_scores
from tests.history_fixtures import add_metric, make_session

D = Decimal


def _result(client: TestClient, headers: dict, session) -> dict:
    response = client.get(f"/api/v1/sessions/{session.id}/result", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _history(client: TestClient, headers: dict, dog) -> list[dict]:
    response = client.get(f"/api/v1/dogs/{dog.id}/sessions", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


# ---- 식 ----


def test_one_pair_gives_100_minus_its_symmetry_index() -> None:
    # 대칭 지수 = 7.2 ÷ 34.6 × 100 = 20.81 → 100 − 20.81 = 79.19 → 79
    assert score_of({"TROT": [(D("31.0"), D("38.2"))]}) == 79


def test_score_is_the_mean_over_the_pairs_that_have_both_sides() -> None:
    pairs = [(D("50"), D("50")), (D("90"), D("110")), (None, D("40")), (D("30"), None), (None, None)]
    # 대칭 지수 0과 20의 평균 10 → 90. 한쪽이 없는 쌍은 평균에 넣지 않는다
    assert score_of({"TROT": pairs}) == 90


def test_no_pair_or_no_gait_gives_none_not_zero() -> None:
    assert score_of({}) is None
    assert score_of({"TROT": [(None, D("40")), (D("30"), None)]}) is None
    assert score_of({"TROT": []}) is None


def test_pair_whose_sum_is_zero_is_left_out() -> None:
    assert score_of({"TROT": [(D("0"), D("0"))]}) is None
    assert score_of({"TROT": [(D("0"), D("0")), (D("50"), D("50"))]}) == 100


def test_score_never_goes_below_zero() -> None:
    # 대칭 지수는 200까지 갈 수 있다(한쪽이 0). 평균이 100을 넘어도 0에서 멈춘다
    assert score_of({"TROT": [(D("0"), D("40")), (D("1"), D("100"))]}) == 0


def test_half_rounds_up() -> None:
    # 대칭 지수 21.5 → 78.5 → 79
    assert score_of({"TROT": [(D("110.75"), D("89.25"))]}) == 79


def test_gait_is_trot_then_walk_then_other_and_does_not_fall_through() -> None:
    same, apart = [(D("50"), D("50"))], [(D("90"), D("110"))]
    assert score_of({"WALK": same, "TROT": apart}) == 80
    assert score_of({"OTHER": apart, "WALK": same}) == 100
    assert score_of({"OTHER": apart}) == 80
    # 속보 행이 있는데 계산할 쌍이 없으면 평보로 넘어가지 않는다
    assert score_of({"TROT": [(D("50"), None)], "WALK": same}) is None


def test_the_five_pairs_are_the_ones_the_web_uses() -> None:
    assert SCORE_PAIRS == (
        ("rom_stifle", "LH", "RH"),
        ("rom_hip", "LH", "RH"),
        ("rom_elbow", "LF", "RF"),
        ("stride_length", "LH", "RH"),
        ("stance_ratio", "LH", "RH"),
    )


# ---- 행에서 계산 ----


def _fill(db: Session, session, *, gait: str = "TROT") -> None:
    """대상 쌍 셋과 점수에 넣지 않는 수치들. 대칭 지수 20.81, 0, 20 → 평균 13.60 → 86."""
    add_metric(db, session, "rom_stifle", "LH", 31.0, gait=gait)
    add_metric(db, session, "rom_stifle", "RH", 38.2, gait=gait)
    add_metric(db, session, "rom_hip", "LH", 25.0, gait=gait)
    add_metric(db, session, "rom_hip", "RH", 25.0, gait=gait)
    add_metric(db, session, "stride_length", "LH", 90.0, gait=gait)
    add_metric(db, session, "stride_length", "RH", 110.0, gait=gait)
    # 아래는 점수에 넣지 않는다: 앞다리의 걸음 길이, 대상이 아닌 수치, 한쪽만 있는 쌍
    add_metric(db, session, "stride_length", "LF", 10.0, gait=gait)
    add_metric(db, session, "stride_length", "RF", 200.0, gait=gait)
    add_metric(db, session, "rom_tarsus", "LH", 5.0, gait=gait)
    add_metric(db, session, "rom_tarsus", "RH", 60.0, gait=gait)
    add_metric(db, session, "rom_elbow", "LF", 40.0, gait=gait)
    add_metric(db, session, "stance_ratio", "LH", None, gait=gait, reason="NO_PASS_FOR_LIMB")
    add_metric(db, session, "stance_ratio", "RH", 60.0, gait=gait)


def test_rows_and_one_query_give_the_same_score(db: Session, dog, staff) -> None:
    session = make_session(db, dog, staff, date(2026, 10, 20))
    _fill(db, session)
    db.refresh(session)
    assert session_score(session.metrics) == 86
    assert session_scores(db, [session.id]) == {session.id: 86}


def test_scores_of_many_sessions_come_from_one_query(db: Session, dog, staff) -> None:
    trot = make_session(db, dog, staff, date(2026, 10, 1))
    _fill(db, trot)
    walk_only = make_session(db, dog, staff, date(2026, 10, 8))
    _fill(db, walk_only, gait="WALK")
    both = make_session(db, dog, staff, date(2026, 10, 15))
    add_metric(db, both, "rom_stifle", "LH", 50.0, gait="WALK")
    add_metric(db, both, "rom_stifle", "RH", 50.0, gait="WALK")
    add_metric(db, both, "rom_stifle", "LH", 90.0, gait="TROT")
    add_metric(db, both, "rom_stifle", "RH", 110.0, gait="TROT")
    one_side = make_session(db, dog, staff, date(2026, 10, 22))
    add_metric(db, one_side, "rom_stifle", "LH", 50.0)
    empty = make_session(db, dog, staff, date(2026, 10, 29))

    ids = [trot.id, walk_only.id, both.id, one_side.id, empty.id]
    assert session_scores(db, ids) == {trot.id: 86, walk_only.id: 86, both.id: 80, one_side.id: None}
    assert session_scores(db, []) == {}


# ---- API ----


def test_result_and_history_carry_the_same_score(client: TestClient, db: Session, dog, staff, auth_headers) -> None:
    session = make_session(db, dog, staff, date(2026, 10, 20))
    _fill(db, session)
    assert _result(client, auth_headers, session)["symmetry_score"] == 86
    assert _history(client, auth_headers, dog)[0]["symmetry_score"] == 86
    dog_out = client.get(f"/api/v1/dogs/{dog.id}", headers=auth_headers).json()
    assert dog_out["last_symmetry"] == 86


def test_score_is_null_without_pairs_and_for_unfinished_sessions(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    done = make_session(db, dog, staff, date(2026, 10, 1))
    add_metric(db, done, "rom_stifle", "LH", 31.0)
    measuring = make_session(db, dog, staff, date(2026, 10, 20), status="MEASURING", model_version=None)
    # 측정 중인 회차에 수치 행이 있어도(있을 수 없지만) 점수를 내지 않는다
    add_metric(db, measuring, "rom_stifle", "LH", 31.0)
    add_metric(db, measuring, "rom_stifle", "RH", 38.2)

    assert _result(client, auth_headers, done)["symmetry_score"] is None
    by_id = {item["id"]: item for item in _history(client, auth_headers, dog)}
    assert by_id[str(done.id)]["symmetry_score"] is None
    assert by_id[str(measuring.id)]["symmetry_score"] is None
