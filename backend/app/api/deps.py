"""요청 단위 의존성(11.2 deps.py): DB 세션(11.7), 로그인 담당자(11.6), 관리자 확인, 서명 URL 검사(11.6).

Spring에 빗대면 get_db는 요청 하나를 감싸는 @Transactional 경계이고,
get_current_staff는 JWT 필터 + @AuthenticationPrincipal이다.
"""

import logging
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session, joinedload

from app.core.db import SessionLocal
from app.core.errors import AppError, ErrorCode
from app.core.security import TokenError, TokenExpiredError, decode_access_token, verify_signed_url
from app.models import Staff
from app.models.enums import StaffRole

logger = logging.getLogger(__name__)


def delete_created_files(db: Session) -> None:
    """이 요청이 만든 파일(db.info["created_files"])을 지운다(12.4). 요청이 실패했을 때 get_db가 부른다.

    DB에 키가 없는 파일이 남으면 파기에서 빠지므로(REQ-CM-002) 하나가 실패해도 나머지는 계속 지운다.
    """
    keys = list(db.info.get("created_files") or [])
    if not keys:
        return
    from app.storage.base import get_storage

    storage = get_storage()
    for key in keys:
        try:
            storage.delete(key)
        except Exception:
            logger.exception("failed to delete file created by a failed request: %s", key)
    db.info["created_files"] = []


def get_db() -> Iterator[Session]:
    """요청 하나에 세션 하나. 성공하면 commit, 예외면 rollback하고 이 요청이 만든 파일을 지운다(11.7)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        delete_created_files(db)
        raise
    finally:
        db.close()


# scope="function": 응답을 보내기 전에 commit한다. 기본값이면 commit이 실패해도 화면은 성공 응답을 받는다(11.7).
DbSession = Annotated[Session, Depends(get_db, scope="function")]


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise AppError(ErrorCode.AUTH_REQUIRED)
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AppError(ErrorCode.AUTH_REQUIRED)
    return token.strip()


def get_current_staff(db: DbSession, authorization: Annotated[str | None, Header()] = None) -> Staff:
    """Authorization: Bearer <token>에서 담당자를 꺼낸다.

    토큰이 없거나 잘못되면 401 AUTH_REQUIRED, 만료면 401 AUTH_EXPIRED, 계정이 막혔으면 403 ACCOUNT_DISABLED(15.1, 17.2).
    기관 ID는 토큰이 아니라 DB의 담당자 행에서 가져온다. 모든 조회는 이 담당자의 institution_id로 거른다(11.6).
    """
    token = _bearer_token(authorization)
    try:
        claims = decode_access_token(token)
    except TokenExpiredError:
        raise AppError(ErrorCode.AUTH_EXPIRED) from None
    except TokenError:
        raise AppError(ErrorCode.AUTH_REQUIRED) from None
    staff = db.get(Staff, claims.staff_id, options=[joinedload(Staff.institution)])
    if staff is None:
        raise AppError(ErrorCode.AUTH_REQUIRED)
    if not staff.is_active:
        raise AppError(ErrorCode.ACCOUNT_DISABLED)
    return staff


CurrentStaff = Annotated[Staff, Depends(get_current_staff)]


def require_admin(staff: CurrentStaff) -> Staff:
    """/api/v1/admin/*: role이 ADMIN이 아니면 403 FORBIDDEN(11.6)."""
    if staff.role != StaffRole.ADMIN:
        raise AppError(ErrorCode.FORBIDDEN)
    return staff


AdminStaff = Annotated[Staff, Depends(require_admin)]


# ---- 서명 URL로 여는 파일 (11.6, 15.2의 16·21번) ----


def check_file_link(path: str, exp: str | None, sig: str | None) -> None:
    """결과 영상·보고서 PDF처럼 로그인 토큰 없이 서명으로 여는 파일 API의 exp·sig 검사(11.6).

    path는 서명을 만들 때 쓴 /api/v1부터의 경로다. exp·sig가 없거나, exp가 10진수 정수가 아니거나, 서명이 틀리거나,
    exp가 지났으면 모두 403 FILE_LINK_EXPIRED다(15.6). 쿼리를 통째로 지운 주소도 "고친 주소"라 같은 답이다.
    서명은 기관 확인을 거친 조회 API만 만들므로, 맞으면 기관 확인을 다시 하지 않는다. DB를 보기 전에 부른다.
    """
    if exp is None or sig is None or not (exp.isascii() and exp.isdigit()):
        raise AppError(ErrorCode.FILE_LINK_EXPIRED)
    if not verify_signed_url(path, int(exp), sig):
        raise AppError(ErrorCode.FILE_LINK_EXPIRED)
