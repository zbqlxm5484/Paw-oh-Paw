"""촬영·통과 응답 모델(15.3 ShotOut, PassOut, ShotDetailOut)."""

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


class AnglePassOut(BaseModel):
    """유효 통과 하나의 프레임별 관절 각도(15.6). angles의 i번째 값은 start_frame + i 프레임의 각도(°)다.

    관절점을 못 찾은 프레임은 null이다. 다리는 camera_side 쪽이다.
    """

    pass_no: int
    camera_side: str
    gait_type: str
    start_frame: int
    angles: dict[str, list[float | None]]


class ShotAnglesOut(BaseModel):
    """GET /shots/{id}/angles(15.6). 줄 것이 없으면 passes가 빈 배열이다."""

    shot_id: uuid.UUID
    fps: float
    passes: list[AnglePassOut]


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


class ShotDetailOut(ShotOut):
    """GET /shots/{id} 응답(15.3): ShotOut + 영상 정보·모델·시각·결과 영상 주소.

    fps·duration_sec는 DB의 NUMERIC을 JSON 숫자로 내보내려고 float다(15.1). video_url은 video_status가 READY일 때만
    서명 URL(11.6)이고, 아니면 url_expires_at과 함께 null이다. 원본 영상의 주소·키는 넣지 않는다(BE-12).
    """

    width: int
    height: int
    fps: float
    duration_sec: float
    bitrate_kbps: int
    codec: str
    model_name: str | None
    model_version: str | None
    submitted_at: UtcDateTime | None
    video_ready_at: UtcDateTime | None
    video_url: str | None
    url_expires_at: UtcDateTime | None
