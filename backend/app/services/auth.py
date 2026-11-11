"""로그인, 담당자 스냅샷, 비밀번호 변경·내 정보 수정(11.6, 13.4, 13.7, 15.4)."""

import uuid
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.auth_cache import AuthStaff, auth_cache
from app.core.errors import AppError, ErrorCode
from app.core.security import hash_password, verify_password
from app.models import Institution, Staff
from app.models.enums import EffectiveRole, StaffRole
from app.schemas.auth import InstitutionOut, MeUpdate, StaffOut


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
        notif_on=staff.notif_on,
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


def _staff_row(db: Session, staff_id: uuid.UUID) -> Staff:
    """로그인한 담당자의 행(기관 포함). 그 사이 지워졌으면 401 AUTH_REQUIRED."""
    staff = db.get(Staff, staff_id, options=[joinedload(Staff.institution)])
    if staff is None:
        raise AppError(ErrorCode.AUTH_REQUIRED)
    return staff


def change_password(db: Session, staff_id: uuid.UUID, *, current_password: str, new_password: str) -> AuthStaff:
    """비밀번호 변경(13.7, 15.4 BE-26). 현재 비밀번호가 틀리면 400 PASSWORD_MISMATCH.

    새 비밀번호 규칙(8자 이상, 72바이트 이하, 현재와 다름)은 PasswordChangeIn이 422로 본다.
    바꾼 뒤 자기 스냅샷을 캐시에서 지운다. 이미 받은 토큰은 그대로 유효하다(토큰 무효화는 없다).
    """
    staff = _staff_row(db, staff_id)
    if not verify_password(current_password, staff.password_hash):
        raise AppError(ErrorCode.PASSWORD_MISMATCH)
    staff.password_hash = hash_password(new_password)
    db.flush()
    auth_cache.invalidate(staff.id)
    return snapshot_of(staff)


def update_me(db: Session, staff_id: uuid.UUID, data: MeUpdate) -> AuthStaff:
    """이름·이메일·알림 설정 수정(13.7, 15.4 BE-26). 보낸 필드만 바꾸고 자기 스냅샷을 캐시에서 지운다."""
    staff = _staff_row(db, staff_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("name") is not None:
        staff.name = changes["name"]
    if changes.get("email") is not None:
        staff.email = changes["email"]
    if changes.get("notif_on") is not None:
        staff.notif_on = changes["notif_on"]
    db.flush()
    auth_cache.invalidate(staff.id)
    return snapshot_of(staff)


def withdraw(db: Session, staff_id: uuid.UUID, *, password: str) -> None:
    """회원 탈퇴(13.7, 15.4 DELETE /auth/me). 계정을 지우지 않고 중지한다(is_active FALSE, withdrawn_at에 시각).

    순서: 기관 행 잠금 → 비밀번호 확인(400 PASSWORD_MISMATCH) → 그 기관에 다른 활성 계정이 있는지(없으면 409
    LAST_ACCOUNT. 기관이 통째로 잠기지 않게) → 중지 → 캐시에서 지움. 기관 행을 잠그는 것은 마지막 두 계정이 동시에
    탈퇴해 둘 다 통과하는 일을 막기 위해서다. 반려견·회차는 기관의 자료라 그대로 둔다.
    """
    staff = _staff_row(db, staff_id)
    db.execute(select(Institution.id).where(Institution.id == staff.institution_id).with_for_update())
    if not verify_password(password, staff.password_hash):
        raise AppError(ErrorCode.PASSWORD_MISMATCH)
    others = db.scalar(
        select(func.count())
        .select_from(Staff)
        .where(Staff.institution_id == staff.institution_id, Staff.is_active.is_(True), Staff.id != staff.id)
    )
    if not others:
        raise AppError(ErrorCode.LAST_ACCOUNT)
    staff.is_active = False
    staff.withdrawn_at = datetime.now(UTC)
    db.flush()
    auth_cache.invalidate(staff.id)


def staff_out(staff: AuthStaff) -> StaffOut:
    """스냅샷 → StaffOut(15.3). effective_role·contract_status는 지금 시점으로 계산한 값이다."""
    return StaffOut(
        id=staff.id,
        login_id=staff.login_id,
        name=staff.name,
        email=staff.email,
        role=staff.role,
        effective_role=staff.effective_role,
        notif_on=staff.notif_on,
        institution=InstitutionOut(
            id=staff.institution_id,
            code=staff.institution_code,
            name=staff.institution_name,
            contract_ends_at=staff.contract_ends_at,
            contract_status=staff.contract_status,
        ),
    )


# 인쇄 토큰으로 GET /auth/me를 부르면 주는 값의 자리 채움(15.4). 사람이 아니라 서버가 만든 토큰이다
PRINT_STAFF_ID = uuid.UUID(int=0)
PRINT_LOGIN_ID = "print"


def print_staff_out(db: Session, institution_id: uuid.UUID) -> StaffOut:
    """인쇄 토큰의 기관을 그 기관의 CLIENT처럼 보이는 StaffOut으로(11.6, 15.4). 기관이 없으면 401.

    인쇄 화면은 institution·role·effective_role만 쓴다. 계약이 끝났어도 effective_role은 CLIENT다(인쇄 토큰은
    계약 상태를 보지 않는다). institution의 계약 값은 실제 값이다.
    """
    institution = db.get(Institution, institution_id)
    if institution is None:
        raise AppError(ErrorCode.AUTH_REQUIRED)
    snapshot = AuthStaff(
        id=PRINT_STAFF_ID,
        institution_id=institution.id,
        login_id=PRINT_LOGIN_ID,
        name=PRINT_LOGIN_ID,
        email=None,
        role=StaffRole.CLIENT.value,
        is_active=True,
        institution_code=institution.code,
        institution_name=institution.name,
        contract_ends_at=institution.contract_ends_at,
        notif_on=False,
    )
    return staff_out(snapshot).model_copy(update={"effective_role": EffectiveRole.CLIENT.value})
