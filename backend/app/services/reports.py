"""보고서 API(15.7의 19~21, BE-15·16): 판본별 상태, 다시 만들기, PDF 미리보기·내려받기.

기관 확인은 보고서 → 회차 → 반려견의 institution_id로 한다(11.6). 파일 주소는 저장소가 만드는 서명 URL이고, PDF를
내보내는 로컬 파일 API는 서명만 확인한다(결과 영상과 같다, 15.6). 내려받는 파일 이름은
{반려견 이름}_{측정일}_{보호자용|수의사용}.pdf이고 저장소 경로에는 이름을 쓰지 않는다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError, ErrorCode
from app.models import Dog, MeasureSession, Report
from app.models.enums import ReportEdition, ReportStatus
from app.schemas.common import reason_out
from app.schemas.reports import ReportOut, SessionReportsOut
from app.services.dogs import in_institution
from app.services.sessions import get_session
from app.storage.base import get_storage
from app.storage.local import LocalStorage

REPORT_API_PATH = "/api/v1/reports/{report_id}/file"
EDITION_LABELS = {ReportEdition.OWNER.value: "보호자용", ReportEdition.VET.value: "수의사용"}
EDITION_ORDER = {ReportEdition.OWNER.value: 0, ReportEdition.VET.value: 1}
ASCII_FILE_NAME = "report.pdf"


def download_name(dog_name: str, measured_on: object, edition: str) -> str:
    return f"{dog_name}_{measured_on}_{EDITION_LABELS.get(edition, edition)}.pdf"


def content_disposition(name: str, *, download: bool) -> str:
    """한글 이름은 filename*=UTF-8''<퍼센트 인코딩>으로, 이를 무시하는 뷰어용 ASCII 이름도 넣는다(RFC 6266, 15.7)."""
    kind = "attachment" if download else "inline"
    return f"{kind}; filename=\"{ASCII_FILE_NAME}\"; filename*=UTF-8''{quote(name)}"


def to_report_out(report: Report, dog_name: str, measured_on: object) -> ReportOut:
    file_url = download_url = expires_at = None
    if report.status == ReportStatus.DONE.value and report.file_key:
        storage = get_storage()
        path = REPORT_API_PATH.format(report_id=report.id)
        now = datetime.now(UTC)  # 초가 넘어가도 두 주소의 만료가 같게 한다(15.7)
        file_url, expires_at = storage.file_url(report.file_key, path, now=now)
        name = download_name(dog_name, measured_on, report.edition)
        download_url, _ = storage.file_url(report.file_key, path, name, now=now)
    return ReportOut(
        id=report.id,
        session_id=report.session_id,
        edition=report.edition,
        status=report.status,
        fail_reason=reason_out(report.fail_reason),
        generation_ms=report.generation_ms,
        template_version=report.template_version,
        model_version=report.model_version,
        updated_at=report.updated_at,
        file_url=file_url,
        download_url=download_url,
        url_expires_at=expires_at,
    )


def list_reports(db: Session, institution_id: uuid.UUID, session_id: uuid.UUID) -> SessionReportsOut:
    """판본별 보고서 상태. 회차가 없거나 다른 기관이면 404. OWNER, VET 순서."""
    session = get_session(db, institution_id, session_id)
    reports = sorted(session.reports, key=lambda report: EDITION_ORDER.get(report.edition, 9))
    dog = session.dog
    return SessionReportsOut(
        session_id=session.id,
        session_status=session.status,
        reports=[to_report_out(report, dog.name, session.measured_on) for report in reports],
    )


def _report_in_institution(db: Session, institution_id: uuid.UUID, report_id: uuid.UUID, *, for_update: bool) -> Report:
    query = (
        select(Report)
        .join(MeasureSession, Report.session_id == MeasureSession.id)
        .join(Dog, MeasureSession.dog_id == Dog.id)
        .where(Report.id == report_id, in_institution(institution_id))
    )
    if for_update:
        query = query.with_for_update(of=Report)
    else:
        query = query.options(joinedload(Report.session).joinedload(MeasureSession.dog))
    report = db.scalars(query).one_or_none()
    if report is None:
        raise AppError(ErrorCode.NOT_FOUND)
    return report


def regenerate(db: Session, institution_id: uuid.UUID, report_id: uuid.UUID) -> ReportOut:
    """보고서 다시 만들기(BE-15). GENERATING이면 409 REPORT_IN_PROGRESS. 같은 행을 PENDING으로 되돌린다(12.2).

    file_key는 그대로 두고(키는 보고서 ID로 정해진다) fail_reason만 지운다. 워커가 새 PDF로 덮어쓴다.
    """
    report = _report_in_institution(db, institution_id, report_id, for_update=True)
    if report.status == ReportStatus.GENERATING.value:
        raise AppError(ErrorCode.REPORT_IN_PROGRESS)
    report.status = ReportStatus.PENDING.value
    report.fail_reason = None
    db.flush()
    session = db.get(MeasureSession, report.session_id)
    assert session is not None
    dog = db.get(Dog, session.dog_id)
    assert dog is not None
    return to_report_out(report, dog.name, session.measured_on)


def report_file(db: Session, report_id: uuid.UUID) -> tuple[Path, str]:
    """GET /reports/{id}/file이 FileResponse에 넘길 (경로, 내려받기 이름). 서명 확인은 라우트가 먼저 한다.

    보고서가 없거나 DONE이 아니거나 파일이 없으면 404 NOT_FOUND.
    다시 만드는 중이거나 실패한 판본의 예전 PDF는 내보내지 않는다.
    저장소가 S3면 file_url이 S3 주소라 이 API는 쓰이지 않고, 불리면 404다(11.11).
    """
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise AppError(ErrorCode.NOT_FOUND)
    report = db.scalars(
        select(Report).options(joinedload(Report.session).joinedload(MeasureSession.dog)).where(Report.id == report_id)
    ).one_or_none()
    if report is None or report.status != ReportStatus.DONE.value or not report.file_key:
        raise AppError(ErrorCode.NOT_FOUND)
    path = storage.path(report.file_key)
    if not path.is_file():
        raise AppError(ErrorCode.NOT_FOUND)
    return path, download_name(report.session.dog.name, report.session.measured_on, report.edition)
