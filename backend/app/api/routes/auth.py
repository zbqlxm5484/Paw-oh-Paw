"""POST /api/v1/auth/login, GET /api/v1/auth/me (15.4, BE-01)."""

from fastapi import APIRouter

from app.api.deps import CurrentStaff, DbSession
from app.core.security import create_access_token
from app.schemas.auth import LoginIn, StaffOut, TokenOut
from app.services.auth import authenticate

router = APIRouter(prefix="/auth", tags=["인증"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: DbSession) -> TokenOut:
    staff = authenticate(db, institution_code=body.institution_code, login_id=body.login_id, password=body.password)
    token, expires_at = create_access_token(staff_id=staff.id, institution_id=staff.institution_id, role=staff.role)
    return TokenOut(access_token=token, expires_at=expires_at, staff=StaffOut.model_validate(staff))


@router.get("/me", response_model=StaffOut)
def me(staff: CurrentStaff) -> StaffOut:
    return StaffOut.model_validate(staff)
