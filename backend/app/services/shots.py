"""촬영 응답 만들기와 촬영 상세·다시 분석·삭제(13.3, 15.3, 15.6, BE-08·10·11). 업로드 검사·저장은 services/uploads.py.

촬영은 shot → measure_session → dog를 거쳐 기관으로 거른다(11.6). 없거나 다른 기관의 촬영이면 똑같이 404다(15.1).
상태를 바꾸는 다시 분석·삭제는 그 회차 행을 FOR UPDATE로 잠근 뒤 조건을 본다(12.4 잠금). 워커가 UPLOADED 촬영을
가져갈 때 같은 잠금을 잡으므로, 지우는 사이에 워커가 그 촬영을 보내거나 결과를 쓰는 일이 없다(13.3).
Spring에 빗대면 @Transactional 없이 flush까지만 하는 서비스이고, commit은 get_db가 한다(11.7).
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError, ErrorCode
from app.models import Dog, MeasureSession, Shot, WalkPass
from app.models.enums import SessionStatus, ShotStatus, VideoStatus
from app.schemas.common import reason_out
from app.schemas.shots import PassOut, ShotDetailOut, ShotOut
from app.storage.base import get_storage
from app.storage.keys import shot_prefix

# 결과 영상 재생 API의 경로(15.6). 서명은 이 경로로 만든다(11.6). 앞부분은 app/main.py의 API_PREFIX와 같다
VIDEO_API_PATH = "/api/v1/shots/{shot_id}/video"
# 분석 API에 맡겨 둔 상태. 이 상태의 촬영은 지울 수 없다(13.3)
IN_PROGRESS_STATUSES = (ShotStatus.SUBMITTED.value, ShotStatus.ANALYZING.value)


# ---- 응답 ----


def to_pass_out(walk_pass: WalkPass) -> PassOut:
    return PassOut(
        pass_no=walk_pass.pass_no,
        camera_side=walk_pass.camera_side,
        gait_type=walk_pass.gait_type,
        is_valid=walk_pass.is_valid,
        exclude_reason=reason_out(walk_pass.exclude_reason),
        start_frame=walk_pass.start_frame,
        end_frame=walk_pass.end_frame,
    )


def to_shot_out(shot: Shot) -> ShotOut:
    """passes는 DONE일 때만 채우고 pass_no 오름차순이다(15.3)."""
    passes = sorted(shot.passes, key=lambda p: p.pass_no) if shot.status == ShotStatus.DONE else []
    return ShotOut(
        id=shot.id,
        seq_no=shot.seq_no,
        status=shot.status,
        fail_reason=reason_out(shot.fail_reason),
        validity=shot.validity,
        validity_reason=reason_out(shot.validity_reason),
        video_status=shot.video_status,
        below_min_spec=shot.below_min_spec,
        passes=[to_pass_out(p) for p in passes],
        uploaded_at=shot.uploaded_at,
        analyzed_at=shot.analyzed_at,
    )


def to_shot_detail_out(shot: Shot) -> ShotDetailOut:
    """ShotOut + 영상 정보·모델·시각. 결과 영상 주소는 READY일 때만 서명 URL로 만든다(11.6, 15.3)."""
    video_url = url_expires_at = None
    if shot.video_status == VideoStatus.READY and shot.result_key:
        video_url, url_expires_at = get_storage().file_url(shot.result_key, VIDEO_API_PATH.format(shot_id=shot.id))
    return ShotDetailOut(
        **to_shot_out(shot).model_dump(),
        width=shot.width,
        height=shot.height,
        fps=float(shot.fps),
        duration_sec=float(shot.duration_sec),
        bitrate_kbps=shot.bitrate_kbps,
        codec=shot.codec,
        model_name=shot.model_name,
        model_version=shot.model_version,
        submitted_at=shot.submitted_at,
        video_ready_at=shot.video_ready_at,
        video_url=video_url,
        url_expires_at=url_expires_at,
    )


# ---- 조회 ----


def _shot_query(institution_id: uuid.UUID, shot_id: uuid.UUID):
    return (
        select(Shot)
        .join(MeasureSession, Shot.session_id == MeasureSession.id)
        .join(Dog, MeasureSession.dog_id == Dog.id)
        .where(Shot.id == shot_id, Dog.institution_id == institution_id)
    )


def get_shot(db: Session, institution_id: uuid.UUID, shot_id: uuid.UUID) -> Shot:
    """없거나 다른 기관의 촬영이면 똑같이 404 NOT_FOUND(15.1)."""
    shot = db.scalars(_shot_query(institution_id, shot_id)).one_or_none()
    if shot is None:
        raise AppError(ErrorCode.NOT_FOUND)
    return shot


def shot_detail(db: Session, institution_id: uuid.UUID, shot_id: uuid.UUID) -> ShotDetailOut:
    """GET /shots/{id}(BE-08·11). 통과 행은 selectinload로 한 번에 읽고, 다시 부를 때마다 DB에서 새로 채운다."""
    shot = db.scalars(
        _shot_query(institution_id, shot_id)
        .options(selectinload(Shot.passes))
        .execution_options(populate_existing=True)
    ).one_or_none()
    if shot is None:
        raise AppError(ErrorCode.NOT_FOUND)
    return to_shot_detail_out(shot)


# ---- 다시 분석·삭제 ----


def _lock_session(db: Session, institution_id: uuid.UUID, session_id: uuid.UUID) -> MeasureSession:
    """촬영이 속한 회차 행을 FOR UPDATE로 잠근다(12.4 잠금). joinedload 없이(11.7)."""
    session = db.scalars(
        select(MeasureSession)
        .join(Dog, MeasureSession.dog_id == Dog.id)
        .where(MeasureSession.id == session_id, Dog.institution_id == institution_id)
        .with_for_update(of=MeasureSession)
    ).one_or_none()
    if session is None:  # 촬영을 읽은 뒤 회차가 통째로 지워졌다
        raise AppError(ErrorCode.NOT_FOUND)
    return session


def retry_shot(db: Session, institution_id: uuid.UUID, shot_id: uuid.UUID) -> Shot:
    """POST /shots/{id}/retry(BE-10, 13.3): FAILED이고 회차가 MEASURING일 때만 UPLOADED로 되돌린다.

    fail_reason·job_id를 비우고 attempt_count를 0, video_status를 PENDING으로 돌리며 남은 통과 행을 지운다(15.6).
    uploaded_at은 그대로라 워커는 올린 순서대로 다시 가져간다(12.4 FAILED → UPLOADED).
    """
    shot = get_shot(db, institution_id, shot_id)
    session = _lock_session(db, institution_id, shot.session_id)
    db.refresh(shot)  # 잠근 뒤의 상태로 다시 본다
    if shot.status != ShotStatus.FAILED:
        raise AppError(ErrorCode.SHOT_NOT_FAILED)
    if session.status != SessionStatus.MEASURING:
        raise AppError(ErrorCode.SESSION_CLOSED)
    db.execute(delete(WalkPass).where(WalkPass.shot_id == shot.id))
    shot.status = ShotStatus.UPLOADED.value
    shot.fail_reason = None
    shot.job_id = None
    shot.attempt_count = 0
    shot.video_status = VideoStatus.PENDING.value
    db.flush()
    db.refresh(shot)
    return shot


def delete_shot(db: Session, institution_id: uuid.UUID, shot_id: uuid.UUID) -> None:
    """DELETE /shots/{id}(BE-10, 13.3): 회차가 MEASURING이고 촬영이 SUBMITTED·ANALYZING이 아닐 때만.

    12.5 순서: 파일(촬영 접두어 전체: 원본·분석 JSON·결과 영상) → walk_pass → shot. 남은 촬영의 seq_no는 그대로다(15.6).
    """
    shot = get_shot(db, institution_id, shot_id)
    session = _lock_session(db, institution_id, shot.session_id)
    db.refresh(shot)
    if session.status != SessionStatus.MEASURING:
        raise AppError(ErrorCode.SESSION_CLOSED)
    if shot.status in IN_PROGRESS_STATUSES:
        raise AppError(ErrorCode.SHOT_IN_PROGRESS)
    get_storage().delete_prefix(shot_prefix(institution_id, session.dog_id, session.id, shot.id))
    db.execute(delete(WalkPass).where(WalkPass.shot_id == shot.id))
    db.execute(delete(Shot).where(Shot.id == shot.id))
    db.expunge(shot)
