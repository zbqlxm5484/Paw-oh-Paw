"""크림오프 관리자 API 업무 규칙(11.6, 13.6, 15.9, BE-24): 기관·디바이스 코드·계정 메타데이터.

기관 필터가 없다(크림오프가 모든 기관을 본다). 고객 자료(반려견·회차)는 열지 않는다(10절 Q31).
담당자·기관을 바꾸면 인증 캐시에서 지운다(11.6 무효화). 첫 인자는 DB 세션이고 flush()까지만 한다.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_cache import auth_cache
from app.core.dates import contract_status
from app.core.db import UNIQUE_VIOLATION, db_error_code
from app.core.errors import AppError, ErrorCode
from app.models import DeviceCode, Institution, Staff
from app.schemas.admin import (
    DeviceCodeCreate,
    DeviceCodeOut,
    DeviceCodeUpdate,
    InstitutionAdminOut,
    InstitutionCreate,
    InstitutionUpdate,
    StaffAdminOut,
    StaffUpdate,
)
from app.services.device_codes import CODE_ALPHABET, active_accounts, format_code, generate_code

# 13.6: 기관 코드를 비우면 INST- + 코드 글자 6자
INSTITUTION_CODE_PREFIX = "INST-"
INSTITUTION_CODE_RANDOM = 6
_DUPLICATE_CODE = {"fields": [{"field": "code", "type": "duplicate"}]}


# ---- 기관 ----


def _institution_rows(db: Session, *where: object) -> list:
    """기관 + 계정 수 + 코드 수를 한 번에(15.1 N+1 금지). name 오름차순."""
    staff_count = (
        select(func.count()).select_from(Staff).where(Staff.institution_id == Institution.id).scalar_subquery()
    )
    code_count = (
        select(func.count())
        .select_from(DeviceCode)
        .where(DeviceCode.institution_id == Institution.id)
        .scalar_subquery()
    )
    stmt = select(Institution, staff_count, code_count).order_by(Institution.name, Institution.created_at)
    if where:
        stmt = stmt.where(*where)
    return db.execute(stmt).all()


def _institution_out(institution: Institution, staff_count: int, code_count: int) -> InstitutionAdminOut:
    return InstitutionAdminOut(
        id=institution.id,
        code=institution.code,
        name=institution.name,
        contract_ends_at=institution.contract_ends_at,
        contract_status=contract_status(institution.contract_ends_at),
        staff_count=staff_count,
        device_code_count=code_count,
        created_at=institution.created_at,
    )


def list_institutions(db: Session) -> list[InstitutionAdminOut]:
    return [_institution_out(*row) for row in _institution_rows(db)]


def get_institution_out(db: Session, institution_id: uuid.UUID) -> InstitutionAdminOut:
    rows = _institution_rows(db, Institution.id == institution_id)
    if not rows:
        raise AppError(ErrorCode.NOT_FOUND)
    return _institution_out(*rows[0])


def _require_institution(db: Session, institution_id: uuid.UUID) -> Institution:
    institution = db.get(Institution, institution_id)
    if institution is None:
        raise AppError(ErrorCode.NOT_FOUND)
    return institution


def _code_exists(db: Session, code: str) -> bool:
    return db.scalar(select(Institution.id).where(Institution.code == code)) is not None


def _new_institution_code(db: Session) -> str:
    for _ in range(10):
        code = INSTITUTION_CODE_PREFIX + "".join(secrets.choice(CODE_ALPHABET) for _ in range(INSTITUTION_CODE_RANDOM))
        if not _code_exists(db, code):
            return code
    raise RuntimeError("could not pick an unused institution code")


def create_institution(db: Session, data: InstitutionCreate) -> InstitutionAdminOut:
    """기관 만들기(15.9). 코드 중복은 422 VALIDATION_ERROR(fields: code).

    동시에 만들어 uq_institution_code에 걸려도 같은 422다.
    """
    if data.code is not None and _code_exists(db, data.code):
        raise AppError(ErrorCode.VALIDATION_ERROR, _DUPLICATE_CODE)
    institution = Institution(
        code=data.code or _new_institution_code(db), name=data.name, contract_ends_at=data.contract_ends_at
    )
    db.add(institution)
    try:
        db.flush()
    except IntegrityError as error:
        if db_error_code(error) == UNIQUE_VIOLATION:
            raise AppError(ErrorCode.VALIDATION_ERROR, _DUPLICATE_CODE) from None
        raise
    db.refresh(institution)
    return _institution_out(institution, 0, 0)


def update_institution(db: Session, institution_id: uuid.UUID, data: InstitutionUpdate) -> InstitutionAdminOut:
    """이름·계약 종료일 수정(보낸 필드만). 바꾼 뒤 그 기관 담당자를 캐시에서 지운다(11.6)."""
    institution = _require_institution(db, institution_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("name") is not None:
        institution.name = changes["name"]
    if "contract_ends_at" in changes:
        institution.contract_ends_at = changes["contract_ends_at"]
    db.flush()
    auth_cache.invalidate_institution(institution_id)
    return get_institution_out(db, institution_id)


# ---- 디바이스 코드 ----


def _code_out(code: DeviceCode, active: int) -> DeviceCodeOut:
    return DeviceCodeOut(
        id=code.id,
        code=format_code(code.code),
        institution_id=code.institution_id,
        active_accounts=active,
        revoked_at=code.revoked_at,
        note=code.note,
        created_at=code.created_at,
    )


def _active_counts(db: Session, code_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not code_ids:
        return {}
    rows = db.execute(
        select(Staff.device_code_id, func.count())
        .where(Staff.device_code_id.in_(code_ids), Staff.is_active.is_(True))
        .group_by(Staff.device_code_id)
    ).all()
    return {code_id: int(count) for code_id, count in rows}


def _require_device_code(db: Session, device_code_id: uuid.UUID) -> DeviceCode:
    code = db.get(DeviceCode, device_code_id)
    if code is None:
        raise AppError(ErrorCode.NOT_FOUND)
    return code


def list_device_codes(db: Session, institution_id: uuid.UUID) -> list[DeviceCodeOut]:
    """회수된 코드도 포함한다(revoked_at으로 구분). 발급 순."""
    _require_institution(db, institution_id)
    codes = db.scalars(
        select(DeviceCode)
        .where(DeviceCode.institution_id == institution_id)
        .order_by(DeviceCode.created_at, DeviceCode.id)
    ).all()
    counts = _active_counts(db, [code.id for code in codes])
    return [_code_out(code, counts.get(code.id, 0)) for code in codes]


def create_device_code(db: Session, institution_id: uuid.UUID, data: DeviceCodeCreate) -> DeviceCodeOut:
    """코드 발급(15.9). 기관마다 쓸 수 있는 코드는 하나라, 회수하지 않은 코드가 있으면 409 DEVICE_CODE_EXISTS다.

    동시에 두 번 발급하면 uq_device_code_active가 막는다(같은 409). 코드 값은 20자 무작위라 겹칠 일이 사실상 없다.
    """
    _require_institution(db, institution_id)
    usable = db.scalar(
        select(DeviceCode.id).where(DeviceCode.institution_id == institution_id, DeviceCode.revoked_at.is_(None))
    )
    if usable is not None:
        raise AppError(ErrorCode.DEVICE_CODE_EXISTS)
    code = DeviceCode(institution_id=institution_id, code=generate_code(), note=data.note)
    db.add(code)
    try:
        db.flush()
    except IntegrityError as error:
        if db_error_code(error) == UNIQUE_VIOLATION:
            raise AppError(ErrorCode.DEVICE_CODE_EXISTS) from None
        raise
    db.refresh(code)
    return _code_out(code, 0)


def update_device_code(db: Session, device_code_id: uuid.UUID, data: DeviceCodeUpdate) -> DeviceCodeOut:
    """메모 수정(보낸 필드만). note의 null은 메모 지우기다."""
    code = _require_device_code(db, device_code_id)
    changes = data.model_dump(exclude_unset=True)
    if "note" in changes:
        code.note = changes["note"]
    db.flush()
    db.refresh(code)
    return _code_out(code, active_accounts(db, code.id))


def revoke_device_code(db: Session, device_code_id: uuid.UUID) -> DeviceCodeOut:
    """회수(멱등). 이미 회수됐으면 그대로. 기존 계정은 그대로 쓴다(막으려면 계정 중지)."""
    code = _require_device_code(db, device_code_id)
    if code.revoked_at is None:
        code.revoked_at = datetime.now(UTC)
        db.flush()
        db.refresh(code)
    return _code_out(code, active_accounts(db, code.id))


# ---- 계정 ----


def list_staff(db: Session, institution_id: uuid.UUID) -> list[StaffAdminOut]:
    _require_institution(db, institution_id)
    rows = db.scalars(
        select(Staff).where(Staff.institution_id == institution_id).order_by(Staff.created_at, Staff.login_id)
    ).all()
    return [StaffAdminOut.model_validate(row) for row in rows]


def update_staff(db: Session, staff_id: uuid.UUID, data: StaffUpdate, *, actor_id: uuid.UUID) -> StaffAdminOut:
    """중지·재개(15.9). 자기 자신을 중지하면 409 SELF_DISABLE. 바꾼 뒤 그 담당자를 캐시에서 지운다(11.6)."""
    row = db.get(Staff, staff_id)
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND)
    if row.id == actor_id and not data.is_active:
        raise AppError(ErrorCode.SELF_DISABLE)
    row.is_active = data.is_active
    db.flush()
    db.refresh(row)
    auth_cache.invalidate(row.id)
    return StaffAdminOut.model_validate(row)
