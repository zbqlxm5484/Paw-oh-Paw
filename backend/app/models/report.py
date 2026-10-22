"""보고서. 판본마다 1행, 다시 만들면 같은 행을 덮어쓴다. 명세 12.2 report."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import ReportEdition, ReportStatus, check_in

if TYPE_CHECKING:
    from app.models.measure_session import MeasureSession


class Report(Base):
    __tablename__ = "report"
    __table_args__ = (
        UniqueConstraint("session_id", "edition", name="uq_report_edition"),
        check_in("edition", ReportEdition, name="ck_report_edition"),
        check_in("status", ReportStatus, name="ck_report_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("measure_session.id", name="fk_report_session"))
    # 보호자용·수의사용
    edition: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(
        String(20), default=ReportStatus.PENDING, server_default=ReportStatus.PENDING.value
    )
    file_key: Mapped[str | None] = mapped_column(String(255))
    # 오류 코드(14절)
    fail_reason: Mapped[str | None] = mapped_column(String(50))
    # 생성 시간. KPI-29 측정용
    generation_ms: Mapped[int | None] = mapped_column(Integer)
    model_version: Mapped[str | None] = mapped_column(String(50))
    template_version: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # 워커는 PENDING 보고서를 updated_at, id 순으로 꺼낸다(12.4). onupdate가 이 값을 바꾼다.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    session: Mapped[MeasureSession] = relationship(back_populates="reports")
