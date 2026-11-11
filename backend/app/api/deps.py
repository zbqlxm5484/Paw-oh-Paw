"""요청 단위 의존성(11.2 deps.py): DB 세션(11.7), 로그인 담당자·계약 검사·역할 확인(11.6), 서명 URL 검사(11.6),
인쇄 토큰으로도 열리는 조회(11.6 get_reader).

Spring에 빗대면 get_db는 요청 하나를 감싸는 @Transactional 경계이고,
get_current_staff는 JWT 필터 + @AuthenticationPrincipal, require_contract는 isAccountNonExpired() 검사,
require_admin·require_creamoff는 @PreAuthorize("hasRole(...)")다.
"""

import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClient, HttpAnalysisClient, build_analysis_client
from app.core.auth_cache import AuthStaff, auth_cache
from app.core.db import SessionLocal
from app.core.errors import AppError, ErrorCode
from app.core.security import (
    TokenError,
    TokenExpiredError,
    decode_access_token,
    decode_print_token,
    verify_signed_url,
)
from app.models.enums import EffectiveRole, StaffRole
from app.services.auth import load_snapshot

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


def get_current_staff(db: DbSession, authorization: Annotated[str | None, Header()] = None) -> AuthStaff:
    """Authorization: Bearer <token>에서 담당자 스냅샷을 꺼낸다(11.6 요청마다 하는 검사 ①~③).

    토큰이 없거나 잘못되면 401 AUTH_REQUIRED, 만료면 401 AUTH_EXPIRED, 계정이 막혔으면 403 ACCOUNT_DISABLED.
    기관 ID·역할은 토큰이 아니라 스냅샷(캐시, 없으면 DB의 담당자 + 기관 행)에서 가져온다.
    캐시에 있으면 DB를 읽지 않는다.
    계약 검사(④)는 require_contract가 한다. GET /auth/me만 이 함수를 그대로(CurrentStaffAny) 쓴다.
    """
    token = _bearer_token(authorization)
    try:
        claims = decode_access_token(token)
    except TokenExpiredError:
        raise AppError(ErrorCode.AUTH_EXPIRED) from None
    except TokenError:
        raise AppError(ErrorCode.AUTH_REQUIRED) from None
    snapshot = auth_cache.get(claims.staff_id)
    if snapshot is None:
        snapshot = load_snapshot(db, claims.staff_id)
        if snapshot is None:
            raise AppError(ErrorCode.AUTH_REQUIRED)
        auth_cache.put(snapshot)
    if not snapshot.is_active:
        raise AppError(ErrorCode.ACCOUNT_DISABLED)
    return snapshot


CurrentStaffAny = Annotated[AuthStaff, Depends(get_current_staff)]


def require_contract(staff: CurrentStaffAny) -> AuthStaff:
    """④ 계약이 끝난 CLIENT(effective_role GUEST)는 403 CONTRACT_EXPIRED(11.6). ADMIN·STAFF는 계약을 보지 않는다."""
    if staff.effective_role == EffectiveRole.GUEST:
        raise AppError(ErrorCode.CONTRACT_EXPIRED)
    return staff


CurrentStaff = Annotated[AuthStaff, Depends(require_contract)]


def require_admin(staff: CurrentStaff) -> AuthStaff:
    """/api/v1/admin/* 쓰기: role이 ADMIN이 아니면 403 FORBIDDEN(11.6)."""
    if staff.role != StaffRole.ADMIN:
        raise AppError(ErrorCode.FORBIDDEN)
    return staff


def require_creamoff(staff: CurrentStaff) -> AuthStaff:
    """/api/v1/admin/* 조회: 크림오프 쪽(ADMIN·STAFF)이 아니면 403 FORBIDDEN(11.6)."""
    if staff.role not in (StaffRole.ADMIN, StaffRole.STAFF):
        raise AppError(ErrorCode.FORBIDDEN)
    return staff


AdminStaff = Annotated[AuthStaff, Depends(require_admin)]
CreamoffStaff = Annotated[AuthStaff, Depends(require_creamoff)]


# ---- 인쇄 토큰으로도 열리는 조회 (11.6, 15.2의 2·3·8·9·17·18·22·55·62번) ----


@dataclass(frozen=True)
class Reader:
    """조회를 부른 쪽. 로그인한 담당자든 인쇄 토큰이든 그 기관의 것을 읽는다(11.6).

    인쇄 토큰은 그 기관의 읽기 전용이다: 이 Reader를 받는 GET 라우트만 열리고, 로그인한 CLIENT가 읽는 것과 같은
    것을 읽는다(다른 기관·휴지통의 반려견은 404). 쓰기 라우트는 CurrentStaff를 받으므로 인쇄 토큰으로는 401이다.
    """

    institution_id: uuid.UUID
    is_print: bool = False


def _print_reader(token: str) -> Reader | None:
    """인쇄 토큰이면 그 기관의 Reader, 아니면 None. 만료된 인쇄 토큰은 401 AUTH_EXPIRED다.

    인쇄 토큰은 서명 키가 달라 로그인 토큰과 섞이지 않는다. 서버가 만든 것이라 계정·계약 상태를 보지 않고 DB도
    읽지 않는다.
    """
    try:
        claims = decode_print_token(token)
    except TokenExpiredError:
        raise AppError(ErrorCode.AUTH_EXPIRED) from None
    except TokenError:
        return None
    return Reader(institution_id=claims.institution_id, is_print=True)


def get_reader(db: DbSession, authorization: Annotated[str | None, Header()] = None) -> Reader:
    """Authorization의 토큰이 인쇄 토큰이면 그 기관의 Reader, 아니면 로그인 담당자(계약 검사 포함)의 Reader."""
    reader = _print_reader(_bearer_token(authorization))
    if reader is not None:
        return reader
    staff = require_contract(get_current_staff(db, authorization))
    return Reader(institution_id=staff.institution_id)


def get_me_caller(db: DbSession, authorization: Annotated[str | None, Header()] = None) -> AuthStaff | Reader:
    """GET /auth/me를 부른 쪽: 인쇄 토큰이면 Reader, 아니면 로그인 담당자(계약 검사 없음. GUEST도 된다)."""
    reader = _print_reader(_bearer_token(authorization))
    if reader is not None:
        return reader
    return get_current_staff(db, authorization)


# 인쇄 토큰도 받는 GET 라우트가 쓴다. 나머지 라우트는 CurrentStaff다
ReadCaller = Annotated[Reader, Depends(get_reader)]
MeCaller = Annotated[AuthStaff | Reader, Depends(get_me_caller)]


def get_analysis_client() -> Iterator[AnalysisClient]:
    """분석 API 사본을 지울 때 쓴다: 자료 파기(15.9), 촬영 삭제·다시 분석·측정 취소(15.6).

    테스트는 dependency_overrides로 바꿔 끼운다.
    """
    client = build_analysis_client()
    try:
        yield client
    finally:
        if isinstance(client, HttpAnalysisClient):
            client.close()


AnalysisClientDep = Annotated[AnalysisClient, Depends(get_analysis_client)]


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
