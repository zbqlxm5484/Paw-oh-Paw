"""/api/v1/auth(15.4): 로그인·내 정보(BE-01), 디바이스 코드 확인·회원가입(BE-22), 비밀번호 변경·내 정보 수정(BE-26),
비밀번호 재설정(BE-27)."""

from fastapi import APIRouter, status

from app.api.deps import CurrentStaff, CurrentStaffAny, DbSession, MeCaller, Reader
from app.core.auth_cache import AuthStaff
from app.core.errors import AppError, ErrorCode
from app.core.security import create_access_token
from app.schemas.auth import (
    DeviceCodeVerifyIn,
    DeviceCodeVerifyOut,
    DeviceOut,
    LoginIn,
    MeUpdate,
    MyDeviceOut,
    PasswordChangeIn,
    PasswordResetConfirmIn,
    PasswordResetRequestIn,
    SignupIn,
    StaffOut,
    TokenOut,
    WithdrawIn,
)
from app.services import auth as auth_service
from app.services import device_codes as device_code_service
from app.services import password_reset as password_reset_service
from app.services import signup as signup_service
from app.services.auth import authenticate, refresh_snapshot, staff_out

router = APIRouter(prefix="/auth", tags=["인증"])


def _token_out(staff: AuthStaff) -> TokenOut:
    """토큰 발급 응답(15.4). 로그인과 가입이 같은 모양이다."""
    token, expires_at = create_access_token(staff_id=staff.id, institution_id=staff.institution_id, role=staff.role)
    return TokenOut(access_token=token, expires_at=expires_at, staff=staff_out(staff))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: DbSession) -> TokenOut:
    return _token_out(authenticate(db, login_id=body.login_id, password=body.password))


@router.post("/device-codes/verify", response_model=DeviceCodeVerifyOut)
def verify_device_code(body: DeviceCodeVerifyIn, db: DbSession) -> DeviceCodeVerifyOut:
    """디바이스 코드 확인(인증 없음). 쓸 수 없는 코드는 어느 경우든 404 DEVICE_CODE_INVALID 하나다."""
    return signup_service.verify_code(db, body.code)


@router.post("/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, db: DbSession) -> TokenOut:
    """회원가입(인증 없음). 가입 즉시 로그인된 상태라 응답이 로그인과 같다."""
    return _token_out(signup_service.signup(db, body))


@router.get("/me", response_model=StaffOut)
def me(caller: MeCaller, db: DbSession) -> StaffOut:
    """내 정보. 계약이 끝난 CLIENT(GUEST)도 된다. 캐시를 거치지 않고 DB를 읽어 캐시를 갱신한다(11.6).

    인쇄 토큰(11.6)이면 사람이 없으므로 그 기관의 CLIENT처럼 보이는 값을 준다(인쇄 화면이 기관과 역할을 읽는다).
    """
    if isinstance(caller, Reader):
        return auth_service.print_staff_out(db, caller.institution_id)
    fresh = refresh_snapshot(db, caller.id)
    if fresh is None:
        raise AppError(ErrorCode.AUTH_REQUIRED)
    if not fresh.is_active:
        raise AppError(ErrorCode.ACCOUNT_DISABLED)
    return staff_out(fresh)


@router.get("/me/device", response_model=MyDeviceOut)
def my_device(staff: CurrentStaffAny, db: DbSession) -> MyDeviceOut:
    """내 기관의 측정 기기(쓸 수 있는 디바이스 코드, BE-36). 코드는 가운데를 가려서 준다. GUEST도 된다."""
    code = device_code_service.usable_code_of(db, staff.institution_id)
    if code is None:
        return MyDeviceOut(device=None)
    return MyDeviceOut(
        device=DeviceOut(code_masked=device_code_service.mask_code(code.code), issued_at=code.created_at)
    )


@router.patch("/me", response_model=StaffOut)
def update_me(body: MeUpdate, staff: CurrentStaff, db: DbSession) -> StaffOut:
    """이름·이메일·알림 설정 수정(보낸 필드만). GUEST는 403 CONTRACT_EXPIRED(조회만 된다)."""
    return staff_out(auth_service.update_me(db, staff.id, body))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def withdraw(body: WithdrawIn, staff: CurrentStaffAny, db: DbSession) -> None:
    """회원 탈퇴. 계약이 끝난 CLIENT(GUEST)도 된다. 비밀번호가 틀리면 400, 기관의 마지막 계정이면 409 LAST_ACCOUNT."""
    auth_service.withdraw(db, staff.id, password=body.password)


@router.patch("/password", response_model=StaffOut)
def change_password(body: PasswordChangeIn, staff: CurrentStaff, db: DbSession) -> StaffOut:
    """비밀번호 변경. 현재 비밀번호가 틀리면 400 PASSWORD_MISMATCH. 이미 받은 토큰은 그대로 유효하다."""
    return staff_out(
        auth_service.change_password(
            db, staff.id, current_password=body.current_password, new_password=body.new_password
        )
    )


@router.post("/password-reset/request", status_code=status.HTTP_204_NO_CONTENT)
def request_password_reset(body: PasswordResetRequestIn, db: DbSession) -> None:
    """재설정 링크 메일(인증 없음). 계정이 있든 없든 204, SMTP가 없거나 발송에 실패하면 503 MAIL_UNAVAILABLE."""
    password_reset_service.request_reset(db, body.login_id)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(body: PasswordResetConfirmIn, db: DbSession) -> None:
    """링크의 토큰으로 비밀번호 바꾸기(인증 없음). 틀리거나 만료됐으면 400 RESET_TOKEN_INVALID."""
    password_reset_service.confirm_reset(db, body.token, body.new_password)
