"""보고서 API(15.7의 19~21·62, BE-15·16)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.api.deps import CurrentStaff, DbSession, ReadCaller, check_file_link
from app.core.config import get_settings
from app.models.enums import ReportEdition
from app.schemas.report_content import ReportContentOut
from app.schemas.reports import ReportOut, SessionReportsOut
from app.services import report_content as content_service
from app.services import reports as report_service

router = APIRouter(tags=["보고서"])


@router.get("/sessions/{session_id}/reports", response_model=SessionReportsOut)
def list_session_reports(session_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> SessionReportsOut:
    """판본별 보고서 상태(S6). 화면은 PENDING·GENERATING인 판본이 있는 동안 3초마다 부른다."""
    return report_service.list_reports(db, staff.institution_id, session_id)


@router.get("/sessions/{session_id}/report-content", response_model=ReportContentOut)
def get_report_content(
    session_id: uuid.UUID, reader: ReadCaller, db: DbSession, edition: ReportEdition
) -> ReportContentOut:
    """판본 하나의 글·표·숫자(BE-15). 검사에 걸리면 409 REPORT_CHECK_FAILED. 인쇄 토큰도 받는다(11.6)."""
    return content_service.report_content(db, reader.institution_id, session_id, edition.value)


@router.post("/reports/{report_id}/regenerate", response_model=ReportOut)
def regenerate_report(report_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> ReportOut:
    """보고서 다시 만들기. GENERATING이면 409 REPORT_IN_PROGRESS."""
    return report_service.regenerate(db, staff.institution_id, report_id)


@router.get("/reports/{report_id}/file", response_class=FileResponse)
def get_report_file(
    report_id: uuid.UUID, db: DbSession, exp: str | None = None, sig: str | None = None, download: bool = False
) -> FileResponse:
    """PDF 미리보기·내려받기(BE-16). 로그인 토큰 없이 서명(exp·sig)으로 연다. download=true면 첨부로 내려받는다.

    서명이 없거나 틀리거나 지났으면 403 FILE_LINK_EXPIRED(DB를 보기 전에 확인한다). 보고서가 DONE이 아니면 404.
    """
    check_file_link(report_service.REPORT_API_PATH.format(report_id=report_id), exp, sig)
    path, name = report_service.report_file(db, report_id)
    headers = {
        "Cache-Control": f"private, max-age={get_settings().FILE_URL_TTL_SEC}",
        "Content-Disposition": report_service.content_disposition(name, download=download),
    }
    return FileResponse(path, media_type="application/pdf", headers=headers)
