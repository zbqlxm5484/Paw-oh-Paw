"""보고서 API(15.7의 19~21, BE-15·16, S15P31A404-195): 판본별 상태, 다시 만들기, PDF 미리보기·내려받기."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.dates import today_local
from app.models import MeasureSession, Report
from app.services.reports import to_report_out
from app.storage.base import get_storage
from app.storage.keys import report_key
from tests.conftest import bearer

PDF = b"%PDF-1.7 fake report"


def _session(db: Session, dog, staff, status: str = "DONE") -> MeasureSession:
    now = datetime.now(UTC)
    session = MeasureSession(
        dog_id=dog.id,
        staff_id=staff.id,
        measured_on=today_local(),
        size_class="MEDIUM",
        status=status,
        completed_at=now,
        aggregated_at=now,
    )
    db.add(session)
    db.flush()
    return session


def _report(db: Session, dog, session: MeasureSession, edition: str, status: str = "PENDING", **values) -> Report:
    report = Report(session_id=session.id, edition=edition, status=status, template_version="0.2", **values)
    db.add(report)
    db.flush()
    if status == "DONE":
        key = report_key(dog.institution_id, dog.id, session.id, report.id)
        get_storage().write_bytes(key, PDF)
        report.file_key = key
        db.flush()
    return report


def _list(client: TestClient, headers: dict, session: MeasureSession):
    return client.get(f"/api/v1/sessions/{session.id}/reports", headers=headers)


# ---- 판본별 상태 ----


def test_reports_are_empty_before_the_session_is_done(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    session = _session(db, dog, staff, status="MEASURING")
    body = _list(client, auth_headers, session).json()
    assert body == {"session_id": str(session.id), "session_status": "MEASURING", "reports": []}


def test_reports_come_owner_first_and_only_done_has_urls(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    session = _session(db, dog, staff)
    vet = _report(db, dog, session, "VET", status="DONE", generation_ms=8400, model_version="v1")
    owner = _report(db, dog, session, "OWNER", status="PENDING")
    body = _list(client, auth_headers, session).json()
    assert [r["edition"] for r in body["reports"]] == ["OWNER", "VET"]
    pending, done = body["reports"]
    assert pending["id"] == str(owner.id) and pending["status"] == "PENDING"
    assert pending["file_url"] is None and pending["download_url"] is None and pending["url_expires_at"] is None
    assert done["id"] == str(vet.id) and done["generation_ms"] == 8400 and done["template_version"] == "0.2"
    assert done["file_url"].startswith(f"/api/v1/reports/{vet.id}/file?exp=") and "sig=" in done["file_url"]
    assert done["download_url"] == done["file_url"] + "&download=true" and done["url_expires_at"].endswith("Z")


def test_file_and_download_urls_share_one_expiry_across_a_second_boundary(
    db: Session, dog, staff, monkeypatch: pytest.MonkeyPatch
) -> None:
    class MovingClock(datetime):
        """서명 함수가 시각을 직접 읽으면 부를 때마다 1초씩 간다."""

        ticks = 0

        @classmethod
        def now(cls, tz=None):
            cls.ticks += 1
            return datetime(2026, 11, 3, 5, 0, cls.ticks, tzinfo=UTC)

    monkeypatch.setattr("app.core.security.datetime", MovingClock)
    session = _session(db, dog, staff)
    out = to_report_out(_report(db, dog, session, "OWNER", status="DONE"), dog.name, session.measured_on)
    assert out.download_url == f"{out.file_url}&download=true"
    assert parse_qs(urlsplit(out.file_url).query)["exp"][0] == str(int(out.url_expires_at.timestamp()))


def test_failed_report_shows_the_reason(client: TestClient, db: Session, dog, staff, auth_headers) -> None:
    session = _session(db, dog, staff)
    _report(db, dog, session, "OWNER", status="FAILED", fail_reason="REPORT_CHECK_FAILED")
    [row] = _list(client, auth_headers, session).json()["reports"]
    assert row["fail_reason"]["code"] == "REPORT_CHECK_FAILED" and row["fail_reason"]["message"]


def test_other_institution_cannot_see_reports(client: TestClient, db: Session, dog, staff, other_staff) -> None:
    session = _session(db, dog, staff)
    response = _list(client, bearer(other_staff), session)
    assert response.status_code == 404 and response.json()["error"]["code"] == "NOT_FOUND"


# ---- 다시 만들기 ----


def test_regenerate_resets_failed_or_done_reports_to_pending(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    session = _session(db, dog, staff)
    failed = _report(db, dog, session, "OWNER", status="FAILED", fail_reason="REPORT_FAILED")
    response = client.post(f"/api/v1/reports/{failed.id}/regenerate", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PENDING" and body["fail_reason"] is None and body["file_url"] is None
    db.expire_all()
    assert db.get(Report, failed.id).status == "PENDING"


def test_regenerate_while_generating_is_in_progress(client: TestClient, db: Session, dog, staff, auth_headers) -> None:
    session = _session(db, dog, staff)
    report = _report(db, dog, session, "VET", status="GENERATING")
    response = client.post(f"/api/v1/reports/{report.id}/regenerate", headers=auth_headers)
    assert response.status_code == 409 and response.json()["error"]["code"] == "REPORT_IN_PROGRESS"


def test_regenerate_unknown_or_other_institution_is_not_found(
    client: TestClient, db: Session, dog, staff, auth_headers, other_staff
) -> None:
    session = _session(db, dog, staff)
    report = _report(db, dog, session, "OWNER")
    assert client.post(f"/api/v1/reports/{uuid.uuid4()}/regenerate", headers=auth_headers).status_code == 404
    assert client.post(f"/api/v1/reports/{report.id}/regenerate", headers=bearer(other_staff)).status_code == 404


# ---- PDF 파일 ----


def test_signed_url_opens_the_pdf_inline_and_download_as_attachment(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    session = _session(db, dog, staff)
    _report(db, dog, session, "OWNER", status="DONE")
    [row] = _list(client, auth_headers, session).json()["reports"]

    inline = client.get(row["file_url"])  # 로그인 토큰 없이 서명으로 연다
    assert inline.status_code == 200 and inline.headers["content-type"] == "application/pdf"
    assert inline.content == PDF
    assert inline.headers["content-disposition"].startswith("inline; filename=\"report.pdf\"; filename*=UTF-8''")
    assert inline.headers["cache-control"].startswith("private, max-age=")

    download = client.get(row["download_url"])
    disposition = download.headers["content-disposition"]
    assert download.status_code == 200
    assert disposition.startswith("attachment; filename=\"report.pdf\"; filename*=UTF-8''")
    assert unquote(disposition.split("''", 1)[1]) == f"{dog.name}_{session.measured_on}_보호자용.pdf"


def test_bad_or_missing_signature_is_file_link_expired(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    session = _session(db, dog, staff)
    report = _report(db, dog, session, "VET", status="DONE")
    [row] = _list(client, auth_headers, session).json()["reports"]
    path = f"/api/v1/reports/{report.id}/file"
    query = parse_qs(urlsplit(row["file_url"]).query)
    exp, sig = query["exp"][0], query["sig"][0]
    flipped = sig[:-1] + ("0" if sig[-1] != "0" else "1")
    for url in (path, f"{path}?exp={exp}", f"{path}?exp={exp}&sig={flipped}", f"{path}?exp={int(exp) + 1}&sig={sig}"):
        response = client.get(url)
        assert response.status_code == 403 and response.json()["error"]["code"] == "FILE_LINK_EXPIRED", url


def test_file_of_a_report_that_is_not_done_is_not_found(client: TestClient, db: Session, dog, staff) -> None:
    from app.core.security import make_signed_url  # noqa: PLC0415

    session = _session(db, dog, staff)
    pending = _report(db, dog, session, "OWNER", status="PENDING")
    url, _ = make_signed_url(f"/api/v1/reports/{pending.id}/file")
    assert client.get(url).status_code == 404
    missing, _ = make_signed_url(f"/api/v1/reports/{uuid.uuid4()}/file")
    assert client.get(missing).status_code == 404
