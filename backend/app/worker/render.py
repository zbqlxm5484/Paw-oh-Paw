"""결과 영상 렌더 프로세스 풀(명세 3절 서버 부담, 12.4 "무거운 일 나누기", 작업 단위 7, Jira 128).

주 반복(app/worker/main.py)이 바퀴마다 VideoRenderer.run(db, stats)을 부른다. run은 (1) 끝난 작업을 거두고(reap)
(2) 빈 자리만큼 새 촬영을 맡긴다(dispatch). 어느 쪽도 자식 프로세스를 기다리지 않으므로 결과 영상이 밀려 있어도
분석 제출·상태 조회는 2초 주기대로 돈다(17.6).

- 풀: ProcessPoolExecutor(mp_context=spawn), 크기는 WORKER_RENDER_CONCURRENCY(16절). fork면 DB 연결 풀이 자식에
  복사되므로 spawn이다(12.4). 보고서 풀(1개, 작업 단위 9)은 같은 모양으로 하나 더 둔다.
- 자식: app/video/render.py의 render_video만 부른다. DB·저장소·분석 API를 모른다(11.3). 얼굴 검출 모델은 그 패키지에
  들어 있어 따로 설정할 것이 없다(Jira 150).
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
- 관절 각도 파일: 관절점 파일을 받은 김에 통과별 각도를 뽑아 촬영 키의 angles.json에 쓴다(12.4 관절 각도 파일,
  services/shot_angles.py). 주 반복에서 바로 하고(가벼운 일), 실패해도 결과 영상은 그대로 맡긴다.
- 관절 각도 파일 다시 만들기(repair_angles, 271 리뷰 박규원): 결과 영상이 READY가 되면 그 촬영은 맡기기 대상에서
  빠지므로, 각도 파일을 못 쓴 촬영은 따로 다시 만든다. ① 못 쓴 촬영을 메모리에 기억해 두고 ANGLES_RETRY_SEC마다
  관절점 파일을 다시 받아 만든다. ② 워커를 켤 때와 ANGLES_CHECK_SEC마다, 최근 ANGLES_CHECK_WINDOW 안에 분석이 끝난
  촬영 중 각도 파일이 없거나 앞 분석의 것인 촬영을 찾아 ①에 넣는다(워커가 재시작되어 기억이 사라진 경우).
  분석 결과가 계약과 다르거나 분석 API에 작업이 없으면 다시 해도 같으므로 그만둔다.
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
from datetime import UTC, datetime, timedelta
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
from app.services.analysis_results import ResultFormatError
from app.services.shot_angles import build_angles, dump_angles
from app.storage.base import StorageError, StorageService
from app.storage.keys import angles_key, result_key
from app.video.render import RenderResult, VideoRenderError, render_video

logger = logging.getLogger("app.worker.render")

DONE = ShotStatus.DONE.value
PENDING = VideoStatus.PENDING.value
READY = VideoStatus.READY.value
FAILED = VideoStatus.FAILED.value

# 관절 각도 파일 다시 만들기(12.4 관절 각도 파일)
ANGLES_RETRY_SEC = 300  # 못 쓴 촬영을 다시 시도하는 간격
ANGLES_CHECK_SEC = 1800  # 최근 촬영에 각도 파일이 있는지 보는 간격. 켤 때도 한 번 본다
ANGLES_CHECK_WINDOW = timedelta(hours=48)  # 분석이 끝난 지 이보다 오래된 촬영은 보지 않는다
ANGLES_CHECK_LIMIT = 200  # 한 번에 보는 촬영 수(최근 것부터)
ANGLES_RETRY_BATCH = 10  # 한 번에 다시 만드는 촬영 수
ANGLES_RETRY_MAX_SEC = 10.0  # 한 번에 쓰는 시간 상한. 주 반복과 같은 스레드라 오래 잡으면 상태 조회가 밀린다

_STORED, _RETRY, _GAVE_UP, _API_DOWN = "stored", "retry", "gave_up", "api_down"

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
    analysis_key: str | None = None
    angles_key: str | None = None


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
        # 각도 파일을 못 쓴 촬영 → 그때의 job_id. 메모리에만 둔다(다시 켜면 _find_missing_angles가 다시 찾는다)
        self._angles_missing: dict[uuid.UUID, str | None] = {}
        self._angles_given_up: set[tuple[uuid.UUID, str | None]] = set()
        self._next_angles_retry = 0.0  # time.monotonic() 기준
        self._next_angles_check = 0.0  # 0이면 켜자마자 한 번 본다

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
        """끝난 작업을 거두고 빈 자리만큼 새로 맡긴다. 기다리지 않는다. 빠진 관절 각도 파일도 여기서 다시 만든다."""
        self.reap(db, stats)
        self.dispatch(db, stats)
        try:
            self.repair_angles(db)
        except Exception as error:  # 각도 파일은 덤이다. 여기서 실패해도 주 반복의 나머지는 돈다
            db.rollback()
            logger.error("angles repair failed; continuing: %s", describe_error(error))

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
            select(
                Shot.id,
                Shot.job_id,
                Shot.original_key,
                Shot.analysis_key,
                MeasureSession.id,
                Dog.id,
                Dog.institution_id,
            )
            .join(MeasureSession, Shot.session_id == MeasureSession.id)
            .join(Dog, MeasureSession.dog_id == Dog.id)
            .where(Shot.status == DONE, Shot.video_status == PENDING)
            .order_by(Shot.analyzed_at, Shot.id)
            .limit(limit)
        )
        if self.jobs:
            query = query.where(Shot.id.not_in(list(self.jobs)))
        return [
            _Candidate(
                shot_id,
                job_id,
                original_key,
                result_key(institution_id, dog_id, session_id, shot_id),
                analysis_key,
                angles_key(institution_id, dog_id, session_id, shot_id),
            )
            for shot_id, job_id, original_key, analysis_key, session_id, dog_id, institution_id in db.execute(
                query
            ).all()
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

    def _store_angles(self, db: Session, candidate: _Candidate, fetch: Callable[[], dict[str, Any]]) -> str:
        """통과별 관절 각도를 angles.json에 써 둔다(12.4 관절 각도 파일). 실패해도 결과 영상은 만든다.

        fetch는 관절점 파일을 주는 함수다(맡길 때는 이미 받은 것, 다시 만들 때는 분석 API 호출). 분석 결과를 먼저
        읽으므로 그것을 못 읽으면 분석 API를 부르지 않는다. 쓴 뒤 촬영이 그대로인지(DONE이고 job_id가 같음) 다시 보고,
        아니면 방금 쓴 파일을 지운다. 저장소·분석 API가 잠깐 안 된 것이면 기억해 두어 repair_angles가 다시 만들고,
        다시 해도 같은 실패면 그만둔다.
        """
        shot_id = candidate.shot_id
        if not candidate.analysis_key or not candidate.angles_key:
            return _GAVE_UP  # 분석 결과 파일이 없는 촬영이다. 만들 재료가 없다
        try:
            result = json.loads(self.storage.read_bytes(candidate.analysis_key))
            doc = build_angles(result, fetch(), shot_id=shot_id, job_id=candidate.job_id)
            self.storage.write_bytes(candidate.angles_key, dump_angles(doc))
        except AnalysisClientError as error:
            if error.job_gone or not error.retryable:
                logger.error("angles impossible shot=%s job=%s; giving up: %s", shot_id, candidate.job_id, error)
                return self._give_up_angles(candidate)
            logger.warning(
                "angles keypoints fetch failed shot=%s job=%s; retrying later: %s", shot_id, candidate.job_id, error
            )
            self._remember_missing_angles(candidate)
            return _API_DOWN
        except (StorageError, OSError) as error:
            # 저장소를 읽거나 쓰지 못했다. 잠깐일 수 있다. 경로가 섞일 수 있어 종류만 남긴다(11.8)
            logger.error("angles store failed shot=%s; retrying later: %s", shot_id, describe_error(error))
            self._remember_missing_angles(candidate)
            return _RETRY
        except (ValueError, ResultFormatError) as error:
            # 분석 결과가 깨졌거나 계약과 다르다. 다시 해도 같다
            logger.error("angles store failed shot=%s; giving up: %s", shot_id, describe_error(error))
            return self._give_up_angles(candidate)
        self._angles_missing.pop(shot_id, None)
        unchanged = db.scalar(
            select(Shot.id).where(Shot.id == shot_id, Shot.status == DONE, Shot.job_id == candidate.job_id)
        )
        if unchanged is None:
            self._discard(candidate.angles_key, shot_id)
            logger.warning("shot %s changed before its angles were stored; angles.json discarded", shot_id)
        return _STORED

    # ---- 관절 각도 파일 다시 만들기 ----

    def _remember_missing_angles(self, candidate: _Candidate) -> None:
        if not self._angles_missing:
            self._next_angles_retry = time.monotonic() + ANGLES_RETRY_SEC
        self._angles_missing[candidate.shot_id] = candidate.job_id

    def _give_up_angles(self, candidate: _Candidate) -> str:
        self._angles_missing.pop(candidate.shot_id, None)
        self._angles_given_up.add((candidate.shot_id, candidate.job_id))
        return _GAVE_UP

    def _angles_candidates(
        self, db: Session, *, shot_id: uuid.UUID | None = None, job_id: str | None = None
    ) -> list[_Candidate]:
        """각도 파일을 다시 만들 수 있는 촬영: DONE이고 분석 결과 파일이 있으며 분석이 끝난 지 오래되지 않았다.

        shot_id를 주면 그 촬영 하나(job_id가 그대로일 때만. 결과 영상이 아직 PENDING이어도 된다), 아니면 결과 영상이
        끝난(PENDING이 아닌) 최근 촬영들이다. PENDING은 맡길 때 각도 파일을 쓰므로 찾지 않는다.
        """
        query = (
            select(
                Shot.id,
                Shot.job_id,
                Shot.original_key,
                Shot.analysis_key,
                MeasureSession.id,
                Dog.id,
                Dog.institution_id,
            )
            .join(MeasureSession, Shot.session_id == MeasureSession.id)
            .join(Dog, MeasureSession.dog_id == Dog.id)
            .where(
                Shot.status == DONE,
                Shot.job_id.is_not(None),
                Shot.analysis_key.is_not(None),
                Shot.analyzed_at >= _now() - ANGLES_CHECK_WINDOW,
            )
        )
        if shot_id is not None:
            query = query.where(Shot.id == shot_id, Shot.job_id == job_id)
        else:
            query = (
                query.where(Shot.video_status != PENDING)
                .order_by(Shot.analyzed_at.desc(), Shot.id)
                .limit(ANGLES_CHECK_LIMIT)
            )
        return [
            _Candidate(
                found_id,
                found_job,
                original_key,
                result_key(institution_id, dog_id, session_id, found_id),
                analysis_key,
                angles_key(institution_id, dog_id, session_id, found_id),
            )
            for found_id, found_job, original_key, analysis_key, session_id, dog_id, institution_id in db.execute(
                query
            ).all()
        ]

    def _angles_present(self, candidate: _Candidate) -> bool:
        """이 분석의 각도 파일이 있다. 못 읽거나 앞 분석의 파일이면 없는 것으로 본다(API가 빈 배열을 주는 경우)."""
        try:
            doc = json.loads(self.storage.read_bytes(candidate.angles_key or ""))
        except (StorageError, OSError, ValueError):
            return False
        return isinstance(doc, dict) and doc.get("job_id") == candidate.job_id

    def _find_missing_angles(self, db: Session, deadline: float) -> int:
        """최근 촬영 중 각도 파일이 빠진 것을 기억 목록에 넣고 그 수를 돌려준다. 워커를 다시 켠 뒤의 복구 길이다."""
        found = 0
        for candidate in self._angles_candidates(db):
            if time.monotonic() >= deadline:
                break
            key = (candidate.shot_id, candidate.job_id)
            if candidate.shot_id in self._angles_missing or key in self._angles_given_up:
                continue
            if not self._angles_present(candidate):
                self._angles_missing[candidate.shot_id] = candidate.job_id
                found += 1
        if found:
            logger.info("angles check: %d shot(s) have no angles file; rebuilding", found)
        return found

    def _retry_angles(self, db: Session, shot_id: uuid.UUID) -> bool:
        """기억해 둔 촬영 하나의 각도 파일을 다시 만든다. 분석 API가 답하지 않으면 False다(이번 차례를 멈춘다)."""
        job_id = self._angles_missing.pop(shot_id)
        found = self._angles_candidates(db, shot_id=shot_id, job_id=job_id)
        if not found:
            return True  # 지워졌거나, 다시 분석에 들어갔거나, 너무 오래됐다. 더 볼 것이 없다
        candidate = found[0]
        if self._angles_present(candidate):
            return True  # 그사이 생겼다(저장소가 잠깐 안 읽혀 빠진 것으로 보였던 경우)
        outcome = self._store_angles(db, candidate, lambda: self.client.get_keypoints(candidate.job_id or ""))
        if outcome == _STORED:
            logger.info("angles rebuilt shot=%s", shot_id)
        return outcome != _API_DOWN

    def repair_angles(self, db: Session) -> None:
        """빠진 관절 각도 파일을 다시 만든다(12.4 관절 각도 파일). 할 일이 없으면 시각만 보고 돌아온다."""
        now = time.monotonic()
        deadline = now + ANGLES_RETRY_MAX_SEC
        if now >= self._next_angles_check:
            self._next_angles_check = now + ANGLES_CHECK_SEC
            if self._find_missing_angles(db, deadline):
                self._next_angles_retry = 0.0  # 찾은 것은 기다리지 않고 만든다
        if not self._angles_missing or now < self._next_angles_retry:
            return
        self._next_angles_retry = now + ANGLES_RETRY_SEC
        for shot_id in list(self._angles_missing)[:ANGLES_RETRY_BATCH]:
            if time.monotonic() >= deadline or not self._retry_angles(db, shot_id):
                break

    def _start(self, db: Session, candidate: _Candidate, stats: Any) -> None:
        keypoints = self._fetch_keypoints(db, candidate, stats)
        if keypoints is None:
            return
        self._store_angles(db, candidate, lambda: keypoints)
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
                "video ready shot=%s frames=%d drawn=%d faces=%d size=%dx%d bytes=%d in %.1fs",
                shot_id,
                result.frames,
                result.drawn_frames,
                result.face_frames,
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
            logger.error("file discard failed shot=%s: %s", shot_id, describe_error(error))

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
