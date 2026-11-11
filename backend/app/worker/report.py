"""보고서 워커(12.4 "보고서 한 건"·"무거운 일 나누기", 17.4 BE-15, 17.6).

PENDING 보고서를 자식 프로세스에 맡겨 PDF를 만든다.

- 풀: ProcessPoolExecutor(mp_context=spawn) 1개(결과 영상 풀과 따로 두어 보고서가 결과 영상 뒤에서 기다리지 않는다).
- PDF를 만드는 길(8절 6번): REPORT_RENDERER_URL·REPORT_PRINT_URL이 있으면 화면 인쇄다. 맡길 때 그 회차의 인쇄 토큰을
  만들어 인쇄 화면 주소에 붙이고, 자식은 그 주소를 렌더러에 넘겨 PDF를 받는다. 렌더러가 안 되면 기본 템플릿으로 만든다.
  설정이 없으면 늘 기본 템플릿이다. 어느 길이든 글 검사와 수치 대조는 같다. 주소(토큰)는 로그에 남기지 않는다.
- 가져가기: UPDATE report SET status='GENERATING' WHERE id=:id AND status='PENDING' → commit → 입력 dict(report_input)를
  UPLOAD_TMP_DIR/worker/report-{id}/input.json으로 쓰고 generate_report(입력, 출력)를 맡긴다.
  자식은 DB·저장소를 모른다(11.3). 입력의 settings.tolerance는 시작할 때 읽은 config/tolerance.yaml 값이다(197).
- 거두기: 성공이면 PDF를 put_file로 넣고 status='DONE', file_key, generation_ms, model_version, template_version,
  fail_reason=NULL을 WHERE status='GENERATING'으로 쓴다. 바뀐 행이 0개면 방금 넣은 파일을 지운다. ReportCheckError면
  FAILED(REPORT_CHECK_FAILED), 그 밖의 예외는 FAILED(REPORT_FAILED). 키는 보고서 ID로 정해져 다시 만들면 덮어쓴다.
- 대조(8절 7번 첫 항목, 196): 붙이기 전에 자식이 돌려준 실린 숫자 목록(ReportResult.numbers)을 DB의 session_metric 값과
  15.7 다리 비교 계산값에 맞춘다(report/verify.compare_numbers, 기준은 services/report_numbers.reference_numbers).
  값이 다르거나 기준에 없는 숫자가 있으면 PDF를 저장하지 않고 FAILED(REPORT_CHECK_FAILED), DB 오류가 아닌 이유로
  기준을 읽지 못하면 FAILED(REPORT_FAILED). 기준에는 있는데 싣지 않은 수치는 불일치가 아니다(로그에 개수만).
- DB 오류: 거두는 중에 나면 작업과 PDF를 그대로 두고 다음 바퀴에 다시 거둔다. GENERATING인데 맡은 작업이 없는
  보고서(가져간 뒤 DB가 끊겨 맡기지 못한 것)는 매 바퀴 PENDING으로 돌린다.
- 자식이 죽으면(BrokenProcessPool) 풀을 새로 만들고 실행 중이던 보고서는 FAILED(REPORT_FAILED).
- 다시 켤 때: reset_generating이 GENERATING을 PENDING으로 돌린다(만들던 중에 꺼진 것).
VideoRenderer와 같은 모양이다. Spring에 빗대면 @Async 큐 소비자 하나가 트랜잭션 밖에서 PDF를 만들고 결과만 적는 것이다.
"""

from __future__ import annotations

import functools
import json
import logging
import multiprocessing
import shutil
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Executor, Future, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.clients.renderer import ScreenPrint, screen_pdf
from app.core.config import Settings
from app.core.errors import AppError, FailReason
from app.core.security import create_print_token
from app.models import Dog, MeasureSession, Report
from app.models.enums import ReportStatus
from app.report import ReportCheckError, ReportInputError
from app.report.generate import ReportResult, generate_report
from app.report.verify import Verification, compare_numbers, summarize
from app.services.report_input import build_report_input, load_report
from app.services.report_numbers import reference_numbers
from app.services.tolerance import get_tolerance
from app.storage.base import StorageError, StorageService
from app.storage.keys import report_key
from app.worker.render import describe_error

logger = logging.getLogger("app.worker")

PENDING = ReportStatus.PENDING.value
GENERATING = ReportStatus.GENERATING.value
DONE = ReportStatus.DONE.value
FAILED = ReportStatus.FAILED.value
# 12.4: 보고서 풀은 1개다
REPORT_CONCURRENCY = 1

GenerateFn = Callable[..., ReportResult]


@dataclass
class ReportJob:
    report_id: uuid.UUID
    session_id: uuid.UUID
    file_key: str
    model_version: str | None
    future: Future
    job_dir: Path
    output: Path
    started_at: float
    previous_id: uuid.UUID | None = None  # 입력에 넣은 직전 회차. 수치 대조가 같은 회차의 값과 맞춘다


def _previous_id(data: dict[str, Any]) -> uuid.UUID | None:
    raw = (data.get("previous") or {}).get("id")
    try:
        return uuid.UUID(str(raw)) if raw else None
    except ValueError:
        return None


@dataclass(frozen=True)
class _Candidate:
    report_id: uuid.UUID
    session_id: uuid.UUID
    file_key: str
    model_version: str | None


class ReportGenerator:
    def __init__(
        self,
        settings: Settings,
        storage: StorageService,
        *,
        executor_factory: Callable[[], Executor] | None = None,
        generate: GenerateFn = generate_report,
    ) -> None:
        """executor_factory·generate는 테스트가 가짜 풀·가짜 생성 함수를 끼우는 자리다."""
        self.settings = settings
        self.storage = storage
        # 오차 범위(5절·15.8)는 시작할 때 한 번 읽는다. 파일 모양이 틀리면 ToleranceFileError로 바로 멈춘다(197)
        self.tolerance = get_tolerance(settings.TOLERANCE_FILE)
        # 화면 인쇄(8절 6번)는 두 주소가 다 있을 때만 켠다. 하나만 있으면 잘못 적은 것이라 시작을 멈춘다
        self.renderer_url = settings.REPORT_RENDERER_URL.strip()
        self.print_url = settings.REPORT_PRINT_URL.strip().rstrip("/")
        if bool(self.renderer_url) != bool(self.print_url):
            raise ValueError("REPORT_RENDERER_URL과 REPORT_PRINT_URL은 둘 다 채우거나 둘 다 비워야 합니다")
        self.concurrency = REPORT_CONCURRENCY
        self.tmp_root = Path(settings.UPLOAD_TMP_DIR) / "worker"
        self._executor_factory = executor_factory or self._spawn_pool
        self._generate = generate
        self._pool: Executor | None = None
        self.jobs: dict[uuid.UUID, ReportJob] = {}

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
        """워커가 멈출 때. 풀을 닫고 작업 폴더를 지운다.

        GENERATING 행은 다시 켤 때 reset_generating이 PENDING으로 돌린다.
        """
        self._reset_pool()
        for job in list(self.jobs.values()):
            self._cleanup(job)
        self.jobs.clear()

    # ---- 다시 켤 때 ----

    @staticmethod
    def reset_generating(db: Session) -> int:
        """만들던 중에 꺼진 보고서(GENERATING)를 PENDING으로. 워커가 한 대일 때만 맞다(12.4)."""
        count = db.execute(update(Report).where(Report.status == GENERATING).values(status=PENDING)).rowcount
        db.commit()
        if count:
            logger.info("reports reset to PENDING after restart: %d", count)
        return int(count)

    # ---- 한 바퀴 ----

    def run(self, db: Session, stats: Any) -> None:
        self._release_orphans(db)
        self.reap(db, stats)
        self.dispatch(db, stats)

    def reap(self, db: Session, stats: Any) -> None:
        for report_id, job in list(self.jobs.items()):
            if not job.future.done():
                continue
            error = job.future.exception()
            if isinstance(error, BrokenProcessPool):
                self._fail_all(db, stats, error)
                return
            keep = False
            try:
                if error is None:
                    self._verify_and_attach(db, job, job.future.result(), stats)
                elif isinstance(error, ReportCheckError):
                    logger.error("report check failed report=%s: %s", report_id, error)
                    self._fail(db, report_id, FailReason.REPORT_CHECK_FAILED, stats)
                else:
                    logger.error("report generation failed report=%s: %s", report_id, describe_error(error))
                    self._fail(db, report_id, FailReason.REPORT_FAILED, stats)
            except SQLAlchemyError as cause:  # 보고서 탓이 아니다. 작업과 PDF를 두고 다음 바퀴에 다시 거둔다
                db.rollback()
                logger.error("report reap failed report=%s; retrying next loop: %s", report_id, describe_error(cause))
                keep = True
            finally:
                if not keep:
                    self.jobs.pop(report_id)
                    self._cleanup(job)

    def dispatch(self, db: Session, stats: Any) -> None:
        room = self.concurrency - len(self.jobs)
        if room <= 0:
            return
        for candidate in self._candidates(db, room):
            if len(self.jobs) >= self.concurrency:
                break
            self._start(db, candidate, stats)

    def _release_orphans(self, db: Session) -> None:
        """GENERATING인데 맡은 작업이 없는 보고서를 PENDING으로. 워커가 한 대일 때만 맞다(12.4).

        그대로 두면 워커를 다시 켤 때까지 다시 만들기도 409로 막힌다.
        """
        query = update(Report).where(Report.status == GENERATING)
        if self.jobs:
            query = query.where(Report.id.not_in(list(self.jobs)))
        count = db.execute(query.values(status=PENDING)).rowcount
        db.commit()
        if count:
            logger.warning("reports without a job reset to PENDING: %d", count)

    # ---- 맡기기 ----

    def _candidates(self, db: Session, limit: int) -> list[_Candidate]:
        """PENDING 보고서를 updated_at, id 순으로 limit개. 맡겨 둔 것은 뺀다."""
        query = (
            select(
                Report.id, Report.session_id, MeasureSession.dog_id, Dog.institution_id, MeasureSession.model_version
            )
            .join(MeasureSession, Report.session_id == MeasureSession.id)
            .join(Dog, MeasureSession.dog_id == Dog.id)
            .where(Report.status == PENDING)
            .order_by(Report.updated_at, Report.id)
            .limit(limit)
        )
        if self.jobs:
            query = query.where(Report.id.not_in(list(self.jobs)))
        return [
            _Candidate(report_id, session_id, report_key(institution_id, dog_id, session_id, report_id), model_version)
            for report_id, session_id, dog_id, institution_id, model_version in db.execute(query).all()
        ]

    def _claim(self, db: Session, report_id: uuid.UUID) -> bool:
        changed = db.execute(
            update(Report).where(Report.id == report_id, Report.status == PENDING).values(status=GENERATING)
        ).rowcount
        db.commit()
        return bool(changed)

    def _release(self, db: Session, report_id: uuid.UUID) -> None:
        """맡기지 못했을 때 GENERATING을 PENDING으로 되돌려 다음 바퀴에 다시 하게 한다."""
        db.execute(update(Report).where(Report.id == report_id, Report.status == GENERATING).values(status=PENDING))
        db.commit()

    def _start(self, db: Session, candidate: _Candidate, stats: Any) -> None:
        report_id = candidate.report_id
        if not self._claim(db, report_id):
            return  # 그사이 다른 상태가 됐다
        report = load_report(db, report_id)
        if report is None:
            return
        try:
            data = build_report_input(db, report, tolerance=self.tolerance)
        except (ReportInputError, AppError) as error:
            logger.error("report input unavailable report=%s: %s", report_id, describe_error(error))
            self._fail(db, report_id, FailReason.REPORT_FAILED, stats)
            return
        job_dir = self.tmp_root / f"report-{report_id}"
        try:
            shutil.rmtree(job_dir, ignore_errors=True)
            job_dir.mkdir(parents=True, exist_ok=True)
            input_path = job_dir / "input.json"
            input_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            output = job_dir / "report.pdf"
            screen = self._screen_print(report)
            if screen is None:
                future = self._executor().submit(self._generate, input_path, output)
            else:
                to_pdf = functools.partial(screen_pdf, screen)
                future = self._executor().submit(self._generate, input_path, output, to_pdf=to_pdf)
        except BrokenProcessPool as error:
            shutil.rmtree(job_dir, ignore_errors=True)
            self._release(db, report_id)
            self._fail_all(db, stats, error)
            return
        except OSError as error:
            shutil.rmtree(job_dir, ignore_errors=True)
            self._release(db, report_id)
            logger.error("report could not prepare report=%s; retrying next loop: %s", report_id, describe_error(error))
            return
        self.jobs[report_id] = ReportJob(
            report_id=report_id,
            session_id=candidate.session_id,
            file_key=candidate.file_key,
            model_version=candidate.model_version,
            future=future,
            job_dir=job_dir,
            output=output,
            started_at=time.monotonic(),
            previous_id=_previous_id(data),
        )
        stats.report_started += 1
        logger.info("report generation started report=%s edition=%s", report_id, report.edition)

    def _screen_print(self, report: Report) -> ScreenPrint | None:
        """화면 인쇄 한 건: 그 기관의 읽기 전용 인쇄 토큰(11.6)을 붙인 인쇄 화면 주소. None이면 기본 템플릿이다.

        설정이 없으면 None. 반려견이 휴지통에 있어도 None이다: 인쇄 토큰은 로그인처럼 휴지통의 반려견을 읽지
        못하므로, 인쇄 화면이 그리지 못하고 시간 제한까지 기다리기만 한다.
        """
        if not self.renderer_url:
            return None
        session = report.session
        if session.dog.deleted_at is not None:
            return None
        token, _ = create_print_token(session_id=session.id, institution_id=session.dog.institution_id)
        page_url = f"{self.print_url}/print/reports/{session.id}?edition={report.edition}&token={token}"
        return ScreenPrint(
            renderer_url=self.renderer_url, page_url=page_url, timeout_sec=self.settings.REPORT_RENDER_TIMEOUT_SEC
        )

    # ---- 거두기 ----

    def _verify_and_attach(self, db: Session, job: ReportJob, result: ReportResult, stats: Any) -> None:
        """실린 숫자 목록을 DB와 대조하고(8절 7번 첫 항목) 맞을 때만 PDF를 붙인다."""
        report_id = job.report_id
        try:
            reference = reference_numbers(db, job.session_id, job.previous_id)
        except SQLAlchemyError:  # reap이 다음 바퀴에 다시 거둔다
            raise
        except Exception as error:  # 기준을 읽지 못하면 대조할 수 없으므로 DONE으로 두지 않는다
            db.rollback()
            logger.error("report numbers reference unavailable report=%s: %s", report_id, describe_error(error))
            self._fail(db, report_id, FailReason.REPORT_FAILED, stats)
            return
        verification = compare_numbers(result.numbers, reference)
        if not verification.ok:
            logger.error("report numbers mismatch report=%s: %s", report_id, summarize(verification))
            self._fail(db, report_id, FailReason.REPORT_CHECK_FAILED, stats)
            return
        self._attach(db, job, result, stats, verification)

    def _attach(
        self, db: Session, job: ReportJob, result: ReportResult, stats: Any, verification: Verification
    ) -> None:
        """PDF를 먼저 넣고 조건을 건 UPDATE로 키를 붙인다. 바뀐 행이 0개면 방금 넣은 파일을 지운다(12.4)."""
        report_id = job.report_id
        try:
            self.storage.put_file(job.output, job.file_key)
        except (StorageError, OSError) as error:
            logger.error("report store failed report=%s: %s", report_id, describe_error(error))
            self._fail(db, report_id, FailReason.REPORT_FAILED, stats)
            return
        try:
            changed = db.execute(
                update(Report)
                .where(Report.id == report_id, Report.status == GENERATING)
                .values(
                    status=DONE,
                    file_key=job.file_key,
                    generation_ms=result.generation_ms,
                    model_version=job.model_version,
                    template_version=result.template_version,
                    fail_reason=None,
                )
            ).rowcount
            db.commit()
        except Exception as error:  # DB 오류. 넣은 파일을 지우고 PENDING으로 돌려 다음 바퀴에 다시 만든다
            db.rollback()
            self._discard(job.file_key, report_id)
            logger.error("report attach failed report=%s: %s", report_id, describe_error(error))
            self._release(db, report_id)
            return
        if changed:
            stats.reported += 1
            logger.info(
                "report ready report=%s made_by=%s bytes=%d generation_ms=%d numbers=%d omitted=%d in %.1fs",
                report_id,
                result.made_by,
                result.pdf_bytes,
                result.generation_ms,
                verification.checked,
                len(verification.omitted),
                time.monotonic() - job.started_at,
            )
        else:
            self._discard(job.file_key, report_id)
            logger.warning("report %s changed before its file was attached; pdf discarded", report_id)

    def _discard(self, key: str, report_id: uuid.UUID) -> None:
        try:
            self.storage.delete(key)
        except (StorageError, OSError) as error:
            logger.error("report discard failed report=%s: %s", report_id, describe_error(error))

    def _fail(self, db: Session, report_id: uuid.UUID, reason: FailReason, stats: Any) -> bool:
        changed = db.execute(
            update(Report)
            .where(Report.id == report_id, Report.status == GENERATING)
            .values(status=FAILED, fail_reason=reason.value)
        ).rowcount
        db.commit()
        if changed:
            stats.report_failed += 1
        return bool(changed)

    def _fail_all(self, db: Session, stats: Any, error: BaseException) -> None:
        logger.error(
            "report pool broken; restarting it and failing %d job(s): %s", len(self.jobs), describe_error(error)
        )
        self._reset_pool()
        for report_id, job in list(self.jobs.items()):
            self.jobs.pop(report_id)
            try:
                self._fail(db, report_id, FailReason.REPORT_FAILED, stats)
            finally:
                self._cleanup(job)

    def _cleanup(self, job: ReportJob) -> None:
        shutil.rmtree(job.job_dir, ignore_errors=True)
