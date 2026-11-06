"""촬영 API(15.6): 상세, 다시 분석, 삭제, 결과 영상 재생(서명 URL), 통과별 관절 각도."""

import uuid

from fastapi import APIRouter, Response, status
from fastapi.responses import FileResponse

from app.api.deps import AnalysisClientDep, CurrentStaff, DbSession, check_file_link
from app.core.config import get_settings
from app.schemas.shots import ShotAnglesOut, ShotDetailOut, ShotOut
from app.services import shot_angles as angle_service
from app.services import shots as shot_service
from app.storage.base import get_storage

router = APIRouter(prefix="/shots", tags=["회차 측정"])


@router.get("/{shot_id}", response_model=ShotDetailOut)
def get_shot(shot_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> ShotDetailOut:
    return shot_service.shot_detail(db, staff.institution_id, shot_id)


@router.post("/{shot_id}/retry", response_model=ShotOut)
def retry_shot(shot_id: uuid.UUID, staff: CurrentStaff, db: DbSession, analysis: AnalysisClientDep) -> ShotOut:
    """FAILED 촬영을 다시 대기열에 넣는다(BE-10). status는 UPLOADED다. 실패했던 작업의 분석 API 사본을 먼저 지운다."""
    shot = shot_service.retry_shot(db, staff.institution_id, shot_id, analysis)
    return shot_service.to_shot_out(shot)


@router.delete("/{shot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shot(shot_id: uuid.UUID, staff: CurrentStaff, db: DbSession, analysis: AnalysisClientDep) -> Response:
    """촬영을 지운다(BE-10). 분석 API 사본 → 파일 → 행 순서다(12.5)."""
    shot_service.delete_shot(db, staff.institution_id, shot_id, analysis)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{shot_id}/angles", response_model=ShotAnglesOut)
def get_shot_angles(shot_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> ShotAnglesOut:
    """유효 통과의 프레임별 관절 각도(BE-14). 워커가 써 둔 angles.json을 읽는다. 없으면 passes가 빈 배열이다."""
    return angle_service.shot_angles(db, get_storage(), staff.institution_id, shot_id)


@router.get("/{shot_id}/video", response_class=FileResponse)
def get_shot_video(shot_id: uuid.UUID, db: DbSession, exp: str | None = None, sig: str | None = None) -> FileResponse:
    """결과 영상 재생(BE-12). 로그인 토큰 없이 서명(exp·sig)으로 연다.

    앞뒤로 넘기는 Range 요청은 Starlette FileResponse가 206으로 답한다(15.6).
    서명이 없거나 틀리거나 지났으면 403 FILE_LINK_EXPIRED(DB를 보기 전에 확인한다).
    촬영이 없거나 READY가 아니거나 저장소가 S3면 404 NOT_FOUND(15.6, 11.11).
    Cache-Control은 private이고 서명 URL의 유효 시간만큼만 둔다.
    """
    check_file_link(shot_service.VIDEO_API_PATH.format(shot_id=shot_id), exp, sig)
    path = shot_service.result_video_path(db, shot_id)
    cache_control = f"private, max-age={get_settings().FILE_URL_TTL_SEC}"
    return FileResponse(path, media_type="video/mp4", headers={"Cache-Control": cache_control})
