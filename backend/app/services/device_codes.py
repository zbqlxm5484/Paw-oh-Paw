"""디바이스 코드(11.6, 12.5, 13.5): 글자 규칙, 정리, 발급, 쓸 수 있는 코드 찾기, 활성 계정 수(목록 표시용).

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


def mask_code(code: str) -> str:
    """화면 모양에서 첫 묶음과 끝 묶음만 남기고 가운데를 *로 가린다(15.4 측정 기기 정보, v1.46).

    코드는 가입에 쓰는 값이라 기관 계정에게도 통째로 보여 주지 않는다. 네 묶음보다 짧으면 전부 가린다.
    """
    groups = [code[i : i + CODE_GROUP] for i in range(0, len(code), CODE_GROUP)]
    shown = {0, len(groups) - 1} if len(groups) >= 4 else set()
    return "-".join(group if i in shown else "*" * len(group) for i, group in enumerate(groups))


def usable_code_of(db: Session, institution_id: uuid.UUID) -> DeviceCode | None:
    """기관의 쓸 수 있는(회수하지 않은) 코드. 기관마다 하나이고(uq_device_code_active) 없으면 None이다."""
    return db.scalars(
        select(DeviceCode).where(DeviceCode.institution_id == institution_id, DeviceCode.revoked_at.is_(None))
    ).one_or_none()


def active_accounts(db: Session, device_code_id: uuid.UUID) -> int:
    """이 코드로 가입했고 is_active인 계정 수(12.5). 관리자 목록에 보여 줄 뿐이고 가입을 막지 않는다."""
    return int(
        db.scalar(
            select(func.count())
            .select_from(Staff)
            .where(Staff.device_code_id == device_code_id, Staff.is_active.is_(True))
        )
        or 0
    )


def find_usable_code(db: Session, raw: str) -> DeviceCode:
    """가입에 쓸 수 있는 코드 행(15.4 verify).

    형식 오류·없음·회수됨·기관 계약 만료는 모두 404 DEVICE_CODE_INVALID 하나다. 형식이 틀리면 DB를 보지 않는다.
    계정 수 상한이 없어 코드 행을 잠그지 않는다(v1.32).
    """
    normalized = normalize_code(raw)
    if normalized is None:
        raise AppError(ErrorCode.DEVICE_CODE_INVALID)
    code = db.scalars(select(DeviceCode).where(DeviceCode.code == normalized)).one_or_none()
    if code is None or code.revoked_at is not None:
        raise AppError(ErrorCode.DEVICE_CODE_INVALID)
    ends_at = code.institution.contract_ends_at
    if ends_at is not None and ends_at < today_local():
        raise AppError(ErrorCode.DEVICE_CODE_INVALID)
    return code
