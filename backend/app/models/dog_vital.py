"""바이탈: 반려견마다 하루 한 줄(체중·체온·심박·혈압). 잰 값만 적는다(v1.41). 명세 12.2 dog_vital, 12.5 차트 자료."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.staff import Staff


class DogVital(Base):
    __tablename__ = "dog_vital"
    __table_args__ = (
        UniqueConstraint("dog_id", "measured_on", name="uq_dog_vital_day"),
        # 값이 하나는 있어야 하고, 혈압은 수축기·이완기가 함께 있거나 함께 없다(12.5)
        CheckConstraint(
            "weight_kg IS NOT NULL OR temp_c IS NOT NULL OR heart_rate IS NOT NULL OR sbp IS NOT NULL",
            name="ck_dog_vital_any_value",
        ),
        CheckConstraint("(sbp IS NULL) = (dbp IS NULL)", name="ck_dog_vital_bp_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dog_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dog.id", name="fk_dog_vital_dog"))
    measured_on: Mapped[date] = mapped_column(Date)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    # 체온(℃)
    temp_c: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    # 심박(회/분)
    heart_rate: Mapped[int | None] = mapped_column(SmallInteger)
    # 수축기·이완기 혈압(mmHg)
    sbp: Mapped[int | None] = mapped_column(SmallInteger)
    dbp: Mapped[int | None] = mapped_column(SmallInteger)
    # 마지막으로 저장한 담당자
    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id", name="fk_dog_vital_staff"))
    # 회차를 시작하며 함께 보낸 값이면 그 회차. 회차를 취소하면 NULL로 돌린다(12.5 삭제 순서)
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("measure_session.id", name="fk_dog_vital_session"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    staff: Mapped[Staff] = relationship()
