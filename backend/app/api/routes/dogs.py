"""/api/v1/dogs (15.5, BE-02·03, 휴지통·영구 삭제는 BE-19). 요청 검사 → services → 응답만 한다(11.3)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import AnalysisClientDep, CurrentStaff, DbSession
from app.schemas.dogs import DogCreate, DogListOut, DogOut, DogUpdate
from app.services import dogs as dog_service
from app.services import trash as trash_service
from app.storage.base import get_storage

router = APIRouter(prefix="/dogs", tags=["반려견"])


@router.get("", response_model=DogListOut)
def list_dogs(
    staff: CurrentStaff,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=50)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    trash: bool = False,
    changed_within_days: Annotated[int | None, Query(ge=1, le=30)] = None,
) -> DogListOut:
    """trash=true면 휴지통 목록이다(최근에 넣은 것부터). 기본은 휴지통에 없는 반려견이다.

    changed_within_days를 주면 그 기간에 변동이 있는 반려견만 준다(15.5).
    """
    items, total = dog_service.list_dogs(
        db,
        staff.institution_id,
        q=q,
        page=page,
        size=size,
        trash=trash,
        changed_within_days=changed_within_days,
    )
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
def delete_dog(dog_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> Response:
    """반려견을 휴지통에 넣는다(15.5). 지우지 않으므로 복원할 수 있고, 30일 뒤 워커가 영구 삭제한다."""
    trash_service.move_to_trash(db, staff.institution_id, dog_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{dog_id}/restore", response_model=DogOut)
def restore_dog(dog_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> DogOut:
    """휴지통에서 꺼낸다(15.5). 휴지통에 없는 반려견은 404다."""
    trash_service.restore(db, staff.institution_id, dog_id)
    return dog_service.get_dog_out(db, staff.institution_id, dog_id)


@router.delete("/{dog_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
def delete_dog_permanently(
    dog_id: uuid.UUID, staff: CurrentStaff, db: DbSession, analysis: AnalysisClientDep
) -> Response:
    """휴지통의 반려견을 영구 삭제한다(15.5). 관리자 파기의 DOG와 같은 서비스라 순서·오류·purge_log가 같다."""
    trash_service.delete_permanently(db, get_storage(), analysis, staff.institution_id, dog_id, executed_by=staff.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
