"""결과 영상 렌더 프로세스 풀(명세 3절 서버 부담, 12.4 "무거운 일 나누기", 작업 단위 7, Jira 128).

주 반복(app/worker/main.py)이 바퀴마다 VideoRenderer.run(db, stats)을 부른다. run은 (1) 끝난 작업을 거두고(reap)
(2) 빈 자리만큼 새 촬영을 맡긴다(dispatch). 어느 쪽도 자식 프로세스를 기다리지 않으므로 결과 영상이 밀려 있어도
분석 제출·상태 조회는 2초 주기대로 돈다(17.6).

- 풀: ProcessPoolExecutor(mp_context=spawn), 크기는 WORKER_RENDER_CONCURRENCY(16절). fork면 DB 연결 풀이 자식에
  복사되므로 spawn이다(12.4). 보고서 풀(1개, 작업 단위 9)은 같은 모양으로 하나 더 둔다.
- 자식: app/video/render.py의 render_video만 부른다. DB·저장소·분석 API를 모른다(11.3).
- 작업 폴더: UPLOAD_TMP_DIR/worker/{촬영 ID}/. 원본은 storage.local_copy로 준비해 작업별 ExitStack에 열어 두고(S3면
  내려받은 복사본, local이면 저장소 경로 그대로), 관절점 파일(분석 API get_keypoints)을 keypoints.json으로 쓴다.
  성공·실패 모두 ExitStack을 닫고 폴더를 지운다.
- 맡기기: status=DONE AND video_status=PENDING인 촬영을 analyzed_at, id 순으로 빈 자리 수만큼만 읽는다. 맡긴 ID는
  메모리의 jobs에 있어 두 번 맡기지 않는다. 미리 줄 세우지 않는다(12.4).
- 거두기: 성공이면 result.mp4를 put_file로 넣고 조건을 건 UPDATE(status=DONE AND video_status=PENDING)로 READY·
  result_key·video_ready_at을 붙인다. 바뀐 행이 0개면(그사이 촬영이 지워졌거나 다시 분석) 방금 넣은 파일을 지운다
  (BE-10 "만드는 도중에 지워도 파일이 남지 않는다"). 실패면 같은 조건으로 FAILED와 fail_reason=VIDEO_RENDER_FAILED
  (14.2). 결과 영상이 실패해도 판정 결과는 그대로다.
- 관절점을 못 받으면: 분석 API에 작업이 없거나(404·410) 요청을 거부하면 바로 FAILED, 연결 실패·5xx면 다음 바퀴에 다시.
- 자식이 죽으면(BrokenProcessPool): 풀을 새로 만들고 그 풀에서 실행 중이던 작업은 모두 FAILED다(12.4).
- 워커가 멈추면 풀을 닫고 작업 폴더를 지운다. 만들던 촬영은 PENDING 그대로라 다시 켜면 처음부터 다시 만든다(12.4).

Spring에 빗대면 @Async용 ThreadPoolTaskExecutor를 프로세스 풀로 바꾼 것이고, 스케줄러가 매 바퀴 Future.isDone()을
확인한다. add_done_callback은 쓰지 않는다(콜백은 다른 스레드에서 돌아 DB 세션을 만지면 안 된다, 12.4).
"""

from __future__ import annotations

import json
import logging
import multiprocessing
import shutil
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Executor, Future, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClient, AnalysisClientError
from app.core.config import Settings
from app.core.db import db_error_code
from app.core.errors import FailReason
from app.models import Dog, MeasureSession, Shot
from app.models.enums import ShotStatus, VideoStatus
from app.storage.base import StorageError, StorageService
from app.storage.keys import result_key
from app.video.render import RenderResult, VideoRenderError, render_video

logger = logging.getLogger("app.worker.render")

DONE = ShotStatus.DONE.value
PENDING = VideoStatus.PENDING.value
READY = VideoStatus.READY.value
FAILED = VideoStatus.FAILED.value

RenderFn = Callable[..., RenderResult]


def describe_error(error: BaseException) -> str:
    """로그용 한 줄. str(error)에는 파일 경로(OSError)나 SQL 매개변수(DB 오류)가 섞이므로 종류와 번호만 남긴다(11.8).

    VideoRenderError와 AnalysisClientError의 메시지는 우리가 만든 것이라(경로 없음) 그대로 쓴다.
    """
    name = type(error).__name__
    if isinstance(error, VideoRenderError | AnalysisClientError):
        return f"{name}: {error}"
    if isinstance(error, OSError):
        return f"{name} errno={error.errno}"
    sqlstate = db_error_code(error)
    return f"{name} sqlstate={sqlstate}" if sqlstate else name


@dataclass
class RenderJob:
    """자식 프로세스에 맡겨 둔 결과 영상 작업 하나."""

    shot_id: uuid.UUID
    result_key: str
    future: Future[RenderResult]
    stack: ExitStack  # local_copy를 열어 둔다. 작업이 끝날 때 닫는다(12.4)
    job_dir: Path
    output: Path
    started_at: float  # time.monotonic()


@dataclass(frozen=True)
class _Candidate:
    shot_id: uuid.UUID
    job_id: str | None
    original_key: str
    result_key: str


def _now() -> datetime:
    return datetime.now(UTC)


class VideoRenderer:
    def __init__(
        self,
        settings: Settings,
        storage: StorageService,
        client: AnalysisClient,
        *,
        executor_factory: Callable[[], Executor] | None = None,
        render: RenderFn = render_video,
    ) -> None:
        """executor_factory·render는 테스트가 가짜 풀·가짜 그리기 함수를 끼우는 자리다. 기본은 spawn 풀·render_video."""
        self.settings = settings
        self.storage = storage
        self.client = client
        self.concurrency = settings.WORKER_RENDER_CONCURRENCY
        self.tmp_root = Path(settings.UPLOAD_TMP_DIR) / "worker"
        self._executor_factory = executor_factory or self._spawn_pool
        self._render = render
        self._pool: Executor | None = None
        self.jobs: dict[uuid.UUID, RenderJob] = {}

    # ---- 풀 ----

    def _spawn_pool(self) -> Executor:
        return ProcessPoolExecutor(max_workers=self.concurrency, mp_context=multiprocessing.get_context("spawn"))

    def _executor(self) -> Executor:
        if self._pool is None:
            self._pool = self._executor_factory()
        return self._pool

    def _reset_pool(self) -> None:
        pool, self._pool = self._pool, None
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)

    def shutdown(self) -> None:
        """워커가 멈출 때. 풀을 닫고 작업 폴더를 지운다. 촬영은 PENDING 그대로라 다시 켜면 처음부터 다시 만든다."""
        self._reset_pool()
        for job in list(self.jobs.values()):
            self._cleanup(job)
        self.jobs.clear()

    # ---- 한 바퀴 ----

    def run(self, db: Session, stats: Any) -> None:
        """끝난 작업을 거두고 빈 자리만큼 새로 맡긴다. 기다리지 않는다."""
        self.reap(db, stats)
        self.dispatch(db, stats)

    def reap(self, db: Session, stats: Any) -> None:
        for shot_id, job in list(self.jobs.items()):
            if not job.future.done():
                continue
            error = job.future.exception()  # done이므로 바로 돌아온다
            if isinstance(error, BrokenProcessPool):
                self._fail_all(db, stats, error)
                return
            self.jobs.pop(shot_id)
            try:
                if error is None:
                    self._attach(db, job, job.future.result(), stats)
                else:
                    logger.error("video render failed shot=%s: %s", shot_id, describe_error(error))
                    self._fail_shot(db, shot_id, stats)
            finally:
                self._cleanup(job)

    def dispatch(self, db: Session, stats: Any) -> None:
        room = self.concurrency - len(self.jobs)
        if room <= 0:
            return
        for candidate in self._candidates(db, room):
            if len(self.jobs) >= self.concurrency:
                break
            self._start(db, candidate, stats)

    # ---- 맡기기 ----

    def _candidates(self, db: Session, limit: int) -> list[_Candidate]:
        """status=DONE AND video_status=PENDING인 촬영을 analyzed_at, id 순으로 limit개. 맡겨 둔 것은 뺀다."""
        query = (
            select(Shot.id, Shot.job_id, Shot.original_key, MeasureSession.id, Dog.id, Dog.institution_id)
            .join(MeasureSession, Shot.session_id == MeasureSession.id)
            .join(Dog, MeasureSession.dog_id == Dog.id)
            .where(Shot.status == DONE, Shot.video_status == PENDING)
            .order_by(Shot.analyzed_at, Shot.id)
            .limit(limit)
        )
        if self.jobs:
            query = query.where(Shot.id.not_in(list(self.jobs)))
        return [
            _Candidate(shot_id, job_id, original_key, result_key(institution_id, dog_id, session_id, shot_id))
            for shot_id, job_id, original_key, session_id, dog_id, institution_id in db.execute(query).all()
        ]

    def _fetch_keypoints(self, db: Session, candidate: _Candidate, stats: Any) -> dict[str, Any] | None:
        """분석 API의 관절점 파일. 못 받으면 None이고, 다시 받을 수 없는 실패면 촬영의 결과 영상을 FAILED로 둔다."""
        shot_id = candidate.shot_id
        if not candidate.job_id:
            logger.error("video render impossible shot=%s: no analysis job id", shot_id)
            self._fail_shot(db, shot_id, stats)
            return None
        try:
            return self.client.get_keypoints(candidate.job_id)
        except AnalysisClientError as error:
            if error.job_gone or not error.retryable:
                # 작업이 분석 API에 없거나(재시작·보관 기간 만료) 요청을 거부했다. 기다려도 오지 않는다(12.4)
                logger.error("keypoints unavailable shot=%s job=%s: %s", shot_id, candidate.job_id, error)
                self._fail_shot(db, shot_id, stats)
            else:
                logger.warning(
                    "keypoints fetch failed shot=%s job=%s; retrying next loop: %s", shot_id, candidate.job_id, error
                )
            return None

    def _start(self, db: Session, candidate: _Candidate, stats: Any) -> None:
        keypoints = self._fetch_keypoints(db, candidate, stats)
        if keypoints is None:
            return
        shot_id = candidate.shot_id
        job_dir = self.tmp_root / str(shot_id)
        stack = ExitStack()
        try:
            shutil.rmtree(job_dir, ignore_errors=True)
            job_dir.mkdir(parents=True, exist_ok=True)
            video = stack.enter_context(self.storage.local_copy(candidate.original_key))
            keypoints_path = job_dir / "keypoints.json"
            keypoints_path.write_text(json.dumps(keypoints), encoding="utf-8")
            output = job_dir / "result.mp4"
            future = self._executor().submit(
                self._render, video, keypoints_path, output, ffmpeg_path=self.settings.FFMPEG_PATH
            )
        except BrokenProcessPool as error:
            # 풀이 이미 깨져 있다. 새로 만들고 이 촬영은 PENDING 그대로 두어 다음 바퀴에 다시 맡긴다
            stack.close()
            shutil.rmtree(job_dir, ignore_errors=True)
            self._fail_all(db, stats, error)
            return
        except StorageError as error:
            # 원본 키가 잘못되었거나 S3에서 내려받지 못했다. 다시 해도 같다
            stack.close()
            shutil.rmtree(job_dir, ignore_errors=True)
            logger.error("video render input unavailable shot=%s: %s", shot_id, describe_error(error))
            self._fail_shot(db, shot_id, stats)
            return
        except OSError as error:
            # 임시 폴더에 쓰지 못했다(디스크 가득 참 등). 다음 바퀴에 다시
            stack.close()
            shutil.rmtree(job_dir, ignore_errors=True)
            logger.error(
                "video render could not prepare shot=%s; retrying next loop: %s", shot_id, describe_error(error)
            )
            return
        self.jobs[shot_id] = RenderJob(
            shot_id=shot_id,
            result_key=candidate.result_key,
            future=future,
            stack=stack,
            job_dir=job_dir,
            output=output,
            started_at=time.monotonic(),
        )
        stats.render_started += 1
        logger.info("video render started shot=%s in_progress=%d", shot_id, len(self.jobs))

    # ---- 거두기 ----

    def _attach(self, db: Session, job: RenderJob, result: RenderResult, stats: Any) -> None:
        """파일을 먼저 넣고 조건을 건 UPDATE로 키를 붙인다. 바뀐 행이 0개면 방금 넣은 파일을 지운다(12.4)."""
        shot_id = job.shot_id
        try:
            self.storage.put_file(job.output, job.result_key)
        except (StorageError, OSError) as error:
            logger.error("result video store failed shot=%s: %s", shot_id, describe_error(error))
            self._fail_shot(db, shot_id, stats)
            return
        try:
            changed = db.execute(
                update(Shot)
                .where(Shot.id == shot_id, Shot.status == DONE, Shot.video_status == PENDING)
                .values(video_status=READY, result_key=job.result_key, video_ready_at=_now())
            ).rowcount
            db.commit()
        except Exception as error:  # DB 오류. 촬영은 PENDING 그대로라 다음 바퀴에 다시 만든다
            db.rollback()
            self._discard(job.result_key, shot_id)
            logger.error("result video attach failed shot=%s; retrying next loop: %s", shot_id, describe_error(error))
            return
        if changed:
            stats.rendered += 1
            logger.info(
                "video ready shot=%s frames=%d drawn=%d size=%dx%d bytes=%d in %.1fs",
                shot_id,
                result.frames,
                result.drawn_frames,
                result.width,
                result.height,
                result.bytes,
                time.monotonic() - job.started_at,
            )
        else:
            self._discard(
                job.result_key, shot_id
            )  # 그사이 지워졌거나 다시 분석에 들어갔다. 키 없는 파일을 남기지 않는다
            logger.warning("shot %s changed before its video was attached; result.mp4 discarded", shot_id)

    def _discard(self, key: str, shot_id: uuid.UUID) -> None:
        try:
            self.storage.delete(key)
        except (StorageError, OSError) as error:
            logger.error("result video discard failed shot=%s: %s", shot_id, describe_error(error))

    def _fail_shot(self, db: Session, shot_id: uuid.UUID, stats: Any) -> bool:
        """결과 영상을 FAILED(VIDEO_RENDER_FAILED)로. 그사이 촬영 상태가 달라졌으면 건드리지 않는다."""
        changed = db.execute(
            update(Shot)
            .where(Shot.id == shot_id, Shot.status == DONE, Shot.video_status == PENDING)
            .values(video_status=FAILED, fail_reason=FailReason.VIDEO_RENDER_FAILED.value)
        ).rowcount
        db.commit()
        if changed:
            stats.render_failed += 1
        return bool(changed)

    def _fail_all(self, db: Session, stats: Any, error: BaseException) -> None:
        """자식 프로세스가 죽었다. 풀을 새로 만들고 실행 중이던 작업을 모두 FAILED로 둔다(12.4)."""
        logger.error(
            "render pool broken; restarting it and failing %d job(s): %s", len(self.jobs), describe_error(error)
        )
        self._reset_pool()
        for shot_id, job in list(self.jobs.items()):
            self.jobs.pop(shot_id)
            try:
                self._fail_shot(db, shot_id, stats)
            finally:
                self._cleanup(job)

    def _cleanup(self, job: RenderJob) -> None:
        """ExitStack을 닫고(S3 복사본 삭제) 작업 폴더를 지운다. 성공·실패 모두 부른다(12.4)."""
        try:
            job.stack.close()
        except OSError as error:
            logger.error("local copy cleanup failed shot=%s: %s", job.shot_id, describe_error(error))
        shutil.rmtree(job.job_dir, ignore_errors=True)
