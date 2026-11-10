"""이력·비교·추이 API(15.8의 8·22·23, BE-17·18). 요청 검사 → services → 응답만 한다(11.3)."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentStaff, DbSession
from app.models.enums import GaitType, Limb
from app.schemas.history import BASE_QUERY_PATTERN, CompareOut, SessionHistoryOut, TrendsOut
from app.services import compare as compare_service
from app.services import history as history_service
from app.services import trends as trends_service

router = APIRouter(prefix="/dogs", tags=["이력·비교·추이"])


@router.get("/{dog_id}/sessions", response_model=SessionHistoryOut)
def list_sessions(
    dog_id: uuid.UUID,
    staff: CurrentStaff,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SessionHistoryOut:
    """측정 이력(BE-17). measured_on 내림차순, 같으면 created_at 내림차순."""
    items, total = history_service.list_sessions(db, staff.institution_id, dog_id, page=page, size=size)
    return SessionHistoryOut(items=items, total=total, page=page, size=size)


@router.get("/{dog_id}/compare", response_model=CompareOut)
def compare_sessions(
    dog_id: uuid.UUID,
    staff: CurrentStaff,
    db: DbSession,
    target: uuid.UUID | None = None,
    base: Annotated[str, Query(pattern=BASE_QUERY_PATTERN)] = compare_service.BASELINE,
    gait_type: GaitType | None = None,
) -> CompareOut:
    """회차 비교(BE-18). base는 BASELINE·PREVIOUS·회차 ID, 그 밖은 422. 비교할 수 없으면 400 COMPARE_INVALID."""
    return compare_service.compare_sessions(
        db, staff.institution_id, dog_id, target_id=target, base=base, gait_type=gait_type
    )


@router.get("/{dog_id}/trends", response_model=TrendsOut)
def get_trends(
    dog_id: uuid.UUID,
    staff: CurrentStaff,
    db: DbSession,
    metric_code: Annotated[str, Query(max_length=50)],
    gait_type: GaitType,
    limb: Limb | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> TrendsOut:
    """수치 추이(BE-18). metric_code·gait_type은 필수, from·to는 measured_on 기간(날짜 포함)."""
    return trends_service.trends(
        db,
        staff.institution_id,
        dog_id,
        metric_code=metric_code,
        gait_type=gait_type,
        limb=limb,
        date_from=date_from,
        date_to=date_to,
    )
