"""보고서 워커(12.4 "보고서 한 건", 17.4 BE-15, 17.6, S15P31A404-195).

PENDING → GENERATING → DONE·FAILED, 다시 켜기, 다시 만들기, 실린 숫자 대조(196).
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from concurrent.futures.process import BrokenProcessPool
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.dates import today_local
from app.models import MeasureSession, Report, SessionMetric
from app.report import ReportCheckError
from app.report.checks import Finding
from app.report.generate import ReportResult
from app.report.numbers import ListedNumber, build_tables
from app.services import reports as report_service
from app.services.tolerance import ToleranceFileError, get_tolerance
from app.storage.base import get_storage
from app.storage.keys import report_key
from app.worker.main import WorkerStats, run_once
from app.worker.report import ReportGenerator
from tests.report_fixtures import MODEL_VERSION, FakeExecutor
from tests.test_render_worker import KeypointClient

MARK = b"%PDF-fake "


def _settings(**overrides: Any) -> Settings:
    return get_settings().model_copy(update=overrides)


def _done_session(db: Session, dog, staff, *, status: str = "DONE", reports: bool = True) -> MeasureSession:
    now = datetime.now(UTC)
    session = MeasureSession(
        dog_id=dog.id,
        staff_id=staff.id,
        measured_on=today_local(),
        size_class="MEDIUM",
        status=status,
        model_name="fs-v4",
        model_version=MODEL_VERSION,
        completed_at=now,
        aggregated_at=now,
    )
    db.add(session)
    db.flush()
    for limb, value in (("LH", "47.3"), ("RH", "43.1")):
        db.add(
            SessionMetric(
                session_id=session.id,
                gait_type="TROT",
                limb=limb,
                metric_code="rom_stifle",
                value=Decimal(value),
                unit="deg",
                measurable=True,
                n_passes=2,
            )
        )
    if reports:
        # updated_at 순서로 가져가므로 OWNER가 먼저 오게 고정한다(같은 flush면 now()가 같아 id 순이 된다)
        for offset, edition in enumerate(("OWNER", "VET")):
            db.add(
                Report(
                    session_id=session.id,
                    edition=edition,
                    template_version="0.1",
                    updated_at=now - timedelta(seconds=10 - offset),
                )
            )
    db.flush()
    db.commit()
    return session


def _reports(db: Session, session: MeasureSession) -> dict[str, Report]:
    db.expire_all()
    rows = db.query(Report).filter(Report.session_id == session.id).all() if False else list(session.reports)
    return {row.edition: row for row in rows}


def fake_generate(input_path: Path, output: Path) -> ReportResult:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    body = MARK + data["edition"].encode("utf-8") + b" " + data["dog"]["name"].encode("utf-8")
    output.write_bytes(body)
    numbers = tuple(build_tables(data["result"])[1])  # 실제 모듈처럼 입력의 수치를 그대로 싣는다(대조 통과)
    return ReportResult(
        pdf_bytes=len(body), generation_ms=12, template_version="0.2", numbers=numbers, edition=data["edition"]
    )


def _reporter(settings: Settings, executor: FakeExecutor, storage: Any = None) -> ReportGenerator:
    return ReportGenerator(
        settings, storage or get_storage(), executor_factory=lambda: executor, generate=fake_generate
    )


def _run(db: Session, reporter: ReportGenerator, settings: Settings) -> WorkerStats:
    return run_once(db, KeypointClient(), settings, get_storage(), None, reporter)


# ---- 맡기기와 거두기 ----


def test_pending_reports_are_generated_one_at_a_time_and_become_done(db: Session, dog, staff) -> None:
    session = _done_session(db, dog, staff)
    settings = _settings()
    executor = FakeExecutor()
    reporter = _reporter(settings, executor)

    first = _run(db, reporter, settings)
    assert first.report_started == 1 and first.reported == 0 and len(reporter.jobs) == 1
    assert {r.status for r in _reports(db, session).values()} == {"GENERATING", "PENDING"}

    second = _run(db, reporter, settings)  # 첫 보고서를 거두고 둘째를 맡긴다
    third = _run(db, reporter, settings)
    assert (second.reported, second.report_started, third.reported) == (1, 1, 1)
    rows = _reports(db, session)
    for edition, row in rows.items():
        assert row.status == "DONE" and row.fail_reason is None
        assert row.file_key == report_key(dog.institution_id, dog.id, session.id, row.id)
        assert get_storage().read_bytes(row.file_key).startswith(MARK + edition.encode("utf-8"))
        assert (row.generation_ms, row.template_version, row.model_version) == (12, "0.2", MODEL_VERSION)
    assert [args[0].name for _, args, _ in executor.calls] == ["input.json", "input.json"]
    assert reporter.jobs == {} and not any((Path(settings.UPLOAD_TMP_DIR) / "worker").glob("report-*"))


def test_input_written_for_the_child_has_the_report_shape(db: Session, dog, staff, tmp_path: Path) -> None:
    session = _done_session(db, dog, staff)
    settings = _settings(UPLOAD_TMP_DIR=str(tmp_path))
    captured: dict[str, Any] = {}

    def capture(input_path: Path, output: Path) -> ReportResult:
        captured.update(json.loads(input_path.read_text(encoding="utf-8")))
        return fake_generate(input_path, output)

    reporter = ReportGenerator(settings, get_storage(), executor_factory=FakeExecutor, generate=capture)
    _run(db, reporter, settings)
    assert captured["edition"] == "OWNER" and captured["dog"]["name"] == dog.name
    assert captured["session"]["id"] == str(session.id) and captured["session"]["model_version"] == MODEL_VERSION
    assert captured["result"]["gaits"][0]["metrics"][0]["metric_code"] == "rom_stifle"
    assert captured["previous"] is None
    assert captured["settings"] == {"tolerance": get_tolerance(settings.TOLERANCE_FILE)}
    assert captured["settings"]["tolerance"]["rom_stifle"] == 4.2  # config/tolerance.yaml의 임시값(통합본 9-3)


def test_previous_done_session_of_the_dog_is_included(db: Session, dog, staff, tmp_path: Path) -> None:
    older = _done_session(db, dog, staff, reports=False)
    older.measured_on = today_local().replace(day=1) if today_local().day > 1 else today_local()
    db.flush()
    db.commit()
    session = _done_session(db, dog, staff)
    captured: dict[str, Any] = {}

    def capture(input_path: Path, output: Path) -> ReportResult:
        captured.update(json.loads(input_path.read_text(encoding="utf-8")))
        return fake_generate(input_path, output)

    settings = _settings(UPLOAD_TMP_DIR=str(tmp_path))
    reporter = ReportGenerator(settings, get_storage(), executor_factory=FakeExecutor, generate=capture)
    _run(db, reporter, settings)
    assert captured["session"]["id"] == str(session.id)
    assert captured["previous"] is not None and captured["previous"]["id"] == str(older.id)


def test_check_failure_marks_report_check_failed_without_a_file(db: Session, dog, staff) -> None:
    session = _done_session(db, dog, staff)
    settings = _settings()
    error = ReportCheckError([Finding("FORBIDDEN", "확진", "title", "확진이 보행")])
    reporter = _reporter(settings, FakeExecutor(error))
    _run(db, reporter, settings)
    stats = _run(db, reporter, settings)
    row = _reports(db, session)["OWNER"]
    assert row.status == "FAILED" and row.fail_reason == "REPORT_CHECK_FAILED" and row.file_key is None
    assert stats.report_failed == 1


def test_other_errors_mark_report_failed(db: Session, dog, staff) -> None:
    session = _done_session(db, dog, staff)
    settings = _settings()
    reporter = _reporter(settings, FakeExecutor(RuntimeError("boom")))
    _run(db, reporter, settings)
    _run(db, reporter, settings)
    assert _reports(db, session)["OWNER"].fail_reason == "REPORT_FAILED"


def test_session_that_is_not_done_fails_the_report_without_submitting(db: Session, dog, staff) -> None:
    session = _done_session(db, dog, staff, status="AGGREGATING")
    settings = _settings()
    executor = FakeExecutor()
    reporter = _reporter(settings, executor)
    stats = _run(db, reporter, settings)
    row = _reports(db, session)["OWNER"]
    assert row.status == "FAILED" and row.fail_reason == "REPORT_FAILED"
    assert executor.calls == [] and stats.report_failed == 1 and stats.report_started == 0


# ---- 다시 켜기·깨진 풀·다시 만들기 ----


def test_generating_reports_are_reset_to_pending_on_start(db: Session, dog, staff) -> None:
    session = _done_session(db, dog, staff)
    rows = _reports(db, session)
    rows["OWNER"].status = "GENERATING"
    db.flush()
    db.commit()
    assert ReportGenerator.reset_generating(db) == 1
    assert {r.status for r in _reports(db, session).values()} == {"PENDING"}
    assert ReportGenerator.reset_generating(db) == 0


def test_broken_pool_fails_the_in_flight_report_and_is_recreated(db: Session, dog, staff) -> None:
    session = _done_session(db, dog, staff)
    settings = _settings()
    executors: list[FakeExecutor] = []

    def factory() -> FakeExecutor:
        executors.append(FakeExecutor("hang"))
        return executors[-1]

    reporter = ReportGenerator(settings, get_storage(), executor_factory=factory, generate=fake_generate)
    _run(db, reporter, settings)
    executors[0].futures[0].set_exception(BrokenProcessPool("child died"))
    stats = _run(db, reporter, settings)  # 거두기에서 풀이 깨진 것을 보고, 같은 바퀴의 맡기기가 새 풀에 둘째를 맡긴다
    assert stats.report_failed == 1 and stats.report_started == 1 and len(reporter.jobs) == 1
    rows = _reports(db, session)
    assert (rows["OWNER"].status, rows["OWNER"].fail_reason) == ("FAILED", "REPORT_FAILED")
    assert rows["VET"].status == "GENERATING"
    assert len(executors) == 2 and executors[0].closed and len(executors[1].calls) == 1


def test_regenerate_resets_the_row_and_the_worker_overwrites_the_same_key(db: Session, dog, staff) -> None:
    session = _done_session(db, dog, staff)
    settings = _settings()
    reporter = _reporter(settings, FakeExecutor())
    for _ in range(3):
        _run(db, reporter, settings)
    row = _reports(db, session)["OWNER"]
    key = row.file_key
    assert row.status == "DONE" and key

    out = report_service.regenerate(db, dog.institution_id, row.id)
    db.commit()
    assert out.status == "PENDING" and out.fail_reason is None and out.file_url is None
    db.expire_all()
    assert _reports(db, session)["OWNER"].file_key == key  # 키는 보고서 ID로 정해져 그대로다

    _run(db, reporter, settings)
    _run(db, reporter, settings)
    row = _reports(db, session)["OWNER"]
    assert row.status == "DONE" and row.file_key == key
    assert get_storage().read_bytes(key).startswith(MARK + b"OWNER")


def test_shutdown_closes_the_pool_and_removes_job_dirs(db: Session, dog, staff, tmp_path: Path) -> None:
    _done_session(db, dog, staff)
    settings = _settings(UPLOAD_TMP_DIR=str(tmp_path))
    executor = FakeExecutor("hang")
    reporter = _reporter(settings, executor)
    _run(db, reporter, settings)
    assert list((tmp_path / "worker").glob("report-*"))
    reporter.shutdown()
    assert executor.closed and reporter.jobs == {} and not list((tmp_path / "worker").glob("report-*"))


def test_unknown_report_id_in_candidates_is_skipped_quietly(db: Session, dog, staff) -> None:
    # 가져가기(claim) 뒤 행이 사라진 경우를 흉내 낸다: 존재하지 않는 보고서는 아무것도 하지 않는다
    settings = _settings()
    reporter = _reporter(settings, FakeExecutor())
    assert reporter._claim(db, uuid.uuid4()) is False


# ---- 수치 대조(8절 7번 첫 항목, S15P31A404-196) ----


def _with_numbers(
    numbers_of: Callable[[tuple[ListedNumber, ...]], tuple[ListedNumber, ...]],
) -> Callable[[Path, Path], ReportResult]:
    """fake_generate가 돌려주는 실린 숫자 목록을 바꿔 끼운 생성 함수."""

    def generate(input_path: Path, output: Path) -> ReportResult:
        result = fake_generate(input_path, output)
        return replace(result, numbers=numbers_of(result.numbers))

    return generate


def test_matching_numbers_are_verified_and_counted_in_the_log(db: Session, dog, staff, caplog) -> None:
    session = _done_session(db, dog, staff)
    settings = _settings()
    reporter = _reporter(settings, FakeExecutor())
    with caplog.at_level(logging.INFO, logger="app.worker"):
        _run(db, reporter, settings)
        _run(db, reporter, settings)
    assert _reports(db, session)["OWNER"].status == "DONE"
    # 수치 2개(LH·RH) + 뒷다리 쌍 4개(왼쪽·오른쪽·차이·대칭 지수) = 6, 싣지 않은 기준값 없음
    assert any("numbers=6 omitted=0" in message for message in caplog.messages)


def test_a_number_that_differs_from_the_session_metric_fails_the_check_without_a_file(db: Session, dog, staff) -> None:
    session = _done_session(db, dog, staff)
    settings = _settings()

    def wrong(numbers: tuple[ListedNumber, ...]) -> tuple[ListedNumber, ...]:
        return tuple(replace(n, value=n.value + 0.5) if (n.limb, n.kind) == ("LH", "metric") else n for n in numbers)

    reporter = ReportGenerator(settings, get_storage(), executor_factory=FakeExecutor, generate=_with_numbers(wrong))
    _run(db, reporter, settings)
    stats = _run(db, reporter, settings)
    row = _reports(db, session)["OWNER"]
    assert (row.status, row.fail_reason, row.file_key) == ("FAILED", "REPORT_CHECK_FAILED", None)
    assert stats.report_failed == 1 and stats.reported == 0
    assert not get_storage().path(report_key(dog.institution_id, dog.id, session.id, row.id)).exists()


def test_a_number_the_session_does_not_have_fails_the_check(db: Session, dog, staff) -> None:
    session = _done_session(db, dog, staff)
    settings = _settings()
    extra = ListedNumber("TROT", "rom_hip", "LH", "metric", 41.9)
    reporter = ReportGenerator(
        settings,
        get_storage(),
        executor_factory=FakeExecutor,
        generate=_with_numbers(lambda numbers: (*numbers, extra)),
    )
    _run(db, reporter, settings)
    _run(db, reporter, settings)
    assert _reports(db, session)["OWNER"].fail_reason == "REPORT_CHECK_FAILED"


def test_metrics_changed_while_the_report_was_being_made_fail_the_check(db: Session, dog, staff) -> None:
    session = _done_session(db, dog, staff)
    settings = _settings()
    executor = FakeExecutor("hang")
    reporter = _reporter(settings, executor)
    _run(db, reporter, settings)  # 맡겼지만 아직 끝나지 않았다
    fn, args, kwargs = executor.calls[0]
    made = fn(*args, **kwargs)  # 자식은 맡길 때의 입력으로 만든다
    row = db.query(SessionMetric).filter(SessionMetric.session_id == session.id, SessionMetric.limb == "LH").one()
    row.value = Decimal("40.0")  # 그사이 회차 수치가 바뀌었다
    db.flush()
    db.commit()
    executor.futures[0].set_result(made)
    stats = _run(db, reporter, settings)
    report = _reports(db, session)["OWNER"]
    assert (report.status, report.fail_reason) == ("FAILED", "REPORT_CHECK_FAILED") and stats.report_failed == 1


def test_a_report_that_lists_no_numbers_is_not_a_mismatch(db: Session, dog, staff) -> None:
    session = _done_session(db, dog, staff)
    settings = _settings()
    reporter = ReportGenerator(
        settings, get_storage(), executor_factory=FakeExecutor, generate=_with_numbers(lambda numbers: ())
    )
    _run(db, reporter, settings)
    _run(db, reporter, settings)
    assert _reports(db, session)["OWNER"].status == "DONE"


# ---- 오차 범위 파일(S15P31A404-197) ----


def test_malformed_tolerance_file_stops_the_worker_at_start(tmp_path: Path) -> None:
    bad = tmp_path / "tolerance.yaml"
    bad.write_text("rom_knee: 3.0\n", encoding="utf-8")
    with pytest.raises(ToleranceFileError):
        ReportGenerator(_settings(TOLERANCE_FILE=str(bad)), get_storage(), executor_factory=FakeExecutor)


def test_missing_tolerance_file_means_no_tolerance_in_the_input(db: Session, dog, staff, tmp_path: Path) -> None:
    _done_session(db, dog, staff)
    settings = _settings(TOLERANCE_FILE=str(tmp_path / "none.yaml"), UPLOAD_TMP_DIR=str(tmp_path))
    captured: dict[str, Any] = {}

    def capture(input_path: Path, output: Path) -> ReportResult:
        captured.update(json.loads(input_path.read_text(encoding="utf-8")))
        return fake_generate(input_path, output)

    reporter = ReportGenerator(settings, get_storage(), executor_factory=FakeExecutor, generate=capture)
    assert reporter.tolerance == {}
    _run(db, reporter, settings)
    assert captured["settings"] == {"tolerance": {}}
