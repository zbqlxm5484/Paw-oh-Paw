"""촬영 응답 만들기와 촬영 상세·다시 분석·삭제(13.3, 15.3, 15.6, BE-08·10·11). 업로드 검사·저장은 services/uploads.py.

촬영은 shot → measure_session → dog를 거쳐 기관으로 거른다(11.6). 없거나 다른 기관의 촬영이면 똑같이 404다(15.1).
결과 영상 재생(result_video_path)만 예외로 촬영 ID로만 찾는다. 서명 URL은 기관 확인을 거친 조회 API만 만들고,
서명이 맞으면 기관 확인을 다시 하지 않기 때문이다(15.6).
상태를 바꾸는 다시 분석·삭제는 그 회차 행을 FOR UPDATE로 잠근 뒤 조건을 본다(12.4 잠금). 워커가 UPLOADED 촬영을
가져갈 때 같은 잠금을 잡으므로, 지우는 사이에 워커가 그 촬영을 보내거나 결과를 쓰는 일이 없다(13.3).
둘 다 분석 API에 남은 그 촬영의 사본(영상·결과·관절점)을 먼저 지운다(199 리뷰 조유진). job_id를 비우거나 행을
지우면 그 사본을 다시 찾을 수 없기 때문이다. 분석 API는 HTTP라 잠그기 전에 부르고(조건은 미리 한 번 본다), 잠근
뒤에는 조건을 다시 보고 그사이 작업이 바뀌었을 때만 한 번 더 부른다(services/analysis_copies.py).
Spring에 빗대면 @Transactional 없이 flush까지만 하는 서비스이고, commit은 get_db가 한다(11.7).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.clients.analysis import AnalysisClient
from app.core.errors import AppError, ErrorCode
from app.models import Dog, MeasureSession, Shot, WalkPass
from app.models.enums import SessionStatus, ShotStatus, VideoStatus
from app.schemas.common import reason_out
from app.schemas.shots import PassOut, ShotDetailOut, ShotOut
from app.services.analysis_copies import delete_shot_copies
from app.services.dogs import in_institution
from app.storage.base import get_storage
from app.storage.keys import shot_prefix
from app.storage.local import LocalStorage

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
        .where(Shot.id == shot_id, in_institution(institution_id))
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


def result_video_path(db: Session, shot_id: uuid.UUID) -> Path:
    """GET /shots/{id}/video(BE-12, 15.6)가 FileResponse에 넘길 결과 영상의 실제 경로. 서명 확인은 라우트가 먼저 한다.

    촬영이 없거나 video_status가 READY가 아니면 404 NOT_FOUND이고, READY인데 파일이 없어도 같다(열 것이 없다).
    저장소가 S3면 video_url이 S3 주소라 이 API는 쓰이지 않고, 불리면 404다(11.11). 경로는 LocalStorage.path로만 얻는다.
    """
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise AppError(ErrorCode.NOT_FOUND)
    shot = db.get(Shot, shot_id)
    if shot is None or shot.video_status != VideoStatus.READY or not shot.result_key:
        raise AppError(ErrorCode.NOT_FOUND)
    path = storage.path(shot.result_key)
    if not path.is_file():
        raise AppError(ErrorCode.NOT_FOUND)
    return path


# ---- 다시 분석·삭제 ----


def _lock_session(db: Session, institution_id: uuid.UUID, session_id: uuid.UUID) -> MeasureSession:
    """촬영이 속한 회차 행을 FOR UPDATE로 잠근다(12.4 잠금). joinedload 없이(11.7)."""
    session = db.scalars(
        select(MeasureSession)
        .join(Dog, MeasureSession.dog_id == Dog.id)
        .where(MeasureSession.id == session_id, in_institution(institution_id))
        .with_for_update(of=MeasureSession)
    ).one_or_none()
    if session is None:  # 촬영을 읽은 뒤 회차가 통째로 지워졌다
        raise AppError(ErrorCode.NOT_FOUND)
    return session


def _session_status(db: Session, session_id: uuid.UUID) -> str | None:
    """잠그지 않고 회차 상태만 읽는다(분석 API를 부르기 전 미리 보기용)."""
    return db.scalar(select(MeasureSession.status).where(MeasureSession.id == session_id))


def _require_retryable(shot_status: str, session_status: str | None) -> None:
    if session_status is None:
        raise AppError(ErrorCode.NOT_FOUND)
    if shot_status != ShotStatus.FAILED:
        raise AppError(ErrorCode.SHOT_NOT_FAILED)
    if session_status != SessionStatus.MEASURING:
        raise AppError(ErrorCode.SESSION_CLOSED)


def _require_deletable(shot_status: str, session_status: str | None) -> None:
    if session_status is None:
        raise AppError(ErrorCode.NOT_FOUND)
    if session_status != SessionStatus.MEASURING:
        raise AppError(ErrorCode.SESSION_CLOSED)
    if shot_status in IN_PROGRESS_STATUSES:
        raise AppError(ErrorCode.SHOT_IN_PROGRESS)


def retry_shot(db: Session, institution_id: uuid.UUID, shot_id: uuid.UUID, analysis: AnalysisClient | None) -> Shot:
    """POST /shots/{id}/retry(BE-10, 13.3): FAILED이고 회차가 MEASURING일 때만 UPLOADED로 되돌린다.

    fail_reason·job_id를 비우고 attempt_count를 0, video_status를 PENDING으로 돌리며 남은 통과 행을 지운다(15.6).
    uploaded_at은 그대로라 워커는 올린 순서대로 다시 가져간다(12.4 FAILED → UPLOADED).
    job_id를 비우기 전에 이 촬영으로 만든 작업의 분석 API 사본을 모두 지운다(팀 서비스가 작업 ID를 모르는 것도,
    services/analysis_copies.py). 못 지우면 503 ANALYSIS_UNAVAILABLE, 분석 API가 아직 이 촬영의 작업을 돌리고
    있으면 409 SHOT_IN_PROGRESS이고 촬영은 FAILED 그대로다.
    """
    shot = get_shot(db, institution_id, shot_id)
    # 잠그기 전에 미리 본다. 조건이 안 맞는 요청 때문에 사본을 지우지 않게
    _require_retryable(shot.status, _session_status(db, shot.session_id))
    first_job = shot.job_id
    delete_shot_copies(analysis, [(shot.id, first_job)])
    session = _lock_session(db, institution_id, shot.session_id)
    db.refresh(shot)  # 잠근 뒤의 상태로 다시 본다
    _require_retryable(shot.status, session.status)
    if shot.job_id and shot.job_id != first_job:  # 그사이 다시 제출됐다가 실패했다. 드물다
        delete_shot_copies(analysis, [(shot.id, shot.job_id)])
    db.execute(delete(WalkPass).where(WalkPass.shot_id == shot.id))
    shot.status = ShotStatus.UPLOADED.value
    shot.fail_reason = None
    shot.job_id = None
    shot.attempt_count = 0
    shot.video_status = VideoStatus.PENDING.value
    db.flush()
    db.refresh(shot)
    return shot


def delete_shot(db: Session, institution_id: uuid.UUID, shot_id: uuid.UUID, analysis: AnalysisClient | None) -> None:
    """DELETE /shots/{id}(BE-10, 13.3): 회차가 MEASURING이고 촬영이 SUBMITTED·ANALYZING이 아닐 때만.

    12.5 순서: 분석 API 사본 → 파일(촬영 접두어 전체: 원본·분석 JSON·결과 영상) → walk_pass → shot. 남은 촬영의
    seq_no는 그대로다(15.6). 분석 API 사본을 못 지우면 503 ANALYSIS_UNAVAILABLE이고 아무것도 지우지 않는다.
    """
    shot = get_shot(db, institution_id, shot_id)
    # 잠그기 전에 미리 본다. 조건이 안 맞는 요청 때문에 사본을 지우지 않게
    _require_deletable(shot.status, _session_status(db, shot.session_id))
    first_job = shot.job_id
    delete_shot_copies(analysis, [(shot.id, first_job)])
    session = _lock_session(db, institution_id, shot.session_id)
    db.refresh(shot)
    _require_deletable(shot.status, session.status)
    if shot.job_id and shot.job_id != first_job:  # 그사이 다시 제출됐다가 끝났다. 드물다
        delete_shot_copies(analysis, [(shot.id, shot.job_id)])
    get_storage().delete_prefix(shot_prefix(institution_id, session.dog_id, session.id, shot.id))
    db.execute(delete(WalkPass).where(WalkPass.shot_id == shot.id))
    db.execute(delete(Shot).where(Shot.id == shot.id))
    db.expunge(shot)
