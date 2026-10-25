"""회차 API(15.6): 시작, 상태·진행·촬영 목록, 측정 취소. 측정 종료·업로드는 다음 작업 단위에서 더한다."""

import uuid

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentStaff, DbSession
from app.schemas.sessions import SessionCreate, SessionDetailOut, SessionOut
from app.services import sessions as session_service

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
