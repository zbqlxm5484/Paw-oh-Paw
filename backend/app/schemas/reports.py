"""보고서 응답(15.3 ReportOut, 15.7 판본별 보고서 상태)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.schemas.common import ReasonOut, UtcDateTime


class ReportOut(BaseModel):
    """보고서 판본 1개. file_url·download_url·url_expires_at은 status가 DONE일 때만 있다."""

    id: uuid.UUID
    session_id: uuid.UUID
    edition: str
    status: str
    fail_reason: ReasonOut | None
    generation_ms: int | None
    template_version: str
    model_version: str | None
    updated_at: UtcDateTime
    file_url: str | None
    download_url: str | None
    url_expires_at: UtcDateTime | None


class SessionReportsOut(BaseModel):
    """GET /sessions/{id}/reports. reports는 OWNER, VET 순서이고 회차가 DONE이 되기 전에는 비어 있다."""

    session_id: uuid.UUID
    session_status: str
    reports: list[ReportOut]
