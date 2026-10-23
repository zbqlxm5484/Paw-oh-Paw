"""워커(명세 3절, 12.4). 실행: python -m app.worker.main

주 반복(WORKER_POLL_INTERVAL_SEC, 기본 2초)마다 가벼운 일만 한다(12.4 "무거운 일 나누기").

1. 제출한 촬영의 상태 조회(BE-07): running이면 ANALYZING, failed면 FAILED(ANALYSIS_FAILED. 분석 API의 원래 사유는
   로그에만), 제출 뒤 ANALYSIS_TIMEOUT_SEC가 지나면 FAILED(ANALYSIS_TIMEOUT). done이면 결과를 저장할 차례인데 그 일은
   다음 작업(2/2 결과 저장)이 한다. 여기서는 ANALYZING으로만 둔다.
2. UPLOADED 촬영 가져오기(BE-06): 그 회차 행을 잠근 채 조건을 건 UPDATE로 SUBMITTED로 바꾸고 commit한다. 측정 취소·촬영
   삭제도 같은 회차 행을 잠그므로 둘 중 하나만 먼저 간다(12.4 잠금, 13.3). WORKER_MAX_IN_FLIGHT까지만 가져온다.
3. 가져온 촬영(SUBMITTED인데 job_id가 없는 것)을 분석 API에 보낸다. 되면 job_id를 적고, 못 보내면 SUBMITTED에 둔 채
   attempt_count를 올려 다음 바퀴에 다시 보내며, ANALYSIS_SUBMIT_MAX_ATTEMPTS번 실패하면 FAILED(ANALYSIS_SUBMIT_FAILED).

상태는 조건을 건 UPDATE로만 바꾼다(12.4). 바뀐 행이 0개면 그사이 상태가 달라진 것이므로 건너뛴다. 작업 큐는
DB(shot.status)이고 워커는 한 대다. 메모리에 상태를 두지 않으므로 껐다 켜도 하던 일이 이어진다.

Spring에 빗대면 @Scheduled(fixedDelay = 2000) 메서드 하나를 가진 별도 프로세스다.
"""

from __future__ import annotations

import logging
import shutil
import signal
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClient, AnalysisClientError, SubmitInfo, build_analysis_client
from app.core.config import Settings, get_settings
from app.core.db import SessionLocal
from app.core.errors import FailReason
from app.main import configure_logging
from app.models import MeasureSession, Shot
from app.models.enums import ShotStatus
from app.storage.base import StorageError, StorageService, get_storage

logger = logging.getLogger("app.worker")

UPLOADED = ShotStatus.UPLOADED.value
SUBMITTED = ShotStatus.SUBMITTED.value
ANALYZING = ShotStatus.ANALYZING.value
FAILED = ShotStatus.FAILED.value
# 분석 API에 맡겨 둔(또는 맡기는 중인) 상태 두 가지. WORKER_MAX_IN_FLIGHT는 이 둘의 합이다.
IN_FLIGHT = (SUBMITTED, ANALYZING)


@dataclass
class WorkerStats:
    """한 바퀴에서 한 일의 개수. 로그와 테스트용."""

    claimed: int = 0  # UPLOADED → SUBMITTED (아직 안 보냄)
    submitted: int = 0  # 분석 API가 받아 job_id를 적음
    submit_attempt_failed: int = 0  # 제출 실패했지만 아직 다시 보낼 차례가 남음
    polled: int = 0  # 상태를 조회한 수
    analyzing: int = 0  # SUBMITTED → ANALYZING
    done: int = 0  # 분석 API가 done이라고 답한 수(결과 저장은 2/2)
    failed: int = 0  # → FAILED (제출 포기, 분석 실패)
    timed_out: int = 0  # → FAILED (ANALYSIS_TIMEOUT)

    def busy(self) -> bool:
        return any(value for value in self.__dict__.values())


def _now() -> datetime:
    return datetime.now(UTC)


# ---- 상태 조회 ----


def count_in_flight(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Shot).where(Shot.status.in_(IN_FLIGHT))) or 0


def _fail(db: Session, shot: Shot, reason: FailReason) -> bool:
    """맡겨 둔 촬영을 FAILED로. 그사이 상태가 바뀌었으면(삭제·다시 분석) 건드리지 않는다."""
    changed = db.execute(
        update(Shot)
        .where(Shot.id == shot.id, Shot.status.in_(IN_FLIGHT))
        .values(status=FAILED, fail_reason=reason.value)
    ).rowcount
    db.commit()
    return bool(changed)


def _set_analyzing(db: Session, shot: Shot) -> bool:
    changed = db.execute(
        update(Shot).where(Shot.id == shot.id, Shot.status == SUBMITTED).values(status=ANALYZING)
    ).rowcount
    db.commit()
    return bool(changed)


def poll_in_flight(db: Session, client: AnalysisClient, settings: Settings, stats: WorkerStats) -> None:
    """SUBMITTED·ANALYZING 촬영의 상태를 분석 API에 묻는다. 시간 초과가 먼저다(분석 API가 안 답해도 끝나게)."""
    shots = db.scalars(select(Shot).where(Shot.status.in_(IN_FLIGHT)).order_by(Shot.submitted_at, Shot.id)).all()
    deadline = _now() - timedelta(seconds=settings.ANALYSIS_TIMEOUT_SEC)
    for shot in shots:
        started = shot.submitted_at or shot.uploaded_at
        if started <= deadline:
            if _fail(db, shot, FailReason.ANALYSIS_TIMEOUT):
                stats.timed_out += 1
                logger.error(
                    "analysis timeout shot=%s job=%s after %ss", shot.id, shot.job_id, settings.ANALYSIS_TIMEOUT_SEC
                )
            continue
        if not shot.job_id:
            continue  # 가져왔지만 아직 안 보낸 촬영. 아래 send_claimed가 맡는다
        try:
            status = client.get_status(shot.job_id)
        except AnalysisClientError as e:
            logger.warning("status check failed shot=%s job=%s: %s", shot.id, shot.job_id, e)
            continue
        stats.polled += 1
        if status.state in ("running", "done"):
            if _set_analyzing(db, shot):
                stats.analyzing += 1
            if status.state == "done":
                # 결과 저장(analysis.json, 통과·판정 행, DONE)은 다음 작업(2/2 결과 저장)에서 한다
                stats.done += 1
        elif status.state == "failed":
            # 14.2: 화면에는 ANALYSIS_FAILED만, 분석 API의 원래 사유는 로그에
            logger.error(
                "analysis failed shot=%s job=%s code=%s message=%s",
                shot.id,
                shot.job_id,
                status.error_code,
                status.error_message,
            )
            if _fail(db, shot, FailReason.ANALYSIS_FAILED):
                stats.failed += 1
        # queued: 아직 대기 중. 그대로 둔다


# ---- 가져오기 ----


def claim_uploaded(db: Session, settings: Settings, stats: WorkerStats) -> None:
    """UPLOADED 촬영을 올린 순서대로 SUBMITTED로 가져온다. 자리(WORKER_MAX_IN_FLIGHT)가 있는 만큼만.

    회차 행을 잠근 채 바꾼다(12.4 잠금). 측정 취소·촬영 삭제가 같은 행을 잠그므로, 취소가 먼저면 여기서 바뀐 행이
    0개이고 여기가 먼저면 취소가 SUBMITTED를 보고 409 SHOT_IN_PROGRESS를 낸다. 분석 API는 아직 부르지 않아 잠금이 짧다.
    """
    # TODO(S15P31A404 다음 이슈 "기관별 동시 처리 상한"): WORKER_MAX_IN_FLIGHT_PER_INSTITUTION은 거기서 더한다(12.4)
    room = settings.WORKER_MAX_IN_FLIGHT - count_in_flight(db)
    if room <= 0:
        return
    rows = db.execute(
        select(Shot.id, Shot.session_id).where(Shot.status == UPLOADED).order_by(Shot.uploaded_at, Shot.id).limit(room)
    ).all()
    for shot_id, session_id in rows:
        locked = db.execute(select(MeasureSession.id).where(MeasureSession.id == session_id).with_for_update()).first()
        if locked is None:  # 그사이 회차가 지워졌다
            db.commit()
            continue
        changed = db.execute(
            update(Shot)
            .where(Shot.id == shot_id, Shot.status == UPLOADED)
            .values(status=SUBMITTED, submitted_at=_now(), fail_reason=None)
        ).rowcount
        db.commit()  # 잠금을 바로 푼다
        if changed:
            stats.claimed += 1


# ---- 제출 ----


def _submit_attempt_failed(db: Session, shot: Shot, settings: Settings, error: Exception, stats: WorkerStats) -> None:
    attempts = shot.attempt_count + 1
    final = attempts >= settings.ANALYSIS_SUBMIT_MAX_ATTEMPTS
    values: dict[str, Any] = {"attempt_count": attempts}
    if final:
        values.update(status=FAILED, fail_reason=FailReason.ANALYSIS_SUBMIT_FAILED.value)
    changed = db.execute(
        update(Shot).where(Shot.id == shot.id, Shot.status == SUBMITTED, Shot.job_id.is_(None)).values(**values)
    ).rowcount
    db.commit()
    if not changed:
        return
    if final:
        stats.failed += 1
        logger.error("submit gave up shot=%s after %d attempts: %s", shot.id, attempts, error)
    else:
        stats.submit_attempt_failed += 1
        logger.warning(
            "submit attempt %d/%d failed shot=%s: %s", attempts, settings.ANALYSIS_SUBMIT_MAX_ATTEMPTS, shot.id, error
        )


def send_claimed(
    db: Session, client: AnalysisClient, settings: Settings, storage: StorageService, stats: WorkerStats
) -> None:
    """가져왔지만 아직 분석 API가 받지 않은 촬영(SUBMITTED, job_id 없음)을 보낸다. 실패했던 것도 여기서 다시 보낸다."""
    rows = db.execute(
        select(Shot, MeasureSession.size_class)
        .join(MeasureSession, Shot.session_id == MeasureSession.id)
        .where(Shot.status == SUBMITTED, Shot.job_id.is_(None))
        .order_by(Shot.submitted_at, Shot.id)
    ).all()
    for shot, size_class in rows:
        try:
            with storage.local_copy(shot.original_key) as video:
                job_id = client.submit(video, SubmitInfo(shot_id=shot.id, size_class=size_class))
        except (AnalysisClientError, StorageError) as e:
            _submit_attempt_failed(db, shot, settings, e, stats)
            continue
        changed = db.execute(
            update(Shot)
            .where(Shot.id == shot.id, Shot.status == SUBMITTED, Shot.job_id.is_(None))
            .values(job_id=job_id, submitted_at=_now(), attempt_count=shot.attempt_count + 1)
        ).rowcount
        db.commit()
        if changed:
            stats.submitted += 1
            logger.info("submitted shot=%s job=%s", shot.id, job_id)
        else:
            # 보내는 사이 행이 사라졌거나(파기) 상태가 바뀌었다. 분석 API 쪽 작업은 그냥 버려진다
            logger.warning("shot %s changed before job %s was recorded; analysis job is left unused", shot.id, job_id)


# ---- 주 반복 ----


def run_once(db: Session, client: AnalysisClient, settings: Settings, storage: StorageService) -> WorkerStats:
    """한 바퀴. 상태를 조회해 자리를 비우고 → 새 촬영을 가져오고 → 가져온 것을 보낸다."""
    stats = WorkerStats()
    poll_in_flight(db, client, settings, stats)
    claim_uploaded(db, settings, stats)
    send_claimed(db, client, settings, storage, stats)
    return stats


def clean_worker_tmp(settings: Settings) -> Path:
    """다시 켤 때 UPLOAD_TMP_DIR/worker/를 비운다(12.4). 만들던 중에 꺼진 결과 영상·보고서 조각이 남아 있을 수 있다."""
    tmp = Path(settings.UPLOAD_TMP_DIR) / "worker"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp


class Worker:
    def __init__(
        self,
        settings: Settings | None = None,
        client: AnalysisClient | None = None,
        storage: StorageService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or build_analysis_client(self.settings)
        self.storage = storage or get_storage()
        self._stop = False

    def stop(self, *_: object) -> None:
        """SIGINT·SIGTERM 처리기. 하던 바퀴는 끝내고 멈춘다."""
        self._stop = True

    def run_forever(self, max_loops: int | None = None) -> int:
        """주 반복. 한 바퀴가 실패해도(DB 끊김 등) 로그만 남기고 다음 바퀴를 돈다. 돈 바퀴 수를 돌려준다."""
        loops = 0
        while not self._stop and (max_loops is None or loops < max_loops):
            loops += 1
            started = time.monotonic()
            try:
                with SessionLocal() as db:
                    stats = run_once(db, self.client, self.settings, self.storage)
                if stats.busy():
                    logger.info("loop: %s", stats)
            except Exception:
                logger.exception("worker loop failed; retrying next loop")
            if self._stop or (max_loops is not None and loops >= max_loops):
                break
            time.sleep(max(0.0, self.settings.WORKER_POLL_INTERVAL_SEC - (time.monotonic() - started)))
        return loops


def main() -> int:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    clean_worker_tmp(settings)
    worker = Worker(settings)
    signal.signal(signal.SIGINT, worker.stop)
    signal.signal(signal.SIGTERM, worker.stop)
    logger.info(
        "worker started mode=%s interval=%ss max_in_flight=%d timeout=%ss",
        settings.ANALYSIS_API_MODE,
        settings.WORKER_POLL_INTERVAL_SEC,
        settings.WORKER_MAX_IN_FLIGHT,
        settings.ANALYSIS_TIMEOUT_SEC,
    )
    worker.run_forever()
    logger.info("worker stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
