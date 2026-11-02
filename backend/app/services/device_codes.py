"""디바이스 코드(11.6, 12.5, 13.5): 글자 규칙, 정리, 발급, 쓸 수 있는 코드 찾기, 활성 계정 수.

가입(services/signup.py)과 크림오프 관리자 API(services/admin.py)가 함께 쓴다.
"""

from __future__ import annotations

import secrets
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dates import today_local
from app.core.errors import AppError, ErrorCode
from app.models import DeviceCode, Staff

# 13.5: 혼동되는 0·O·1·I·L을 뺀 32종. 20자 = 100비트라 요청 횟수 제한 없이도 추측이 안 된다(15.10)
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 20
# 화면 표시 XXXXX-XXXXX-XXXXX-XXXXX
CODE_GROUP = 5


def normalize_code(raw: str) -> str | None:
    """하이픈·공백을 지우고 대문자로. 20자가 아니거나 코드 글자가 아닌 것이 있으면 None(13.5)."""
    cleaned = raw.replace("-", "").replace(" ", "").upper()
    if len(cleaned) != CODE_LENGTH or any(ch not in CODE_ALPHABET for ch in cleaned):
        return None
    return cleaned


def generate_code() -> str:
    """새 코드 20자(하이픈 없이 저장하는 모양)."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def format_code(code: str) -> str:
    """저장 모양 → 화면 모양(XXXXX-XXXXX-XXXXX-XXXXX)."""
    return "-".join(code[i : i + CODE_GROUP] for i in range(0, len(code), CODE_GROUP))


def active_accounts(db: Session, device_code_id: uuid.UUID) -> int:
    """이 코드로 가입했고 is_active인 계정 수(12.5). 중지한 계정은 자리를 돌려준다."""
    return int(
        db.scalar(
            select(func.count())
            .select_from(Staff)
            .where(Staff.device_code_id == device_code_id, Staff.is_active.is_(True))
        )
        or 0
    )


def remaining_accounts(db: Session, code: DeviceCode) -> int:
    """남은 자리 = max_accounts − 활성 계정 수. 상한을 활성 수보다 낮게 내렸으면 0이다(음수를 내지 않는다)."""
    return max(code.max_accounts - active_accounts(db, code.id), 0)


def find_usable_code(db: Session, raw: str, *, for_update: bool = False) -> DeviceCode:
    """가입에 쓸 수 있는 코드 행(15.4 verify).

    형식 오류·없음·회수됨·기관 계약 만료는 모두 404 DEVICE_CODE_INVALID 하나다. 형식이 틀리면 DB를 보지 않는다.
    for_update면 코드 행만 잠근다(12.5 활성 계정 수. joinedload 없이, 11.7).
    """
    normalized = normalize_code(raw)
    if normalized is None:
        raise AppError(ErrorCode.DEVICE_CODE_INVALID)
    stmt = select(DeviceCode).where(DeviceCode.code == normalized)
    if for_update:
        stmt = stmt.with_for_update()
    code = db.scalars(stmt).one_or_none()
    if code is None or code.revoked_at is not None:
        raise AppError(ErrorCode.DEVICE_CODE_INVALID)
    ends_at = code.institution.contract_ends_at
    if ends_at is not None and ends_at < today_local():
        raise AppError(ErrorCode.DEVICE_CODE_INVALID)
    return code
