"""반려견. 보호자 이름·연락처는 받지 않는다. 명세 12.2 dog."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import FocusLimb, Sex, SizeClass, check_in
from app.models.institution import Institution

if TYPE_CHECKING:
    from app.models.measure_session import MeasureSession


class Dog(Base):
    __tablename__ = "dog"
    __table_args__ = (
        check_in("size_class", SizeClass, name="ck_dog_size_class"),
        check_in("sex", Sex, name="ck_dog_sex"),
        check_in("focus_limb", FocusLimb, name="ck_dog_focus_limb"),
        Index("ix_dog_institution_name", "institution_id", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institution.id", name="fk_dog_institution"))
    name: Mapped[str] = mapped_column(String(50))
    breed: Mapped[str] = mapped_column(String(50))
    # 등록할 때 체중
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    # 견종으로 분류, 견종표에 없으면 체중으로(12.5)
    size_class: Mapped[str] = mapped_column(String(20))
    # 담당자가 직접 고쳤으면 TRUE
    size_class_manual: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    birth_year: Mapped[int | None] = mapped_column(SmallInteger)
    sex: Mapped[str | None] = mapped_column(String(20))
    # 재활 시작일
    rehab_start_date: Mapped[date | None] = mapped_column(Date)
    # 관심 다리: 왼앞·오른앞·왼뒤·오른뒤
    focus_limb: Mapped[str | None] = mapped_column(String(20))
    # 기준 회차. dog ↔ measure_session이 서로를 가리키므로 이 외래키는 measure_session을 만든 뒤에 붙인다(use_alter).
    baseline_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("measure_session.id", name="fk_dog_baseline", use_alter=True)
    )
    # 내부 메모. 보고서에 넣지 않는다
    memo: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    institution: Mapped[Institution] = relationship()
    # 외래키가 두 갈래(dog_id, baseline_session_id)라 어느 쪽인지 적는다.
    sessions: Mapped[list[MeasureSession]] = relationship(back_populates="dog", foreign_keys="MeasureSession.dog_id")
    # post_update: 회차를 만든 뒤에 기준 회차를 붙여, 서로를 가리키는 순환을 끊는다.
    baseline_session: Mapped[MeasureSession | None] = relationship(foreign_keys=[baseline_session_id], post_update=True)
