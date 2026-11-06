"""디바이스 코드. 크림오프가 기관에 발급하고 가입 때만 쓴다. 명세 12.2 device_code, 11.6, 13.5."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.institution import Institution


class DeviceCode(Base):
    __tablename__ = "device_code"
    __table_args__ = (
        UniqueConstraint("code", name="uq_device_code"),
        # 기관마다 쓸 수 있는(회수하지 않은) 코드는 하나다(12.5). 회수한 코드는 기록으로 여러 개 남는다
        Index("uq_device_code_active", "institution_id", unique=True, postgresql_where=text("revoked_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institution.id", name="fk_device_code_institution"))
    # 20자, 하이픈 없이 저장(13.5). 화면에는 XXXXX-XXXXX-XXXXX-XXXXX로 보여 준다
    code: Mapped[str] = mapped_column(String(32))
    # 회수 시각. NULL이면 쓸 수 있다. 지우지 않고 회수만 한다(12.5 삭제 순서)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 운영 메모(예: "2호기")
    note: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    institution: Mapped[Institution] = relationship()
