"""POST /api/v1/auth/login, GET /api/v1/auth/me (15.4, BE-01)."""

from fastapi import APIRouter

from app.api.deps import CurrentStaffAny, DbSession
from app.core.errors import AppError, ErrorCode
from app.core.security import create_access_token
from app.schemas.auth import LoginIn, StaffOut, TokenOut
from app.services.auth import authenticate, refresh_snapshot, staff_out

router = APIRouter(prefix="/auth", tags=["인증"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: DbSession) -> TokenOut:
    staff = authenticate(db, login_id=body.login_id, password=body.password)
    token, expires_at = create_access_token(staff_id=staff.id, institution_id=staff.institution_id, role=staff.role)
    return TokenOut(access_token=token, expires_at=expires_at, staff=staff_out(staff))


@router.get("/me", response_model=StaffOut)
def me(staff: CurrentStaffAny, db: DbSession) -> StaffOut:
    """내 정보. 계약이 끝난 CLIENT(GUEST)도 된다. 캐시를 거치지 않고 DB를 읽어 캐시를 갱신한다(11.6)."""
    fresh = refresh_snapshot(db, staff.id)
    if fresh is None:
        raise AppError(ErrorCode.AUTH_REQUIRED)
    if not fresh.is_active:
        raise AppError(ErrorCode.ACCOUNT_DISABLED)
    return staff_out(fresh)
