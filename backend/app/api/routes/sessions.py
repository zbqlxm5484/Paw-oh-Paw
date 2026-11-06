"""회차 API(15.6, 15.7): 시작, 상태·진행·촬영 목록, 측정 취소, 영상 업로드, 측정 종료, 회차 결과."""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Response, UploadFile, status

from app.api.deps import AnalysisClientDep, CurrentStaff, DbSession
from app.schemas.common import reason_out
from app.schemas.sessions import SessionCreate, SessionDetailOut, SessionOut, SessionResultOut
from app.schemas.shots import ShotUploadOut
from app.services import session_results as result_service
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
def cancel_session(session_id: uuid.UUID, staff: CurrentStaff, db: DbSession, analysis: AnalysisClientDep) -> Response:
    session_service.cancel_session(db, staff.institution_id, session_id, analysis)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/{session_id}/complete", response_model=SessionOut)
def complete_session(session_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> SessionOut:
    """측정 종료(BE-13). 마지막 촬영의 분석을 기다리지 않고 바로 답한다."""
    session = session_service.complete_session(db, staff.institution_id, session_id)
    return session_service.to_session_out(session)


@router.get("/sessions/{session_id}/result", response_model=SessionResultOut)
def get_session_result(session_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> SessionResultOut:
    """회차 수치와 다리 비교 요약(BE-14·21)."""
    return result_service.session_result(db, staff.institution_id, session_id)


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
