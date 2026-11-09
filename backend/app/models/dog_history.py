"""진단 이력: 진단·수술·재활 한 줄씩. 고치고 지울 수 있다(v1.41). 명세 12.2 dog_history, 12.5 차트 자료."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import HistoryKind, HistorySite, check_in

if TYPE_CHECKING:
    from app.models.staff import Staff


class DogHistory(Base):
    __tablename__ = "dog_history"
    __table_args__ = (
        check_in("kind", HistoryKind, name="ck_dog_history_kind"),
        check_in("site", HistorySite, name="ck_dog_history_site"),
        Index("ix_dog_history_dog_date", "dog_id", "occurred_on"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dog_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dog.id", name="fk_dog_history_dog"))
    # 진단·수술한 날, 재활을 시작하거나 끝낸 날
    occurred_on: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(20))
    # 예: 앞십자인대 파열, TPLO. 로그에 남기지 않는다(11.8)
    title: Mapped[str] = mapped_column(String(100))
    # 부위: 네 다리 또는 척추(SP)
    site: Mapped[str | None] = mapped_column(String(20))
    # 진단·집도 수의사(자유 입력)
    clinician: Mapped[str | None] = mapped_column(String(50))
    # 적은 담당자
    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id", name="fk_dog_history_staff"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    staff: Mapped[Staff] = relationship()
