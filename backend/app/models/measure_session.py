"""회차: 한 번 방문해 잰 통과의 묶음. 보고서 1부의 단위. 명세 12.2 measure_session.

DB 세션(SQLAlchemy Session)과 헷갈리지 않게 테이블은 measure_session, 클래스는 MeasureSession이다(12.5).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import SessionStatus, SizeClass, check_in

if TYPE_CHECKING:
    from app.models.dog import Dog
    from app.models.report import Report
    from app.models.session_metric import SessionMetric
    from app.models.shot import Shot
    from app.models.staff import Staff


class MeasureSession(Base):
    __tablename__ = "measure_session"
    __table_args__ = (
        check_in("status", SessionStatus, name="ck_session_status"),
        check_in("size_class", SizeClass, name="ck_session_size_class"),
        Index("ix_session_dog_date", "dog_id", "measured_on"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dog_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dog.id", name="fk_session_dog"))
    # 측정한 담당자
    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id", name="fk_session_staff"))
    measured_on: Mapped[date] = mapped_column(Date)
    # 측정한 날 체중
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    # 회차 시점 체급(12.5): 시작할 때 그날 체중(없으면 등록 체중)으로 정하고, 반려견 체급이 바뀌어도 그대로다
    size_class: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(
        String(20), default=SessionStatus.MEASURING, server_default=SessionStatus.MEASURING.value
    )
    # 오류 코드(14절)
    fail_reason: Mapped[str | None] = mapped_column(String(50))
    model_name: Mapped[str | None] = mapped_column(String(50))
    # 회차 수치를 만든 분석 모델 버전
    model_version: Mapped[str | None] = mapped_column(String(50))
    # 측정 종료를 누른 시각
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 회차 집계가 끝난 시각
    aggregated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    dog: Mapped[Dog] = relationship(back_populates="sessions", foreign_keys=[dog_id])
    staff: Mapped[Staff] = relationship()
    shots: Mapped[list[Shot]] = relationship(back_populates="session", order_by="Shot.seq_no")
    metrics: Mapped[list[SessionMetric]] = relationship(back_populates="session")
    reports: Mapped[list[Report]] = relationship(back_populates="session")
