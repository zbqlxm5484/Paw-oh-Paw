"""차트 자료 API(15.11, BE-28~30): 바이탈, 진단 이력, 메모·진료 기록. 요청 검사 → services → 응답만 한다(11.3)."""

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentStaff, DbSession
from app.schemas.chart import (
    DogHistoryCreate,
    DogHistoryListOut,
    DogHistoryOut,
    DogHistoryUpdate,
    NoteBatchCreate,
    NoteBatchOut,
    NoteCreate,
    NoteListOut,
    NoteOut,
    NoteRevisionListOut,
    NoteUpdate,
    VitalListOut,
    VitalOut,
    VitalPut,
)
from app.services import dog_history as history_service
from app.services import notes as note_service
from app.services import vitals as vital_service

router = APIRouter(tags=["차트 자료"])


@router.get("/dogs/{dog_id}/vitals", response_model=VitalListOut)
def list_vitals(dog_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> VitalListOut:
    return VitalListOut(items=vital_service.list_vitals(db, staff.institution_id, dog_id))


@router.put("/dogs/{dog_id}/vitals/{measured_on}", response_model=VitalOut)
def put_vital(dog_id: uuid.UUID, measured_on: date, body: VitalPut, staff: CurrentStaff, db: DbSession) -> VitalOut:
    """그날 바이탈을 만들거나 보낸 값만 바꾼다. 어느 쪽이든 200이다."""
    return vital_service.put_vital(
        db, institution_id=staff.institution_id, staff_id=staff.id, dog_id=dog_id, measured_on=measured_on, data=body
    )


@router.get("/dogs/{dog_id}/history", response_model=DogHistoryListOut)
def list_history(dog_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> DogHistoryListOut:
    """진단 이력(진단·수술·재활). 측정 이력은 GET /dogs/{dog_id}/sessions다."""
    return DogHistoryListOut(items=history_service.list_history(db, staff.institution_id, dog_id))


@router.post("/dogs/{dog_id}/history", response_model=DogHistoryOut, status_code=status.HTTP_201_CREATED)
def add_history(dog_id: uuid.UUID, body: DogHistoryCreate, staff: CurrentStaff, db: DbSession) -> DogHistoryOut:
    return history_service.add_history(
        db, institution_id=staff.institution_id, staff_id=staff.id, dog_id=dog_id, data=body
    )


@router.patch("/dogs/{dog_id}/history/{history_id}", response_model=DogHistoryOut)
def update_history(
    dog_id: uuid.UUID, history_id: uuid.UUID, body: DogHistoryUpdate, staff: CurrentStaff, db: DbSession
) -> DogHistoryOut:
    return history_service.update_history(
        db, institution_id=staff.institution_id, staff_id=staff.id, dog_id=dog_id, history_id=history_id, data=body
    )


@router.delete("/dogs/{dog_id}/history/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history(dog_id: uuid.UUID, history_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> Response:
    history_service.delete_history(
        db, institution_id=staff.institution_id, staff_id=staff.id, dog_id=dog_id, history_id=history_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/dogs/{dog_id}/notes", response_model=NoteListOut)
def list_notes(
    dog_id: uuid.UUID,
    staff: CurrentStaff,
    db: DbSession,
    kind: Literal["memo", "chart"] | None = None,
    session_id: uuid.UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> NoteListOut:
    """메모(kind=memo)와 진료 기록(kind=chart). 빼면 둘 다 준다. 쓴 시각 내림차순."""
    items, total = note_service.list_notes(
        db, staff.institution_id, dog_id, kind=kind, session_id=session_id, page=page, size=size
    )
    return NoteListOut(items=items, total=total, page=page, size=size)


@router.post("/dogs/{dog_id}/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def create_note(dog_id: uuid.UUID, body: NoteCreate, staff: CurrentStaff, db: DbSession) -> NoteOut:
    (note,) = note_service.create_notes(
        db,
        institution_id=staff.institution_id,
        staff_id=staff.id,
        dog_id=dog_id,
        session_id=body.session_id,
        items=[body],
    )
    return note


@router.post("/dogs/{dog_id}/notes/batch", response_model=NoteBatchOut, status_code=status.HTTP_201_CREATED)
def create_notes(dog_id: uuid.UUID, body: NoteBatchCreate, staff: CurrentStaff, db: DbSession) -> NoteBatchOut:
    """여러 건을 같은 시각으로 쓴다(SOAP에서 채운 칸들). 하나라도 어긋나면 아무것도 저장하지 않는다."""
    items = note_service.create_notes(
        db,
        institution_id=staff.institution_id,
        staff_id=staff.id,
        dog_id=dog_id,
        session_id=body.session_id,
        items=body.notes,
    )
    return NoteBatchOut(items=items)


@router.patch("/notes/{note_id}", response_model=NoteOut)
def update_note(note_id: uuid.UUID, body: NoteUpdate, staff: CurrentStaff, db: DbSession) -> NoteOut:
    """고치기 전 내용은 수정 이력에 남는다. 지우는 API는 없다."""
    return note_service.update_note(
        db, institution_id=staff.institution_id, staff_id=staff.id, note_id=note_id, data=body
    )


@router.get("/notes/{note_id}/revisions", response_model=NoteRevisionListOut)
def list_note_revisions(note_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> NoteRevisionListOut:
    return NoteRevisionListOut(items=note_service.list_revisions(db, staff.institution_id, note_id))
