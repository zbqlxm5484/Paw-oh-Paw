"""반려견. 보호자 이름·연락처는 병원이 환자를 찾는 데만 쓰고 보고서·로그에 넣지 않는다. 명세 12.2 dog."""

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
    Integer,
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
from app.models.enums import DogStage, FocusLimb, Sex, SizeClass, check_in
from app.models.institution import Institution

if TYPE_CHECKING:
    from app.models.measure_session import MeasureSession


def _next_version(current: int | None) -> int:
    """낙관적 잠금 번호(12.5): 등록 때 0, 수정마다 1 는다. SQLAlchemy 기본 생성기는 1부터 시작해서 따로 둔다."""
    return 0 if current is None else current + 1


class Dog(Base):
    __tablename__ = "dog"
    __table_args__ = (
        check_in("size_class", SizeClass, name="ck_dog_size_class"),
        check_in("sex", Sex, name="ck_dog_sex"),
        check_in("focus_limb", FocusLimb, name="ck_dog_focus_limb"),
        check_in("stage", DogStage, name="ck_dog_stage"),
        Index("ix_dog_institution_name", "institution_id", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institution.id", name="fk_dog_institution"))
    name: Mapped[str] = mapped_column(String(50))
    breed: Mapped[str] = mapped_column(String(50))
    # 등록할 때 체중
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    # 등록 체중으로 분류(12.5). 담당자가 직접 고치면 size_class_manual이 TRUE
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
    # 동물번호(병원 차트 번호). 같은 기관에 같은 번호가 있어도 받는다(13.2)
    chart_no: Mapped[str | None] = mapped_column(String(30))
    owner_name: Mapped[str | None] = mapped_column(String(50))
    # 보호자 연락처. 목록 응답에는 뒤 4자리만 준다(15.3)
    owner_phone: Mapped[str | None] = mapped_column(String(20))
    # 단계: 수술 전·재활 중·종결(12.5 차트 자료)
    stage: Mapped[str] = mapped_column(String(20), default=DogStage.REHAB, server_default=DogStage.REHAB.value)
    # 단계가 바뀐 날(한국 날짜). 바뀐 적이 없으면 NULL. 서버만 적는다
    stage_changed_on: Mapped[date | None] = mapped_column(Date)
    # 휴지통에 넣은 시각(12.5). NULL이면 휴지통에 없다. 30일이 지나면 워커가 영구 삭제한다
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 낙관적 잠금(12.5). 수정할 때마다 1 는다. JPA @Version과 같다
    version: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ORM이 UPDATE에 WHERE version = :old를 붙이고, 맞는 행이 없으면 StaleDataError를 낸다.
    # services.dogs가 그것을 409 DOG_MODIFIED로 바꾼다
    __mapper_args__ = {"version_id_col": version, "version_id_generator": _next_version}

    institution: Mapped[Institution] = relationship()
    # 외래키가 두 갈래(dog_id, baseline_session_id)라 어느 쪽인지 적는다.
    sessions: Mapped[list[MeasureSession]] = relationship(back_populates="dog", foreign_keys="MeasureSession.dog_id")
    # post_update: 회차를 만든 뒤에 기준 회차를 붙여, 서로를 가리키는 순환을 끊는다.
    baseline_session: Mapped[MeasureSession | None] = relationship(foreign_keys=[baseline_session_id], post_update=True)
