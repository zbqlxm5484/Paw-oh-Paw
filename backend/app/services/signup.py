"""디바이스 코드 확인·회원가입(11.6, 12.5, 13.5, 15.4 verify·signup, BE-22).

Spring에 빗대면 가입 서비스다. 첫 인자는 DB 세션이고 flush()까지만 한다.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_cache import AuthStaff, auth_cache
from app.core.db import UNIQUE_VIOLATION, db_error_code
from app.core.errors import AppError, ErrorCode
from app.core.security import hash_password
from app.models import Staff
from app.models.enums import StaffRole
from app.schemas.auth import DeviceCodeVerifyOut, InstitutionBriefOut, SignupIn
from app.services.auth import snapshot_of
from app.services.device_codes import find_usable_code


def verify_code(db: Session, raw: str) -> DeviceCodeVerifyOut:
    """코드가 쓸 수 있는지 보고 그 기관을 돌려준다(15.4). DB를 바꾸지 않는다. 계정 수 상한은 없다(v1.32)."""
    code = find_usable_code(db, raw)
    return DeviceCodeVerifyOut(institution=InstitutionBriefOut(id=code.institution_id, name=code.institution.name))


def signup(db: Session, data: SignupIn) -> AuthStaff:
    """가입(15.4 순서): 코드 검사 → 아이디 중복 → CLIENT 계정 생성 → 스냅샷.

    입력 규칙(422)은 SignupIn이 먼저 본다. bcrypt는 DB 작업 전에 끝낸다(트랜잭션을 길게 잡지 않는다).
    같은 아이디로 동시에 가입해 uq_staff_login에 걸리면 409 LOGIN_ID_TAKEN이다.
    """
    password_hash = hash_password(data.password)
    code = find_usable_code(db, data.code)
    if db.scalar(select(Staff.id).where(Staff.login_id == data.login_id)) is not None:
        raise AppError(ErrorCode.LOGIN_ID_TAKEN)

    terms = data.terms
    staff = Staff(
        institution_id=code.institution_id,
        login_id=data.login_id,
        password_hash=password_hash,
        name=data.name,
        role=StaffRole.CLIENT.value,
        device_code_id=code.id,
        email=data.email,
        # 약관 동의 기록(13.5). 시각은 DB 시각이다. 화면이 terms를 보내지 않으면 남기지 않는다
        terms_version=terms.version if terms else None,
        terms_agreed_at=func.now() if terms else None,
        marketing_agreed=bool(terms and terms.marketing),
    )
    db.add(staff)
    try:
        db.flush()
    except IntegrityError as error:
        if db_error_code(error) == UNIQUE_VIOLATION:
            raise AppError(ErrorCode.LOGIN_ID_TAKEN) from None
        raise
    db.refresh(staff)
    snapshot = snapshot_of(staff)
    auth_cache.put(snapshot)
    return snapshot
