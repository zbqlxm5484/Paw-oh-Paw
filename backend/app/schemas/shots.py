"""촬영·통과 응답 모델(15.3 ShotOut, PassOut)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.schemas.common import ReasonOut, UtcDateTime


class PassOut(BaseModel):
    """통과 하나. camera_side는 카메라 쪽에 보인 몸의 방향이다."""

    pass_no: int
    camera_side: str
    gait_type: str
    is_valid: bool
    exclude_reason: ReasonOut | None
    start_frame: int
    end_frame: int


class ShotOut(BaseModel):
    """촬영 1건. passes는 status가 DONE이 되기 전에는 빈 배열이고 pass_no 오름차순이다."""

    id: uuid.UUID
    seq_no: int
    status: str
    fail_reason: ReasonOut | None
    validity: str | None
    validity_reason: ReasonOut | None
    video_status: str
    below_min_spec: bool
    passes: list[PassOut]
    uploaded_at: UtcDateTime
    analyzed_at: UtcDateTime | None


class ShotUploadOut(ShotOut):
    """POST /sessions/{id}/shots 응답(15.6): ShotOut + warnings(14.4 BELOW_MIN_SPEC, ASPECT_NOT_16_9)."""

    warnings: list[ReasonOut]
