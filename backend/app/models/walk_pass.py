"""통과: 반려견이 측정 구간을 한 번 지나간 것. 명세 12.2 walk_pass."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, SmallInteger, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import CameraSide, GaitType, check_in

if TYPE_CHECKING:
    from app.models.shot import Shot


class WalkPass(Base):
    __tablename__ = "walk_pass"
    __table_args__ = (
        UniqueConstraint("shot_id", "pass_no", name="uq_pass_no"),
        check_in("camera_side", CameraSide, name="ck_pass_camera_side"),
        check_in("gait_type", GaitType, name="ck_pass_gait_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    shot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shot.id", name="fk_pass_shot"))
    # 촬영 안 통과 순번, 1부터
    pass_no: Mapped[int] = mapped_column(SmallInteger)
    # 카메라 쪽에 보인 몸의 방향(반려견 기준)
    camera_side: Mapped[str] = mapped_column(String(20))
    # 평보·속보·측대보·기타
    gait_type: Mapped[str] = mapped_column(String(20))
    is_valid: Mapped[bool] = mapped_column(Boolean)
    # 제외 사유 코드(14절)
    exclude_reason: Mapped[str | None] = mapped_column(String(50))
    # 유효 구간 시작 프레임
    start_frame: Mapped[int] = mapped_column(Integer)
    # 유효 구간 끝 프레임
    end_frame: Mapped[int] = mapped_column(Integer)

    shot: Mapped[Shot] = relationship(back_populates="passes")
