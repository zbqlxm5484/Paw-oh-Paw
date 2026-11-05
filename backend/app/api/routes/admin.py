"""/api/v1/admin: 크림오프 관리자 API(15.9, BE-24). 조회는 ADMIN·STAFF, 쓰기는 ADMIN(11.6 역할 검사).

요청 검사 → services → 응답만 한다(11.3). 기관 필터가 없다(크림오프가 모든 기관을 본다).
"""

import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminStaff, AnalysisClientDep, CreamoffStaff, DbSession
from app.schemas.admin import (
    DeviceCodeCreate,
    DeviceCodeListOut,
    DeviceCodeOut,
    DeviceCodeUpdate,
    InstitutionAdminOut,
    InstitutionCreate,
    InstitutionListOut,
    InstitutionUpdate,
    PurgeOut,
    PurgeRequest,
    StaffAdminOut,
    StaffListOut,
    StaffUpdate,
)
from app.services import admin as admin_service
from app.services import purge as purge_service
from app.storage.base import get_storage

router = APIRouter(prefix="/admin", tags=["관리자"])


# ---- 기관 ----


@router.get("/institutions", response_model=InstitutionListOut)
def list_institutions(staff: CreamoffStaff, db: DbSession) -> InstitutionListOut:
    return InstitutionListOut(items=admin_service.list_institutions(db))


@router.post("/institutions", response_model=InstitutionAdminOut, status_code=status.HTTP_201_CREATED)
def create_institution(body: InstitutionCreate, staff: AdminStaff, db: DbSession) -> InstitutionAdminOut:
    return admin_service.create_institution(db, body)


@router.patch("/institutions/{institution_id}", response_model=InstitutionAdminOut)
def update_institution(
    institution_id: uuid.UUID, body: InstitutionUpdate, staff: AdminStaff, db: DbSession
) -> InstitutionAdminOut:
    return admin_service.update_institution(db, institution_id, body)


# ---- 디바이스 코드 ----


@router.get("/institutions/{institution_id}/device-codes", response_model=DeviceCodeListOut)
def list_device_codes(institution_id: uuid.UUID, staff: CreamoffStaff, db: DbSession) -> DeviceCodeListOut:
    return DeviceCodeListOut(items=admin_service.list_device_codes(db, institution_id))


@router.post(
    "/institutions/{institution_id}/device-codes", response_model=DeviceCodeOut, status_code=status.HTTP_201_CREATED
)
def create_device_code(
    institution_id: uuid.UUID, staff: AdminStaff, db: DbSession, body: DeviceCodeCreate | None = None
) -> DeviceCodeOut:
    """본문을 비워도 된다(상한 3, 메모 없음)."""
    return admin_service.create_device_code(db, institution_id, body or DeviceCodeCreate())


@router.patch("/device-codes/{device_code_id}", response_model=DeviceCodeOut)
def update_device_code(
    device_code_id: uuid.UUID, body: DeviceCodeUpdate, staff: AdminStaff, db: DbSession
) -> DeviceCodeOut:
    return admin_service.update_device_code(db, device_code_id, body)


@router.post("/device-codes/{device_code_id}/revoke", response_model=DeviceCodeOut)
def revoke_device_code(device_code_id: uuid.UUID, staff: AdminStaff, db: DbSession) -> DeviceCodeOut:
    """본문 없음. 멱등: 이미 회수됐으면 그대로 200."""
    return admin_service.revoke_device_code(db, device_code_id)


# ---- 계정 ----


@router.get("/institutions/{institution_id}/staff", response_model=StaffListOut)
def list_staff(institution_id: uuid.UUID, staff: CreamoffStaff, db: DbSession) -> StaffListOut:
    return StaffListOut(items=admin_service.list_staff(db, institution_id))


@router.patch("/staff/{staff_id}", response_model=StaffAdminOut)
def update_staff(staff_id: uuid.UUID, body: StaffUpdate, staff: AdminStaff, db: DbSession) -> StaffAdminOut:
    return admin_service.update_staff(db, staff_id, body, actor_id=staff.id)


# ---- 자료 파기(15.9, BE-19) ----


@router.post("/purge", response_model=PurgeOut)
def purge(body: PurgeRequest, staff: AdminStaff, db: DbSession, analysis: AnalysisClientDep) -> PurgeOut:
    """자료 파기(관리자만). dry_run 기본 true. DOG는 기관의 반려견 하나, INSTITUTION은 기관 전체.

    기관은 body.institution_id이고 생략하면 부른 관리자의 기관이다. 응답은 개수뿐이라 고객 자료를 열지 않는다(15.9).
    """
    return purge_service.purge(
        db,
        get_storage(),
        body.scope,
        analysis=analysis,
        institution_id=body.institution_id or staff.institution_id,
        target_id=body.target_id,
        dry_run=body.dry_run,
        executed_by=staff.id,
    )
