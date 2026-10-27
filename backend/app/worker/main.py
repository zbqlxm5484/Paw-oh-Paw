"""워커(명세 3절, 12.4). 실행: python -m app.worker.main

주 반복(WORKER_POLL_INTERVAL_SEC, 기본 2초)마다 가벼운 일만 한다(12.4 "무거운 일 나누기").

1. 제출한 촬영의 상태 조회(BE-07): running이면 ANALYZING, failed면 FAILED(ANALYSIS_FAILED. 분석 API의 원래 사유는
   로그에만), 제출 뒤 ANALYSIS_TIMEOUT_SEC가 지나면 FAILED(ANALYSIS_TIMEOUT). done이면 결과 JSON을 받아
   analysis.json으로 보관하고 촬영 판정·사유·통과 행을 넣은 뒤 DONE(BE-07·08, services/analysis_results.py). 결과
   JSON을 읽을 수 없거나 분석 API가 작업이 없다고 답하면(404·410) FAILED(ANALYSIS_FAILED). 저장 중 오류는 그 촬영만
   건너뛰고(다음 바퀴에 다시) 바퀴는 이어 간다. 결과 영상·회차 집계는 다음 작업이다.
2. UPLOADED 촬영 가져오기(BE-06): 그 회차 행을 잠근 채 조건을 건 UPDATE로 SUBMITTED로 바꾸고 commit한다. 측정 취소·촬영
   삭제도 같은 회차 행을 잠그므로 둘 중 하나만 먼저 간다(12.4 잠금, 13.3). 전체로는 WORKER_MAX_IN_FLIGHT, 기관별로는
   WORKER_MAX_IN_FLIGHT_PER_INSTITUTION까지만 가져와 한 기관이 자리를 다 차지하지 못하게 한다(3절, 12.4 기관별 상한).
3. 가져온 촬영(SUBMITTED인데 job_id가 없는 것)을 분석 API에 보낸다. 되면 job_id를 적고, 못 보내면 SUBMITTED에 둔 채
   attempt_count를 올려 다음 바퀴에 다시 보내며, ANALYSIS_SUBMIT_MAX_ATTEMPTS번 실패하면 FAILED(ANALYSIS_SUBMIT_FAILED).
   분석 API가 요청 자체를 거부하면(400·413·415 같은 4xx) 다시 보내지 않고 바로 FAILED다. 인증 키가 틀리면(401·403)
   촬영의 잘못이 아니라 촬영은 그대로 두고 로그만 남긴 뒤 그 바퀴의 제출을 멈춘다. 키를 고치면 다음 바퀴에 이어 보낸다.

상태는 조건을 건 UPDATE로만 바꾼다(12.4). 바뀐 행이 0개면 그사이 상태가 달라진 것이므로 건너뛴다. 작업 큐는
DB(shot.status)이고 워커는 한 대다. 메모리에 상태를 두지 않으므로 껐다 켜도 하던 일이 이어진다.

Spring에 빗대면 @Scheduled(fixedDelay = 2000) 메서드 하나를 가진 별도 프로세스다.
"""

from __future__ import annotations

import json
import logging
import shutil
import signal
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClient, AnalysisClientError, SubmitInfo, build_analysis_client
from app.core.config import Settings, get_settings
from app.core.db import SessionLocal, db_error_code
from app.core.errors import FailReason
from app.main import configure_logging
from app.models import Dog, MeasureSession, Shot
from app.models.enums import ShotStatus
from app.services.analysis_results import ResultFormatError, apply_result, parse_result
from app.storage.base import StorageError, StorageService, get_storage
from app.storage.keys import analysis_key

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
    done: int = 0  # 결과를 저장해 DONE이 된 수
    failed: int = 0  # → FAILED (제출 포기, 분석 실패)
    timed_out: int = 0  # → FAILED (ANALYSIS_TIMEOUT)

    def busy(self) -> bool:
        return any(value for value in self.__dict__.values())


def _now() -> datetime:
    return datetime.now(UTC)


# ---- 상태 조회 ----


def count_in_flight_by_institution(db: Session) -> dict[uuid.UUID, int]:
    """기관별 SUBMITTED·ANALYZING 수(shot → measure_session → dog를 join해 GROUP BY, 12.4). 전체 수는 값의 합이다."""
    rows = db.execute(
        select(Dog.institution_id, func.count())
        .select_from(Shot)
        .join(MeasureSession, Shot.session_id == MeasureSession.id)
        .join(Dog, MeasureSession.dog_id == Dog.id)
        .where(Shot.status.in_(IN_FLIGHT))
        .group_by(Dog.institution_id)
    ).all()
    return {institution_id: count for institution_id, count in rows}


def _fail(db: Session, shot_id: uuid.UUID, reason: FailReason) -> bool:
    """맡겨 둔 촬영을 FAILED로. 그사이 상태가 바뀌었으면(삭제·다시 분석) 건드리지 않는다."""
    changed = db.execute(
        update(Shot)
        .where(Shot.id == shot_id, Shot.status.in_(IN_FLIGHT))
        .values(status=FAILED, fail_reason=reason.value)
    ).rowcount
    db.commit()
    return bool(changed)


def _set_analyzing(db: Session, shot_id: uuid.UUID) -> bool:
    changed = db.execute(
        update(Shot).where(Shot.id == shot_id, Shot.status == SUBMITTED).values(status=ANALYZING)
    ).rowcount
    db.commit()
    return bool(changed)


def poll_in_flight(
    db: Session, client: AnalysisClient, settings: Settings, storage: StorageService, stats: WorkerStats
) -> None:
    """SUBMITTED·ANALYZING 촬영의 상태를 분석 API에 묻는다. 시간 초과가 먼저다(분석 API가 안 답해도 끝나게)."""
    rows = db.execute(
        select(Shot, MeasureSession.dog_id, Dog.institution_id)
        .join(MeasureSession, Shot.session_id == MeasureSession.id)
        .join(Dog, MeasureSession.dog_id == Dog.id)
        .where(Shot.status.in_(IN_FLIGHT))
        .order_by(Shot.submitted_at, Shot.id)
    ).all()
    deadline = _now() - timedelta(seconds=settings.ANALYSIS_TIMEOUT_SEC)
    for shot, dog_id, institution_id in rows:
        started = shot.submitted_at or shot.uploaded_at
        if started <= deadline:
            if _fail(db, shot.id, FailReason.ANALYSIS_TIMEOUT):
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
            if e.auth_failed:
                # 키가 틀리면 다른 촬영을 물어도 같다. 이 바퀴의 조회를 멈추고 가져오기·제출로 넘어간다(거기서도 멈춘다)
                logger.error("analysis API rejected our key (check ANALYSIS_API_KEY); status checks paused: %s", e)
                break
            if e.job_gone:
                # 분석 API에 그 작업이 없다(재시작·보관 기간 만료). 기다려도 오지 않으므로 바로 끝낸다(12.4)
                logger.error("analysis job missing shot=%s job=%s: %s", shot.id, shot.job_id, e)
                if _fail(db, shot.id, FailReason.ANALYSIS_FAILED):
                    stats.failed += 1
            else:
                logger.warning("status check failed shot=%s job=%s: %s", shot.id, shot.job_id, e)
            continue
        stats.polled += 1
        if status.state in ("running", "done"):
            if _set_analyzing(db, shot.id):
                stats.analyzing += 1
            if status.state == "done":
                _save_result(db, client, storage, shot, dog_id, institution_id, stats)
        elif status.state == "failed":
            # 14.2: 화면에는 ANALYSIS_FAILED만, 분석 API의 원래 사유는 로그에
            logger.error(
                "analysis failed shot=%s job=%s code=%s message=%s",
                shot.id,
                shot.job_id,
                status.error_code,
                status.error_message,
            )
            if _fail(db, shot.id, FailReason.ANALYSIS_FAILED):
                stats.failed += 1
        # queued: 아직 대기 중. 그대로 둔다


# ---- 결과 저장 ----


def _describe(error: BaseException) -> str:
    """로그용 한 줄. str(error)에는 파일 경로(OSError)나 SQL 매개변수(DB 오류)가 섞이므로 종류와 번호만 남긴다(11.8)."""
    name = type(error).__name__
    if isinstance(error, OSError):
        return f"{name} errno={error.errno}"
    sqlstate = db_error_code(error)
    return f"{name} sqlstate={sqlstate}" if sqlstate else name


def _discard(storage: StorageService, key: str, shot_id: uuid.UUID) -> None:
    """DB에 키가 붙지 못한 analysis.json을 지운다(12.4). 지우기가 실패해도 바퀴는 이어 간다."""
    try:
        storage.delete(key)
    except (StorageError, OSError) as e:
        logger.error("analysis.json discard failed shot=%s: %s", shot_id, _describe(e))


def _save_result(
    db: Session,
    client: AnalysisClient,
    storage: StorageService,
    shot: Shot,
    dog_id: uuid.UUID,
    institution_id: uuid.UUID,
    stats: WorkerStats,
) -> None:
    """done인 촬영의 결과를 받아 analysis.json으로 보관하고 DB에 넣는다(6절 결과 저장 원칙, BE-07·08).

    12.4 순서: 파일을 먼저 쓰고, 조건을 건 UPDATE로 키를 붙인다. 바뀐 행이 0개면(그사이 지워졌거나 실패 처리됨) 방금 쓴
    파일을 지운다. 결과를 못 받으면(409 아직 없음, 5xx, 연결 실패) 다음 바퀴에 다시 받고 시간 초과가 끝을 낸다. 작업이
    없다고 답하거나(404·410) 결과 JSON을 읽을 수 없으면 FAILED(ANALYSIS_FAILED)다. DB에 넣다가 오류가 나면 파일을 지우고
    이 촬영만 건너뛴다. 한 촬영의 오류가 같은 바퀴의 다른 촬영·가져오기·제출을 막지 않는다. 통과별 수치는 JSON에만 남고
    회차 집계(작업 단위 8)가 거기서 읽는다.
    """
    shot_id, job_id, session_id = shot.id, shot.job_id, shot.session_id
    try:
        result = client.get_result(job_id)
    except AnalysisClientError as e:
        if e.job_gone:
            logger.error("analysis result missing shot=%s job=%s: %s", shot_id, job_id, e)
            if _fail(db, shot_id, FailReason.ANALYSIS_FAILED):
                stats.failed += 1
        else:
            logger.warning("result fetch failed shot=%s job=%s: %s", shot_id, job_id, e)
        return
    try:
        parsed = parse_result(result, shot_id=shot_id)
    except ResultFormatError as e:
        logger.error("analysis result unreadable shot=%s job=%s: %s", shot_id, job_id, e)
        if _fail(db, shot_id, FailReason.ANALYSIS_FAILED):
            stats.failed += 1
        return
    key = analysis_key(institution_id, dog_id, session_id, shot_id)
    try:
        storage.write_bytes(key, json.dumps(result, ensure_ascii=False).encode("utf-8"))
    except (StorageError, OSError) as e:
        logger.error("analysis.json write failed shot=%s: %s", shot_id, _describe(e))
        return
    try:
        saved = apply_result(db, shot_id, parsed, analysis_key=key, analyzed_at=_now())
        if saved:
            db.commit()
        else:
            db.rollback()
    except Exception as e:  # DB 오류 등. 다시 던지면 바퀴 전체가 끝나 다른 촬영과 새 업로드까지 멈추므로 여기서 삼킨다
        db.rollback()
        _discard(storage, key, shot_id)
        logger.error(
            "analysis result save failed shot=%s job=%s; retrying next loop: %s", shot_id, job_id, _describe(e)
        )
        return
    if saved:
        stats.done += 1
        logger.info("analysis saved shot=%s validity=%s passes=%d", shot_id, parsed.validity, len(parsed.passes))
    else:
        _discard(storage, key, shot_id)  # DB에 키가 없는 파일을 남기지 않는다(12.4)
        logger.warning("shot %s changed before its result was saved; analysis.json discarded", shot_id)


# ---- 가져오기 ----


def claim_uploaded(db: Session, settings: Settings, stats: WorkerStats) -> None:
    """UPLOADED 촬영을 올린 순서대로 SUBMITTED로 가져온다. 전체 자리(WORKER_MAX_IN_FLIGHT)와 그 기관의 자리
    (WORKER_MAX_IN_FLIGHT_PER_INSTITUTION)가 둘 다 있는 것만(12.4 기관별 상한).

    회차 행을 잠근 채 바꾼다(12.4 잠금). 측정 취소·촬영 삭제가 같은 행을 잠그므로, 취소가 먼저면 여기서 바뀐 행이
    0개이고 여기가 먼저면 취소가 SUBMITTED를 보고 409 SHOT_IN_PROGRESS를 낸다. 분석 API는 아직 부르지 않아 잠금이 짧다.
    """
    in_flight = count_in_flight_by_institution(db)
    room = settings.WORKER_MAX_IN_FLIGHT - sum(in_flight.values())
    if room <= 0:
        return
    per_institution = settings.WORKER_MAX_IN_FLIGHT_PER_INSTITUTION
    full = [institution_id for institution_id, count in in_flight.items() if count >= per_institution]
    # 이미 찬 기관은 SQL에서 뺀다. LIMIT은 걸지 않는다: 이 바퀴 안에서 차는 기관의 나머지 촬영은 건너뛰고 그 뒤에 올린
    # 다른 기관의 촬영을 가져와야 하기 때문이다(3절 "한 기관의 대량 업로드"). ID 세 개짜리 행이라 가볍다
    query = (
        select(Shot.id, Shot.session_id, Dog.institution_id)
        .join(MeasureSession, Shot.session_id == MeasureSession.id)
        .join(Dog, MeasureSession.dog_id == Dog.id)
        .where(Shot.status == UPLOADED)
        .order_by(Shot.uploaded_at, Shot.id)
    )
    if full:
        query = query.where(Dog.institution_id.not_in(full))
    claimed = 0
    for shot_id, session_id, institution_id in db.execute(query).all():
        if claimed >= room:
            break
        if in_flight.get(institution_id, 0) >= per_institution:
            continue  # 이 바퀴에서 찼다. 뒤에 다른 기관의 촬영이 있을 수 있으니 계속 본다
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
            claimed += 1
            in_flight[institution_id] = in_flight.get(institution_id, 0) + 1
            stats.claimed += 1


# ---- 제출 ----


def _submit_attempt_failed(db: Session, shot: Shot, settings: Settings, error: Exception, stats: WorkerStats) -> bool:
    """제출 실패 한 건을 기록한다. True면 이 바퀴의 나머지 제출도 멈춰야 한다(인증 키 문제)."""
    if isinstance(error, AnalysisClientError) and error.auth_failed:
        # 키(ANALYSIS_API_KEY)가 틀린 것이지 촬영의 잘못이 아니다. attempt_count를 올리지 않고 SUBMITTED에 둔 채
        # 바퀴마다 한 줄만 남긴다. 키를 고치면 그대로 이어 보내고, 못 고치면 ANALYSIS_TIMEOUT_SEC 뒤 시간 초과로 끝난다
        stats.submit_attempt_failed += 1
        logger.error("analysis API rejected our key (check ANALYSIS_API_KEY); submissions paused: %s", error)
        return True
    attempts = shot.attempt_count + 1
    # 분석 API가 요청 자체를 거부했으면(4xx) 몇 번을 보내도 같다. 바로 포기한다(87 MR 리뷰 제안 A)
    rejected = isinstance(error, AnalysisClientError) and not error.retryable
    final = rejected or attempts >= settings.ANALYSIS_SUBMIT_MAX_ATTEMPTS
    values: dict[str, Any] = {"attempt_count": attempts}
    if final:
        values.update(status=FAILED, fail_reason=FailReason.ANALYSIS_SUBMIT_FAILED.value)
    changed = db.execute(
        update(Shot).where(Shot.id == shot.id, Shot.status == SUBMITTED, Shot.job_id.is_(None)).values(**values)
    ).rowcount
    db.commit()
    if not changed:
        return False
    if rejected:
        stats.failed += 1
        logger.error("submit rejected by analysis API shot=%s (not retried): %s", shot.id, error)
    elif final:
        stats.failed += 1
        logger.error("submit gave up shot=%s after %d attempts: %s", shot.id, attempts, error)
    else:
        stats.submit_attempt_failed += 1
        logger.warning(
            "submit attempt %d/%d failed shot=%s: %s", attempts, settings.ANALYSIS_SUBMIT_MAX_ATTEMPTS, shot.id, error
        )
    return False


def send_claimed(
    db: Session, client: AnalysisClient, settings: Settings, storage: StorageService, stats: WorkerStats
) -> None:
    """가져왔지만 아직 분석 API가 받지 않은 촬영(SUBMITTED, job_id 없음)을 보낸다. 실패했던 것도 여기서 다시 보낸다."""
    # 올린 순서로 보낸다. submitted_at으로 줄 세우면 같은 바퀴에 가져온 촬영은 값이 같아(Windows의 시계 해상도는
    # 15.6ms) UUID 순이 되어 버린다
    rows = db.execute(
        select(Shot, MeasureSession.size_class)
        .join(MeasureSession, Shot.session_id == MeasureSession.id)
        .where(Shot.status == SUBMITTED, Shot.job_id.is_(None))
        .order_by(Shot.uploaded_at, Shot.id)
    ).all()
    for shot, size_class in rows:
        try:
            with storage.local_copy(shot.original_key) as video:
                job_id = client.submit(video, SubmitInfo(shot_id=shot.id, size_class=size_class))
        except (AnalysisClientError, StorageError) as e:
            if _submit_attempt_failed(db, shot, settings, e, stats):
                break  # 키가 틀리면 나머지도 같다
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
    poll_in_flight(db, client, settings, storage, stats)
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
        "worker started mode=%s interval=%ss max_in_flight=%d per_institution=%d timeout=%ss",
        settings.ANALYSIS_API_MODE,
        settings.WORKER_POLL_INTERVAL_SEC,
        settings.WORKER_MAX_IN_FLIGHT,
        settings.WORKER_MAX_IN_FLIGHT_PER_INSTITUTION,
        settings.ANALYSIS_TIMEOUT_SEC,
    )
    worker.run_forever()
    logger.info("worker stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
