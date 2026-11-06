"""담당자 계정(크림오프 ADMIN·STAFF, 고객 CLIENT). 디바이스 코드 가입 또는 seed.py로 만든다. 명세 12.2 staff."""

import uuid
from datetime import datetime

from sqlalchemy import CHAR, Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.device_code import DeviceCode
from app.models.enums import StaffRole, check_in
from app.models.institution import Institution


class Staff(Base):
    __tablename__ = "staff"
    __table_args__ = (
        # 아이디는 모든 기관에서 유일하다(v1.12). 로그인에 기관 코드를 받지 않기 때문이다(11.6)
        UniqueConstraint("login_id", name="uq_staff_login"),
        check_in("role", StaffRole, name="ck_staff_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institution.id", name="fk_staff_institution"))
    login_id: Mapped[str] = mapped_column(String(50))
    # bcrypt 해시
    password_hash: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(50))
    # 저장 역할(11.6). GUEST는 저장하지 않고 AuthStaff.effective_role로 계산한다
    role: Mapped[str] = mapped_column(String(20), default=StaffRole.CLIENT, server_default=StaffRole.CLIENT.value)
    # FALSE면 로그인 불가
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    # 어느 디바이스 코드로 가입했는지. seed.py로 만든 계정은 NULL
    device_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("device_code.id", name="fk_staff_device_code"))
    # 가입 계정은 필수(13.5), seed 계정은 비울 수 있다. 소문자로 저장
    email: Mapped[str | None] = mapped_column(String(254))
    # 비밀번호 재설정 토큰의 SHA-256과 만료 시각(15.4). 쓰거나 만료되면 NULL
    password_reset_hash: Mapped[str | None] = mapped_column(CHAR(64))
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 가입 때 동의한 약관 버전과 시각(13.5). 동의 기록 없이 만든 계정(seed.py, 예전 가입)은 NULL
    terms_version: Mapped[str | None] = mapped_column(String(20))
    terms_agreed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 선택 항목(마케팅 정보 수신) 동의
    marketing_agreed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    # 스스로 탈퇴한 시각(15.4 DELETE /auth/me). 탈퇴하면 is_active도 FALSE다. 관리자가 다시 켜면 NULL로 돌린다
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 알림을 받을지(13.7). 설정값만 저장하고 서버가 알림을 보내지는 않는다
    notif_on: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    institution: Mapped[Institution] = relationship()
    device_code: Mapped[DeviceCode | None] = relationship()
