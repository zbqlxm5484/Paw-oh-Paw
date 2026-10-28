"""촬영 API(15.6): 상세, 다시 분석, 삭제. 결과 영상 재생(서명 URL 검증)과 관절 각도는 다음 작업에서 더한다."""

import uuid

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentStaff, DbSession
from app.schemas.shots import ShotDetailOut, ShotOut
from app.services import shots as shot_service

router = APIRouter(prefix="/shots", tags=["회차 측정"])


@router.get("/{shot_id}", response_model=ShotDetailOut)
def get_shot(shot_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> ShotDetailOut:
    return shot_service.shot_detail(db, staff.institution_id, shot_id)


@router.post("/{shot_id}/retry", response_model=ShotOut)
def retry_shot(shot_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> ShotOut:
    """실패한 촬영을 다시 대기열에 넣는다(BE-10). 응답의 status는 UPLOADED다."""
    shot = shot_service.retry_shot(db, staff.institution_id, shot_id)
    return shot_service.to_shot_out(shot)


@router.delete("/{shot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shot(shot_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> Response:
    shot_service.delete_shot(db, staff.institution_id, shot_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
