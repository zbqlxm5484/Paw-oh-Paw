"""워커(명세 3절, 12.4). 실행: python -m app.worker.main

주 반복(WORKER_POLL_INTERVAL_SEC, 기본 2초)마다 가벼운 일만 한다(12.4 "무거운 일 나누기").

1. 제출한 촬영의 상태 조회(BE-07): running이면 ANALYZING, failed면 FAILED(ANALYSIS_FAILED. 분석 API의 원래 사유는
   로그에만), 제출 뒤 ANALYSIS_TIMEOUT_SEC가 지나면 FAILED(ANALYSIS_TIMEOUT). done이면 결과 JSON을 받아
   analysis.json으로 보관하고 촬영 판정·사유·통과 행을 넣은 뒤 DONE(BE-07·08, services/analysis_results.py). 결과
   JSON을 읽을 수 없거나 분석 API가 작업이 없다고 답하면(404·410) FAILED(ANALYSIS_FAILED). 저장 중 오류는 그 촬영만
   건너뛰고(다음 바퀴에 다시) 바퀴는 이어 간다.
2. 회차 집계(BE-13): AGGREGATING 회차 중 촬영이 모두 DONE·FAILED인 것을 services/aggregation.py로 집계해 DONE으로 둔다.
   analysis.json을 읽을 수 없으면 FAILED(AGGREGATION_FAILED), DB 오류는 다음 바퀴에 다시.
3. UPLOADED 촬영 가져오기(BE-06): 그 회차 행을 잠근 채 조건을 건 UPDATE로 SUBMITTED로 바꾸고 commit한다. 측정 취소·촬영
   삭제도 같은 회차 행을 잠그므로 둘 중 하나만 먼저 간다(12.4 잠금, 13.3). 가져오기 전에 회차를 분석 줄에 세운다
   (queued_at): 기관마다 줄에 서 있는 회차는 WORKER_QUEUE_PER_INSTITUTION개까지, 1시간에 줄에 세우는 회차는
   WORKER_HOURLY_PER_INSTITUTION개까지다. 줄에 선 순서대로, 전체로는 촬영 WORKER_MAX_IN_FLIGHT건까지 가져온다.
   한 회차의 촬영은 나누지 않는다(3절, 12.4 분석 줄).
4. 가져온 촬영(SUBMITTED인데 job_id가 없는 것)을 분석 API에 보낸다. 되면 job_id를 적고, 못 보내면 SUBMITTED에 둔 채
   attempt_count를 올려 다음 바퀴에 다시 보내며, ANALYSIS_SUBMIT_MAX_ATTEMPTS번 실패하면 FAILED(ANALYSIS_SUBMIT_FAILED).
   분석 API가 요청 자체를 거부하면(400·413·415 같은 4xx) 다시 보내지 않고 바로 FAILED다. 인증 키가 틀리면(401·403)
   촬영의 잘못이 아니라 촬영은 그대로 두고 로그만 남긴 뒤 그 바퀴의 제출을 멈춘다. 키를 고치면 다음 바퀴에 이어 보낸다.
5. 결과 영상(BE-12, 12.4 "무거운 일 나누기"): app/worker/render.py의 VideoRenderer가 끝난 작업을 거두어 READY·FAILED로
   두고, 빈 자리(WORKER_RENDER_CONCURRENCY)만큼 DONE·PENDING 촬영을 자식 프로세스에 맡긴다. 기다리지 않으므로 결과
   영상이 밀려 있어도 1~4는 2초 주기대로 돈다(17.6).

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
from app.core.db import SessionLocal, use_worker_pool
from app.core.errors import FailReason
from app.main import configure_logging
from app.models import Dog, MeasureSession, Shot
from app.models.enums import SessionStatus, ShotStatus
from app.services import retention as retention_service
from app.services import trash as trash_service
from app.services.aggregation import AggregationError, aggregate_session
from app.services.analysis_copies import Cleared
from app.services.analysis_results import ResultFormatError, apply_result, parse_result
from app.storage.base import StorageError, StorageService, get_storage
from app.storage.keys import analysis_key
from app.worker.render import VideoRenderer, describe_error
from app.worker.report import ReportGenerator

logger = logging.getLogger("app.worker")

UPLOADED = ShotStatus.UPLOADED.value
SUBMITTED = ShotStatus.SUBMITTED.value
ANALYZING = ShotStatus.ANALYZING.value
FAILED = ShotStatus.FAILED.value
# 분석 API에 맡겨 둔(또는 맡기는 중인) 상태 두 가지. WORKER_MAX_IN_FLIGHT는 이 둘의 합이다.
IN_FLIGHT = (SUBMITTED, ANALYZING)
# 회차 집계를 기다리게 하는 촬영 상태. 남은 것은 DONE·FAILED다(12.4)
UNFINISHED = (UPLOADED, SUBMITTED, ANALYZING)
AGGREGATING = SessionStatus.AGGREGATING.value
# 휴지통 자동 비우기와 계약 종료 뒤 자동 파기(12.5)를 보는 간격. 30일·90일 기준이라 자주 볼 필요가 없다
TRASH_SWEEP_INTERVAL_SEC = 3600
# 한 차례가 시간 상한(WORKER_SWEEP_MAX_SEC)에 닿아 남겼을 때 다시 보는 간격. 그사이 주 반복이 밀린 일을 한다
SWEEP_RESUME_SEC = 300


@dataclass
class WorkerStats:
    """한 바퀴에서 한 일의 개수. 로그와 테스트용."""

    queued: int = 0  # 회차를 분석 줄에 세움(queued_at)
    claimed: int = 0  # UPLOADED → SUBMITTED (아직 안 보냄)
    submitted: int = 0  # 분석 API가 받아 job_id를 적음
    submit_attempt_failed: int = 0  # 제출 실패했지만 아직 다시 보낼 차례가 남음
    polled: int = 0  # 상태를 조회한 수
    analyzing: int = 0  # SUBMITTED → ANALYZING
    done: int = 0  # 결과를 저장해 DONE이 된 수
    failed: int = 0  # → FAILED (제출 포기, 분석 실패)
    timed_out: int = 0  # → FAILED (ANALYSIS_TIMEOUT)
    render_started: int = 0  # 결과 영상을 자식 프로세스에 맡긴 수
    rendered: int = 0  # video_status → READY
    render_failed: int = 0  # video_status → FAILED (VIDEO_RENDER_FAILED)
    aggregated: int = 0  # 회차 AGGREGATING → DONE
    aggregation_failed: int = 0  # 회차 AGGREGATING → FAILED (AGGREGATION_FAILED)
    report_started: int = 0  # 보고서를 자식 프로세스에 맡긴 수
    reported: int = 0  # report.status → DONE
    report_failed: int = 0  # report.status → FAILED (REPORT_CHECK_FAILED·REPORT_FAILED)

    def busy(self) -> bool:
        return any(value for value in self.__dict__.values())


def _now() -> datetime:
    return datetime.now(UTC)


# ---- 상태 조회 ----


def count_in_flight(db: Session) -> int:
    """분석 API에 맡겨 둔(SUBMITTED·ANALYZING) 촬영 수. 전체 자리는 WORKER_MAX_IN_FLIGHT에서 이 수를 뺀 것이다."""
    return db.scalar(select(func.count()).select_from(Shot).where(Shot.status.in_(IN_FLIGHT))) or 0


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


def _discard(storage: StorageService, key: str, shot_id: uuid.UUID) -> None:
    """DB에 키가 붙지 못한 analysis.json을 지운다(12.4). 지우기가 실패해도 바퀴는 이어 간다."""
    try:
        storage.delete(key)
    except (StorageError, OSError) as e:
        logger.error("analysis.json discard failed shot=%s: %s", shot_id, describe_error(e))


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
        logger.error("analysis.json write failed shot=%s: %s", shot_id, describe_error(e))
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
            "analysis result save failed shot=%s job=%s; retrying next loop: %s", shot_id, job_id, describe_error(e)
        )
        return
    if saved:
        stats.done += 1
        logger.info("analysis saved shot=%s validity=%s passes=%d", shot_id, parsed.validity, len(parsed.passes))
    else:
        _discard(storage, key, shot_id)  # DB에 키가 없는 파일을 남기지 않는다(12.4)
        logger.warning("shot %s changed before its result was saved; analysis.json discarded", shot_id)


# ---- 회차 집계 ----


def aggregate_finished(db: Session, storage: StorageService, stats: WorkerStats) -> None:
    """AGGREGATING 회차 중 촬영이 모두 DONE·FAILED인 것을 집계한다(12.4). 측정 종료가 빠른 순서로.

    파일을 읽을 수 없으면 다시 해도 같으므로 FAILED(AGGREGATION_FAILED)다. DB 오류는 그 회차만 건너뛰고 다음 바퀴에 다시
    한다. 한 회차의 오류가 다른 회차와 같은 바퀴의 가져오기·제출을 막지 않는다.
    """
    unfinished = select(Shot.id).where(Shot.session_id == MeasureSession.id, Shot.status.in_(UNFINISHED)).exists()
    session_ids = db.scalars(
        select(MeasureSession.id)
        .where(MeasureSession.status == AGGREGATING, ~unfinished)
        .order_by(MeasureSession.completed_at, MeasureSession.id)
    ).all()
    for session_id in session_ids:
        try:
            changed = aggregate_session(db, storage, session_id, now=_now())
            db.commit()
        except AggregationError as e:
            db.rollback()
            logger.error("aggregation failed session=%s: %s", session_id, e)
            failed = db.execute(
                update(MeasureSession)
                .where(MeasureSession.id == session_id, MeasureSession.status == AGGREGATING)
                .values(status=SessionStatus.FAILED.value, fail_reason=FailReason.AGGREGATION_FAILED.value)
            ).rowcount
            db.commit()
            if failed:
                stats.aggregation_failed += 1
            continue
        except Exception as e:  # DB 오류 등. 다시 던지면 바퀴 전체가 끝나 새 업로드까지 멈추므로 여기서 삼킨다
            db.rollback()
            logger.error("aggregation save failed session=%s; retrying next loop: %s", session_id, describe_error(e))
            continue
        if changed:
            stats.aggregated += 1
            logger.info("session aggregated session=%s", session_id)


# ---- 가져오기 ----


def _lock_session(db: Session, session_id: uuid.UUID) -> bool:
    """회차 행을 FOR UPDATE로 잠근다(12.4 잠금). 그사이 지워졌으면 False."""
    row = db.execute(select(MeasureSession.id).where(MeasureSession.id == session_id).with_for_update()).first()
    return row is not None


# 기관별 접수 제한을 세는 기간(12.4 분석 줄): 지난 1시간에 줄에 세운 회차를 센다
QUEUE_WINDOW = timedelta(hours=1)


def admit_to_queue(db: Session, settings: Settings, stats: WorkerStats) -> None:
    """UPLOADED 촬영이 있는데 아직 분석 줄에 서지 않은 회차를 줄에 세운다(queued_at, 12.4 분석 줄).

    기관마다 두 가지를 넘지 않게 한다.
    - 줄에 서 있는 회차는 WORKER_QUEUE_PER_INSTITUTION개까지. 분석 중인 촬영이 있는 회차는 세지 않는다.
    - 지난 1시간에 줄에 세운 회차는 WORKER_HOURLY_PER_INSTITUTION개까지.

    넘치는 회차는 거절하지 않는다. 촬영은 UPLOADED로 남고(화면에는 대기 중) 자리가 나면 다음 바퀴에 줄에 선다.
    줄에 선 순서가 분석 순서다. 한 기관이 회차를 많이 올려도 앞에 세울 수 있는 회차는 줄 크기까지이고, 그 뒤에 온 다른
    기관의 회차가 그다음에 선다. queued_at은 이미 있는 값보다 늘 뒤가 되게 적는다(시계가 같은 값을 주어도 순서가 선다).
    """
    in_flight = select(Shot.session_id).where(Shot.status.in_(IN_FLIGHT))
    queued = dict(
        db.execute(
            select(Dog.institution_id, func.count(func.distinct(MeasureSession.id)))
            .select_from(Shot)
            .join(MeasureSession, Shot.session_id == MeasureSession.id)
            .join(Dog, MeasureSession.dog_id == Dog.id)
            .where(
                Shot.status == UPLOADED,
                MeasureSession.queued_at.is_not(None),
                MeasureSession.id.not_in(in_flight),
            )
            .group_by(Dog.institution_id)
        ).all()
    )
    recent = dict(
        db.execute(
            select(Dog.institution_id, func.count())
            .select_from(MeasureSession)
            .join(Dog, MeasureSession.dog_id == Dog.id)
            .where(MeasureSession.queued_at > _now() - QUEUE_WINDOW)
            .group_by(Dog.institution_id)
        ).all()
    )
    # 아직 줄에 서지 않은 회차를 기관별로 처음 올린 순서대로. 한 바퀴에 기관마다 줄 크기까지만 읽는다
    first_uploaded = func.min(Shot.uploaded_at)
    waiting = (
        select(
            MeasureSession.id.label("session_id"),
            Dog.institution_id.label("institution_id"),
            first_uploaded.label("first_uploaded"),
            func.row_number()
            .over(partition_by=Dog.institution_id, order_by=(first_uploaded, MeasureSession.id))
            .label("rank"),
        )
        .select_from(Shot)
        .join(MeasureSession, Shot.session_id == MeasureSession.id)
        .join(Dog, MeasureSession.dog_id == Dog.id)
        .where(Shot.status == UPLOADED, MeasureSession.queued_at.is_(None))
        .group_by(MeasureSession.id, Dog.institution_id)
    ).subquery("waiting")
    rows = db.execute(
        select(waiting.c.session_id, waiting.c.institution_id)
        .where(waiting.c.rank <= settings.WORKER_QUEUE_PER_INSTITUTION)
        .order_by(waiting.c.first_uploaded, waiting.c.session_id)
    ).all()
    if not rows:
        return
    last = db.scalar(select(func.max(MeasureSession.queued_at)))
    at = _now()
    if last is not None and last >= at:
        at = last + timedelta(microseconds=1)
    for session_id, institution_id in rows:
        if queued.get(institution_id, 0) >= settings.WORKER_QUEUE_PER_INSTITUTION:
            continue
        if recent.get(institution_id, 0) >= settings.WORKER_HOURLY_PER_INSTITUTION:
            continue
        changed = db.execute(
            update(MeasureSession)
            .where(MeasureSession.id == session_id, MeasureSession.queued_at.is_(None))
            .values(queued_at=at)
        ).rowcount
        db.commit()
        if changed:
            at += timedelta(microseconds=1)
            queued[institution_id] = queued.get(institution_id, 0) + 1
            recent[institution_id] = recent.get(institution_id, 0) + 1
            stats.queued += 1


def claim_uploaded(db: Session, settings: Settings, stats: WorkerStats) -> None:
    """분석 줄에 선 회차의 UPLOADED 촬영을 줄에 선 순서대로 SUBMITTED로 가져온다(12.4 분석 줄).

    전체 자리는 촬영 수다(WORKER_MAX_IN_FLIGHT − 분석 중인 촬영 수). 한 회차의 촬영은 나누지 않으므로, 자리가 있으면 한
    회차에 올린 16건이 한꺼번에 간다. 줄에 선 순서(queued_at)가 먼저이고 같은 회차 안에서는 올린 순서다. 읽는 행은 남은
    자리 수까지다(LIMIT). 그래서 대기열이 아무리 길어도 읽어 오는 행은 남은 자리 수다.

    회차 행을 잠근 채 바꾼다(12.4 잠금). 측정 취소·촬영 삭제가 같은 행을 잠그므로, 취소가 먼저면 여기서 바뀐 행이
    0개이고 여기가 먼저면 취소가 SUBMITTED를 보고 409 SHOT_IN_PROGRESS를 낸다. 분석 API는 아직 부르지 않아 잠금이 짧다.
    """
    room = settings.WORKER_MAX_IN_FLIGHT - count_in_flight(db)
    if room <= 0:
        return
    query = (
        select(Shot.id, Shot.session_id)
        .join(MeasureSession, Shot.session_id == MeasureSession.id)
        .where(Shot.status == UPLOADED, MeasureSession.queued_at.is_not(None))
        .order_by(MeasureSession.queued_at, Shot.uploaded_at, Shot.id)
        .limit(room)
    )
    for shot_id, session_id in db.execute(query).all():
        if not _lock_session(db, session_id):  # 그사이 회차가 지워졌다(촬영도 함께)
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
            # 보내는 사이 행이 사라졌거나(파기) 상태가 바뀌었다. job_id를 적을 행이 없어 나중에 찾을 수 없으므로
            # 지금 사본을 지워 본다. 아직 분석 중이면(409) 못 지우고, 그때는 분석 API의 전체 파기가 거둔다
            try:
                client.delete(job_id)
                logger.warning("shot %s changed before job %s was recorded; analysis copy deleted", shot.id, job_id)
            except AnalysisClientError as e:
                logger.warning(
                    "shot %s changed before job %s was recorded; analysis copy is left behind: %s", shot.id, job_id, e
                )


# ---- 주 반복 ----


def run_once(
    db: Session,
    client: AnalysisClient,
    settings: Settings,
    storage: StorageService,
    renderer: VideoRenderer | None = None,
    reporter: ReportGenerator | None = None,
) -> WorkerStats:
    """한 바퀴. 상태를 조회해 자리를 비우고 → 끝난 회차를 집계하고 → 회차를 분석 줄에 세우고 → 줄에 선 순서대로
    새 촬영을 가져오고 → 가져온 것을 보내고 → 결과 영상을 거두고 맡긴다.

    renderer·reporter가 없으면 결과 영상·보고서는 건너뛴다(분석 쪽만 보는 테스트용). Worker는 늘 넘긴다.
    """
    stats = WorkerStats()
    poll_in_flight(db, client, settings, storage, stats)
    aggregate_finished(db, storage, stats)
    admit_to_queue(db, settings, stats)
    claim_uploaded(db, settings, stats)
    send_claimed(db, client, settings, storage, stats)
    if renderer is not None:
        renderer.run(db, stats)
    if reporter is not None:
        reporter.run(db, stats)
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
        renderer: VideoRenderer | None = None,
        reporter: ReportGenerator | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or build_analysis_client(self.settings)
        self.storage = storage or get_storage()
        self.renderer = renderer or VideoRenderer(self.settings, self.storage, self.client)
        self.reporter = reporter or ReportGenerator(self.settings, self.storage)
        self._stop = False
        self._next_trash_sweep = 0.0  # time.monotonic() 기준. 0이면 켜자마자 한 번 본다
        # 계약 종료 뒤 자동 파기는 켠 뒤 한 간격이 지나야 처음 돈다. 배포하자마자 기관의 자료가 지워지지 않게
        # 하려는 것이다(되돌릴 수 없다). 켤 때는 대상 기관을 로그로만 알린다(199 리뷰 박규원)
        self._contract_sweep_from = time.monotonic() + TRASH_SWEEP_INTERVAL_SEC
        # 자동 파기가 시간 상한에 닿아 남겼을 때, 분석 API 사본을 끝낸 촬영을 다음 차례까지 기억한다. 없으면 차례마다
        # 처음부터 다시 불러, 촬영이 많은 기관은 끝나지 않는다(services/analysis_copies.py)
        self._cleared: Cleared = {}

    def stop(self, *_: object) -> None:
        """SIGINT·SIGTERM 처리기. 하던 바퀴는 끝내고 멈춘다."""
        self._stop = True

    def empty_trash(self, deadline: float | None = None) -> bool:
        """휴지통에 30일 넘게 있던 반려견을 영구 삭제한다(12.5). 실패해도 로그만 남기고 다음 차례에 다시 한다.

        시간 상한(deadline)에 닿아 남겼으면 True다.
        """
        try:
            with SessionLocal() as db:
                result = trash_service.purge_expired(
                    db, self.storage, self.client, deadline=deadline, cleared=self._cleared
                )
                db.commit()
            if result.purged or result.failed or result.out_of_time:
                logger.info(
                    "trash sweep: purged=%d failed=%d out_of_time=%s", result.purged, result.failed, result.out_of_time
                )
            return result.out_of_time
        except Exception:
            logger.exception("trash sweep failed; retrying at the next sweep")
            return False

    def purge_expired_contracts(self, deadline: float | None = None) -> bool:
        """계약이 끝난 지 90일이 지난 기관의 자료와 가입 계정을 지운다(12.5). 실패해도 다음 차례에 다시 한다.

        시간 상한(deadline)에 닿아 남겼으면 True다.
        """
        try:
            with SessionLocal() as db:
                result = retention_service.purge_expired_contracts(
                    db, self.storage, self.client, deadline=deadline, cleared=self._cleared
                )
                db.commit()
            if result.purged or result.failed or result.out_of_time:
                logger.info(
                    "contract sweep: purged=%d failed=%d out_of_time=%s",
                    result.purged,
                    result.failed,
                    result.out_of_time,
                )
            return result.out_of_time
        except Exception:
            logger.exception("contract sweep failed; retrying at the next sweep")
            return False

    def warn_contract_purge(self) -> None:
        """켤 때 한 번: 계약 종료 뒤 자동 파기 대상 기관이 있으면 로그로 알린다(12.4). 기관 ID만 적는다."""
        try:
            with SessionLocal() as db:
                due = retention_service.due_institution_ids(db)
        except Exception:
            logger.exception("could not list institutions due for the contract sweep; continuing")
            return
        if due:
            logger.warning(
                "contract sweep: %d institution(s) are past the retention period; their data and CLIENT accounts "
                "will be purged in about %d min unless contract_ends_at is changed: %s",
                len(due),
                TRASH_SWEEP_INTERVAL_SEC // 60,
                ", ".join(str(value) for value in due),
            )

    def sweep(self) -> bool:
        """휴지통 자동 비우기와 계약 종료 뒤 자동 파기를 한 차례 돈다. 시간 상한에 닿아 남겼으면 True다.

        둘이 합쳐 WORKER_SWEEP_MAX_SEC를 넘지 않게 같은 deadline을 쓴다. 주 반복과 같은 스레드라, 오래 걸리면 상태
        조회가 밀려 정상 진행 중인 촬영이 ANALYSIS_TIMEOUT으로 끝날 수 있기 때문이다(199 리뷰 박규원).
        """
        deadline = time.monotonic() + self.settings.WORKER_SWEEP_MAX_SEC
        out_of_time = self.empty_trash(deadline)
        if not out_of_time and time.monotonic() >= self._contract_sweep_from:
            out_of_time = self.purge_expired_contracts(deadline)
        if not out_of_time:
            self._cleared.clear()  # 남긴 것이 없다. 못 지운 것은 다음 차례에 처음부터 다시 부른다
        return out_of_time

    def run_forever(self, max_loops: int | None = None) -> int:
        """주 반복. 한 바퀴가 실패해도(DB 끊김 등) 로그만 남기고 다음 바퀴를 돈다. 돈 바퀴 수를 돌려준다.

        끝날 때 렌더 풀을 닫는다. 만들던 결과 영상은 PENDING 그대로라 다시 켜면 처음부터 다시 만든다(12.4).
        켤 때 GENERATING 보고서를 PENDING으로 돌린다(만들던 중에 꺼진 것, 12.4).
        """
        loops = 0
        try:
            with SessionLocal() as db:
                self.reporter.reset_generating(db)
        except Exception:
            logger.exception("could not reset generating reports; continuing")
        self.warn_contract_purge()
        try:
            while not self._stop and (max_loops is None or loops < max_loops):
                loops += 1
                started = time.monotonic()
                try:
                    with SessionLocal() as db:
                        stats = run_once(db, self.client, self.settings, self.storage, self.renderer, self.reporter)
                    if stats.busy():
                        logger.info("loop: %s", stats)
                except Exception:
                    logger.exception("worker loop failed; retrying next loop")
                if time.monotonic() >= self._next_trash_sweep:
                    out_of_time = self.sweep()
                    # 남겼으면 한 시간을 기다리지 않고 곧 이어서 한다
                    wait = SWEEP_RESUME_SEC if out_of_time else TRASH_SWEEP_INTERVAL_SEC
                    self._next_trash_sweep = time.monotonic() + wait
                if self._stop or (max_loops is not None and loops >= max_loops):
                    break
                time.sleep(max(0.0, self.settings.WORKER_POLL_INTERVAL_SEC - (time.monotonic() - started)))
        finally:
            self.renderer.shutdown()
            self.reporter.shutdown()
        return loops


def main() -> int:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    use_worker_pool()  # 워커는 연결을 몇 개만 쓴다. 엔진을 만들기 전에 상한을 낮춘다(core/db.py)
    clean_worker_tmp(settings)
    worker = Worker(settings)
    signal.signal(signal.SIGINT, worker.stop)
    signal.signal(signal.SIGTERM, worker.stop)
    logger.info(
        "worker started mode=%s interval=%ss max_in_flight=%d queue_per_institution=%d hourly_per_institution=%d "
        "timeout=%ss render_concurrency=%d report_concurrency=%d sweep_max=%ss",
        settings.ANALYSIS_API_MODE,
        settings.WORKER_POLL_INTERVAL_SEC,
        settings.WORKER_MAX_IN_FLIGHT,
        settings.WORKER_QUEUE_PER_INSTITUTION,
        settings.WORKER_HOURLY_PER_INSTITUTION,
        settings.ANALYSIS_TIMEOUT_SEC,
        settings.WORKER_RENDER_CONCURRENCY,
        settings.WORKER_REPORT_CONCURRENCY,
        settings.WORKER_SWEEP_MAX_SEC,
    )
    worker.run_forever()
    logger.info("worker stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
