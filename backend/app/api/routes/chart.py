"""차트 자료 API(15.11, BE-28~30·35): 바이탈, 진단 이력, 메모·진료 기록, 그날 기록.

요청 검사 → services → 응답만 한다(11.3).
"""

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response, status
from pydantic import BeforeValidator

from app.api.deps import CurrentStaff, DbSession
from app.core.dates import today_local
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
from app.schemas.common import iso_date_text
from app.schemas.daily_records import DailyRecordsOut
from app.services import daily_records as daily_service
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


@router.delete("/dogs/{dog_id}/vitals/{measured_on}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vital(dog_id: uuid.UUID, measured_on: date, staff: CurrentStaff, db: DbSession) -> Response:
    """그날 줄을 통째로 지운다. 없으면 404. 등록 체중과 회차의 체중은 그대로다."""
    vital_service.delete_vital(
        db, institution_id=staff.institution_id, staff_id=staff.id, dog_id=dog_id, measured_on=measured_on
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
        visited_on=body.visited_on,
    )
    return note


@router.post("/dogs/{dog_id}/notes/batch", response_model=NoteBatchOut, status_code=status.HTTP_201_CREATED)
def create_notes(dog_id: uuid.UUID, body: NoteBatchCreate, staff: CurrentStaff, db: DbSession) -> NoteBatchOut:
    """여러 건을 같은 시각·같은 방문일로 쓴다(SOAP에서 채운 칸들). 하나라도 어긋나면 아무것도 저장하지 않는다."""
    items = note_service.create_notes(
        db,
        institution_id=staff.institution_id,
        staff_id=staff.id,
        dog_id=dog_id,
        session_id=body.session_id,
        items=body.notes,
        visited_on=body.visited_on,
    )
    return NoteBatchOut(items=items)


@router.patch("/notes/{note_id}", response_model=NoteOut)
def update_note(note_id: uuid.UUID, body: NoteUpdate, staff: CurrentStaff, db: DbSession) -> NoteOut:
    """고치기 전 내용은 수정 이력에 남는다. 방문일은 바꾸지 않는다."""
    return note_service.update_note(
        db, institution_id=staff.institution_id, staff_id=staff.id, note_id=note_id, data=body
    )


@router.get("/notes/{note_id}/revisions", response_model=NoteRevisionListOut)
def list_note_revisions(note_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> NoteRevisionListOut:
    return NoteRevisionListOut(items=note_service.list_revisions(db, staff.institution_id, note_id))


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> Response:
    """한 건과 그 수정 이력을 지운다. 되돌릴 수 없다."""
    note_service.delete_note(db, institution_id=staff.institution_id, staff_id=staff.id, note_id=note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/daily-records", response_model=DailyRecordsOut)
def daily_records(
    staff: CurrentStaff,
    db: DbSession,
    day: Annotated[date | None, BeforeValidator(iso_date_text), Query(alias="date")] = None,
) -> DailyRecordsOut:
    """기관의 그날 바이탈·메모·진료 기록·회차(BE-35). date를 빼면 오늘(한국 날짜)이다."""
    return daily_service.daily_records(db, staff.institution_id, day or today_local())
