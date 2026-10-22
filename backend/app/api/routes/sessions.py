"""회차 API(15.6): 시작, 상태·진행·촬영 목록, 측정 취소, 영상 업로드. 측정 종료는 작업 단위 8에서 더한다."""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Response, UploadFile, status

from app.api.deps import CurrentStaff, DbSession
from app.schemas.common import reason_out
from app.schemas.sessions import SessionCreate, SessionDetailOut, SessionOut
from app.schemas.shots import ShotUploadOut
from app.services import sessions as session_service
from app.services import uploads as upload_service
from app.services.shots import to_shot_out

router = APIRouter(tags=["회차 측정"])


@router.post("/dogs/{dog_id}/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def start_session(dog_id: uuid.UUID, body: SessionCreate, staff: CurrentStaff, db: DbSession) -> SessionOut:
    session = session_service.start_session(
        db, institution_id=staff.institution_id, staff_id=staff.id, dog_id=dog_id, data=body
    )
    return session_service.to_session_out(session)


@router.get("/sessions/{session_id}", response_model=SessionDetailOut)
def get_session(session_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> SessionDetailOut:
    return session_service.session_detail(db, staff.institution_id, session_id)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_session(session_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> Response:
    session_service.cancel_session(db, staff.institution_id, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/{session_id}/shots", response_model=ShotUploadOut, status_code=status.HTTP_201_CREATED)
def upload_shot(
    session_id: uuid.UUID, staff: CurrentStaff, db: DbSession, file: Annotated[UploadFile, File()]
) -> ShotUploadOut:
    """영상 업로드(BE-05). multipart 필드 file 하나. file이 없으면 FastAPI가 422 VALIDATION_ERROR를 낸다."""
    shot, warnings = upload_service.upload_shot(
        db, institution_id=staff.institution_id, session_id=session_id, upload=file
    )
    notices = [reason for reason in (reason_out(code) for code in warnings) if reason is not None]
    return ShotUploadOut(**to_shot_out(shot).model_dump(), warnings=notices)
