"""보고서 입력 만들기(12.4 "보고서 한 건", 8절 입력). 워커가 GENERATING으로 가져간 보고서 행 → 보고서 모듈 입력 dict.

모양은 app/report/inputs.py 머리말과 같다. 회차 결과는 GET /sessions/{id}/result와 같은 값(session_result)이고, 직전
회차는 같은 반려견의 바로 앞 DONE 회차(순서는 measured_on, created_at. 12.5)다. 오차 범위(settings.tolerance)는
워커가 services/tolerance.py로 읽은 config/tolerance.yaml 값을 넘긴다(197).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError
from app.models import Dog, MeasureSession, Report
from app.models.enums import SessionStatus
from app.report import ReportInputError
from app.services.session_results import session_result


def _number(value: Any) -> float | None:
    return None if value is None else float(value)


def load_report(db: Session, report_id: uuid.UUID) -> Report | None:
    """보고서 행과 회차·반려견을 한 번에. 없으면 None."""
    return db.scalars(
        select(Report)
        .options(joinedload(Report.session).joinedload(MeasureSession.dog))
        .where(Report.id == report_id)
        .execution_options(populate_existing=True)
    ).one_or_none()


def previous_session_id(db: Session, session: MeasureSession) -> uuid.UUID | None:
    """같은 반려견의 바로 앞 DONE 회차. 회차 순서는 (measured_on, created_at) 오름차순이다(12.5)."""
    return db.scalars(
        select(MeasureSession.id)
        .where(
            MeasureSession.dog_id == session.dog_id,
            MeasureSession.status == SessionStatus.DONE.value,
            MeasureSession.id != session.id,
            tuple_(MeasureSession.measured_on, MeasureSession.created_at)
            < tuple_(session.measured_on, session.created_at),
        )
        .order_by(MeasureSession.measured_on.desc(), MeasureSession.created_at.desc())
        .limit(1)
    ).first()


def build_report_input(db: Session, report: Report, *, tolerance: Mapping[str, float] | None = None) -> dict[str, Any]:
    """보고서 행 → 입력 dict. 회차가 DONE이 아니거나 없으면 ReportInputError(워커는 REPORT_FAILED)."""
    session: MeasureSession = report.session
    dog: Dog = session.dog
    try:
        # 워커는 휴지통을 보지 않고 일한다(12.5). 휴지통의 반려견이어도 보고서를 만든다(199 리뷰 박규원)
        result = session_result(db, dog.institution_id, session.id, include_trashed=True).model_dump(mode="json")
    except AppError as error:
        raise ReportInputError("SESSION_NOT_READY", error.code.value) from error
    previous_id = previous_session_id(db, session)
    previous = None
    if previous_id is not None:
        try:
            previous = session_result(db, dog.institution_id, previous_id, include_trashed=True).model_dump(mode="json")
        except AppError:
            previous = None  # 직전 회차는 없어도 만든다(8절 1번: 없는 정보는 그 항목만 뺀다)
    return {
        "edition": report.edition,
        "dog": {
            "name": dog.name,
            "breed": dog.breed,
            "weight_kg": _number(dog.weight_kg),
            "size_class": dog.size_class,
            "sex": dog.sex,
            "birth_year": dog.birth_year,
        },
        "session": {
            "id": str(session.id),
            "measured_on": session.measured_on.isoformat(),
            "weight_kg": _number(session.weight_kg),
            "size_class": session.size_class,
            "model_name": session.model_name,
            "model_version": session.model_version,
        },
        "result": result,
        "previous": previous,
        "settings": {"tolerance": dict(tolerance or {})},  # config/tolerance.yaml(197)
    }
