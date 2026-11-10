"""반려견 사진: 수술 전·후 사진, 방사선 사진, 그 밖의 사진. 파일은 얼굴을 가린 것만 저장한다.
명세 12.2 dog_image, 12.5 사진.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, SmallInteger, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import ImageKind, check_in

if TYPE_CHECKING:
    from app.models.staff import Staff


class DogImage(Base):
    __tablename__ = "dog_image"
    __table_args__ = (
        check_in("kind", ImageKind, name="ck_dog_image_kind"),
        Index("ix_dog_image_dog_taken", "dog_id", "taken_on"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dog_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dog.id", name="fk_dog_image_dog"))
    # 찍은 날
    taken_on: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(20))
    # 짧은 설명. 로그에 남기지 않는다(11.8)
    caption: Mapped[str | None] = mapped_column(String(100))
    # 7절 키: {기관ID}/{반려견ID}/images/{사진ID}.{jpg|png}
    file_key: Mapped[str] = mapped_column(String(255))
    # 저장한 사진의 픽셀 크기
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    # 올릴 때 가린 얼굴 수(12.5 사진)
    masked_faces: Mapped[int] = mapped_column(SmallInteger, default=0, server_default=text("0"))
    # 올린 담당자
    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id", name="fk_dog_image_staff"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    staff: Mapped[Staff] = relationship()
