"""담당자 계정. 회원가입 없이 scripts/seed.py로 만든다. 명세 12.2 staff."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import StaffRole, check_in
from app.models.institution import Institution


class Staff(Base):
    __tablename__ = "staff"
    __table_args__ = (
        UniqueConstraint("institution_id", "login_id", name="uq_staff_login"),
        check_in("role", StaffRole, name="ck_staff_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institution.id", name="fk_staff_institution"))
    login_id: Mapped[str] = mapped_column(String(50))
    # bcrypt 해시
    password_hash: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(20), default=StaffRole.STAFF, server_default=StaffRole.STAFF.value)
    # FALSE면 로그인 불가
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    institution: Mapped[Institution] = relationship()
