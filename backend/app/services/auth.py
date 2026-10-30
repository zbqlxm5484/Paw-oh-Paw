"""로그인과 담당자 스냅샷(11.6, 13.4, 15.4)."""

import uuid
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.auth_cache import AuthStaff, auth_cache
from app.core.errors import AppError, ErrorCode
from app.core.security import hash_password, verify_password
from app.models import Staff
from app.schemas.auth import InstitutionOut, StaffOut


@lru_cache
def _dummy_hash() -> str:
    """없는 아이디에도 bcrypt 비교를 한 번 해서, 응답 시간으로 아이디가 있는지 알 수 없게 한다(15.4)."""
    return hash_password("dummy-password-for-constant-time")


def snapshot_of(staff: Staff) -> AuthStaff:
    """ORM 담당자(기관이 로드된 상태) → 스냅샷(11.6 인증 캐시)."""
    institution = staff.institution
    return AuthStaff(
        id=staff.id,
        institution_id=staff.institution_id,
        login_id=staff.login_id,
        name=staff.name,
        email=staff.email,
        role=staff.role,
        is_active=staff.is_active,
        institution_code=institution.code,
        institution_name=institution.name,
        contract_ends_at=institution.contract_ends_at,
    )


def load_snapshot(db: Session, staff_id: uuid.UUID) -> AuthStaff | None:
    """DB에서 담당자 + 기관을 읽어 스냅샷을 만든다. 없으면 None. 캐시에는 넣지 않는다(부르는 쪽이 정한다)."""
    staff = db.get(Staff, staff_id, options=[joinedload(Staff.institution)])
    return None if staff is None else snapshot_of(staff)


def refresh_snapshot(db: Session, staff_id: uuid.UUID) -> AuthStaff | None:
    """DB를 직접 읽고 캐시를 갱신한다. 로그인과 GET /auth/me가 쓴다(11.6)."""
    snapshot = load_snapshot(db, staff_id)
    if snapshot is not None:
        auth_cache.put(snapshot)
    return snapshot


def authenticate(db: Session, *, login_id: str, password: str) -> AuthStaff:
    """아이디·비밀번호를 확인하고 스냅샷을 돌려준다(캐시도 갱신).

    하나라도 틀리면 401 LOGIN_FAILED 하나로만 답한다(13.4). 순서는 아이디 없음(가짜 해시 비교) → 비밀번호 틀림 →
    is_active FALSE(403 ACCOUNT_DISABLED)다. 아이디는 대소문자를 구분해 입력 그대로 비교한다.
    계약이 끝난 CLIENT도 로그인은 된다(effective_role이 GUEST, 15.4).
    """
    staff = db.scalars(
        select(Staff).where(Staff.login_id == login_id).options(joinedload(Staff.institution))
    ).one_or_none()
    if staff is None:
        verify_password(password, _dummy_hash())
        raise AppError(ErrorCode.LOGIN_FAILED)
    if not verify_password(password, staff.password_hash):
        raise AppError(ErrorCode.LOGIN_FAILED)
    if not staff.is_active:
        raise AppError(ErrorCode.ACCOUNT_DISABLED)
    snapshot = snapshot_of(staff)
    auth_cache.put(snapshot)
    return snapshot


def staff_out(staff: AuthStaff) -> StaffOut:
    """스냅샷 → StaffOut(15.3). effective_role·contract_status는 지금 시점으로 계산한 값이다."""
    return StaffOut(
        id=staff.id,
        login_id=staff.login_id,
        name=staff.name,
        email=staff.email,
        role=staff.role,
        effective_role=staff.effective_role,
        institution=InstitutionOut(
            id=staff.institution_id,
            code=staff.institution_code,
            name=staff.institution_name,
            contract_ends_at=staff.contract_ends_at,
            contract_status=staff.contract_status,
        ),
    )
