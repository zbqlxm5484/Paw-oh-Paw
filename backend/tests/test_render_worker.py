"""결과 영상 렌더 풀(12.4 "무거운 일 나누기"·"맡기기와 거두기", 14.2, 17.3 BE-10·12, 17.6 결과 영상이 밀린 줄).

자식 프로세스 대신 바로 끝나거나(또는 끝나지 않는) Future를 주는 가짜 풀과, 파일만 쓰는 가짜 render 함수를 끼워
주 반복 쪽 규칙을 본다. 마지막 테스트 하나만 진짜 spawn 풀·OpenCV·ffmpeg로 끝까지 돌린다(ffmpeg가 없으면 건너뛴다).
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
import uuid
from concurrent.futures import Future
from concurrent.futures.process import BrokenProcessPool
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClientError, AnalysisStatus, SubmitInfo
from app.core.config import Settings, get_settings
from app.core.dates import today_local
from app.models import MeasureSession, Shot, WalkPass
from app.services.shots import delete_shot
from app.storage.base import StorageError, get_storage
from app.storage.keys import original_key, result_key
from app.video.render import RenderResult, VideoRenderError
from app.worker.main import WorkerStats, run_once
from app.worker.render import VideoRenderer
from tests.test_video_render import HEIGHT, WIDTH, _grid_points

# ---- 준비 ----


def _settings(**overrides: Any) -> Settings:
    return get_settings().model_copy(
        update={"WORKER_RENDER_CONCURRENCY": 1, "WORKER_MAX_IN_FLIGHT_PER_INSTITUTION": 100, **overrides}
    )


def _session(db: Session, dog, staff) -> MeasureSession:
    session = MeasureSession(
        dog_id=dog.id, staff_id=staff.id, measured_on=today_local(), size_class="MEDIUM", status="MEASURING"
    )
    db.add(session)
    db.flush()
    return session


def _done_shot(
    db: Session,
    dog,
    session: MeasureSession,
    seq_no: int,
    *,
    analyzed_sec: int = 0,
    status: str = "DONE",
    job_id: str | None = "job-1",
    original: bytes = b"\x00\x00\x00\x18ftypmp42 fake video",
) -> Shot:
    """분석이 끝나(DONE) 결과 영상을 기다리는(PENDING) 촬영. 원본은 7절 키 형식으로 저장소에 둔다."""
    shot_id = uuid.uuid4()
    key = original_key(dog.institution_id, dog.id, session.id, shot_id, "mp4")
    get_storage().write_bytes(key, original)
    now = datetime.now(UTC)
    shot = Shot(
        id=shot_id,
        session_id=session.id,
        seq_no=seq_no,
        status=status,
        job_id=job_id,
        validity="VALID" if status == "DONE" else None,
        original_key=key,
        analysis_key=None,
        width=64,
        height=48,
        fps=Decimal("10"),
        duration_sec=Decimal("1"),
        bitrate_kbps=4000,
        codec="h264",
        uploaded_at=now - timedelta(minutes=1),
        submitted_at=now - timedelta(seconds=50),
        analyzed_at=now + timedelta(seconds=analyzed_sec),
    )
    db.add(shot)
    db.flush()
    return shot


def _fresh(db: Session, shot: Shot) -> Shot | None:
    db.expire_all()
    return db.get(Shot, shot.id)


def _result_key(dog, session: MeasureSession, shot: Shot) -> str:
    return result_key(dog.institution_id, dog.id, session.id, shot.id)


def fake_render(video: Path, keypoints_path: Path, output: Path, *, ffmpeg_path: str) -> RenderResult:
    """자식 대신: 원본 바이트와 관절점 파일을 이어 붙여 output에 쓴다. 자식이 받는 인자 모양은 render_video와 같다.

    원본이 이미 지워졌으면(만드는 도중 촬영 삭제) 그 자리는 비운다. 진짜 자식은 Linux에서 열어 둔 파일을 계속 읽는다.
    """
    original = video.read_bytes() if video.is_file() else b"<gone>"
    data = b"RENDERED:" + original + b":" + keypoints_path.read_bytes()
    output.write_bytes(data)
    return RenderResult(frames=3, drawn_frames=2, width=64, height=48, fps=10.0, bytes=len(data))


class FakeExecutor:
    """가짜 풀. behavior가 "run"이면 submit 때 함수를 바로 돌려 끝난 Future를, "hang"이면 끝나지 않은 Future를 준다.
    예외 객체면 그 예외로 끝난 Future다."""

    def __init__(self, behavior: Any = "run") -> None:
        self.behavior = behavior
        self.calls: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []
        self.futures: list[Future] = []
        self.closed = False

    def submit(self, fn: Any, *args: Any, **kwargs: Any) -> Future:
        future: Future = Future()
        self.calls.append((fn, args, kwargs))
        if isinstance(self.behavior, BaseException):
            future.set_exception(self.behavior)
        elif self.behavior == "run":
            try:
                future.set_result(fn(*args, **kwargs))
            except BaseException as error:
                future.set_exception(error)
        self.futures.append(future)
        return future

    def finish(self, index: int) -> None:
        """끝나지 않은 Future를 가짜 render로 끝낸다(자식이 결과 파일을 다 쓴 상황)."""
        fn, args, kwargs = self.calls[index]
        self.futures[index].set_result(fn(*args, **kwargs))

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        self.closed = True


class KeypointClient:
    """관절점 파일만 돌려주는(또는 실패하는) 분석 클라이언트. 제출은 17.6 테스트용으로 작업 ID만 준다."""

    def __init__(self, keypoints: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.keypoints = keypoints or {"width": WIDTH, "height": HEIGHT, "fps": 10, "frames": []}
        self.error = error
        self.calls: list[str] = []
        self.submits: list[SubmitInfo] = []

    def submit(self, video: Path, info: SubmitInfo) -> str:
        self.submits.append(info)
        return f"job-{len(self.submits)}"

    def get_status(self, job_id: str) -> AnalysisStatus:
        return AnalysisStatus("queued")  # 분석 중인 촬영이 섞여 있어도 그대로 둔다

    def get_result(self, job_id: str) -> dict[str, Any]:
        raise AssertionError("이 테스트는 결과 조회를 하지 않는다")

    def get_keypoints(self, job_id: str) -> dict[str, Any]:
        self.calls.append(job_id)
        if self.error is not None:
            raise self.error
        return self.keypoints


def _renderer(settings: Settings, client: KeypointClient, executor: FakeExecutor, storage: Any = None) -> VideoRenderer:
    return VideoRenderer(
        settings, storage or get_storage(), client, executor_factory=lambda: executor, render=fake_render
    )


def _run(db: Session, renderer: VideoRenderer, settings: Settings, client: KeypointClient) -> WorkerStats:
    return run_once(db, client, settings, get_storage(), renderer)


def _job_dir(settings: Settings, shot: Shot) -> Path:
    return Path(settings.UPLOAD_TMP_DIR) / "worker" / str(shot.id)


# ---- 맡기기와 거두기 ----


def test_done_shots_are_rendered_in_analyzed_order_up_to_concurrency(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    a = _done_shot(db, dog, session, 1, analyzed_sec=2)
    b = _done_shot(db, dog, session, 2, analyzed_sec=1)
    c = _done_shot(db, dog, session, 3, analyzed_sec=3)
    _done_shot(db, dog, session, 4, status="ANALYZING", job_id="job-9")  # 아직 분석 중: 대상이 아니다
    settings = _settings(WORKER_RENDER_CONCURRENCY=2)
    client, executor = KeypointClient(), FakeExecutor("hang")
    renderer = _renderer(settings, client, executor)

    stats = _run(db, renderer, settings, client)

    # analyzed_at 순으로 빈 자리(2)만큼만 맡긴다. 자식에는 원본 경로·관절점 파일·출력 경로·ffmpeg 경로를 넘긴다
    assert stats.render_started == 2 and stats.rendered == 0 and stats.render_failed == 0
    assert list(renderer.jobs) == [b.id, a.id]
    (_, args, kwargs), *_ = executor.calls
    video, keypoints_path, output = args
    assert video == get_storage().path(b.original_key) and video.is_file()  # local이면 저장소 경로 그대로(11.11)
    assert keypoints_path == _job_dir(settings, b) / "keypoints.json" and output == _job_dir(settings, b) / "result.mp4"
    assert json.loads(keypoints_path.read_text(encoding="utf-8")) == client.keypoints
    assert kwargs == {"ffmpeg_path": settings.FFMPEG_PATH}
    assert client.calls == ["job-1", "job-1"]
    for shot in (a, b, c):
        assert _fresh(db, shot).video_status == "PENDING" and _fresh(db, shot).result_key is None

    # 자리가 없으면 아무것도 더 맡기지 않고, 맡겨 둔 촬영을 두 번 맡기지도 않는다
    stats = _run(db, renderer, settings, client)
    assert stats.render_started == 0 and len(executor.calls) == 2

    # b가 끝나면 거두어 READY로 붙이고, 빈 자리에 c를 맡긴다
    executor.finish(0)
    stats = _run(db, renderer, settings, client)
    assert stats.rendered == 1 and stats.render_started == 1 and stats.render_failed == 0
    assert list(renderer.jobs) == [a.id, c.id]
    row = _fresh(db, b)
    assert row.status == "DONE" and row.video_status == "READY" and row.fail_reason is None
    assert row.result_key == _result_key(dog, session, b) and row.video_ready_at is not None
    assert get_storage().read_bytes(row.result_key).startswith(b"RENDERED:")
    assert not _job_dir(settings, b).exists()  # 작업 폴더는 지운다(12.4)
    assert _job_dir(settings, a).is_dir()  # 아직 만드는 중인 것은 그대로
    assert _fresh(db, a).video_status == "PENDING" and _fresh(db, c).video_status == "PENDING"


def test_render_failure_marks_the_video_failed_and_keeps_the_verdict(
    db: Session, dog, staff, caplog: pytest.LogCaptureFixture
) -> None:
    session = _session(db, dog, staff)
    shot = _done_shot(db, dog, session, 1)
    db.add(
        WalkPass(
            shot_id=shot.id, pass_no=1, camera_side="LEFT", gait_type="TROT", is_valid=True, start_frame=1, end_frame=9
        )
    )
    db.flush()
    settings = _settings()
    client = KeypointClient()
    renderer = _renderer(settings, client, FakeExecutor(VideoRenderError("ffmpeg 종료 코드 1: broken")))

    assert _run(db, renderer, settings, client).render_started == 1  # 이 바퀴에 맡기고
    with caplog.at_level(logging.ERROR, logger="app.worker.render"):
        stats = _run(db, renderer, settings, client)  # 다음 바퀴에 거둔다

    assert stats.render_started == 0 and stats.render_failed == 1 and stats.rendered == 0
    row = _fresh(db, shot)
    # 14.2: 결과 영상이 실패해도 판정 결과는 그대로다
    assert row.status == "DONE" and row.validity == "VALID" and len(row.passes) == 1
    assert row.video_status == "FAILED" and row.fail_reason == "VIDEO_RENDER_FAILED" and row.result_key is None
    assert not get_storage().path(_result_key(dog, session, shot)).exists()
    assert not _job_dir(settings, shot).exists() and renderer.jobs == {}
    assert "video render failed" in caplog.text and "broken" in caplog.text
    # FAILED는 다시 맡기지 않는다
    assert _run(db, renderer, settings, client).render_started == 0


def test_shot_deleted_or_changed_during_render_discards_the_file(
    db: Session, dog, staff, caplog: pytest.LogCaptureFixture
) -> None:
    # 17.3 BE-10: 결과 영상을 만드는 도중에 지워도 파일이 남지 않는다
    session = _session(db, dog, staff)
    deleted = _done_shot(db, dog, session, 1, analyzed_sec=1)
    changed = _done_shot(db, dog, session, 2, analyzed_sec=2)
    settings = _settings(WORKER_RENDER_CONCURRENCY=2)
    client, executor = KeypointClient(), FakeExecutor("hang")
    renderer = _renderer(settings, client, executor)
    assert _run(db, renderer, settings, client).render_started == 2

    delete_shot(db, staff.institution_id, deleted.id)  # DONE 촬영은 만드는 중에도 지울 수 있다(13.3)
    db.execute(update(Shot).where(Shot.id == changed.id).values(status="UPLOADED"))  # 다시 분석에 들어간 것처럼
    db.commit()
    executor.finish(0)
    executor.finish(1)
    with caplog.at_level(logging.WARNING, logger="app.worker.render"):
        stats = _run(db, renderer, settings, client)

    assert stats.rendered == 0 and stats.render_failed == 0 and renderer.jobs == {}
    assert _fresh(db, deleted) is None
    assert not get_storage().path(_result_key(dog, session, deleted)).exists()
    row = _fresh(db, changed)
    # 같은 바퀴의 가져오기(claim_uploaded)가 UPLOADED를 SUBMITTED로 바꿨다. 결과 영상은 붙지 않았다
    assert row.status == "SUBMITTED" and row.video_status == "PENDING" and row.result_key is None
    assert not get_storage().path(_result_key(dog, session, changed)).exists()
    assert caplog.text.count("result.mp4 discarded") == 2
    assert not _job_dir(settings, deleted).exists() and not _job_dir(settings, changed).exists()


def test_keypoints_gone_fails_but_a_transient_error_retries(
    db: Session, dog, staff, caplog: pytest.LogCaptureFixture
) -> None:
    session = _session(db, dog, staff)
    settings = _settings()
    executor = FakeExecutor("run")

    # 분석 API에 작업이 없다(410) → 바로 FAILED, 맡기지 않는다
    gone = _done_shot(db, dog, session, 1)
    client = KeypointClient(error=AnalysisClientError("gone", status_code=410))
    renderer = _renderer(settings, client, executor)
    stats = _run(db, renderer, settings, client)
    assert stats.render_failed == 1 and stats.render_started == 0 and executor.calls == []
    assert _fresh(db, gone).video_status == "FAILED" and _fresh(db, gone).fail_reason == "VIDEO_RENDER_FAILED"

    # 요청 거부(400)도 같다
    rejected = _done_shot(db, dog, session, 2)
    client.error = AnalysisClientError("bad request", retryable=False, status_code=400)
    assert _run(db, renderer, settings, client).render_failed == 1
    assert _fresh(db, rejected).video_status == "FAILED"

    # 작업 ID가 없는 DONE 촬영은 관절점을 받을 수 없다 → FAILED
    no_job = _done_shot(db, dog, session, 3, job_id=None)
    assert _run(db, renderer, settings, client).render_failed == 1
    assert _fresh(db, no_job).video_status == "FAILED"

    # 연결 실패·5xx → PENDING 그대로 두고 다음 바퀴에 다시
    flaky = _done_shot(db, dog, session, 4)
    client.error = AnalysisClientError("503", status_code=503)
    with caplog.at_level(logging.WARNING, logger="app.worker.render"):
        stats = _run(db, renderer, settings, client)
    assert stats.render_failed == 0 and stats.render_started == 0
    assert _fresh(db, flaky).video_status == "PENDING" and "retrying next loop" in caplog.text
    client.error = None
    assert _run(db, renderer, settings, client).render_started == 1
    assert _run(db, renderer, settings, client).rendered == 1  # 다음 바퀴에 거둔다
    assert _fresh(db, flaky).video_status == "READY"


def test_broken_pool_fails_in_flight_jobs_and_is_recreated(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    first = _done_shot(db, dog, session, 1, analyzed_sec=1)
    second = _done_shot(db, dog, session, 2, analyzed_sec=2)
    settings = _settings(WORKER_RENDER_CONCURRENCY=2)
    client = KeypointClient()
    executors: list[FakeExecutor] = []

    def factory() -> FakeExecutor:
        executors.append(FakeExecutor("hang"))
        return executors[-1]

    renderer = VideoRenderer(settings, get_storage(), client, executor_factory=factory, render=fake_render)
    assert _run(db, renderer, settings, client).render_started == 2 and len(executors) == 1

    for future in executors[0].futures:  # 자식이 죽으면 실행 중이던 Future가 모두 이 예외로 끝난다
        future.set_exception(BrokenProcessPool("a child process terminated abruptly"))
    stats = _run(db, renderer, settings, client)
    assert stats.render_failed == 2 and renderer.jobs == {} and executors[0].closed
    assert {_fresh(db, s).video_status for s in (first, second)} == {"FAILED"}
    assert not _job_dir(settings, first).exists()

    # 다음 촬영은 새 풀에서 맡는다
    third = _done_shot(db, dog, session, 3, analyzed_sec=3)
    assert _run(db, renderer, settings, client).render_started == 1
    assert len(executors) == 2 and list(renderer.jobs) == [third.id]


def test_storing_the_result_fails_the_video(db: Session, dog, staff, caplog: pytest.LogCaptureFixture) -> None:
    class BrokenPut:
        def __getattr__(self, name: str) -> Any:
            return getattr(get_storage(), name)

        def put_file(self, src: Path, key: str) -> int:
            raise StorageError("no space")

    session = _session(db, dog, staff)
    shot = _done_shot(db, dog, session, 1)
    settings = _settings()
    client = KeypointClient()
    renderer = _renderer(settings, client, FakeExecutor("run"), storage=BrokenPut())
    assert _run(db, renderer, settings, client).render_started == 1
    with caplog.at_level(logging.ERROR, logger="app.worker.render"):
        stats = _run(db, renderer, settings, client)  # 다음 바퀴에 거둔다
    assert stats.render_failed == 1 and _fresh(db, shot).video_status == "FAILED"
    assert "result video store failed" in caplog.text and not _job_dir(settings, shot).exists()


def test_shutdown_closes_the_pool_and_removes_job_dirs(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    shot = _done_shot(db, dog, session, 1)
    settings = _settings()
    client, executor = KeypointClient(), FakeExecutor("hang")
    renderer = _renderer(settings, client, executor)
    _run(db, renderer, settings, client)
    assert _job_dir(settings, shot).is_dir()

    renderer.shutdown()

    assert executor.closed and renderer.jobs == {} and not _job_dir(settings, shot).exists()
    assert _fresh(db, shot).video_status == "PENDING"  # 다시 켜면 처음부터 다시 만든다(12.4)


def test_render_backlog_does_not_block_analysis(db: Session, dog, staff) -> None:
    # 17.6: 결과 영상 20건이 밀려 있어도 새 촬영의 가져오기·제출은 그 바퀴에 그대로 된다
    session = _session(db, dog, staff)
    backlog = [_done_shot(db, dog, session, seq_no, analyzed_sec=seq_no) for seq_no in range(1, 21)]
    new_shot = _done_shot(db, dog, session, 21, status="UPLOADED", job_id=None)
    settings = _settings(WORKER_RENDER_CONCURRENCY=1)
    client, executor = KeypointClient(), FakeExecutor("hang")
    renderer = _renderer(settings, client, executor)

    started = time.monotonic()
    stats = _run(db, renderer, settings, client)

    assert time.monotonic() - started < 5
    assert stats.claimed == 1 and stats.submitted == 1 and stats.render_started == 1
    assert _fresh(db, new_shot).status == "SUBMITTED" and [info.shot_id for info in client.submits] == [new_shot.id]
    assert list(renderer.jobs) == [backlog[0].id]
    assert sum(_fresh(db, s).video_status == "PENDING" for s in backlog) == 20


# ---- 진짜 자식 프로세스 (spawn 풀 + OpenCV + ffmpeg) ----


def test_real_process_pool_renders_a_playable_video(db: Session, dog, staff) -> None:
    settings = _settings()
    try:
        subprocess.run([settings.FFMPEG_PATH, "-version"], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("ffmpeg가 없어 자식 프로세스 테스트를 건너뛴다(FFMPEG_PATH)")
    source = Path(settings.UPLOAD_TMP_DIR) / f"src-{uuid.uuid4().hex[:8]}.mp4"
    subprocess.run(
        [settings.FFMPEG_PATH, "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={WIDTH}x{HEIGHT}:r=10:d=1"]
        + ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
        check=True,
        capture_output=True,
    )
    session = _session(db, dog, staff)
    shot = _done_shot(db, dog, session, 1, original=source.read_bytes())
    grid = [[x, y, 0.95] for x, y in _grid_points()]
    frames = [{"frame": n, "points": grid} for n in range(5)]
    client = KeypointClient({"width": WIDTH, "height": HEIGHT, "fps": 10, "frames": frames})
    renderer = VideoRenderer(settings, get_storage(), client)  # 진짜 spawn 풀과 render_video
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            stats = _run(db, renderer, settings, client)
            if stats.rendered or stats.render_failed:
                break
            time.sleep(0.2)
    finally:
        renderer.shutdown()
        source.unlink(missing_ok=True)

    row = _fresh(db, shot)
    assert row.video_status == "READY" and row.result_key == _result_key(dog, session, shot)
    result = get_storage().path(row.result_key)
    streams = json.loads(
        subprocess.run(
            [settings.FFPROBE_PATH, "-v", "error", "-count_frames", "-show_streams", "-of", "json", str(result)],
            check=True,
            capture_output=True,
        ).stdout
    )["streams"]
    assert [(s["codec_name"], s["pix_fmt"], s["nb_read_frames"]) for s in streams] == [("h264", "yuv420p", "10")]
    assert not _job_dir(settings, shot).exists()
