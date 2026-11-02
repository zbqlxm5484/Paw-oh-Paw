"""측정 종료·회차 집계·회차 결과(명세 12.3, 12.4, 15.7, 17.4 BE-13·14·21)."""

import json
import statistics
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.clients.analysis import MockAnalysisClient, load_fixture
from app.core.config import get_settings
from app.core.dates import today_local
from app.models import MeasureSession, Report, SessionMetric, Shot
from app.report import TEMPLATE_VERSION
from app.services import aggregation
from app.services.aggregation import METRICS, PassMetrics, build_metric_rows
from app.services.analysis_results import apply_result, parse_result
from app.storage.base import get_storage
from app.storage.keys import analysis_key
from app.worker.main import WorkerStats, aggregate_finished, run_once
from tests.conftest import bearer

# ---- 준비 ----


def _session(db: Session, dog, staff, status: str = "AGGREGATING") -> MeasureSession:
    session = MeasureSession(
        dog_id=dog.id, staff_id=staff.id, measured_on=today_local(), size_class="MEDIUM", status=status
    )
    db.add(session)
    db.flush()
    return session


def _shot(db: Session, session: MeasureSession, seq_no: int, status: str = "SUBMITTED", **values: Any) -> Shot:
    key = f"{uuid.uuid4()}/{uuid.uuid4()}/{session.id}/{uuid.uuid4()}/original.mp4"
    get_storage().write_bytes(key, b"\x00\x00\x00\x18ftypmp42 fake video")
    values.setdefault("uploaded_at", datetime.now(UTC))
    shot = Shot(
        session_id=session.id,
        seq_no=seq_no,
        status=status,
        original_key=key,
        width=1920,
        height=1080,
        fps=Decimal("30"),
        duration_sec=Decimal("4.5"),
        bitrate_kbps=8000,
        codec="h264",
        **values,
    )
    db.add(shot)
    db.flush()
    return shot


def _pass(index: int, side: str, gait: str | None = "trot", reason: str | None = None, **metrics: Any) -> dict:
    return {
        "index": index,
        "start_frame": index * 100,
        "end_frame": index * 100 + 50,
        "camera_side": side,
        "gait": gait,
        "valid": reason is None,
        "reason_code": reason,
        "metrics": metrics,
    }


def _value(value: float, unit: str = "deg") -> dict:
    return {"value": value, "unit": unit}


def _result(*passes: dict, version: str = "0.1.0/v1/a4261a10", validity: str = "partial") -> dict:
    return {
        "validity": validity,
        "validity_reason": None,
        "passes": list(passes),
        "model": {"name": "fs-v4", "version": version},
    }


def _done_shot(db: Session, session: MeasureSession, dog, seq_no: int, result: dict) -> Shot:
    """워커가 결과를 저장한 뒤의 촬영: analysis.json이 있고 통과 행이 들어 있다."""
    shot = _shot(db, session, seq_no)
    key = analysis_key(dog.institution_id, dog.id, session.id, shot.id)
    get_storage().write_bytes(key, json.dumps(result).encode("utf-8"))
    assert apply_result(
        db, shot.id, parse_result(result, shot_id=shot.id), analysis_key=key, analyzed_at=datetime.now(UTC)
    )
    db.flush()
    db.refresh(shot)
    return shot


def _aggregate(db: Session) -> WorkerStats:
    # 워커의 rollback이 준비한 행까지 되돌리지 않게 먼저 저장한다(db 픽스처의 commit은 세이브포인트만 확정한다)
    db.commit()
    stats = WorkerStats()
    aggregate_finished(db, get_storage(), stats)
    db.expire_all()
    return stats


def _result_url(session_id: Any) -> str:
    return f"/api/v1/sessions/{session_id}/result"


def _metric(gait: dict, code: str, limb: str) -> dict:
    return next(row for row in gait["metrics"] if row["metric_code"] == code and row["limb"] == limb)


def _compare(gait: dict, code: str, pair: str) -> dict:
    return next(row for row in gait["limb_compare"] if row["metric_code"] == code and row["pair"] == pair)


def _pass_metrics(side: str = "RIGHT", gait: str = "TROT", **metrics: Any) -> PassMetrics:
    return PassMetrics(shot_id=uuid.uuid4(), gait_type=gait, camera_side=side, metrics=metrics)


def _rows(*passes: PassMetrics) -> dict[tuple[str, str], Any]:
    return {(row.metric_code, row.limb): row for row in build_metric_rows(list(passes))}


# ---- 측정 종료 (BE-13) ----


def test_complete_answers_aggregating_right_away(
    client: TestClient, db: Session, dog, staff, auth_headers: dict
) -> None:
    session = _session(db, dog, staff, status="MEASURING")
    _shot(db, session, 1, status="ANALYZING", job_id="job-1")  # 분석이 끝나기를 기다리지 않는다

    response = client.post(f"/api/v1/sessions/{session.id}/complete", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "AGGREGATING"
    assert body["completed_at"] is not None and body["completed_at"].endswith("Z")
    assert body["aggregated_at"] is None
    assert body["staff"]["id"] == str(staff.id)


def test_complete_without_shots_is_session_empty(
    client: TestClient, db: Session, dog, staff, auth_headers: dict
) -> None:
    session = _session(db, dog, staff, status="MEASURING")

    response = client.post(f"/api/v1/sessions/{session.id}/complete", headers=auth_headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SESSION_EMPTY"


def test_complete_twice_is_session_closed_and_blocks_upload(
    client: TestClient, db: Session, dog, staff, auth_headers: dict
) -> None:
    session = _session(db, dog, staff, status="MEASURING")
    _shot(db, session, 1, status="DONE")
    url = f"/api/v1/sessions/{session.id}"
    assert client.post(f"{url}/complete", headers=auth_headers).status_code == 200

    again = client.post(f"{url}/complete", headers=auth_headers)
    upload = client.post(
        f"{url}/shots", headers=auth_headers, files={"file": ("a.mp4", b"not checked yet", "video/mp4")}
    )

    assert again.status_code == 409 and again.json()["error"]["code"] == "SESSION_CLOSED"
    assert upload.status_code == 409 and upload.json()["error"]["code"] == "SESSION_CLOSED"


def test_complete_other_institution_is_not_found(client: TestClient, db: Session, dog, staff, other_staff) -> None:
    session = _session(db, dog, staff, status="MEASURING")
    _shot(db, session, 1)

    response = client.post(f"/api/v1/sessions/{session.id}/complete", headers=bearer(other_staff))

    assert response.status_code == 404
    db.expire_all()
    assert db.get(MeasureSession, session.id).status == "MEASURING"


# ---- 회차 집계: 워커 (BE-13, 12.4) ----


@pytest.mark.parametrize("status", ["UPLOADED", "SUBMITTED", "ANALYZING"])
def test_aggregation_waits_for_unfinished_shots(db: Session, dog, staff, status: str) -> None:
    session = _session(db, dog, staff)
    _done_shot(db, session, dog, 1, _result(_pass(1, "right", rom_stifle=_value(40.0))))
    waiting = _shot(db, session, 2, status=status)

    assert _aggregate(db).aggregated == 0
    assert db.get(MeasureSession, session.id).status == "AGGREGATING"

    db.execute(update(Shot).where(Shot.id == waiting.id).values(status="FAILED", fail_reason="ANALYSIS_FAILED"))
    assert _aggregate(db).aggregated == 1
    assert db.get(MeasureSession, session.id).status == "DONE"


def test_measuring_session_is_not_aggregated(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff, status="MEASURING")
    _done_shot(db, session, dog, 1, _result(_pass(1, "right", rom_stifle=_value(40.0))))

    assert _aggregate(db).aggregated == 0
    assert db.get(MeasureSession, session.id).status == "MEASURING"


def test_done_session_gets_report_rows_in_the_same_step(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    _done_shot(db, session, dog, 1, _result(_pass(1, "right", rom_stifle=_value(40.0))))

    _aggregate(db)

    row = db.get(MeasureSession, session.id)
    assert row.status == "DONE" and row.aggregated_at is not None and row.fail_reason is None
    assert (row.model_name, row.model_version) == ("fs-v4", "0.1.0/v1/a4261a10")
    reports = db.scalars(select(Report).where(Report.session_id == session.id)).all()
    assert sorted(report.edition for report in reports) == ["OWNER", "VET"]
    assert {report.status for report in reports} == {"PENDING"}
    assert {report.template_version for report in reports} == {TEMPLATE_VERSION}


def test_session_keeps_the_last_shots_model_version(db: Session, dog, staff, caplog) -> None:
    session = _session(db, dog, staff)
    _done_shot(db, session, dog, 1, _result(_pass(1, "right"), version="old"))
    _done_shot(db, session, dog, 2, _result(_pass(1, "left"), version="new"))

    _aggregate(db)

    assert db.get(MeasureSession, session.id).model_version == "new"
    assert "mixes model versions" in caplog.text


def test_unreadable_analysis_json_fails_only_that_session(db: Session, dog, staff) -> None:
    broken = _session(db, dog, staff)
    shot = _done_shot(db, broken, dog, 1, _result(_pass(1, "right", rom_stifle=_value(40.0))))
    get_storage().write_bytes(shot.analysis_key, b"{not json")
    good = _session(db, dog, staff)
    _done_shot(db, good, dog, 1, _result(_pass(1, "right", rom_stifle=_value(40.0))))

    stats = _aggregate(db)

    assert (stats.aggregated, stats.aggregation_failed) == (1, 1)
    row = db.get(MeasureSession, broken.id)
    assert (row.status, row.fail_reason) == ("FAILED", "AGGREGATION_FAILED")
    assert db.scalars(select(Report).where(Report.session_id == broken.id)).all() == []
    assert db.get(MeasureSession, good.id).status == "DONE"


def test_missing_analysis_file_fails_the_session(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    shot = _done_shot(db, session, dog, 1, _result(_pass(1, "right")))
    get_storage().delete(shot.analysis_key)

    assert _aggregate(db).aggregation_failed == 1
    assert db.get(MeasureSession, session.id).fail_reason == "AGGREGATION_FAILED"


def test_db_error_is_retried_next_loop(db: Session, dog, staff, monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session(db, dog, staff)
    _done_shot(db, session, dog, 1, _result(_pass(1, "right", rom_stifle=_value(40.0))))
    real = aggregation.aggregate_session

    def boom(*args: Any, **kwargs: Any) -> bool:
        raise RuntimeError("db went away")

    monkeypatch.setattr("app.worker.main.aggregate_session", boom)
    stats = _aggregate(db)
    assert (stats.aggregated, stats.aggregation_failed) == (0, 0)
    assert db.get(MeasureSession, session.id).status == "AGGREGATING"

    monkeypatch.setattr("app.worker.main.aggregate_session", real)
    assert _aggregate(db).aggregated == 1


def test_session_deleted_before_lock_writes_nothing(db: Session) -> None:
    assert aggregation.aggregate_session(db, get_storage(), uuid.uuid4(), now=datetime.now(UTC)) is False


# ---- 회차 값 만들기 (12.3) ----


def test_session_value_is_the_median_of_measured_passes() -> None:
    rows = _rows(
        _pass_metrics(rom_stifle=_value(40.0)),
        _pass_metrics(rom_stifle=_value(50.0)),
        _pass_metrics(rom_stifle=_value(42.0)),
        _pass_metrics(rom_stifle={"value": None, "reason": "LOW_CONFIDENCE"}),
    )

    row = rows[("rom_stifle", "RH")]
    assert row.value == Decimal("42.0") and row.measurable is True and row.n_passes == 3
    assert row.unmeasurable_reason is None


def test_median_of_an_even_count_keeps_decimal_precision() -> None:
    rows = _rows(_pass_metrics(rom_stifle=_value(42.1)), _pass_metrics(rom_stifle=_value(38.2)))

    assert rows[("rom_stifle", "RH")].value == Decimal("40.15")


def test_camera_side_decides_the_limb_and_suffix_decides_front_or_hind() -> None:
    rows = _rows(
        _pass_metrics(
            side="LEFT",
            rom_shoulder=_value(11.0),
            rom_hip=_value(22.0),
            paw_lift_front=_value(3.0, "pct_body"),
            paw_lift_hind=_value(4.0, "pct_body"),
        )
    )

    assert rows[("rom_shoulder", "LF")].value == Decimal("11.0")
    assert rows[("rom_hip", "LH")].value == Decimal("22.0")
    assert rows[("paw_lift", "LF")].value == Decimal("3.0")
    assert rows[("paw_lift", "LH")].value == Decimal("4.0")


def test_limb_without_a_pass_is_no_pass_for_limb() -> None:
    rows = _rows(_pass_metrics(side="RIGHT", rom_stifle=_value(40.0)))

    row = rows[("rom_stifle", "LH")]
    assert row.value is None and row.measurable is False
    assert row.unmeasurable_reason == "NO_PASS_FOR_LIMB" and row.n_passes == 0
    assert row.unit == "deg"


def test_all_passes_unmeasurable_keeps_the_most_common_reason() -> None:
    low = {"value": None, "reason": "LOW_CONFIDENCE"}
    rows = _rows(
        _pass_metrics(rom_stifle={"value": None, "reason": "NOT_ENOUGH_CYCLES"}),
        _pass_metrics(rom_stifle=low),
        _pass_metrics(rom_stifle=low),
    )

    row = rows[("rom_stifle", "RH")]
    assert row.value is None and row.unmeasurable_reason == "LOW_CONFIDENCE" and row.n_passes == 3


def test_metric_no_pass_sent_has_no_row() -> None:
    assert ("rom_stifle", "RH") not in _rows(_pass_metrics(rom_hip=_value(40.0)))


@pytest.mark.parametrize("raw", ["41.0", True, float("nan"), float("inf"), 1_000_000, 10**400])
def test_unusable_value_is_unmeasurable_not_a_stored_number(raw: Any) -> None:
    row = _rows(_pass_metrics(rom_stifle={"value": raw}))[("rom_stifle", "RH")]

    assert row.value is None and row.unmeasurable_reason == "UNKNOWN_REASON"


def test_unknown_reason_code_is_stored_as_unknown_reason() -> None:
    row = _rows(_pass_metrics(rom_stifle={"value": None, "reason": "SOMETHING_NEW"}))[("rom_stifle", "RH")]

    assert row.unmeasurable_reason == "UNKNOWN_REASON"


def test_gait_cycles_is_a_sum_and_whole_body_covers_both_sides() -> None:
    rows = _rows(
        _pass_metrics(side="RIGHT", gait_cycles=_value(3, "count"), walk_speed=_value(2.0, "body_per_sec")),
        _pass_metrics(side="LEFT", gait_cycles=_value(4, "count"), walk_speed=_value(3.0, "body_per_sec")),
    )

    assert rows[("gait_cycles", "NONE")].value == Decimal("7") and rows[("gait_cycles", "NONE")].n_passes == 2
    assert rows[("walk_speed", "NONE")].value == Decimal("2.5")


def test_stifle_cv_uses_all_cycles_of_the_limb() -> None:
    rows = _rows(
        _pass_metrics(stifle_cycle_rom={"values": [46.1, 48.0], "unit": "deg"}),
        _pass_metrics(stifle_cycle_rom={"values": [47.6], "unit": "deg"}),
        _pass_metrics(side="LEFT", stifle_cycle_rom={"values": [10.0, 90.0], "unit": "deg"}),
    )

    cycles = [Decimal("46.1"), Decimal("48.0"), Decimal("47.6")]
    row = rows[("stifle_cv", "RH")]
    assert row.value == statistics.stdev(cycles) / statistics.mean(cycles) * 100
    assert row.unit == "pct" and row.n_passes == 2
    assert rows[("stifle_cv", "LH")].n_passes == 1


@pytest.mark.parametrize(
    "entry", [{"values": [46.1]}, {"values": []}, {"values": [0, 0]}, {"values": ["x", None]}, {"reason": None}]
)
def test_stifle_cv_needs_two_cycles_and_a_nonzero_mean(entry: dict) -> None:
    row = _rows(_pass_metrics(stifle_cycle_rom=entry))[("stifle_cv", "RH")]

    assert row.value is None and row.unmeasurable_reason == "NOT_ENOUGH_CYCLES"


def test_stifle_cv_keeps_the_reason_the_engine_sent() -> None:
    row = _rows(_pass_metrics(stifle_cycle_rom={"value": None, "reason": "LOW_CONFIDENCE"}))[("stifle_cv", "RH")]

    assert row.unmeasurable_reason == "LOW_CONFIDENCE"


def test_only_valid_walk_and_trot_passes_are_aggregated(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    _done_shot(
        db,
        session,
        dog,
        1,
        _result(
            _pass(1, "right", gait="walk", rom_stifle=_value(10.0)),
            _pass(2, "right", gait="trot", rom_stifle=_value(20.0)),
            _pass(3, "right", gait="pace", rom_stifle=_value(30.0)),
            _pass(4, "right", gait=None, reason="RUNNING", rom_stifle=_value(40.0)),
        ),
    )

    _aggregate(db)

    rows = db.scalars(
        select(SessionMetric).where(
            SessionMetric.session_id == session.id,
            SessionMetric.metric_code == "rom_stifle",
            SessionMetric.limb == "RH",
        )
    ).all()
    assert {row.gait_type: row.value for row in rows} == {"WALK": Decimal("10.0000"), "TROT": Decimal("20.0000")}


# ---- 회차 결과 조회 (BE-14) ----


def test_result_before_done_is_session_not_done(
    client: TestClient, db: Session, dog, staff, auth_headers: dict
) -> None:
    for status in ("MEASURING", "AGGREGATING", "FAILED"):
        session = _session(db, dog, staff, status=status)

        response = client.get(_result_url(session.id), headers=auth_headers)

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "SESSION_NOT_DONE"


def test_result_of_other_institution_is_not_found(client: TestClient, db: Session, dog, staff, other_staff) -> None:
    session = _session(db, dog, staff, status="DONE")

    assert client.get(_result_url(session.id), headers=bearer(other_staff)).status_code == 404
    assert client.get(_result_url(uuid.uuid4()), headers=bearer(other_staff)).status_code == 404


def test_result_needs_login(client: TestClient, db: Session, dog, staff) -> None:
    session = _session(db, dog, staff, status="DONE")

    assert client.get(_result_url(session.id)).status_code == 401


def test_end_to_end_with_mock_client(client: TestClient, db: Session, dog, auth_headers: dict) -> None:
    """측정 종료를 먼저 눌러도 워커가 분석을 끝낸 뒤 집계한다. 화면 값 = 행 값 = 분석 결과 JSON의 중앙값(PR-F09-05)."""
    session_id = client.post(f"/api/v1/dogs/{dog.id}/sessions", json={}, headers=auth_headers).json()["id"]
    session = db.get(MeasureSession, uuid.UUID(session_id))
    _shot(db, session, 1, status="UPLOADED", uploaded_at=datetime.now(UTC))
    assert client.post(f"/api/v1/sessions/{session_id}/complete", headers=auth_headers).status_code == 200
    settings = get_settings().model_copy(update={"WORKER_MAX_IN_FLIGHT_PER_INSTITUTION": 100})
    mock = MockAnalysisClient(delay_sec=0, case="valid")

    for _ in range(3):
        run_once(db, mock, settings, get_storage())
    response = client.get(_result_url(session_id), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "DONE" and body["aggregated_at"] is not None
    assert body["pass_counts"] == {"measured": 4, "used": 4, "excluded": 0}
    assert body["shot_counts"] == {"total": 1, "failed": 0, "invalid": 0}
    assert body["notices"] == [] and body["exclude_summary"] == []
    assert [gait["gait_type"] for gait in body["gaits"]] == ["TROT"]

    fixture = load_fixture("result_valid")["passes"]
    for side, limb in (("right", "RH"), ("left", "LH")):
        expected = statistics.median(
            Decimal(str(item["metrics"]["rom_stifle"]["value"])) for item in fixture if item["camera_side"] == side
        )
        row = _metric(body["gaits"][0], "rom_stifle", limb)
        assert row["value"] == float(expected) and row["n_passes"] == 2
        stored = db.scalars(
            select(SessionMetric).where(
                SessionMetric.session_id == session.id,
                SessionMetric.metric_code == "rom_stifle",
                SessionMetric.limb == limb,
            )
        ).one()
        assert stored.value == expected


def test_result_shape_matches_the_spec(client: TestClient, db: Session, dog, staff, auth_headers: dict) -> None:
    session = _session(db, dog, staff)
    _done_shot(
        db,
        session,
        dog,
        1,
        _result(_pass(1, "right", rom_stifle=_value(31.0)), _pass(2, "left", rom_stifle=_value(31.0))),
    )
    _aggregate(db)

    body = client.get(_result_url(session.id), headers=auth_headers).json()

    assert set(body) >= {"id", "dog_id", "staff", "status", "pass_counts", "shot_counts", "exclude_summary", "notices"}
    gait = body["gaits"][0]
    assert list(gait) == ["gait_type", "metrics", "limb_compare"]
    assert list(gait["metrics"][0]) == [
        "metric_code",
        "limb",
        "value",
        "unit",
        "measurable",
        "unmeasurable_reason",
        "n_passes",
    ]
    assert list(gait["limb_compare"][0]) == [
        "pair",
        "metric_code",
        "unit",
        "left",
        "right",
        "diff",
        "symmetry_index",
        "comparable",
        "reason",
    ]


def test_unmeasurable_is_null_with_a_reason_never_zero(
    client: TestClient, db: Session, dog, staff, auth_headers: dict
) -> None:
    session = _session(db, dog, staff)
    _done_shot(
        db,
        session,
        dog,
        1,
        _result(
            _pass(1, "right", paw_lift_front={"value": None, "reason": "LOW_CONFIDENCE"}),
            _pass(2, "left", paw_lift_front=_value(0.0, "pct_body")),
        ),
    )
    _aggregate(db)

    gait = client.get(_result_url(session.id), headers=auth_headers).json()["gaits"][0]

    right = _metric(gait, "paw_lift", "RF")
    assert right["value"] is None and right["measurable"] is False
    assert right["unit"] == "pct_body"
    assert right["unmeasurable_reason"] == {
        "code": "LOW_CONFIDENCE",
        "message": "관절점 인식이 불안정해 계산하지 못했습니다.",
    }
    left = _metric(gait, "paw_lift", "LF")  # 진짜 0은 그대로 값이다
    assert left["value"] == 0.0 and left["measurable"] is True and left["unmeasurable_reason"] is None


def test_metrics_follow_table_order_then_limb_order(
    client: TestClient, db: Session, dog, staff, auth_headers: dict
) -> None:
    session = _session(db, dog, staff)
    _done_shot(
        db,
        session,
        dog,
        1,
        _result(
            _pass(
                1,
                "right",
                walk_speed=_value(2.0, "body_per_sec"),
                paw_lift_hind=_value(4.0, "pct_body"),
                paw_lift_front=_value(3.0, "pct_body"),
                rom_stifle=_value(40.0),
            ),
            _pass(
                2,
                "left",
                paw_lift_hind=_value(5.0, "pct_body"),
                paw_lift_front=_value(6.0, "pct_body"),
                rom_stifle=_value(41.0),
            ),
        ),
    )
    _aggregate(db)

    gait = client.get(_result_url(session.id), headers=auth_headers).json()["gaits"][0]

    order = [(row["metric_code"], row["limb"]) for row in gait["metrics"]]
    assert order == [
        ("rom_stifle", "LH"),
        ("rom_stifle", "RH"),
        ("paw_lift", "LF"),
        ("paw_lift", "RF"),
        ("paw_lift", "LH"),
        ("paw_lift", "RH"),
        ("walk_speed", "NONE"),
    ]
    codes = [metric.code for metric in METRICS]
    assert codes.index("rom_stifle") < codes.index("paw_lift") < codes.index("walk_speed")


def test_walk_comes_before_trot(client: TestClient, db: Session, dog, staff, auth_headers: dict) -> None:
    session = _session(db, dog, staff)
    _done_shot(
        db,
        session,
        dog,
        1,
        _result(
            _pass(1, "right", gait="trot", rom_stifle=_value(40.0)),
            _pass(2, "right", gait="walk", rom_stifle=_value(30.0)),
        ),
    )
    _aggregate(db)

    body = client.get(_result_url(session.id), headers=auth_headers).json()

    assert [gait["gait_type"] for gait in body["gaits"]] == ["WALK", "TROT"]


def test_counts_and_exclude_summary(client: TestClient, db: Session, dog, staff, auth_headers: dict) -> None:
    session = _session(db, dog, staff)
    _done_shot(
        db,
        session,
        dog,
        1,
        _result(
            _pass(1, "right", rom_stifle=_value(40.0)),
            _pass(2, "left", rom_stifle=_value(40.0)),
            _pass(3, "right", gait=None, reason="STOPPED"),
            _pass(4, "right", gait=None, reason="RUNNING"),
            _pass(5, "left", gait=None, reason="RUNNING"),
            _pass(6, "left", gait=None, reason="TURNED"),
        ),
    )
    _done_shot(db, session, dog, 2, _result(validity="invalid"))
    _shot(db, session, 3, status="FAILED", fail_reason="ANALYSIS_FAILED")
    _aggregate(db)

    body = client.get(_result_url(session.id), headers=auth_headers).json()

    assert body["pass_counts"] == {"measured": 6, "used": 2, "excluded": 4}
    assert body["shot_counts"] == {"total": 3, "failed": 1, "invalid": 1}
    summary = [(row["code"], row["count"]) for row in body["exclude_summary"]]
    assert summary == [("RUNNING", 2), ("STOPPED", 1), ("TURNED", 1)]
    assert body["exclude_summary"][0]["message"]


def test_one_side_only_notice_and_no_recommended_met(
    client: TestClient, db: Session, dog, staff, auth_headers: dict
) -> None:
    session = _session(db, dog, staff)
    passes = [_pass(index, "right", rom_stifle=_value(40.0)) for index in range(1, 11)]
    _done_shot(db, session, dog, 1, _result(*passes))
    _aggregate(db)

    body = client.get(_result_url(session.id), headers=auth_headers).json()

    assert [notice["code"] for notice in body["notices"]] == ["ONE_SIDE_ONLY"]


def test_both_sides_many_passes_has_no_notice(client: TestClient, db: Session, dog, staff, auth_headers: dict) -> None:
    session = _session(db, dog, staff)
    passes = [_pass(index, "right" if index % 2 else "left") for index in range(1, 21)]
    _done_shot(db, session, dog, 1, _result(*passes))
    _aggregate(db)

    assert client.get(_result_url(session.id), headers=auth_headers).json()["notices"] == []


def test_session_without_valid_passes_is_done_with_no_metrics(
    client: TestClient, db: Session, dog, staff, auth_headers: dict
) -> None:
    session = _session(db, dog, staff)
    _shot(db, session, 1, status="FAILED", fail_reason="ANALYSIS_TIMEOUT")
    _done_shot(db, session, dog, 2, _result(_pass(1, "right", gait=None, reason="RUNNING")))
    _aggregate(db)

    response = client.get(_result_url(session.id), headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["gaits"] == [] and body["notices"] == []
    assert body["pass_counts"] == {"measured": 1, "used": 0, "excluded": 1}
    assert body["shot_counts"]["failed"] == 1
    assert len(db.scalars(select(Report).where(Report.session_id == session.id)).all()) == 2


# ---- 다리 비교 요약 (BE-21) ----


def _session_with_rows(db: Session, dog, staff, *rows: tuple) -> MeasureSession:
    """(수치, 다리, 값 또는 사유)로 session_metric 행을 바로 넣은 DONE 회차. 값은 행 그대로 나가야 한다."""
    session = _session(db, dog, staff, status="DONE")
    for code, limb, answer in rows:
        measured = isinstance(answer, int | float)
        db.add(
            SessionMetric(
                session_id=session.id,
                gait_type="TROT",
                limb=limb,
                metric_code=code,
                value=Decimal(str(answer)) if measured else None,
                unit="deg",
                measurable=measured,
                unmeasurable_reason=None if measured else answer,
                n_passes=6,
            )
        )
    db.flush()
    return session


def _gait_of(client: TestClient, session: MeasureSession, headers: dict) -> dict:
    return client.get(_result_url(session.id), headers=headers).json()["gaits"][0]


def test_compare_example_from_the_spec(client: TestClient, db: Session, dog, staff, auth_headers: dict) -> None:
    session = _session_with_rows(db, dog, staff, ("rom_stifle", "LH", 31.0), ("rom_stifle", "RH", 38.2))

    row = _compare(_gait_of(client, session, auth_headers), "rom_stifle", "HIND")

    assert row == {
        "pair": "HIND",
        "metric_code": "rom_stifle",
        "unit": "deg",
        "left": 31.0,
        "right": 38.2,
        "diff": -7.2,
        "symmetry_index": 20.81,
        "comparable": True,
        "reason": None,
    }


def test_diff_is_computed_in_decimal_not_float(client: TestClient, db: Session, dog, staff, auth_headers: dict) -> None:
    session = _session_with_rows(db, dog, staff, ("rom_stifle", "LH", 42.0), ("rom_stifle", "RH", 38.2))

    assert _compare(_gait_of(client, session, auth_headers), "rom_stifle", "HIND")["diff"] == 3.8


def test_symmetry_index_rounds_half_up(client: TestClient, db: Session, dog, staff, auth_headers: dict) -> None:
    # |100.0625 − 99.9375| ÷ 100 × 100 = 0.125. 은행원 반올림이면 0.12가 된다
    session = _session_with_rows(db, dog, staff, ("rom_stifle", "LH", 100.0625), ("rom_stifle", "RH", 99.9375))

    row = _compare(_gait_of(client, session, auth_headers), "rom_stifle", "HIND")

    assert row["symmetry_index"] == 0.13
    assert row["diff"] == 0.125


def test_one_side_unmeasurable_shows_the_other_value_and_that_reason(
    client: TestClient, db: Session, dog, staff, auth_headers: dict
) -> None:
    session = _session_with_rows(db, dog, staff, ("paw_lift", "LF", "LOW_CONFIDENCE"), ("paw_lift", "RF", 12.4))

    row = _compare(_gait_of(client, session, auth_headers), "paw_lift", "FORE")

    assert row["left"] is None and row["right"] == 12.4
    assert row["diff"] is None and row["symmetry_index"] is None and row["comparable"] is False
    assert row["reason"]["code"] == "LOW_CONFIDENCE"


def test_both_unmeasurable_uses_the_left_reason(
    client: TestClient, db: Session, dog, staff, auth_headers: dict
) -> None:
    session = _session_with_rows(
        db, dog, staff, ("paw_lift", "LF", "NOT_ENOUGH_CYCLES"), ("paw_lift", "RF", "LOW_CONFIDENCE")
    )

    row = _compare(_gait_of(client, session, auth_headers), "paw_lift", "FORE")

    assert row["reason"]["code"] == "NOT_ENOUGH_CYCLES"


def test_missing_row_is_no_data(client: TestClient, db: Session, dog, staff, auth_headers: dict) -> None:
    session = _session_with_rows(db, dog, staff, ("paw_lift", "RF", 12.4), ("rom_hip", "LH", "LOW_CONFIDENCE"))

    gait = _gait_of(client, session, auth_headers)

    row = _compare(gait, "paw_lift", "FORE")
    assert row["left"] is None and row["right"] == 12.4 and row["comparable"] is False
    assert row["reason"] == {"code": "NO_DATA", "message": "이 회차에는 이 수치가 없습니다."}
    assert _compare(gait, "rom_hip", "HIND")["reason"]["code"] == "NO_DATA"  # 없는 행이 먼저다
    assert [entry["pair"] for entry in gait["limb_compare"] if entry["metric_code"] == "paw_lift"] == ["FORE"]


def test_zero_sum_is_comparable_without_a_symmetry_index(
    client: TestClient, db: Session, dog, staff, auth_headers: dict
) -> None:
    session = _session_with_rows(db, dog, staff, ("rom_stifle", "LH", 0.0), ("rom_stifle", "RH", 0.0))

    row = _compare(_gait_of(client, session, auth_headers), "rom_stifle", "HIND")

    assert row["comparable"] is True and row["diff"] == 0.0
    assert row["symmetry_index"] is None and row["reason"] is None


def test_compare_sort_order(client: TestClient, db: Session, dog, staff, auth_headers: dict) -> None:
    session = _session_with_rows(
        db,
        dog,
        staff,
        # 비교할 수 없는 항목은 맨 뒤
        ("rom_shoulder", "LF", "LOW_CONFIDENCE"),
        ("rom_shoulder", "RF", 30.0),
        # 지수만 없는 비교 가능 항목
        ("rom_elbow", "LF", 0.0),
        ("rom_elbow", "RF", 0.0),
        # 큰 지수가 먼저
        ("rom_hip", "LH", 40.0),
        ("rom_hip", "RH", 44.0),
        ("rom_stifle", "LH", 31.0),
        ("rom_stifle", "RH", 38.2),
        # 같은 지수는 12.3 표 순서, 그다음 FORE → HIND
        ("paw_lift", "LH", 11.0),
        ("paw_lift", "RH", 9.0),
        ("paw_lift", "LF", 11.0),
        ("paw_lift", "RF", 9.0),
        ("rom_tarsus", "LH", 11.0),
        ("rom_tarsus", "RH", 9.0),
    )

    gait = _gait_of(client, session, auth_headers)

    assert [(row["metric_code"], row["pair"]) for row in gait["limb_compare"]] == [
        ("rom_stifle", "HIND"),
        ("rom_tarsus", "HIND"),
        ("paw_lift", "FORE"),
        ("paw_lift", "HIND"),
        ("rom_hip", "HIND"),
        ("rom_elbow", "FORE"),
        ("rom_shoulder", "FORE"),
    ]


def test_whole_body_metrics_are_not_compared(client: TestClient, db: Session, dog, staff, auth_headers: dict) -> None:
    session = _session_with_rows(db, dog, staff, ("walk_speed", "NONE", 2.4), ("gait_cycles", "NONE", 6))

    gait = _gait_of(client, session, auth_headers)

    assert gait["limb_compare"] == []
    assert len(gait["metrics"]) == 2
