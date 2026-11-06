"""차트 자료 API(15.11, BE-28~30): 바이탈. 요청 검사 → services → 응답만 한다(11.3)."""

import uuid
from datetime import date

from fastapi import APIRouter

from app.api.deps import CurrentStaff, DbSession
from app.schemas.chart import VitalIn, VitalListOut, VitalOut
from app.services import vitals as vital_service

router = APIRouter(tags=["차트 자료"])


@router.get("/dogs/{dog_id}/vitals", response_model=VitalListOut)
def list_vitals(dog_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> VitalListOut:
    return VitalListOut(items=vital_service.list_vitals(db, staff.institution_id, dog_id))


@router.put("/dogs/{dog_id}/vitals/{measured_on}", response_model=VitalOut)
def put_vital(dog_id: uuid.UUID, measured_on: date, body: VitalIn, staff: CurrentStaff, db: DbSession) -> VitalOut:
    """그날 바이탈을 만들거나 바꾼다. 어느 쪽이든 200이다."""
    return vital_service.put_vital(
        db, institution_id=staff.institution_id, staff_id=staff.id, dog_id=dog_id, measured_on=measured_on, data=body
    )
