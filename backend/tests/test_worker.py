"""워커 분석 제출·조회(명세 3절, 12.4, 13.3, 14.2, 17.3 BE-06·07). 결과 저장(DONE)은 2/2(결과 저장 작업)에서 본다."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClientError, AnalysisStatus, MockAnalysisClient, SubmitInfo
from app.core.config import Settings, get_settings
from app.core.dates import today_local
from app.core.errors import AppError, ErrorCode
from app.models import MeasureSession, Shot
from app.services.sessions import cancel_session
from app.storage.base import get_storage
from app.worker.main import Worker, clean_worker_tmp, run_once

# ---- 준비 ----


def _settings(**overrides: Any) -> Settings:
    return get_settings().model_copy(update=overrides)


def _session(db: Session, dog, staff) -> MeasureSession:
    session = MeasureSession(
        dog_id=dog.id, staff_id=staff.id, measured_on=today_local(), size_class="MEDIUM", status="MEASURING"
    )
    db.add(session)
    db.flush()
    return session


def _shot(db: Session, session: MeasureSession, seq_no: int, status: str = "UPLOADED", **values: Any) -> Shot:
    key = f"{uuid.uuid4()}/{uuid.uuid4()}/{session.id}/{uuid.uuid4()}/original.mp4"
    get_storage().write_bytes(key, b"\x00\x00\x00\x18ftypmp42 fake video")
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
        uploaded_at=datetime.now(UTC) + timedelta(seconds=seq_no),  # seq_no 순서 = 올린 순서
    )
    for name, value in values.items():
        setattr(shot, name, value)
    db.add(shot)
    db.flush()
    return shot


def _fresh(db: Session, shot: Shot) -> Shot | None:
    db.expire_all()
    return db.get(Shot, shot.id)


class FakeClient:
    """제출·상태를 마음대로 정하는 분석 클라이언트. submit_hook은 제출 중에 다른 처리가 끼어드는 상황용."""

    def __init__(self, statuses: dict[str, Any] | None = None, submit_error: Exception | None = None) -> None:
        self.statuses = statuses or {}
        self.submit_error = submit_error
        self.submit_hook = None
        self.submits: list[tuple[Path, SubmitInfo]] = []
        self.status_calls: list[str] = []

    def submit(self, video: Path, info: SubmitInfo) -> str:
        self.submits.append((video, info))
        if self.submit_hook:
            self.submit_hook(info)
        if self.submit_error:
            raise self.submit_error
        return f"job-{len(self.submits)}"

    def get_status(self, job_id: str) -> AnalysisStatus:
        self.status_calls.append(job_id)
        answer = self.statuses.get(job_id, AnalysisStatus("queued"))
        if isinstance(answer, Exception):
            raise answer
        return answer

    def get_result(self, job_id: str) -> dict[str, Any]:
        raise NotImplementedError("결과 저장은 2/2")

    def get_keypoints(self, job_id: str) -> dict[str, Any]:
        raise NotImplementedError("결과 저장은 2/2")


# ---- 가져오기·제출 (BE-06) ----


def test_submits_uploaded_shots_in_upload_order(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    shots = [_shot(db, session, seq_no) for seq_no in (3, 1, 2)]
    client = FakeClient()

    stats = run_once(db, client, _settings(), get_storage())

    assert stats.claimed == 3 and stats.submitted == 3 and stats.failed == 0
    assert [info.shot_id for _, info in client.submits] == [shots[1].id, shots[2].id, shots[0].id]
    assert all(info.size_class == "MEDIUM" for _, info in client.submits)
    assert all(video.is_file() for video, _ in client.submits)  # 저장소의 원본을 그대로 보낸다
    for shot in shots:
        row = _fresh(db, shot)
        assert row.status == "SUBMITTED" and row.job_id and row.job_id.startswith("job-")
        assert row.submitted_at is not None and row.attempt_count == 1 and row.fail_reason is None


def test_five_shots_are_all_submitted_without_waiting(db: Session, dog, staff) -> None:
    # 17.3 BE-06: 5건을 연속으로 올리면 앞 촬영이 끝나기를 기다리지 않고 모두 SUBMITTED
    session = _session(db, dog, staff)
    shots = [_shot(db, session, seq_no) for seq_no in range(1, 6)]
    run_once(db, FakeClient(), _settings(), get_storage())
    assert {_fresh(db, shot).status for shot in shots} == {"SUBMITTED"}


def test_in_flight_cap_limits_claims(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    shots = [_shot(db, session, seq_no) for seq_no in range(1, 4)]
    settings = _settings(WORKER_MAX_IN_FLIGHT=2)
    client = FakeClient()

    first = run_once(db, client, settings, get_storage())
    second = run_once(db, client, settings, get_storage())

    assert (first.claimed, first.submitted) == (2, 2) and (second.claimed, second.submitted) == (0, 0)
    assert [_fresh(db, s).status for s in shots] == ["SUBMITTED", "SUBMITTED", "UPLOADED"]

    # 하나가 실패해 자리가 나면 다음 바퀴에 가져온다
    client.statuses["job-1"] = AnalysisStatus("failed", error_code="DECODE_FAILED", error_message="x")
    third = run_once(db, client, settings, get_storage())
    assert third.failed == 1 and third.claimed == 1 and third.submitted == 1
    assert _fresh(db, shots[2]).status == "SUBMITTED"


def test_submit_failures_keep_the_shot_claimed_then_give_up(db: Session, dog, staff) -> None:
    # 17.3 BE-06: 분석 API가 꺼져 있으면 3번 시도 뒤 FAILED·ANALYSIS_SUBMIT_FAILED
    session = _session(db, dog, staff)
    shot = _shot(db, session, 1)
    client = FakeClient(submit_error=AnalysisClientError("connection refused"))
    settings = _settings(ANALYSIS_SUBMIT_MAX_ATTEMPTS=3)

    for expected_attempts in (1, 2):
        stats = run_once(db, client, settings, get_storage())
        row = _fresh(db, shot)
        assert stats.submit_attempt_failed == 1 and stats.failed == 0
        # 가져온 뒤라 SUBMITTED에 머문다(12.4). job_id는 아직 없다
        assert row.status == "SUBMITTED" and row.job_id is None and row.attempt_count == expected_attempts
        # 13.3: 그동안 측정 취소는 막힌다
        with pytest.raises(AppError) as caught:
            cancel_session(db, dog.institution_id, session.id)
        assert caught.value.code == ErrorCode.SHOT_IN_PROGRESS

    stats = run_once(db, client, settings, get_storage())
    row = _fresh(db, shot)
    assert stats.failed == 1
    assert row.status == "FAILED" and row.fail_reason == "ANALYSIS_SUBMIT_FAILED" and row.attempt_count == 3
    assert len(client.submits) == 3


def test_missing_original_file_is_a_failed_attempt(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    shot = _shot(db, session, 1)
    get_storage().delete(shot.original_key)
    stats = run_once(db, MockAnalysisClient(delay_sec=0), _settings(), get_storage())
    row = _fresh(db, shot)
    assert stats.submit_attempt_failed == 1
    assert row.status == "SUBMITTED" and row.job_id is None and row.attempt_count == 1


def test_claimed_shot_can_be_cancelled_before_claim_but_not_after(db: Session, dog, staff) -> None:
    # 12.4 잠금: 취소가 먼저면 워커는 지워진 행을 보고 건너뛰고, 워커가 먼저면 취소는 SHOT_IN_PROGRESS
    session = _session(db, dog, staff)
    _shot(db, session, 1)
    cancel_session(db, dog.institution_id, session.id)
    db.flush()
    stats = run_once(db, FakeClient(), _settings(), get_storage())
    assert stats.claimed == 0 and stats.submitted == 0


def test_shot_deleted_during_submit_is_not_written(db: Session, dog, staff) -> None:
    # 조건을 건 UPDATE: 보내는 사이 행이 사라졌으면(파기) 바뀐 행이 0개라 건너뛴다
    session = _session(db, dog, staff)
    shot = _shot(db, session, 1)
    client = FakeClient()

    def purge_meanwhile(info: SubmitInfo) -> None:
        db.execute(delete(Shot).where(Shot.id == info.shot_id))

    client.submit_hook = purge_meanwhile
    stats = run_once(db, client, _settings(), get_storage())
    assert stats.claimed == 1 and stats.submitted == 0 and _fresh(db, shot) is None


# ---- 상태 조회 (BE-07) ----


def test_poll_moves_shots_by_analysis_status(db: Session, dog, staff, caplog: pytest.LogCaptureFixture) -> None:
    session = _session(db, dog, staff)
    now = datetime.now(UTC)
    queued = _shot(db, session, 1, "SUBMITTED", job_id="q", submitted_at=now)
    running = _shot(db, session, 2, "SUBMITTED", job_id="r", submitted_at=now)
    done = _shot(db, session, 3, "SUBMITTED", job_id="d", submitted_at=now)
    failed = _shot(db, session, 4, "ANALYZING", job_id="f", submitted_at=now)
    pending = _shot(db, session, 5, "SUBMITTED", job_id=None, submitted_at=now)  # 가져왔지만 아직 안 보낸 것
    client = FakeClient(
        statuses={
            "q": AnalysisStatus("queued"),
            "r": AnalysisStatus("running"),
            "d": AnalysisStatus("done", model_name="fs-v4", model_version="0.1.0/v1/a4261a10"),
            "f": AnalysisStatus("failed", error_code="NO_DOG", error_message="개 미검출"),
        }
    )
    caplog.set_level(logging.ERROR, logger="app.worker")

    stats = run_once(db, client, _settings(), get_storage())

    assert stats.polled == 4 and stats.analyzing == 2 and stats.done == 1 and stats.failed == 1
    assert sorted(client.status_calls) == ["d", "f", "q", "r"]  # job_id 없는 것은 묻지 않는다
    assert _fresh(db, queued).status == "SUBMITTED"
    assert _fresh(db, running).status == "ANALYZING"
    assert _fresh(db, done).status == "ANALYZING"  # DONE과 결과 저장은 2/2
    row = _fresh(db, failed)
    assert row.status == "FAILED" and row.fail_reason == "ANALYSIS_FAILED"
    assert "NO_DOG" in caplog.text and "개 미검출" in caplog.text  # 원래 사유는 로그에만(14.2)
    assert stats.submitted == 1 and _fresh(db, pending).job_id == "job-1"  # 안 보낸 것은 이번 바퀴에 보낸다


def test_timeout_fails_old_submissions_without_asking_the_api(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    old = datetime.now(UTC) - timedelta(seconds=601)
    stale = _shot(db, session, 1, "ANALYZING", job_id="old", submitted_at=old)
    fresh = _shot(db, session, 2, "SUBMITTED", job_id="new", submitted_at=datetime.now(UTC))
    client = FakeClient()

    stats = run_once(db, client, _settings(ANALYSIS_TIMEOUT_SEC=600), get_storage())

    assert stats.timed_out == 1
    row = _fresh(db, stale)
    assert row.status == "FAILED" and row.fail_reason == "ANALYSIS_TIMEOUT"
    assert client.status_calls == ["new"] and _fresh(db, fresh).status == "SUBMITTED"


def test_status_call_error_leaves_the_shot_in_flight(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    now = datetime.now(UTC)
    broken = _shot(db, session, 1, "SUBMITTED", job_id="broken", submitted_at=now)
    fine = _shot(db, session, 2, "SUBMITTED", job_id="fine", submitted_at=now)
    client = FakeClient(statuses={"broken": AnalysisClientError("500"), "fine": AnalysisStatus("running")})

    stats = run_once(db, client, _settings(), get_storage())

    assert stats.polled == 1 and stats.analyzing == 1
    assert _fresh(db, broken).status == "SUBMITTED" and _fresh(db, fine).status == "ANALYZING"


# ---- Mock으로 끝까지 ----


def test_mock_client_end_to_end_reaches_analyzing(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    shot = _shot(db, session, 1)
    client = MockAnalysisClient(delay_sec=0)
    settings = _settings()

    first = run_once(db, client, settings, get_storage())
    row = _fresh(db, shot)
    assert first.submitted == 1 and row.status == "SUBMITTED" and row.job_id.startswith("mock-valid-")

    second = run_once(db, client, settings, get_storage())
    assert second.polled == 1 and second.done == 1
    assert _fresh(db, shot).status == "ANALYZING"


# ---- 실행 ----


def test_clean_worker_tmp_removes_leftovers(tmp_path: Path) -> None:
    leftover = tmp_path / "worker" / "job-1" / "frame.png"
    leftover.parent.mkdir(parents=True)
    leftover.write_bytes(b"x")
    cleaned = clean_worker_tmp(_settings(UPLOAD_TMP_DIR=str(tmp_path)))
    assert cleaned == tmp_path / "worker" and cleaned.is_dir() and not any(cleaned.iterdir())


def test_run_forever_survives_a_failing_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def flaky_run_once(*args: Any, **kwargs: Any):
        calls.append(len(calls))
        if len(calls) == 1:
            raise RuntimeError("db down")
        from app.worker.main import WorkerStats

        return WorkerStats()

    monkeypatch.setattr("app.worker.main.run_once", flaky_run_once)
    worker = Worker(_settings(WORKER_POLL_INTERVAL_SEC=0), client=FakeClient(), storage=get_storage())
    assert worker.run_forever(max_loops=2) == 2
    assert len(calls) == 2

    worker.stop()
    assert worker.run_forever() == 0
