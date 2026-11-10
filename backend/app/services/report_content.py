"""보고서 내용 API(15.7의 62번): 판본 하나의 글·표·숫자를 JSON으로 낸다. 웹의 보고서 인쇄 화면이 그린다.

PDF와 같은 길을 간다: 입력(report_input) → 내용(report/content.py) → 글 검사(report/checks.py) → 수치 대조
(report/verify.py, 기준은 report_numbers). 하나라도 걸리면 내용을 내지 않고 409 REPORT_CHECK_FAILED다(8절 7번).
Spring에 빗대면 PDF 생성기와 화면용 조회가 같은 도메인 서비스를 부르고, 검증을 지난 것만 DTO로 내보내는 것이다.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.models import Dog, MeasureSession, Report
from app.models.enums import SessionStatus
from app.report import TEMPLATE_VERSION, ReportCheckError, ReportInputError
from app.report.checks import ensure_checked
from app.report.content import ReportContent, compose_content, difference_level, leg_summaries
from app.report.numbers import GaitTable
from app.report.verify import compare_numbers, summarize
from app.schemas.report_content import (
    ContentBaseline,
    ContentCell,
    ContentChangeCell,
    ContentChangeRow,
    ContentCompare,
    ContentDog,
    ContentGait,
    ContentHistoryItem,
    ContentLeg,
    ContentPrevious,
    ContentRow,
    ContentSentences,
    ContentSession,
    GlossaryItem,
    ReportContentOut,
)
from app.services.report_input import build_report_input
from app.services.report_numbers import reference_numbers
from app.services.sessions import session_query
from app.services.symmetry import session_scores
from app.services.tolerance import get_tolerance

logger = logging.getLogger(__name__)


HISTORY_SIZE = 8  # 화면의 "지금까지 좌우 대칭 지수" 그래프가 그리는 회차 수(박규원 11-10)
ENDED = (SessionStatus.DONE.value, SessionStatus.FAILED.value)


@dataclass(frozen=True)
class _Timeline:
    """반려견의 끝난 회차(DONE·FAILED)를 12.5 순서로 세운 것. 회차 번호는 이 순서의 자리(1부터)다.

    화면의 회차 번호와 같은 규칙이다(박규원 11-10): 분석 실패 회차도 세고, 측정 중·집계 중 회차는 세지 않는다.
    취소한 회차는 행이 없어 저절로 빠진다.
    """

    sessions: list[MeasureSession]
    scores: dict[uuid.UUID, int | None]

    def round_of(self, session_id: uuid.UUID) -> int | None:
        for index, session in enumerate(self.sessions, start=1):
            if session.id == session_id:
                return index
        return None

    def find(self, session_id: uuid.UUID) -> MeasureSession | None:
        return next((session for session in self.sessions if session.id == session_id), None)

    def until(self, session_id: uuid.UUID) -> list[MeasureSession]:
        """이 회차까지(이 회차 포함)의 끝난 회차."""
        rank = self.round_of(session_id) or 0
        return self.sessions[:rank]


def _timeline(db: Session, dog_id: uuid.UUID) -> _Timeline:
    sessions = list(
        db.scalars(
            select(MeasureSession)
            .where(MeasureSession.dog_id == dog_id, MeasureSession.status.in_(ENDED))
            .order_by(MeasureSession.measured_on, MeasureSession.created_at, MeasureSession.id)
        )
    )
    done = [session.id for session in sessions if session.status == SessionStatus.DONE.value]
    return _Timeline(sessions=sessions, scores=session_scores(db, done))


def _baseline(dog: Dog, session: MeasureSession, timeline: _Timeline) -> ContentBaseline | None:
    """12.5 기준 회차. 없거나 이 회차 자신이면 None. diff는 이 회차 점수 − 기준 회차 점수다."""
    baseline_id = dog.baseline_session_id
    if baseline_id is None:
        first_done = next((row for row in timeline.sessions if row.status == SessionStatus.DONE.value), None)
        baseline_id = first_done.id if first_done else None
    base = timeline.find(baseline_id) if baseline_id else None
    if base is None or base.id == session.id:
        return None
    score, base_score = timeline.scores.get(session.id), timeline.scores.get(base.id)
    return ContentBaseline(
        session_id=base.id,
        measured_on=base.measured_on.isoformat(),
        round=timeline.round_of(base.id),
        symmetry_score=base_score,
        diff=None if score is None or base_score is None else score - base_score,
    )


def _previous_id(data: dict[str, Any]) -> uuid.UUID | None:
    previous = data.get("previous") or {}
    return uuid.UUID(str(previous["id"])) if previous.get("id") else None


def _gait(table: GaitTable, notes: list[str]) -> ContentGait:
    return ContentGait(
        gait_type=table.gait_type,
        label=table.label,
        notes=notes,
        rows=[
            ContentRow(
                metric_code=row.code,
                label=row.label,
                unit=row.unit,
                cells={
                    limb: ContentCell(value=cell.value, text=cell.text, reason=cell.reason)
                    for limb, cell in row.cells.items()
                },
            )
            for row in table.rows
        ],
        compare=[
            ContentCompare(
                pair=line.pair,
                pair_label=line.pair_label,
                metric_code=line.code,
                label=line.label,
                left=line.left,
                right=line.right,
                diff=line.diff,
                symmetry_index=line.symmetry_index,
                diff_value=line.diff_value,
                symmetry_value=line.symmetry_value,
                comparable=line.comparable,
                reason=line.reason,
            )
            for line in table.compare
        ],
        changes=[
            ContentChangeRow(
                metric_code=change.code,
                label=change.label,
                unit=change.unit,
                cells={
                    limb: ContentChangeCell(
                        previous=pair.previous,
                        current=pair.current,
                        diff=pair.diff,
                        change=pair.change,
                        change_label=pair.change_label,
                        note=pair.note,
                    )
                    for limb, pair in change.cells.items()
                },
            )
            for change in table.changes
        ],
    )


def _to_out(content: ReportContent, session: MeasureSession, dog: Dog, timeline: _Timeline) -> ReportContentOut:
    inp, sentences = content.inp, content.sentences
    score = timeline.scores.get(session.id)
    previous = None
    if inp.previous:
        previous_id = uuid.UUID(str(inp.previous["id"]))
        previous = ContentPrevious(
            session_id=previous_id,
            measured_on=str(inp.previous["measured_on"]),
            round=timeline.round_of(previous_id),  # 직전 DONE 회차. 사이에 FAILED 회차가 있으면 번호가 건너뛴다
            model_changed=inp.previous_model_changed,
        )
    return ReportContentOut(
        session_id=session.id,
        edition=inp.edition,
        template_version=TEMPLATE_VERSION,
        session=ContentSession(
            measured_on=inp.session.measured_on,
            round=timeline.round_of(session.id),
            model_name=inp.session.model_name,
            model_version=inp.session.model_version,
            weight_kg=inp.session.weight_kg,
            size_class=inp.session.size_class,
            symmetry_score=score,
            symmetry_level=None if score is None else difference_level(100 - score),
        ),
        dog=ContentDog(
            name=inp.dog.name,
            breed=inp.dog.breed,
            sex=inp.dog.sex,
            birth_year=inp.dog.birth_year,
            focus_limb=dog.focus_limb,
        ),
        previous=previous,
        baseline=_baseline(dog, session, timeline),
        history=[
            ContentHistoryItem(
                measured_on=row.measured_on.isoformat(),
                round=timeline.round_of(row.id),
                symmetry_score=timeline.scores.get(row.id),
            )
            for row in timeline.until(session.id)[-HISTORY_SIZE:]
        ],
        legs=[
            ContentLeg(
                pair=leg.pair,
                gait_type=leg.gait_type,
                metric_code=leg.metric_code,
                label=leg.label,
                symmetry_index=leg.symmetry_index,
                symmetry_value=leg.symmetry_value,
                weak_limb=leg.weak_limb,
                level=leg.level,
            )
            for leg in leg_summaries(content.tables)
        ],
        sentences=ContentSentences(
            title=sentences.title,
            edition_label=sentences.edition_label,
            intro=sentences.intro,
            summary=list(sentences.summary),
            previous_note=sentences.previous_note,
            previous_gaps=list(sentences.previous_gaps),
            caution=list(sentences.caution),
            glossary=[GlossaryItem(term=term, explanation=explanation) for term, explanation in sentences.glossary],
            disclaimer=sentences.disclaimer,
        ),
        gaits=[_gait(table, list(sentences.gait_notes.get(table.gait_type, []))) for table in content.tables],
    )


def report_content(
    db: Session, institution_id: uuid.UUID, session_id: uuid.UUID, edition: str, *, include_trashed: bool = False
) -> ReportContentOut:
    """GET /sessions/{id}/report-content. 없거나 다른 기관이면 404, DONE이 아니면 409 SESSION_NOT_DONE.

    글 검사나 수치 대조에 걸리면 409 REPORT_CHECK_FAILED이고 내용은 내지 않는다(PDF를 내보내지 않는 것과 같다).
    include_trashed는 인쇄 토큰으로 부를 때만 쓴다. 워커는 휴지통에 든 반려견의 보고서도 끝까지 만든다(12.5).
    """
    session = db.scalars(session_query(institution_id, session_id, include_trashed=include_trashed)).one_or_none()
    if session is None:
        raise AppError(ErrorCode.NOT_FOUND)
    if session.status != SessionStatus.DONE.value:
        raise AppError(ErrorCode.SESSION_NOT_DONE)
    report = db.scalars(
        select(Report)
        .options(joinedload(Report.session).joinedload(MeasureSession.dog))
        .where(Report.session_id == session.id, Report.edition == edition)
    ).one_or_none()
    if report is None:
        raise AppError(ErrorCode.NOT_FOUND)
    try:
        data = build_report_input(db, report, tolerance=get_tolerance(get_settings().TOLERANCE_FILE))
    except ReportInputError:
        raise AppError(ErrorCode.SESSION_NOT_DONE) from None
    content = compose_content(data)
    try:
        ensure_checked(content.texts, edition=edition)
    except ReportCheckError as error:
        logger.error("report content check failed session=%s edition=%s: %s", session.id, edition, error)
        raise AppError(ErrorCode.REPORT_CHECK_FAILED) from None
    verification = compare_numbers(content.numbers, reference_numbers(db, session.id, _previous_id(data)))
    if not verification.ok:
        logger.error(
            "report content numbers mismatch session=%s edition=%s: %s", session.id, edition, summarize(verification)
        )
        raise AppError(ErrorCode.REPORT_CHECK_FAILED)
    timeline = _timeline(db, session.dog_id)
    # 대칭 점수는 두 길로 계산해 맞춘다: 회차 결과가 읽은 행으로 낸 값과, 여기서 쿼리로 다시 낸 값(12.3)
    if data["result"].get("symmetry_score") != timeline.scores.get(session.id):
        logger.error("report content symmetry score mismatch session=%s edition=%s", session.id, edition)
        raise AppError(ErrorCode.REPORT_CHECK_FAILED)
    return _to_out(content, session, report.session.dog, timeline)
