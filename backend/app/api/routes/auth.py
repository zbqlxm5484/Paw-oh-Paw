"""/api/v1/auth: 로그인·내 정보(BE-01), 디바이스 코드 확인·회원가입(BE-22) (15.4)."""

from fastapi import APIRouter, status

from app.api.deps import CurrentStaffAny, DbSession
from app.core.auth_cache import AuthStaff
from app.core.errors import AppError, ErrorCode
from app.core.security import create_access_token
from app.schemas.auth import DeviceCodeVerifyIn, DeviceCodeVerifyOut, LoginIn, SignupIn, StaffOut, TokenOut
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
def me(staff: CurrentStaffAny, db: DbSession) -> StaffOut:
    """내 정보. 계약이 끝난 CLIENT(GUEST)도 된다. 캐시를 거치지 않고 DB를 읽어 캐시를 갱신한다(11.6)."""
    fresh = refresh_snapshot(db, staff.id)
    if fresh is None:
        raise AppError(ErrorCode.AUTH_REQUIRED)
    if not fresh.is_active:
        raise AppError(ErrorCode.ACCOUNT_DISABLED)
    return staff_out(fresh)
