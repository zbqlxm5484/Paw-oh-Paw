"""로그인(11.6, 13.4, 15.4)."""

from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session, contains_eager

from app.core.errors import AppError, ErrorCode
from app.core.security import hash_password, verify_password
from app.models import Institution, Staff


@lru_cache
def _dummy_hash() -> str:
    """없는 아이디에도 bcrypt 비교를 한 번 해서, 응답 시간으로 아이디가 있는지 알 수 없게 한다(15.4)."""
    return hash_password("dummy-password-for-constant-time")


def authenticate(db: Session, *, institution_code: str, login_id: str, password: str) -> Staff:
    """기관 코드·아이디·비밀번호를 확인하고 담당자를 돌려준다.

    하나라도 틀리면 401 LOGIN_FAILED 하나로만 답한다(13.4). 비밀번호까지 맞고 is_active가 FALSE면 403 ACCOUNT_DISABLED.
    기관 코드와 아이디는 대소문자를 구분해 입력 그대로 비교한다.
    """
    staff = db.scalars(
        select(Staff)
        .join(Institution, Staff.institution_id == Institution.id)
        .where(Institution.code == institution_code, Staff.login_id == login_id)
        .options(contains_eager(Staff.institution))
    ).one_or_none()
    if staff is None:
        verify_password(password, _dummy_hash())
        raise AppError(ErrorCode.LOGIN_FAILED)
    if not verify_password(password, staff.password_hash):
        raise AppError(ErrorCode.LOGIN_FAILED)
    if not staff.is_active:
        raise AppError(ErrorCode.ACCOUNT_DISABLED)
    return staff
