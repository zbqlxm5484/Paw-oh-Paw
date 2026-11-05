"""/api/v1/dogs (15.5, BE-02·03, 삭제는 BE-19). 요청 검사 → services → 응답만 한다(11.3)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import AnalysisClientDep, CurrentStaff, DbSession
from app.models.enums import PurgeScope
from app.schemas.dogs import DogCreate, DogListOut, DogOut, DogUpdate
from app.services import dogs as dog_service
from app.services import purge as purge_service
from app.storage.base import get_storage

router = APIRouter(prefix="/dogs", tags=["반려견"])


@router.get("", response_model=DogListOut)
def list_dogs(
    staff: CurrentStaff,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=50)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DogListOut:
    items, total = dog_service.list_dogs(db, staff.institution_id, q=q, page=page, size=size)
    return DogListOut(items=items, total=total, page=page, size=size)


@router.post("", response_model=DogOut, status_code=status.HTTP_201_CREATED)
def create_dog(body: DogCreate, staff: CurrentStaff, db: DbSession) -> DogOut:
    dog = dog_service.create_dog(db, staff.institution_id, body)
    return dog_service.get_dog_out(db, staff.institution_id, dog.id)


@router.get("/{dog_id}", response_model=DogOut)
def get_dog(dog_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> DogOut:
    return dog_service.get_dog_out(db, staff.institution_id, dog_id)


@router.patch("/{dog_id}", response_model=DogOut)
def update_dog(dog_id: uuid.UUID, body: DogUpdate, staff: CurrentStaff, db: DbSession) -> DogOut:
    dog = dog_service.update_dog(db, staff.institution_id, dog_id, body)
    return dog_service.get_dog_out(db, staff.institution_id, dog.id)


@router.delete("/{dog_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dog(dog_id: uuid.UUID, staff: CurrentStaff, db: DbSession, analysis: AnalysisClientDep) -> Response:
    """반려견과 그 아래 자료를 지운다(15.5). 관리자 파기의 DOG와 같은 서비스라 순서·오류·purge_log가 같다."""
    purge_service.purge(
        db,
        get_storage(),
        PurgeScope.DOG,
        analysis=analysis,
        institution_id=staff.institution_id,
        target_id=dog_id,
        dry_run=False,
        executed_by=staff.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
