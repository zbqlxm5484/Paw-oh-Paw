"""로그인(잠금 포함), 담당자 스냅샷, 비밀번호 변경·내 정보 수정(11.6, 12.5 로그인 잠금, 13.4, 13.7, 15.4)."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from sqlalchemy import func, select
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session, joinedload

from app.core.auth_cache import AuthStaff, auth_cache
from app.core.errors import AppError, ErrorCode
from app.core.security import hash_password, verify_password
from app.models import Institution, Staff
from app.models.enums import EffectiveRole, StaffRole
from app.schemas.auth import InstitutionOut, MeUpdate, StaffOut

logger = logging.getLogger(__name__)

# 12.5 로그인 잠금(조영운 결정 11-05): 비밀번호를 이어서 5회 틀리면 30분 동안 잠근다.
# 문구(messages/ko.yaml의 LOGIN_FAILED)에 같은 숫자가 적혀 있다. 바꾸면 함께 고친다
LOGIN_MAX_FAILURES = 5
LOGIN_LOCK_MINUTES = 30
# 담당자 행을 잠근 뒤 다시 읽는 칸. 잠겼는지와 비밀번호가 맞는지를 이 값으로 판단한다
_LOGIN_STATE = ("password_hash", "login_fail_count", "login_locked_until", "is_active")
# 어느 담당자의 ID도 아닌 값(uuid4는 0이 될 수 없다). 없는 아이디일 때 잠금 조회 자리를 채운다
_NO_STAFF_ID = uuid.UUID(int=0)


class LoginRejected(AppError):
    """실패 횟수·잠금을 본 뒤에 내는 로그인 거절(401 LOGIN_FAILED). 틀린 비밀번호와 잠긴 계정이 이것이다.

    이 예외가 났을 때 rollback하면 방금 적은 실패 횟수가 사라진다. 그래서 POST /auth/login 라우트는 이것을 잡아
    예외로 올리지 않고 같은 오류 응답을 돌려주고, get_db가 commit한다(11.7 실패해도 commit하는 곳).
    Spring에 빗대면 @Transactional(noRollbackFor = LoginRejected.class)다.
    """

    def __init__(self) -> None:
        super().__init__(ErrorCode.LOGIN_FAILED)


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
        password_changed_at=staff.password_changed_at,
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


def _lock_login_state(db: Session, staff: Staff) -> bool:
    """담당자 행을 잠그고(SELECT … FOR UPDATE) 잠금 판단에 쓰는 칸을 다시 읽는다. 그사이 행이 지워졌으면 False.

    칸만 읽으므로 조인이 붙지 않는다(11.7 잠금 조회). 먼저 읽어 둔 기관은 그대로 쓴다. 잠금은 요청이 끝날 때
    (commit·rollback) 풀린다.
    """
    try:
        db.refresh(staff, attribute_names=_LOGIN_STATE, with_for_update=True)
    except InvalidRequestError:
        return False
    return True


def authenticate(db: Session, *, login_id: str, password: str) -> AuthStaff:
    """아이디·비밀번호를 확인하고 스냅샷을 돌려준다(캐시도 갱신).

    하나라도 틀리면 401 LOGIN_FAILED 하나로만 답한다(13.4). 순서는 아이디 없음(가짜 해시 비교) → 잠김 → 비밀번호
    틀림 → is_active FALSE(403 ACCOUNT_DISABLED)다. 아이디는 대소문자를 구분해 입력 그대로 비교한다.
    계약이 끝난 CLIENT도 로그인은 된다(effective_role이 GUEST, 15.4).

    로그인 잠금(12.5, v1.48): 있는 아이디에 비밀번호를 LOGIN_MAX_FAILURES번 이어서 틀리면 LOGIN_LOCK_MINUTES분
    동안 맞는 비밀번호도 받지 않는다. 잠긴 계정과 틀린 비밀번호는 LoginRejected로 낸다(응답은 같은 401이고,
    부르는 쪽이 commit해야 실패 횟수가 남는다). bcrypt 비교(약 0.3초)는 행을 잠그기 전에 하고, 잠근 뒤 다시 읽은
    값으로 판단한다. 그래서 동시에 여러 비밀번호를 넣어 봐도 다섯 번째 실패 뒤에 차례가 온 요청은 거절되고,
    한 계정에 요청이 몰려도 DB 연결이 행 잠금 앞에 0.3초씩 줄을 서지 않는다.
    로그에는 담당자 ID만 남긴다. 입력한 아이디는 남기지 않는다(아이디 칸에 비밀번호를 넣는 일이 있다, 11.8).
    """
    staff = db.scalars(
        select(Staff).where(Staff.login_id == login_id).options(joinedload(Staff.institution))
    ).one_or_none()
    if staff is None:
        verify_password(password, _dummy_hash())
        # 있는 아이디일 때와 DB를 오가는 횟수를 맞춘다(응답 시간으로 아이디가 있는지 가리지 못하게, 15.4)
        db.execute(select(Staff.id).where(Staff.id == _NO_STAFF_ID).with_for_update()).first()
        logger.info("login failed: unknown account")
        raise AppError(ErrorCode.LOGIN_FAILED)

    checked_hash = staff.password_hash
    matched = verify_password(password, checked_hash)
    if not _lock_login_state(db, staff):
        # 비교하는 사이에 계정이 지워졌다(계약 종료 뒤 자동 파기, 12.5). 없는 아이디와 같다
        logger.info("login failed: unknown account")
        raise AppError(ErrorCode.LOGIN_FAILED)
    if staff.password_hash != checked_hash:
        # 비교하는 사이에 비밀번호가 바뀌었다. 옛 비밀번호로 들어오지 못하게 새 해시로 다시 본다
        matched = verify_password(password, staff.password_hash)

    now = datetime.now(UTC)
    if staff.login_locked_until is not None:
        if now < staff.login_locked_until:
            logger.info("login refused: locked staff=%s", staff.id)
            raise LoginRejected()
        # 잠금 시각이 지났다. 0에서 다시 센다
        staff.login_fail_count = 0
        staff.login_locked_until = None
    if not matched:
        staff.login_fail_count += 1
        if staff.login_fail_count >= LOGIN_MAX_FAILURES:
            staff.login_locked_until = now + timedelta(minutes=LOGIN_LOCK_MINUTES)
            logger.warning(
                "login locked staff=%s failures=%d until=%s",
                staff.id,
                staff.login_fail_count,
                staff.login_locked_until.isoformat(timespec="seconds"),
            )
        else:
            logger.info("login failed staff=%s failures=%d", staff.id, staff.login_fail_count)
        db.flush()
        raise LoginRejected()
    if not staff.is_active:
        raise AppError(ErrorCode.ACCOUNT_DISABLED)
    staff.login_fail_count = 0
    db.flush()
    snapshot = snapshot_of(staff)
    auth_cache.put(snapshot)
    return snapshot


def set_new_password(db: Session, staff: Staff, new_password: str) -> None:
    """새 비밀번호를 적는다(비밀번호 변경·재설정 공용, 12.5 비밀번호를 바꾼 시각, v1.48). flush까지 한다.

    그전에 받은 토큰을 끊고(password_changed_at) 로그인 잠금을 푼다. 순서를 지킨다: 해시(약 0.3초)를 먼저 계산하고,
    담당자 행을 잠근 뒤에 시각을 적는다. 로그인은 같은 행을 잠근 채 토큰을 만들므로(routes/auth.py), 잠근 뒤에 잰
    시각은 옛 비밀번호로 받은 모든 토큰의 발급 시각보다 늦다. 잠그기 전에 시각을 재면 그 직후에 끝난 로그인의
    토큰이 살아남는다. 시각은 토큰의 iat와 같은 시계(API 서버)로 적는다.
    """
    password_hash = hash_password(new_password)
    db.refresh(staff, attribute_names=("login_fail_count", "login_locked_until"), with_for_update=True)
    staff.password_hash = password_hash
    staff.password_changed_at = datetime.now(UTC)
    staff.login_fail_count = 0
    staff.login_locked_until = None
    db.flush()


def _staff_row(db: Session, staff_id: uuid.UUID) -> Staff:
    """로그인한 담당자의 행(기관 포함). 그 사이 지워졌으면 401 AUTH_REQUIRED."""
    staff = db.get(Staff, staff_id, options=[joinedload(Staff.institution)])
    if staff is None:
        raise AppError(ErrorCode.AUTH_REQUIRED)
    return staff


def change_password(db: Session, staff_id: uuid.UUID, *, current_password: str, new_password: str) -> AuthStaff:
    """비밀번호 변경(13.7, 15.4 BE-26). 현재 비밀번호가 틀리면 400 PASSWORD_MISMATCH.

    새 비밀번호 규칙(8자 이상, 72바이트 이하, 현재와 다름)은 PasswordChangeIn이 422로 본다.
    바꾸면 그전에 받은 토큰이 모두 끊긴다(v1.48). 이 요청에 쓴 토큰도 끊기므로 바꾼 본인도 다시 로그인한다.
    로그인 잠금도 풀린다(set_new_password). 바꾼 뒤 자기 스냅샷을 캐시에서 지운다.
    """
    staff = _staff_row(db, staff_id)
    if not verify_password(current_password, staff.password_hash):
        raise AppError(ErrorCode.PASSWORD_MISMATCH)
    set_new_password(db, staff, new_password)
    auth_cache.invalidate(staff.id)
    logger.info("password changed staff=%s", staff.id)
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
