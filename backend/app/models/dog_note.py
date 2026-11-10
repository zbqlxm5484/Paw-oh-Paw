"""메모·진료 기록. 분류만 다르고 모양은 같다. 고치면 이전 내용을 dog_note_revision에 남긴다. 한 건씩 지운다(v1.46).

명세 12.2 dog_note, 12.5 차트 자료. 본문은 보고서·로그에 넣지 않는다(11.8).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import NoteCategory, check_in

if TYPE_CHECKING:
    from app.models.staff import Staff


class DogNote(Base):
    __tablename__ = "dog_note"
    __table_args__ = (
        check_in("category", NoteCategory, name="ck_dog_note_category"),
        Index("ix_dog_note_dog_created", "dog_id", "created_at"),
        # 목록 순서(방문일 → 쓴 시각)와 그날 기록(v1.46)
        Index("ix_dog_note_dog_visited", "dog_id", "visited_on"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dog_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dog.id", name="fk_dog_note_dog"))
    # 회차에 단 기록이면 그 회차. 회차를 취소하면 NULL로 돌린다(12.5 삭제 순서)
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("measure_session.id", name="fk_dog_note_session"))
    # 메모 CAUTION·GUARDIAN·BOOKING·OTHER, 진료 기록 S·O·A·P
    category: Mapped[str] = mapped_column(String(20))
    body: Mapped[str] = mapped_column(Text)
    # 중요 표시
    important: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    # 방문일(v1.46). 그 기록이 어느 날 방문의 것인지. 쓴 뒤에는 바꾸지 않는다. 서비스가 늘 값을 넣는다. 서버 기본값
    # (오늘의 한국 날짜)은 이 칸을 모르는 앞 판 앱이 배포 중에 쓰는 줄을 위한 것이다(마이그레이션 0021)
    visited_on: Mapped[date] = mapped_column(Date, server_default=text("(now() AT TIME ZONE 'Asia/Seoul')::date"))
    # 지금 내용을 쓴 담당자(고치면 고친 사람). 처음 쓴 사람은 가장 오래된 수정 이력에 있다
    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id", name="fk_dog_note_staff"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    staff: Mapped[Staff] = relationship()
