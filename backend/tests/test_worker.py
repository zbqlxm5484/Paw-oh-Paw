"""워커 분석 제출·조회·결과 저장·기관별 상한(명세 3절, 6절, 12.4, 13.3, 14.2, 14.3, 17.3 BE-06·07·08·11, 17.6)."""

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClientError, AnalysisStatus, MockAnalysisClient, SubmitInfo, load_fixture
from app.core.config import Settings, get_settings
from app.core.dates import today_local
from app.core.errors import AppError, ErrorCode
from app.models import Dog, MeasureSession, Shot, WalkPass
from app.services.sessions import cancel_session
from app.storage.base import get_storage
from app.storage.keys import analysis_key
from app.worker.main import Worker, clean_worker_tmp, run_once

# ---- 준비 ----


def _settings(**overrides: Any) -> Settings:
    # 기관별 상한(기본 4)은 그 절의 테스트에서만 건다. 다른 테스트는 촬영이 모두 한 기관이라 상한에 걸리지 않게 둔다
    return get_settings().model_copy(update={"WORKER_MAX_IN_FLIGHT_PER_INSTITUTION": 100, **overrides})


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


def _other_dog(db: Session, other_staff) -> Dog:
    """other_staff 기관(T02)의 반려견. 기관별 상한 확인용."""
    row = Dog(
        institution_id=other_staff.institution_id,
        name="콩이",
        breed="푸들",
        weight_kg=Decimal("6.20"),
        size_class="SMALL",
    )
    db.add(row)
    db.flush()
    return row


class FakeClient:
    """제출·상태·결과를 마음대로 정하는 분석 클라이언트. *_hook은 그 호출 중에 다른 처리가 끼어드는 상황용."""

    def __init__(
        self,
        statuses: dict[str, Any] | None = None,
        submit_error: Exception | None = None,
        results: dict[str, Any] | None = None,
    ) -> None:
        self.statuses = statuses or {}
        self.submit_error = submit_error
        self.results = results or {}
        self.submit_hook = None
        self.result_hook = None
        self.submits: list[tuple[Path, SubmitInfo]] = []
        self.deleted: list[str] = []
        self.delete_error: Exception | None = None
        self.status_calls: list[str] = []
        self.result_calls: list[str] = []

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
        self.result_calls.append(job_id)
        if self.result_hook:
            self.result_hook(job_id)
        answer = self.results.get(job_id, AnalysisClientError("409 NOT_READY"))
        if isinstance(answer, Exception):
            raise answer
        return answer

    def get_keypoints(self, job_id: str) -> dict[str, Any]:
        raise NotImplementedError("관절점 파일은 결과 영상 작업에서 쓴다")

    def delete(self, job_id: str) -> None:
        if self.delete_error:
            raise self.delete_error
        self.deleted.append(job_id)


class HookedStorage:
    """저장소를 감싸 write_bytes 직후에 훅을 부른다. 12.4 "파일을 먼저 쓰고 키를 붙인다"의 그 사이에 끼어드는 상황용."""

    def __init__(self, after_write=None, write_error: Exception | None = None) -> None:
        self._inner = get_storage()
        self._after_write = after_write
        self._write_error = write_error
        self.written: list[str] = []

    def write_bytes(self, key: str, data: bytes) -> None:
        if self._write_error:
            raise self._write_error
        self._inner.write_bytes(key, data)
        self.written.append(key)
        if self._after_write:
            self._after_write(key)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


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


# ---- 기관별 상한 (12.4, 17.6) ----


def test_institution_cap_leaves_room_for_other_institutions(db: Session, dog, staff, other_staff) -> None:
    # 17.6: 한 기관이 30건을 한꺼번에 올려도 그 기관은 상한까지만, 다른 기관의 새 촬영은 바로 SUBMITTED.
    # 30건은 전체 자리 16보다 많아야 한다: 앞에서 16행만 보는 구현이면 T02의 촬영을 못 본다
    mine = _session(db, dog, staff)
    many = [_shot(db, mine, seq_no) for seq_no in range(1, 31)]  # T01이 30건을 먼저 올림
    theirs = _session(db, _other_dog(db, other_staff), other_staff)
    late = _shot(db, theirs, 1, uploaded_at=datetime.now(UTC) + timedelta(seconds=60))  # T02가 가장 늦게 1건
    settings = _settings(WORKER_MAX_IN_FLIGHT=16, WORKER_MAX_IN_FLIGHT_PER_INSTITUTION=4)
    client = FakeClient()

    stats = run_once(db, client, settings, get_storage())

    assert stats.claimed == 5 and stats.submitted == 5
    assert [_fresh(db, s).status for s in many] == ["SUBMITTED"] * 4 + ["UPLOADED"] * 26  # 올린 순서대로 4건
    assert _fresh(db, late).status == "SUBMITTED"
    # 분석이 안 끝났으면 다음 바퀴에도 T01은 더 못 가져간다(SQL이 그 기관의 남은 자리를 0으로 본다)
    assert run_once(db, client, settings, get_storage()).claimed == 0


def test_institution_cap_counts_shots_already_in_flight(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    busy = [_shot(db, session, seq_no, status="ANALYZING", job_id=f"old-{seq_no}") for seq_no in (1, 2, 3)]
    waiting = [_shot(db, session, seq_no) for seq_no in (4, 5)]
    client = FakeClient(statuses={f"old-{n}": AnalysisStatus("running") for n in (1, 2, 3)})
    settings = _settings(WORKER_MAX_IN_FLIGHT=16, WORKER_MAX_IN_FLIGHT_PER_INSTITUTION=4)

    first = run_once(db, client, settings, get_storage())

    assert first.claimed == 1 and first.submitted == 1
    assert [_fresh(db, s).status for s in waiting] == ["SUBMITTED", "UPLOADED"]
    assert {_fresh(db, s).status for s in busy} == {"ANALYZING"}
    # 하나가 끝나 그 기관에 자리가 나면 다음 바퀴에 가져온다
    client.statuses["old-1"] = AnalysisStatus("failed", error_code="DECODE_FAILED", error_message="x")
    second = run_once(db, client, settings, get_storage())
    assert second.failed == 1 and second.claimed == 1
    assert _fresh(db, waiting[1]).status == "SUBMITTED"


def test_global_cap_still_applies_across_institutions(db: Session, dog, staff, other_staff) -> None:
    # 기관별 자리가 남아도 전체 자리(WORKER_MAX_IN_FLIGHT)가 없으면 못 가져간다. 올린 순서대로
    mine = _session(db, dog, staff)
    theirs = _session(db, _other_dog(db, other_staff), other_staff)
    first = [_shot(db, mine, n) for n in (1, 2, 3)]
    second = [_shot(db, theirs, n, uploaded_at=datetime.now(UTC) + timedelta(seconds=10 + n)) for n in (1, 2, 3)]
    settings = _settings(WORKER_MAX_IN_FLIGHT=4, WORKER_MAX_IN_FLIGHT_PER_INSTITUTION=3)

    stats = run_once(db, FakeClient(), settings, get_storage())

    assert stats.claimed == 4
    assert [_fresh(db, s).status for s in first] == ["SUBMITTED"] * 3
    assert [_fresh(db, s).status for s in second] == ["SUBMITTED", "UPLOADED", "UPLOADED"]


def test_two_partially_full_institutions_get_their_remaining_room(db: Session, dog, staff, other_staff) -> None:
    # T01은 3건, T02는 2건이 이미 진행 중(상한 4) → 올린 순서대로 각각 1건·2건만 더
    mine = _session(db, dog, staff)
    theirs = _session(db, _other_dog(db, other_staff), other_staff)
    for seq_no in (1, 2, 3):
        _shot(db, mine, seq_no, status="ANALYZING", job_id=f"m{seq_no}")
    for seq_no in (1, 2):
        _shot(db, theirs, seq_no, status="ANALYZING", job_id=f"t{seq_no}")
    base = datetime.now(UTC) + timedelta(seconds=100)
    waiting_mine = [_shot(db, mine, n, uploaded_at=base + timedelta(seconds=n)) for n in (4, 5, 6)]
    waiting_theirs = [_shot(db, theirs, n, uploaded_at=base + timedelta(seconds=10 + n)) for n in (3, 4, 5)]
    client = FakeClient(statuses={k: AnalysisStatus("running") for k in ("m1", "m2", "m3", "t1", "t2")})
    settings = _settings(WORKER_MAX_IN_FLIGHT=16, WORKER_MAX_IN_FLIGHT_PER_INSTITUTION=4)

    stats = run_once(db, client, settings, get_storage())

    assert stats.claimed == 3
    assert [_fresh(db, s).status for s in waiting_mine] == ["SUBMITTED", "UPLOADED", "UPLOADED"]
    assert [_fresh(db, s).status for s in waiting_theirs] == ["SUBMITTED", "SUBMITTED", "UPLOADED"]


def test_global_cap_reached_mid_loop_then_upload_order_for_the_rest(db: Session, dog, staff, other_staff) -> None:
    # 전체 5·기관별 4: A 4건, B 2건, C 1건 순으로 올림 → A4·B1, C는 기다린다. 자리가 하나 나면 C보다 먼저 올린 B의 둘째
    a = _session(db, dog, staff)
    other = _other_dog(db, other_staff)
    b = _session(db, other, other_staff)
    c_dog = Dog(
        institution_id=other.institution_id, name="보리2", breed="푸들", weight_kg=Decimal("6.20"), size_class="SMALL"
    )
    db.add(c_dog)
    db.flush()
    base = datetime.now(UTC) + timedelta(seconds=100)
    a_shots = [_shot(db, a, n, uploaded_at=base + timedelta(seconds=n)) for n in (1, 2, 3, 4)]
    b_shots = [_shot(db, b, n, uploaded_at=base + timedelta(seconds=4 + n)) for n in (1, 2)]
    # C는 세 번째 기관이어야 하는데 테스트 기관이 둘뿐이라, B와 같은 기관의 다른 회차로 "그 뒤에 올린 촬영"만 본다
    c = _session(db, c_dog, other_staff)
    c_shot = _shot(db, c, 1, uploaded_at=base + timedelta(seconds=7))
    client = FakeClient()
    settings = _settings(WORKER_MAX_IN_FLIGHT=5, WORKER_MAX_IN_FLIGHT_PER_INSTITUTION=4)

    first = run_once(db, client, settings, get_storage())

    assert first.claimed == 5
    assert [_fresh(db, s).status for s in a_shots] == ["SUBMITTED"] * 4
    assert [_fresh(db, s).status for s in b_shots] == ["SUBMITTED", "UPLOADED"]
    assert _fresh(db, c_shot).status == "UPLOADED"

    client.statuses["job-1"] = AnalysisStatus("failed", error_code="DECODE_FAILED", error_message="x")  # A 하나 끝
    second = run_once(db, client, settings, get_storage())
    assert second.failed == 1 and second.claimed == 1
    assert _fresh(db, b_shots[1]).status == "SUBMITTED" and _fresh(db, c_shot).status == "UPLOADED"


def test_session_deleted_between_candidate_query_and_lock_is_skipped(
    db: Session, dog, staff, other_staff, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 후보 조회와 잠금 사이에 회차가 통째로 지워지면(파기) 그 촬영은 건너뛰고 나머지는 그대로 가져간다
    from app.worker import main as worker_main

    gone = _session(db, dog, staff)
    gone_shot = _shot(db, gone, 1)
    kept = _session(db, _other_dog(db, other_staff), other_staff)
    kept_shot = _shot(db, kept, 1, uploaded_at=datetime.now(UTC) + timedelta(seconds=30))
    real_lock = worker_main._lock_session

    def purge_then_lock(db_: Session, session_id: uuid.UUID) -> bool:
        if session_id == gone.id:
            db_.execute(delete(Shot).where(Shot.session_id == gone.id))
            db_.execute(delete(MeasureSession).where(MeasureSession.id == gone.id))
            db_.commit()
        return real_lock(db_, session_id)

    monkeypatch.setattr("app.worker.main._lock_session", purge_then_lock)
    stats = run_once(db, FakeClient(), _settings(), get_storage())

    assert stats.claimed == 1 and stats.submitted == 1
    assert _fresh(db, gone_shot) is None and _fresh(db, kept_shot).status == "SUBMITTED"


def test_submit_order_follows_upload_time_not_claim_time(db: Session, dog, staff) -> None:
    # 5ef46df: 보내는 순서는 uploaded_at이다. submitted_at(가져온 시각)으로 세우면 같은 바퀴에 가져온 것은 동률이라
    # UUID 순이 된다. 여기서는 두 값의 순서를 반대로 두어 어느 쪽으로 세우는지 드러낸다
    session = _session(db, dog, staff)
    now = datetime.now(UTC)
    first_uploaded = _shot(
        db, session, 1, "SUBMITTED", uploaded_at=now + timedelta(seconds=1), submitted_at=now + timedelta(seconds=10)
    )
    second_uploaded = _shot(
        db, session, 2, "SUBMITTED", uploaded_at=now + timedelta(seconds=2), submitted_at=now + timedelta(seconds=5)
    )
    client = FakeClient()

    stats = run_once(db, client, _settings(), get_storage())

    assert stats.submitted == 2
    assert [info.shot_id for _, info in client.submits] == [first_uploaded.id, second_uploaded.id]


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
            cancel_session(db, dog.institution_id, session.id, client)
        assert caught.value.code == ErrorCode.SHOT_IN_PROGRESS

    stats = run_once(db, client, settings, get_storage())
    row = _fresh(db, shot)
    assert stats.failed == 1
    assert row.status == "FAILED" and row.fail_reason == "ANALYSIS_SUBMIT_FAILED" and row.attempt_count == 3
    assert len(client.submits) == 3


def test_rejected_submit_fails_without_retry(db: Session, dog, staff) -> None:
    # 87 MR 리뷰 제안 A: 분석 API가 요청 자체를 거부하면(415 등 4xx) 다시 보내지 않고 바로 FAILED
    session = _session(db, dog, staff)
    shot = _shot(db, session, 1)
    client = FakeClient(submit_error=AnalysisClientError("415 UNSUPPORTED_MEDIA", retryable=False))

    stats = run_once(db, client, _settings(ANALYSIS_SUBMIT_MAX_ATTEMPTS=3), get_storage())

    row = _fresh(db, shot)
    assert stats.failed == 1 and stats.submit_attempt_failed == 0
    assert row.status == "FAILED" and row.fail_reason == "ANALYSIS_SUBMIT_FAILED" and row.attempt_count == 1
    assert len(client.submits) == 1


def test_auth_failure_pauses_submissions_without_counting_attempts(
    db: Session, dog, staff, caplog: pytest.LogCaptureFixture
) -> None:
    # 12.4: 401·403은 키 설정 문제다. 촬영을 실패시키지도, attempt_count를 올리지도 않고 그 바퀴의 제출을 멈춘다
    session = _session(db, dog, staff)
    shots = [_shot(db, session, seq_no) for seq_no in (1, 2)]
    client = FakeClient(submit_error=AnalysisClientError("401 AUTH_REQUIRED", status_code=401))
    caplog.set_level(logging.ERROR, logger="app.worker")

    stats = run_once(db, client, _settings(ANALYSIS_SUBMIT_MAX_ATTEMPTS=3), get_storage())

    assert stats.claimed == 2 and stats.submitted == 0 and stats.failed == 0 and stats.submit_attempt_failed == 1
    assert len(client.submits) == 1  # 첫 촬영에서 멈춘다. 나머지도 같은 키라 같다
    for shot in shots:
        row = _fresh(db, shot)
        assert row.status == "SUBMITTED" and row.job_id is None and row.attempt_count == 0
    assert "ANALYSIS_API_KEY" in caplog.text

    client.submit_error = None  # 키를 고치면 다음 바퀴에 그대로 보낸다
    stats = run_once(db, client, _settings(), get_storage())
    assert stats.submitted == 2 and all(_fresh(db, shot).job_id for shot in shots)


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
    cancel_session(db, dog.institution_id, session.id, FakeClient())
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
    # job_id를 적을 행이 없어 나중에 찾을 수 없으므로 방금 만든 분석 API 사본을 바로 지운다(199 리뷰)
    assert client.deleted == ["job-1"]


def test_an_unrecorded_job_that_cannot_be_deleted_is_only_logged(
    db: Session, dog, staff, caplog: pytest.LogCaptureFixture
) -> None:
    session = _session(db, dog, staff)
    _shot(db, session, 1)
    client = FakeClient()
    client.delete_error = AnalysisClientError("JOB_IN_PROGRESS", status_code=409)
    client.submit_hook = lambda info: db.execute(delete(Shot).where(Shot.id == info.shot_id))
    with caplog.at_level(logging.WARNING, logger="app.worker"):
        stats = run_once(db, client, _settings(), get_storage())
    assert stats.claimed == 1 and stats.submitted == 0  # 바퀴는 이어 간다
    assert "analysis copy is left behind" in caplog.text


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
        },
        results={"d": load_fixture("result_valid")},
    )
    caplog.set_level(logging.ERROR, logger="app.worker")

    stats = run_once(db, client, _settings(), get_storage())

    assert stats.polled == 4 and stats.analyzing == 2 and stats.done == 1 and stats.failed == 1
    assert sorted(client.status_calls) == ["d", "f", "q", "r"]  # job_id 없는 것은 묻지 않는다
    assert _fresh(db, queued).status == "SUBMITTED"
    assert _fresh(db, running).status == "ANALYZING"
    assert _fresh(db, done).status == "DONE"
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


def test_missing_job_fails_the_shot_immediately(db: Session, dog, staff, caplog: pytest.LogCaptureFixture) -> None:
    # 12.4: 상태 조회에서 작업이 없다고 답하면(404·410) 시간 초과를 기다리지 않고 바로 ANALYSIS_FAILED
    session = _session(db, dog, staff)
    gone = _shot(db, session, 1, "ANALYZING", job_id="gone", submitted_at=datetime.now(UTC))
    client = FakeClient(statuses={"gone": AnalysisClientError("404 NOT_FOUND", retryable=False, status_code=404)})
    caplog.set_level(logging.ERROR, logger="app.worker")

    stats = run_once(db, client, _settings(ANALYSIS_TIMEOUT_SEC=600), get_storage())

    row = _fresh(db, gone)
    assert stats.failed == 1 and stats.timed_out == 0
    assert row.status == "FAILED" and row.fail_reason == "ANALYSIS_FAILED"
    assert "NOT_FOUND" in caplog.text


def test_auth_failure_pauses_status_checks(db: Session, dog, staff) -> None:
    # 12.4: 키가 틀리면 다른 촬영을 물어도 같다. 촬영은 그대로 두고 그 바퀴의 조회를 멈춘다
    session = _session(db, dog, staff)
    now = datetime.now(UTC)
    shots = [_shot(db, session, seq_no, "ANALYZING", job_id=f"j{seq_no}", submitted_at=now) for seq_no in (1, 2)]
    denied = AnalysisClientError("403 FORBIDDEN", status_code=403)
    client = FakeClient(statuses={"j1": denied, "j2": denied})

    stats = run_once(db, client, _settings(), get_storage())

    assert stats.failed == 0 and stats.polled == 0
    assert len(client.status_calls) == 1  # 첫 촬영에서 멈춘다(같은 시각에 보낸 둘의 순서는 UUID 순이라 정하지 않는다)
    assert [_fresh(db, shot).status for shot in shots] == ["ANALYZING", "ANALYZING"]


# ---- Mock으로 끝까지 ----


def test_mock_client_end_to_end_reaches_done(db: Session, dog, staff) -> None:
    # 17.3 BE-06: Mock 모드에서 MOCK_ANALYSIS_DELAY_SEC 뒤 DONE
    session = _session(db, dog, staff)
    shot = _shot(db, session, 1)
    client = MockAnalysisClient(delay_sec=0)
    settings = _settings()

    first = run_once(db, client, settings, get_storage())
    row = _fresh(db, shot)
    assert first.submitted == 1 and row.status == "SUBMITTED" and row.job_id.startswith("mock-valid-")

    second = run_once(db, client, settings, get_storage())
    row = _fresh(db, shot)
    assert second.polled == 1 and second.done == 1
    assert row.status == "DONE" and row.validity == "VALID" and len(row.passes) == 4
    assert row.analysis_key and json.loads(get_storage().read_bytes(row.analysis_key))["status"] == "done"


# ---- 결과 저장 (BE-07·08·11) ----


def _done_shot(db: Session, session: MeasureSession, seq_no: int = 1, status: str = "ANALYZING") -> Shot:
    return _shot(db, session, seq_no, status, job_id="d", submitted_at=datetime.now(UTC))


def _client_done(result: Any) -> FakeClient:
    return FakeClient(statuses={"d": AnalysisStatus("done")}, results={"d": result})


def _pass_tuples(shot: Shot) -> list[tuple]:
    return [
        (p.pass_no, p.camera_side, p.gait_type, p.is_valid, p.exclude_reason, p.start_frame, p.end_frame)
        for p in shot.passes
    ]


def test_valid_result_is_saved_as_done_with_passes(db: Session, dog, staff) -> None:
    # 17.3 BE-07·11: DONE이 되고 통과별 start_frame·end_frame·exclude_reason이 결과 JSON과 같다
    session = _session(db, dog, staff)
    shot = _done_shot(db, session)
    result = load_fixture("result_valid")

    stats = run_once(db, _client_done(result), _settings(), get_storage())

    row = _fresh(db, shot)
    assert stats.done == 1 and stats.failed == 0
    assert row.status == "DONE" and row.validity == "VALID" and row.validity_reason is None
    assert row.model_name == "fs-v4" and row.model_version == "0.4.0/v1/a4261a10"
    assert row.analyzed_at is not None and row.fail_reason is None
    assert row.analysis_key == analysis_key(dog.institution_id, dog.id, session.id, shot.id)
    assert json.loads(get_storage().read_bytes(row.analysis_key)) == result  # 받은 그대로 보관(6절)
    assert _pass_tuples(row) == [
        (p["index"], p["camera_side"].upper(), "TROT", True, None, p["start_frame"], p["end_frame"])
        for p in result["passes"]
    ]


def test_partial_result_keeps_null_reason_and_maps_excluded_pass(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    shot = _done_shot(db, session)

    run_once(db, _client_done(load_fixture("result_partial")), _settings(), get_storage())

    row = _fresh(db, shot)
    assert row.status == "DONE" and row.validity == "PARTIAL"
    assert row.validity_reason is None  # partial의 null = 유효 통과는 충분한데 일부 제외(14.3, 조유진 MR !30)
    assert _pass_tuples(row)[2] == (3, "RIGHT", "OTHER", False, "NOT_SIDE_VIEW", 470, 560)  # gait null → OTHER
    assert [p.is_valid for p in row.passes] == [True, True, False]


def test_invalid_result_has_no_passes(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    shot = _done_shot(db, session)
    run_once(db, _client_done(load_fixture("result_invalid")), _settings(), get_storage())
    row = _fresh(db, shot)
    assert row.status == "DONE" and row.validity == "INVALID" and row.validity_reason == "NO_DOG"
    assert row.passes == []


def test_invalid_without_reason_defaults_to_no_valid_pass(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    shot = _done_shot(db, session)
    result = load_fixture("result_invalid")
    result["validity_reason"] = None
    run_once(db, _client_done(result), _settings(), get_storage())
    assert _fresh(db, shot).validity_reason == "NO_VALID_PASS"


def test_unknown_reason_codes_are_stored_as_unknown_and_logged(
    db: Session, dog, staff, caplog: pytest.LogCaptureFixture
) -> None:
    # 17.3 BE-08: 모르는 코드는 UNKNOWN_REASON으로 저장되고 원래 코드가 로그에 남는다
    session = _session(db, dog, staff)
    shot = _done_shot(db, session)
    result = load_fixture("result_partial")
    result["validity_reason"] = "SOMETHING_NEW"
    result["passes"][2]["reason_code"] = "WEIRD_CODE"
    caplog.set_level(logging.WARNING)

    run_once(db, _client_done(result), _settings(), get_storage())

    row = _fresh(db, shot)
    assert row.validity_reason == "UNKNOWN_REASON" and row.passes[2].exclude_reason == "UNKNOWN_REASON"
    assert "SOMETHING_NEW" in caplog.text and "WEIRD_CODE" in caplog.text


def test_done_straight_from_submitted(db: Session, dog, staff) -> None:
    # 12.4: SUBMITTED → DONE도 가능
    session = _session(db, dog, staff)
    shot = _done_shot(db, session, status="SUBMITTED")
    stats = run_once(db, _client_done(load_fixture("result_valid")), _settings(), get_storage())
    assert stats.done == 1 and _fresh(db, shot).status == "DONE"


def test_result_fetch_error_keeps_the_shot_analyzing_and_retries(db: Session, dog, staff) -> None:
    # 409 NOT_READY(HttpAnalysisClient는 retryable=False로 분류)도 결과 조회에서는 "아직"이라 다음 바퀴에 다시 받는다
    session = _session(db, dog, staff)
    shot = _done_shot(db, session, status="SUBMITTED")
    client = _client_done(AnalysisClientError("409 NOT_READY", retryable=False, status_code=409))

    first = run_once(db, client, _settings(), get_storage())
    row = _fresh(db, shot)
    assert first.done == 0 and first.failed == 0
    assert row.status == "ANALYZING" and row.analysis_key is None and row.passes == []

    client.results["d"] = load_fixture("result_valid")
    second = run_once(db, client, _settings(), get_storage())
    assert second.done == 1 and _fresh(db, shot).status == "DONE"


def test_missing_result_fails_the_shot_immediately(db: Session, dog, staff) -> None:
    # 12.4: done인데 결과가 없다고 답하면(404·410) 바로 ANALYSIS_FAILED. 엉뚱한 ANALYSIS_TIMEOUT으로 끝내지 않는다
    session = _session(db, dog, staff)
    shot = _done_shot(db, session)
    client = _client_done(AnalysisClientError("404 NOT_FOUND", retryable=False, status_code=404))

    stats = run_once(db, client, _settings(), get_storage())

    row = _fresh(db, shot)
    assert stats.failed == 1 and stats.done == 0
    assert row.status == "FAILED" and row.fail_reason == "ANALYSIS_FAILED" and row.analysis_key is None


def test_integer_valued_floats_are_accepted(db: Session, dog, staff) -> None:
    # 분석 쪽이 numpy 값을 JSON으로 내보내면 40.0처럼 온다. 정수값이면 받는다
    session = _session(db, dog, staff)
    shot = _done_shot(db, session)
    result = load_fixture("result_valid")
    result["passes"][0].update(index=1.0, start_frame=40.0, end_frame=205.0)

    stats = run_once(db, _client_done(result), _settings(), get_storage())

    row = _fresh(db, shot)
    assert stats.done == 1 and row.status == "DONE"
    assert (row.passes[0].pass_no, row.passes[0].start_frame, row.passes[0].end_frame) == (1, 40, 205)


@pytest.mark.parametrize(
    ("index_edit", "message_part"),
    [
        ({0: 40_000}, "unusable"),  # SMALLINT 초과 → 받은 순서
        ({1: 1}, "renumbered"),  # 1이 둘 → 전부 받은 순서로
    ],
)
def test_unusable_or_duplicate_index_is_renumbered_and_logged(
    db: Session, dog, staff, caplog: pytest.LogCaptureFixture, index_edit: dict[int, int], message_part: str
) -> None:
    session = _session(db, dog, staff)
    shot = _done_shot(db, session)
    result = load_fixture("result_valid")
    for position, value in index_edit.items():
        result["passes"][position]["index"] = value
    caplog.set_level(logging.WARNING)

    stats = run_once(db, _client_done(result), _settings(), get_storage())

    assert stats.done == 1 and [p.pass_no for p in _fresh(db, shot).passes] == [1, 2, 3, 4]
    assert message_part in caplog.text


@pytest.mark.parametrize(
    "broken",
    [
        {"validity": "weird", "passes": []},
        {"validity": "valid", "passes": [{"index": 1, "start_frame": 1, "end_frame": 2, "valid": True}]},
        {"validity": "valid", "passes": [{"index": 1, "camera_side": "left", "start_frame": "a", "end_frame": 2}]},
        {"validity": "valid"},
        # valid가 없거나 문자열이면 전부 제외·전부 유효로 조용히 저장되므로 형식 오류여야 한다
        {"validity": "valid", "passes": [{"index": 1, "camera_side": "left", "start_frame": 1, "end_frame": 2}]},
        {
            "validity": "valid",
            "passes": [{"index": 1, "camera_side": "left", "start_frame": 1, "end_frame": 2, "valid": "false"}],
        },
        # INTEGER 범위를 넘는 프레임은 DB까지 가면 저장 중 오류다. 여기서 막는다
        {
            "validity": "valid",
            "passes": [{"index": 1, "camera_side": "left", "start_frame": 1, "end_frame": 2**31, "valid": True}],
        },
    ],
)
def test_unreadable_result_fails_the_shot(
    db: Session, dog, staff, caplog: pytest.LogCaptureFixture, broken: dict[str, Any]
) -> None:
    # 6절 계약과 다른 결과 JSON: FAILED(ANALYSIS_FAILED), 어느 필드인지 로그에, 파일은 남기지 않는다
    session = _session(db, dog, staff)
    shot = _done_shot(db, session)
    caplog.set_level(logging.ERROR, logger="app.worker")

    stats = run_once(db, _client_done(broken), _settings(), get_storage())

    row = _fresh(db, shot)
    assert stats.failed == 1 and stats.done == 0
    assert row.status == "FAILED" and row.fail_reason == "ANALYSIS_FAILED"
    assert row.analysis_key is None and row.passes == []
    assert "unreadable" in caplog.text


def test_shot_deleted_during_result_save_discards_the_file(db: Session, dog, staff) -> None:
    # 12.4: 파일을 먼저 쓰고 키를 붙이는 UPDATE가 0행이면(파기로 행이 사라짐) 방금 쓴 analysis.json을 지운다.
    # 훅은 파일을 쓴 직후에 끼어든다. 결과를 받는 중에 끼어들면 파일이 아예 안 쓰여 이 순서를 못 본다
    session = _session(db, dog, staff)
    shot = _done_shot(db, session)
    key = analysis_key(dog.institution_id, dog.id, session.id, shot.id)

    def purge_after_write(written_key: str) -> None:
        db.execute(delete(Shot).where(Shot.id == shot.id))
        db.commit()

    storage = HookedStorage(after_write=purge_after_write)
    stats = run_once(db, _client_done(load_fixture("result_valid")), _settings(), storage)

    assert stats.done == 0 and _fresh(db, shot) is None
    assert storage.written == [key] and get_storage().delete(key) == 0  # 썼다가 지웠다


def test_shot_changed_during_result_save_discards_the_file(db: Session, dog, staff) -> None:
    # 12.4: 행은 있지만 그사이 상태가 바뀌었어도(여기서는 FAILED) 0행이라 파일을 지우고 행은 건드리지 않는다
    session = _session(db, dog, staff)
    shot = _done_shot(db, session)
    key = analysis_key(dog.institution_id, dog.id, session.id, shot.id)

    def fail_after_write(written_key: str) -> None:
        db.execute(update(Shot).where(Shot.id == shot.id).values(status="FAILED", fail_reason="ANALYSIS_TIMEOUT"))
        db.commit()

    storage = HookedStorage(after_write=fail_after_write)
    stats = run_once(db, _client_done(load_fixture("result_valid")), _settings(), storage)

    row = _fresh(db, shot)
    assert stats.done == 0
    assert row.status == "FAILED" and row.fail_reason == "ANALYSIS_TIMEOUT" and row.analysis_key is None
    assert row.passes == [] and storage.written == [key] and get_storage().delete(key) == 0


def test_save_error_skips_only_that_shot(
    db: Session, dog, staff, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 저장 중 예외(DB 오류)는 그 촬영만 건너뛴다. 같은 바퀴의 다른 촬영 저장과 가져오기·제출은 이어진다
    from app.services.analysis_results import apply_result as real_apply_result

    session = _session(db, dog, staff)
    now = datetime.now(UTC)
    bad = _shot(db, session, 1, "ANALYZING", job_id="bad", submitted_at=now)
    good = _shot(db, session, 2, "ANALYZING", job_id="good", submitted_at=now)
    waiting = _shot(db, session, 3)  # UPLOADED. 같은 바퀴의 가져오기·제출이 맡는다
    done = AnalysisStatus("done")
    client = FakeClient(
        statuses={"bad": done, "good": done},
        results={"bad": load_fixture("result_valid"), "good": load_fixture("result_valid")},
    )
    failing: set[uuid.UUID] = {bad.id}

    def flaky_apply_result(db_: Session, shot_id: uuid.UUID, parsed, **kwargs):
        if shot_id in failing:
            raise RuntimeError("db hiccup")
        return real_apply_result(db_, shot_id, parsed, **kwargs)

    monkeypatch.setattr("app.worker.main.apply_result", flaky_apply_result)
    storage = HookedStorage()
    caplog.set_level(logging.ERROR, logger="app.worker")
    bad_key = analysis_key(dog.institution_id, dog.id, session.id, bad.id)

    stats = run_once(db, client, _settings(), storage)

    assert stats.done == 1 and stats.failed == 0 and stats.claimed == 1 and stats.submitted == 1
    assert _fresh(db, bad).status == "ANALYZING" and _fresh(db, bad).analysis_key is None
    assert _fresh(db, good).status == "DONE" and _fresh(db, waiting).status == "SUBMITTED"
    assert bad_key in storage.written and get_storage().delete(bad_key) == 0  # 썼다가 지웠다
    assert "save failed" in caplog.text and "RuntimeError" in caplog.text

    failing.clear()  # 다음 바퀴에 다시 저장한다
    assert run_once(db, client, _settings(), storage).done == 1 and _fresh(db, bad).status == "DONE"


def test_storage_write_failure_keeps_the_shot_and_hides_the_path(
    db: Session, dog, staff, caplog: pytest.LogCaptureFixture
) -> None:
    # 파일을 못 쓰면 DB는 건드리지 않고 다음 바퀴에 다시 한다. 로그에 파일 경로를 남기지 않는다(11.8)
    session = _session(db, dog, staff)
    shot = _done_shot(db, session)
    storage = HookedStorage(write_error=OSError(28, "No space left on device", "D:/secret-root/analysis.json"))
    caplog.set_level(logging.ERROR, logger="app.worker")

    stats = run_once(db, _client_done(load_fixture("result_valid")), _settings(), storage)

    row = _fresh(db, shot)
    assert stats.done == 0 and stats.failed == 0
    assert row.status == "ANALYZING" and row.analysis_key is None and row.passes == []
    assert "errno=28" in caplog.text and "secret-root" not in caplog.text


def test_saving_replaces_leftover_passes(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    shot = _done_shot(db, session)
    db.add(
        WalkPass(
            shot_id=shot.id, pass_no=9, camera_side="LEFT", gait_type="WALK", is_valid=True, start_frame=0, end_frame=1
        )
    )
    db.flush()
    run_once(db, _client_done(load_fixture("result_valid")), _settings(), get_storage())
    assert [p.pass_no for p in _fresh(db, shot).passes] == [1, 2, 3, 4]


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


def _fake_sweeps(monkeypatch: pytest.MonkeyPatch, results: dict[str, Any]) -> list[tuple[str, float | None]]:
    """자동 파기 두 가지를 가짜로 바꾸고, 불린 순서와 받은 deadline을 모은다."""
    from app.services.purge import SweepResult
    from app.worker.main import WorkerStats

    calls: list[tuple[str, float | None]] = []

    def fake(name: str):
        def run(*args: Any, deadline: float | None = None, **kwargs: Any) -> SweepResult:
            calls.append((name, deadline))
            return results.get(name, SweepResult(0, 0))

        return run

    monkeypatch.setattr("app.worker.main.run_once", lambda *args, **kwargs: WorkerStats())
    monkeypatch.setattr("app.worker.main.trash_service.purge_expired", fake("trash"))
    monkeypatch.setattr("app.worker.main.retention_service.purge_expired_contracts", fake("contract"))
    monkeypatch.setattr("app.worker.main.retention_service.due_institution_ids", lambda db: [])
    return calls


def test_run_forever_sweeps_the_trash_once_per_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    """휴지통 자동 비우기(12.4)는 켜자마자 한 번, 그 뒤로는 한 시간마다다. 주 반복마다 돌지 않는다.

    계약 종료 뒤 자동 파기는 켠 뒤 한 간격이 지나야 처음 돈다. 배포하자마자 기관의 자료가 지워지지 않게(199 리뷰).
    """
    calls = _fake_sweeps(monkeypatch, {})
    worker = Worker(_settings(WORKER_POLL_INTERVAL_SEC=0), client=FakeClient(), storage=get_storage())
    assert worker.run_forever(max_loops=3) == 3
    assert [name for name, _ in calls] == ["trash"]
    assert calls[0][1] is not None  # 시간 상한을 넘긴다

    worker._contract_sweep_from = 0.0  # 한 간격이 지났다
    worker._next_trash_sweep = 0.0
    calls.clear()
    assert worker.run_forever(max_loops=3) == 3
    assert [name for name, _ in calls] == ["trash", "contract"]
    assert calls[0][1] == calls[1][1]  # 둘이 같은 상한을 나눠 쓴다


def test_a_sweep_that_ran_out_of_time_resumes_soon_and_skips_the_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    """시간 상한(WORKER_SWEEP_MAX_SEC)에 닿아 남기면 그 차례의 나머지는 건너뛰고, 한 시간이 아니라 곧 다시 본다."""
    import time

    from app.services.purge import SweepResult
    from app.worker.main import SWEEP_RESUME_SEC, TRASH_SWEEP_INTERVAL_SEC

    calls = _fake_sweeps(monkeypatch, {"trash": SweepResult(1, 0, out_of_time=True)})
    worker = Worker(_settings(WORKER_POLL_INTERVAL_SEC=0), client=FakeClient(), storage=get_storage())
    worker._contract_sweep_from = 0.0
    before = time.monotonic()
    assert worker.run_forever(max_loops=1) == 1
    assert [name for name, _ in calls] == ["trash"]
    assert worker._next_trash_sweep - before < TRASH_SWEEP_INTERVAL_SEC
    assert worker._next_trash_sweep - before >= SWEEP_RESUME_SEC


def test_the_worker_warns_at_start_about_institutions_due_for_the_contract_sweep(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _fake_sweeps(monkeypatch, {})
    due = uuid.uuid4()
    monkeypatch.setattr("app.worker.main.retention_service.due_institution_ids", lambda db: [due])
    worker = Worker(_settings(WORKER_POLL_INTERVAL_SEC=0), client=FakeClient(), storage=get_storage())
    with caplog.at_level(logging.WARNING, logger="app.worker"):
        worker.run_forever(max_loops=1)
    assert str(due) in caplog.text and "past the retention period" in caplog.text


def test_a_failing_trash_sweep_does_not_stop_the_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.worker.main import WorkerStats

    def broken(*args: Any, **kwargs: Any) -> tuple[int, int]:
        raise RuntimeError("db down")

    monkeypatch.setattr("app.worker.main.run_once", lambda *args, **kwargs: WorkerStats())
    monkeypatch.setattr("app.worker.main.trash_service.purge_expired", broken)
    monkeypatch.setattr("app.worker.main.retention_service.purge_expired_contracts", broken)
    monkeypatch.setattr("app.worker.main.retention_service.due_institution_ids", broken)
    worker = Worker(_settings(WORKER_POLL_INTERVAL_SEC=0), client=FakeClient(), storage=get_storage())
    worker._contract_sweep_from = 0.0
    assert worker.run_forever(max_loops=2) == 2
