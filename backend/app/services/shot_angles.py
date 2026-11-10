"""통과별 프레임 관절 각도(BE-14, 명세 12.4 관절 각도 파일, 15.6 GET /shots/{shot_id}/angles).

프레임별 각도는 분석 결과 JSON이 아니라 분석 API의 관절점 파일에만 있다. 워커가 결과 영상을 맡기려고 관절점 파일을
받았을 때 build_angles로 통과별 각도만 뽑아 촬영 키의 angles.json에 써 두고, API는 그 파일을 읽기만 한다.
파일에는 그 분석의 job_id를 적어, 다시 분석한 뒤 앞 분석의 각도가 나가지 않게 한다.
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.models import Dog, MeasureSession, Shot
from app.models.enums import CameraSide, ShotStatus
from app.schemas.shots import ShotAnglesOut
from app.services.analysis_results import parse_result
from app.services.dogs import in_institution
from app.storage.base import StorageError, StorageService
from app.storage.keys import angles_key

logger = logging.getLogger(__name__)

# 응답의 관절 순서(15.6). 관절점 파일의 키는 여기에 카메라 쪽 접미사가 붙는다(shoulder_r)
JOINTS = ("shoulder", "elbow", "carpus", "hip", "stifle", "tarsus")
SIDE_SUFFIX = {CameraSide.RIGHT.value: "r", CameraSide.LEFT.value: "l"}
# 통과 하나의 프레임 수 상한. 60fps로 10분이다. 넘으면 결과가 잘못된 것으로 보고 만들지 않는다
MAX_PASS_FRAMES = 36_000


def _frame_no(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _angle(angles: dict[str, Any] | None, key: str) -> float | None:
    """그 프레임의 각도. 관절점을 못 찾았거나 숫자가 아니면 None이다(0을 넣지 않는다)."""
    value = angles.get(key) if angles else None
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return None
    return float(value)


def _window(raw: dict[str, Any], start_frame: int, end_frame: int) -> tuple[int, int]:
    """유효 구간: measure_start~measure_end. 없거나 통과 구간을 벗어나면 통과 구간 전체다."""
    start, end = _frame_no(raw.get("measure_start")), _frame_no(raw.get("measure_end"))
    if start is None or end is None or not start_frame <= start <= end <= end_frame:
        return start_frame, end_frame
    return start, end


def build_angles(result: Any, keypoints: Any, *, shot_id: uuid.UUID, job_id: str | None) -> dict[str, Any]:
    """분석 결과 JSON과 관절점 파일 → angles.json에 쓸 내용. 유효 통과의 유효 구간만 담는다.

    결과 JSON이 계약과 다르면 ResultFormatError, 통과가 터무니없이 길면 ValueError다.
    """
    parsed = parse_result(result, shot_id=shot_id)
    frames: dict[int, dict[str, Any]] = {}
    raw_frames = keypoints.get("frames") if isinstance(keypoints, dict) else None
    for item in raw_frames if isinstance(raw_frames, list) else []:
        if isinstance(item, dict) and _frame_no(item.get("frame")) is not None and isinstance(item.get("angles"), dict):
            frames[item["frame"]] = item["angles"]

    passes: list[dict[str, Any]] = []
    for row, raw in zip(parsed.passes, result["passes"], strict=True):
        if not row.is_valid:
            continue
        start, end = _window(raw, row.start_frame, row.end_frame)
        if end - start >= MAX_PASS_FRAMES:
            raise ValueError(f"pass {row.pass_no} spans {end - start + 1} frames")
        suffix = SIDE_SUFFIX[row.camera_side]
        passes.append(
            {
                "pass_no": row.pass_no,
                "camera_side": row.camera_side,
                "gait_type": row.gait_type,
                "start_frame": start,
                "angles": {
                    joint: [_angle(frames.get(frame), f"{joint}_{suffix}") for frame in range(start, end + 1)]
                    for joint in JOINTS
                },
            }
        )
    fps = keypoints.get("fps") if isinstance(keypoints, dict) else None
    return {"job_id": job_id, "fps": _angle({"fps": fps}, "fps"), "passes": passes}


def dump_angles(doc: dict[str, Any]) -> bytes:
    return json.dumps(doc, separators=(",", ":")).encode("utf-8")


def shot_angles(
    db: Session,
    storage: StorageService,
    institution_id: uuid.UUID,
    shot_id: uuid.UUID,
    *,
    print_session_id: uuid.UUID | None = None,
) -> ShotAnglesOut:
    """GET /shots/{id}/angles. 없거나 다른 기관·휴지통의 촬영이면 404, 줄 것이 없으면 passes가 빈 배열이다(15.6)."""
    row = db.execute(
        select(Shot, MeasureSession.dog_id)
        .join(MeasureSession, Shot.session_id == MeasureSession.id)
        .join(Dog, MeasureSession.dog_id == Dog.id)
        # 인쇄 토큰이면 휴지통에 든 반려견의 촬영도 읽는다(워커가 그런 보고서도 만든다, 12.5)
        .where(
            Shot.id == shot_id,
            in_institution(institution_id) if print_session_id is None else Dog.institution_id == institution_id,
        )
    ).one_or_none()
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND)
    shot, dog_id = row
    if print_session_id is not None and shot.session_id != print_session_id:
        raise AppError(ErrorCode.NOT_FOUND)  # 인쇄 토큰은 그 회차의 촬영만 연다(11.6)
    empty = ShotAnglesOut(shot_id=shot.id, fps=float(shot.fps), passes=[])
    if shot.status != ShotStatus.DONE or not shot.job_id:
        return empty
    try:
        doc = json.loads(storage.read_bytes(angles_key(institution_id, dog_id, shot.session_id, shot.id)))
    except (StorageError, OSError, ValueError):
        return empty  # 아직 없거나(결과 영상을 맡기기 전), 이 기능 전에 분석한 촬영이다
    if not isinstance(doc, dict) or doc.get("job_id") != shot.job_id:
        return empty  # 다시 분석하기 전의 파일이다. 새 파일이 쓰일 때까지 비워 둔다
    try:
        return ShotAnglesOut(shot_id=shot.id, fps=doc.get("fps") or float(shot.fps), passes=doc.get("passes"))
    except ValidationError:
        logger.error("angles file unreadable shot=%s", shot.id)
        return empty
