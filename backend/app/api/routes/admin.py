"""/api/v1/admin: 크림오프 관리자 API(15.9, BE-24). 조회는 ADMIN·STAFF, 쓰기는 ADMIN(11.6 역할 검사).

요청 검사 → services → 응답만 한다(11.3). 기관 필터가 없다(크림오프가 모든 기관을 본다).
"""

import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminStaff, CreamoffStaff, DbSession
from app.schemas.admin import (
    DeviceCodeCreate,
    DeviceCodeListOut,
    DeviceCodeOut,
    DeviceCodeUpdate,
    InstitutionAdminOut,
    InstitutionCreate,
    InstitutionListOut,
    InstitutionUpdate,
    StaffAdminOut,
    StaffListOut,
    StaffUpdate,
)
from app.services import admin as admin_service

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
