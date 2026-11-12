"""기관(병원·재활 센터). 크림오프 자체 기관도 한 행이다(계약 종료일 NULL). 명세 12.2 institution."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Institution(Base):
    __tablename__ = "institution"
    __table_args__ = (UniqueConstraint("code", name="uq_institution_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # 관리 화면 표시용 식별 코드. v1.12부터 로그인에 쓰지 않는다
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(100))
    # 계약 마지막 날(당일 포함). NULL = 기한 없음(11.6). 이 날이 지나면 그 기관 CLIENT는 GUEST로 계산된다
    contract_ends_at: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
