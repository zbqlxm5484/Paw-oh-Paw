"""보고서 내용 API(명세 15.7의 62번, 8절 7번, S15P31A404-276).

웹의 보고서 인쇄 화면이 그릴 글·표·숫자를 낸다. PDF와 같은 함수로 만든 값인지, 검사에 걸리면 내지 않는지,
인쇄 토큰으로는 그 회차만 열리는지를 본다. 문장·표 자체의 규칙은 test_report_module.py가 본다.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_print_token
from app.report import TEMPLATE_VERSION, ReportCheckError
from app.report.content import LEG_CODES, LEG_GAITS, compose_content, difference_level
from app.services import report_content as content_service
from app.services.report_input import build_report_input
from app.services.symmetry import SCORE_GAITS, SCORE_PAIRS
from app.services.tolerance import get_tolerance
from tests.conftest import bearer
from tests.history_fixtures import add_metric, add_report, make_session

CONTENT = "/api/v1/sessions/{}/report-content"
COMPARE = "/api/v1/dogs/{}/compare"


def _print_headers(session, staff) -> dict[str, str]:
    token, _ = create_print_token(session_id=session.id, institution_id=staff.institution_id)
    return {"Authorization": f"Bearer {token}"}


def _get(client: TestClient, session, headers: dict, edition: str | None = "OWNER"):
    params = {} if edition is None else {"edition": edition}
    return client.get(CONTENT.format(session.id), params=params, headers=headers)


def _code(response) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def _done_session(db: Session, dog, staff, measured_on: date, left: float, right: float):
    """DONE 회차 하나: 속보 뒷다리 무릎 가동 범위 두 줄과 판본 두 행."""
    session = make_session(db, dog, staff, measured_on)
    add_metric(db, session, "rom_stifle", "LH", left)
    add_metric(db, session, "rom_stifle", "RH", right)
    reports = {edition: add_report(db, session, edition, "DONE") for edition in ("OWNER", "VET")}
    return session, reports


@pytest.fixture
def two_sessions(db: Session, dog, staff):
    first, _ = _done_session(db, dog, staff, date(2026, 10, 1), 40.0, 41.0)
    second, reports = _done_session(db, dog, staff, date(2026, 10, 15), 47.0, 42.0)
    return first, second, reports


# ---- 내용 ----


def test_content_has_the_header_sentences_and_tables(client: TestClient, staff, dog, two_sessions) -> None:
    first, second, _ = two_sessions
    response = _get(client, second, bearer(staff))
    assert response.status_code == 200
    body = response.json()

    assert (body["session_id"], body["edition"], body["template_version"]) == (
        str(second.id),
        "OWNER",
        TEMPLATE_VERSION,
    )
    assert body["session"]["measured_on"] == "2026-10-15"
    assert body["session"]["round"] == 2
    assert body["dog"]["name"] == dog.name
    assert body["previous"] == {
        "session_id": str(first.id),
        "measured_on": "2026-10-01",
        "round": 1,
        "model_changed": False,
    }
    sentences = body["sentences"]
    assert sentences["edition_label"] == "보호자용"
    assert dog.name in sentences["title"]
    assert "보행 평가 보조 자료" in sentences["disclaimer"]
    assert sentences["previous_note"]

    (gait,) = body["gaits"]
    assert gait["gait_type"] == "TROT"
    (row,) = gait["rows"]
    assert row["metric_code"] == "rom_stifle"
    assert row["cells"]["LH"] == {"value": 47.0, "text": "47.0°", "reason": None}
    (line,) = gait["compare"]
    assert (line["left"], line["right"], line["comparable"]) == ("47.0°", "42.0°", True)
    assert line["diff_value"] == 5.0
    assert isinstance(line["symmetry_value"], float) and f"{line['symmetry_value']:.1f}%" == line["symmetry_index"]
    (change,) = gait["changes"]
    left = change["cells"]["LH"]
    assert (left["previous"], left["current"], left["diff"]) == ("40.0°", "47.0°", "+7.0°")


def test_content_is_what_the_pdf_is_made_from(client: TestClient, db: Session, staff, two_sessions) -> None:
    """같은 입력으로 PDF가 쓰는 함수(compose_content)를 불러 글과 표가 같은지 본다(화면과 PDF가 어긋나지 않는다)."""
    _, second, reports = two_sessions
    body = _get(client, second, bearer(staff), "VET").json()

    data = build_report_input(db, reports["VET"], tolerance=get_tolerance(get_settings().TOLERANCE_FILE))
    content = compose_content(data)
    assert body["sentences"]["intro"] == content.sentences.intro
    assert body["sentences"]["summary"] == content.sentences.summary
    assert body["sentences"]["caution"] == content.sentences.caution
    assert body["sentences"]["edition_label"] == "수의사용"
    table = content.tables[0]
    assert [row["label"] for row in body["gaits"][0]["rows"]] == [row.label for row in table.rows]
    assert body["gaits"][0]["rows"][0]["cells"]["RH"]["text"] == table.rows[0].cells["RH"].text


def test_first_session_has_no_previous_and_no_changes(client: TestClient, staff, two_sessions) -> None:
    first, _, _ = two_sessions
    body = _get(client, first, bearer(staff)).json()

    assert body["session"]["round"] == 1
    assert body["previous"] is None
    assert body["baseline"] is None  # 기준 회차가 이 회차 자신이다
    assert [item["round"] for item in body["history"]] == [1]
    assert body["sentences"]["previous_note"] is None
    assert [gait["changes"] for gait in body["gaits"]] == [[]]


# ---- 요청 검사 ----


@pytest.mark.parametrize("edition", [None, "PET", "owner"])
def test_edition_is_required_and_must_be_owner_or_vet(client: TestClient, staff, two_sessions, edition) -> None:
    _, second, _ = two_sessions
    assert _get(client, second, bearer(staff), edition).status_code == 422


def test_session_of_another_institution_is_404(client: TestClient, other_staff, two_sessions) -> None:
    _, second, _ = two_sessions
    assert _code(_get(client, second, bearer(other_staff))) == (404, "NOT_FOUND")


def test_session_that_is_not_done_is_409(client: TestClient, db: Session, staff, dog) -> None:
    session = make_session(db, dog, staff, date(2026, 10, 20), status="MEASURING")
    assert _code(_get(client, session, bearer(staff))) == (409, "SESSION_NOT_DONE")


# ---- 검사에 걸리면 내지 않는다 ----


def test_number_mismatch_is_409_and_gives_no_content(
    client: TestClient, staff, two_sessions, monkeypatch: pytest.MonkeyPatch
) -> None:
    """기준값이 실린 숫자와 다르면(여기서는 기준을 비워 '기준에 없는 숫자'로 만든다) 내용을 내지 않는다."""
    _, second, _ = two_sessions
    monkeypatch.setattr(content_service, "reference_numbers", lambda *args, **kwargs: {})

    response = _get(client, second, bearer(staff))
    assert _code(response) == (409, "REPORT_CHECK_FAILED")
    assert "sentences" not in response.text


def test_text_check_failure_is_409(client: TestClient, staff, two_sessions, monkeypatch: pytest.MonkeyPatch) -> None:
    _, second, _ = two_sessions

    def refuse(texts, *, edition, rules=None):
        raise ReportCheckError("forbidden=1")

    monkeypatch.setattr(content_service, "ensure_checked", refuse)
    assert _code(_get(client, second, bearer(staff))) == (409, "REPORT_CHECK_FAILED")


# ---- 인쇄 토큰 ----


def test_print_token_opens_the_content_of_its_session_only(client: TestClient, staff, two_sessions) -> None:
    first, second, _ = two_sessions
    headers = _print_headers(second, staff)

    by_print = _get(client, second, headers, "VET")
    assert by_print.status_code == 200
    assert by_print.json() == _get(client, second, bearer(staff), "VET").json()
    assert _code(_get(client, first, headers)) == (404, "NOT_FOUND")


def test_print_token_does_not_open_the_compare_api(client: TestClient, staff, dog, two_sessions) -> None:
    """직전 회차 비교는 내용 API의 changes로 받는다. 비교 API는 인쇄 토큰을 받지 않는다(11.6)."""
    _, second, _ = two_sessions
    response = client.get(
        COMPARE.format(dog.id),
        params={"target": str(second.id), "base": "PREVIOUS"},
        headers=_print_headers(second, staff),
    )
    assert _code(response) == (401, "AUTH_REQUIRED")


def test_print_token_reads_a_trashed_dog_but_login_does_not(
    client: TestClient, db: Session, staff, dog, two_sessions
) -> None:
    """휴지통에 든 반려견: 담당자에게는 404지만, 워커가 그 보고서도 만들므로 인쇄 토큰은 읽는다(12.5)."""
    _, second, _ = two_sessions
    dog.deleted_at = datetime.now(UTC)
    db.flush()

    assert _code(_get(client, second, bearer(staff))) == (404, "NOT_FOUND")
    headers = _print_headers(second, staff)
    assert _get(client, second, headers).status_code == 200
    assert client.get(f"/api/v1/sessions/{second.id}/result", headers=headers).status_code == 200


# ---- 회차 번호·대칭 점수·기준 회차·지난 회차(박규원 11-10) ----


def test_symmetry_score_baseline_and_history_come_from_the_server(client: TestClient, staff, dog, two_sessions) -> None:
    """화면이 대칭 점수의 차이나 그래프를 따로 계산하지 않게, 이 회차·기준 회차·지난 회차의 점수를 함께 낸다."""
    first, second, _ = two_sessions
    body = _get(client, second, bearer(staff)).json()
    result = client.get(f"/api/v1/sessions/{second.id}/result", headers=bearer(staff)).json()
    first_result = client.get(f"/api/v1/sessions/{first.id}/result", headers=bearer(staff)).json()

    assert body["session"]["symmetry_score"] == result["symmetry_score"]
    assert isinstance(body["session"]["symmetry_score"], int)
    assert body["baseline"] == {
        "session_id": str(first.id),
        "measured_on": "2026-10-01",
        "round": 1,
        "symmetry_score": first_result["symmetry_score"],
        "diff": result["symmetry_score"] - first_result["symmetry_score"],
    }
    assert body["history"] == [
        {"measured_on": "2026-10-01", "round": 1, "symmetry_score": first_result["symmetry_score"]},
        {"measured_on": "2026-10-15", "round": 2, "symmetry_score": result["symmetry_score"]},
    ]
    assert body["dog"]["focus_limb"] is None


def test_round_counts_failed_sessions_but_not_open_ones(
    client: TestClient, db: Session, staff, dog, two_sessions
) -> None:
    """화면과 같은 규칙: 분석 실패 회차도 세고, 측정 중 회차는 세지 않는다. 직전 회차는 여전히 바로 앞 DONE 회차다."""
    first, second, _ = two_sessions
    make_session(db, dog, staff, date(2026, 10, 8), status="FAILED")
    make_session(db, dog, staff, date(2026, 10, 10), status="MEASURING")

    body = _get(client, second, bearer(staff)).json()
    assert body["session"]["round"] == 3
    assert (body["previous"]["session_id"], body["previous"]["round"]) == (str(first.id), 1)
    assert [(item["round"], item["symmetry_score"] is None) for item in body["history"]] == [
        (1, False),
        (2, True),
        (3, False),
    ]


def test_designated_baseline_and_focus_limb(client: TestClient, db: Session, staff, dog) -> None:
    sessions = [_done_session(db, dog, staff, date(2026, 9, day), 40.0 + day, 41.0)[0] for day in (1, 8, 15)]
    dog.baseline_session_id = sessions[1].id
    dog.focus_limb = "LH"
    db.flush()

    body = _get(client, sessions[2], bearer(staff)).json()
    assert (body["baseline"]["session_id"], body["baseline"]["round"]) == (str(sessions[1].id), 2)
    assert body["dog"]["focus_limb"] == "LH"
    # 기준 회차가 이 회차 자신이면 낼 것이 없다
    assert _get(client, sessions[1], bearer(staff)).json()["baseline"] is None


def test_history_keeps_the_latest_eight(client: TestClient, db: Session, staff, dog) -> None:
    sessions = [_done_session(db, dog, staff, date(2026, 9, day), 40.0, 41.0)[0] for day in range(1, 11)]

    body = _get(client, sessions[-1], bearer(staff)).json()
    assert [item["round"] for item in body["history"]] == list(range(3, 11))
    assert body["session"]["round"] == 10


# ---- 화면이 계산하던 값(박규원 11-10): 다리 쌍 요약, 차이 단계 ----


def test_legs_pick_the_metric_with_the_largest_difference_of_each_pair(
    client: TestClient, db: Session, staff, dog
) -> None:
    session, _ = _done_session(db, dog, staff, date(2026, 10, 15), 47.0, 42.0)  # 무릎: 대칭 지수 11.2
    add_metric(db, session, "rom_hip", "LH", 30.0)
    add_metric(db, session, "rom_hip", "RH", 36.0)  # 고관절: 18.2 → 뒷다리에서 가장 크다
    add_metric(db, session, "rom_elbow", "LF", 50.0)
    add_metric(db, session, "rom_elbow", "RF", 51.0)  # 팔꿈치: 2.0 → 비슷

    body = _get(client, session, bearer(staff)).json()
    legs = {leg["pair"]: leg for leg in body["legs"]}

    assert set(legs) == {"FORE", "HIND"}
    hind = legs["HIND"]
    assert (hind["metric_code"], hind["gait_type"], hind["level"], hind["weak_limb"]) == (
        "rom_hip",
        "TROT",
        "LARGE",
        "LH",
    )
    assert hind["symmetry_index"] == f"{hind['symmetry_value']:.1f}%" == "18.2%"
    fore = legs["FORE"]
    assert (fore["metric_code"], fore["level"], fore["weak_limb"]) == ("rom_elbow", "SIMILAR", None)
    # 요약의 숫자는 좌우 비교 줄의 것이다(수치 대조를 지난 값)
    lines = {(line["pair"], line["metric_code"]): line for line in body["gaits"][0]["compare"]}
    assert lines[("HIND", "rom_hip")]["symmetry_value"] == hind["symmetry_value"]


def test_legs_skip_a_pair_without_a_comparable_target_metric(client: TestClient, staff, two_sessions) -> None:
    _, second, _ = two_sessions  # 뒷다리 무릎만 있다
    assert [leg["pair"] for leg in _get(client, second, bearer(staff)).json()["legs"]] == ["HIND"]


def test_symmetry_level_uses_the_same_bounds_on_100_minus_the_score(client: TestClient, staff, two_sessions) -> None:
    _, second, _ = two_sessions
    session = _get(client, second, bearer(staff)).json()["session"]
    assert session["symmetry_level"] == difference_level(100 - session["symmetry_score"])
    assert [difference_level(value) for value in (0, 4.9, 5, 9.9, 10, 40)] == [
        "SIMILAR",
        "SIMILAR",
        "SLIGHT",
        "SLIGHT",
        "LARGE",
        "LARGE",
    ]


def test_leg_targets_and_gait_order_follow_the_symmetry_score() -> None:
    """다리 쌍 요약은 대칭 점수(12.3)와 같은 수치·같은 보행 유형 순서를 본다."""
    assert {code for codes in LEG_CODES.values() for code in codes} == {code for code, _, _ in SCORE_PAIRS}
    assert LEG_GAITS == SCORE_GAITS


def test_symmetry_score_that_differs_between_the_two_paths_is_409(
    client: TestClient, staff, two_sessions, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, second, _ = two_sessions
    monkeypatch.setattr(content_service, "session_scores", lambda db, ids: {session_id: 1 for session_id in ids})
    assert _code(_get(client, second, bearer(staff))) == (409, "REPORT_CHECK_FAILED")
