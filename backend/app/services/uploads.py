"""영상 업로드 검사·저장(13.1, 15.6, BE-05). 검사 순서는 13.1 표 그대로이고, 처음 걸린 하나만 오류로 낸다.

흐름: 회차 잠금·상태 확인 → 임시 폴더에 저장 → 크기·확장자·ffprobe·코덱·방향·길이 검사 → 경고 판단
→ 저장소로 옮김(키를 db.info["created_files"]에 기록) → 촬영 행 UPLOADED. 분석 요청은 워커가 가져간다(작업 단위 6).
검사에 걸리면 임시 파일을 지우고 DB에는 아무것도 남기지 않는다. 저장 뒤 commit이 실패하면 get_db가 파일을 지운다(12.4).
"""

from __future__ import annotations

import shutil
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode, NoticeCode
from app.models import Shot
from app.models.enums import SessionStatus
from app.services.sessions import get_session
from app.storage.base import get_storage
from app.storage.keys import ORIGINAL_EXTENSIONS, original_key
from app.video.probe import VideoInfo, VideoProbeError, probe

ALLOWED_CODECS = ("h264", "hevc")
# 최저 사양(13.1 8번): 640×360, 30fps(29.5 이상), 4 Mbps(4,000 kbps)
MIN_WIDTH = 640
MIN_HEIGHT = 360
MIN_FPS = Decimal("29.5")
MIN_BITRATE_KBPS = 4000
ASPECT_16_9 = Decimal(16) / Decimal(9)
ASPECT_TOLERANCE = Decimal("0.02")
MB = 1024 * 1024  # 13.1 값 해석: MB는 1,048,576바이트


def _extension(filename: str | None) -> str | None:
    """허용 확장자(mp4·mov, 대소문자 무시)면 소문자로, 아니면 None."""
    if not filename or "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[1].lower()
    return ext if ext in ORIGINAL_EXTENSIONS else None


def _plain_number(value: float) -> int | float:
    """문구용: 1.0은 1로, 4.5는 4.5로."""
    return int(value) if float(value).is_integer() else value


def save_to_tmp(upload: UploadFile) -> Path:
    """python-multipart가 시스템 임시 폴더에 받은 파일을 UPLOAD_TMP_DIR로 옮긴다(13.1). 이름은 무작위다."""
    tmp_dir = Path(get_settings().UPLOAD_TMP_DIR)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp = tmp_dir / f"upload-{uuid.uuid4().hex}.bin"
    upload.file.seek(0)
    with tmp.open("wb") as out:
        shutil.copyfileobj(upload.file, out, MB)
    return tmp


def check_video(tmp: Path, filename: str | None) -> tuple[VideoInfo, str, list[str]]:
    """13.1의 2~9번 검사. 걸리면 AppError. 통과하면 (영상 정보, 확장자, 경고 코드 목록)."""
    settings = get_settings()
    if tmp.stat().st_size > settings.UPLOAD_MAX_MB * MB:
        raise AppError(ErrorCode.VIDEO_TOO_LARGE, {"max_mb": settings.UPLOAD_MAX_MB})
    ext = _extension(filename)
    if ext is None:
        raise AppError(ErrorCode.VIDEO_FORMAT)
    try:
        info = probe(tmp, settings.FFPROBE_PATH)
    except VideoProbeError:
        raise AppError(ErrorCode.VIDEO_UNREADABLE) from None
    if info.codec not in ALLOWED_CODECS:
        raise AppError(ErrorCode.VIDEO_CODEC)
    if info.width <= info.height:
        raise AppError(ErrorCode.VIDEO_PORTRAIT)
    min_sec, max_sec = Decimal(str(settings.VIDEO_MIN_SEC)), Decimal(str(settings.VIDEO_MAX_SEC))
    if not (min_sec <= info.duration_sec <= max_sec):
        raise AppError(
            ErrorCode.VIDEO_DURATION,
            {"min_sec": _plain_number(settings.VIDEO_MIN_SEC), "max_sec": _plain_number(settings.VIDEO_MAX_SEC)},
        )

    warnings: list[str] = []
    below_spec = (
        info.width < MIN_WIDTH or info.height < MIN_HEIGHT or info.fps < MIN_FPS or info.bitrate_kbps < MIN_BITRATE_KBPS
    )
    if below_spec:
        warnings.append(NoticeCode.BELOW_MIN_SPEC.value)
    if abs(Decimal(info.width) / Decimal(info.height) / ASPECT_16_9 - 1) > ASPECT_TOLERANCE:
        warnings.append(NoticeCode.ASPECT_NOT_16_9.value)
    return info, ext, warnings


def upload_shot(
    db: Session, *, institution_id: uuid.UUID, session_id: uuid.UUID, upload: UploadFile
) -> tuple[Shot, list[str]]:
    """POST /sessions/{id}/shots. 회차 행을 잠근 뒤(12.4) 검사·저장하고 촬영 행을 UPLOADED로 만든다."""
    session = get_session(db, institution_id, session_id, for_update=True)
    if session.status != SessionStatus.MEASURING:
        raise AppError(ErrorCode.SESSION_CLOSED)

    tmp = save_to_tmp(upload)
    try:
        info, ext, warnings = check_video(tmp, upload.filename)
        shot_id = uuid.uuid4()
        key = original_key(institution_id, session.dog_id, session.id, shot_id, ext)
        get_storage().put_file(tmp, key)  # 임시 파일을 저장소로 옮긴다
    finally:
        tmp.unlink(missing_ok=True)  # 검사에 걸렸거나 옮기다 실패하면 임시 파일을 지운다
    db.info.setdefault("created_files", []).append(key)

    last_seq = db.scalar(select(func.max(Shot.seq_no)).where(Shot.session_id == session.id)) or 0
    shot = Shot(
        id=shot_id,
        session_id=session.id,
        seq_no=last_seq + 1,
        original_key=key,
        width=info.width,
        height=info.height,
        fps=info.fps,
        duration_sec=info.duration_sec,
        bitrate_kbps=info.bitrate_kbps,
        codec=info.codec,
        below_min_spec=NoticeCode.BELOW_MIN_SPEC.value in warnings,
        uploaded_at=datetime.now(UTC),
    )
    db.add(shot)
    db.flush()
    db.refresh(shot)
    return shot, warnings
