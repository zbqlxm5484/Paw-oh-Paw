"""메모·진료 기록의 수정 이력: 고칠 때마다 고치기 전 내용 한 줄. 명세 12.2 dog_note_revision, 12.5 차트 자료."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import NoteCategory, check_in

if TYPE_CHECKING:
    from app.models.staff import Staff


class DogNoteRevision(Base):
    __tablename__ = "dog_note_revision"
    __table_args__ = (
        check_in("category", NoteCategory, name="ck_dog_note_revision_category"),
        Index("ix_dog_note_revision_note", "note_id", "revised_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    note_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dog_note.id", name="fk_dog_note_revision_note"))
    # 고치기 전 내용
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(20))
    important: Mapped[bool] = mapped_column(Boolean)
    # 그 내용을 쓴 담당자
    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id", name="fk_dog_note_revision_staff"))
    # 그 내용이 바뀐 시각
    revised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    staff: Mapped[Staff] = relationship()
