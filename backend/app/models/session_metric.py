"""회차 수치. 한 행에 수치 하나. 명세 12.2 session_metric, 코드는 12.3."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, SmallInteger, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import GaitType, Limb, check_in

if TYPE_CHECKING:
    from app.models.measure_session import MeasureSession


class SessionMetric(Base):
    __tablename__ = "session_metric"
    __table_args__ = (
        UniqueConstraint("session_id", "gait_type", "limb", "metric_code", name="uq_metric"),
        check_in("gait_type", GaitType, name="ck_metric_gait_type"),
        check_in("limb", Limb, name="ck_metric_limb"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("measure_session.id", name="fk_metric_session"))
    gait_type: Mapped[str] = mapped_column(String(20))
    # NONE은 몸 전체 수치
    limb: Mapped[str] = mapped_column(String(20))
    # 12.3 표
    metric_code: Mapped[str] = mapped_column(String(50))
    # 측정 불가면 NULL. 0을 넣지 않는다(12.5).
    value: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    unit: Mapped[str] = mapped_column(String(20))
    measurable: Mapped[bool] = mapped_column(Boolean)
    # 측정 불가 사유 코드(14절)
    unmeasurable_reason: Mapped[str | None] = mapped_column(String(50))
    # 계산에 쓴 유효 통과 수
    n_passes: Mapped[int] = mapped_column(SmallInteger)

    session: Mapped[MeasureSession] = relationship(back_populates="metrics")
