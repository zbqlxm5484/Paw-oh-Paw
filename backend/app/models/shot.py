"""촬영 1건 = 업로드한 영상 1개. 명세 12.2 shot."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import ShotStatus, Validity, VideoStatus, check_in

if TYPE_CHECKING:
    from app.models.measure_session import MeasureSession
    from app.models.walk_pass import WalkPass


class Shot(Base):
    __tablename__ = "shot"
    __table_args__ = (
        UniqueConstraint("session_id", "seq_no", name="uq_shot_seq"),
        check_in("status", ShotStatus, name="ck_shot_status"),
        check_in("validity", Validity, name="ck_shot_validity"),
        check_in("video_status", VideoStatus, name="ck_shot_video_status"),
        Index("ix_shot_status", "status"),
        Index("ix_shot_video", "video_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("measure_session.id", name="fk_shot_session"))
    # 회차 안 순번, 1부터
    seq_no: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(
        String(20), default=ShotStatus.UPLOADED, server_default=ShotStatus.UPLOADED.value
    )
    # 오류 코드(14절)
    fail_reason: Mapped[str | None] = mapped_column(String(50))
    # 분석 API 제출 시도 횟수
    attempt_count: Mapped[int] = mapped_column(SmallInteger, default=0, server_default=text("0"))
    # 분석 API가 준 작업 ID
    job_id: Mapped[str | None] = mapped_column(String(100))
    # 촬영 판정. DONE일 때만 값이 있다
    validity: Mapped[str | None] = mapped_column(String(20))
    # 무효·일부 유효 사유 코드(14절)
    validity_reason: Mapped[str | None] = mapped_column(String(50))
    # 결과 영상 상태
    video_status: Mapped[str] = mapped_column(
        String(20), default=VideoStatus.PENDING, server_default=VideoStatus.PENDING.value
    )
    # 원본 영상 파일 키
    original_key: Mapped[str] = mapped_column(String(255))
    # 결과 영상(골격 + 얼굴 가림) 파일 키
    result_key: Mapped[str | None] = mapped_column(String(255))
    # 분석 결과 JSON 원본 파일 키
    analysis_key: Mapped[str | None] = mapped_column(String(255))
    width: Mapped[int] = mapped_column(SmallInteger)
    height: Mapped[int] = mapped_column(SmallInteger)
    fps: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    duration_sec: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    bitrate_kbps: Mapped[int] = mapped_column(Integer)
    # h264 또는 hevc
    codec: Mapped[str] = mapped_column(String(20))
    # 최저 사양(640x360, 30fps, 4 Mbps) 미만
    below_min_spec: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    model_name: Mapped[str | None] = mapped_column(String(50))
    model_version: Mapped[str | None] = mapped_column(String(50))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    video_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    session: Mapped[MeasureSession] = relationship(back_populates="shots")
    passes: Mapped[list[WalkPass]] = relationship(back_populates="shot", order_by="WalkPass.pass_no")
