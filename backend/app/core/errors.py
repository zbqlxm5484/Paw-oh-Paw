"""오류 코드(명세 14절), AppError, 예외 처리기(11.5).

- 응답 오류는 모두 {"error": {"code", "message", "detail"}} 한 가지 모양이다(11.5).
- code는 14절 표의 값만 쓰고, message는 messages/ko.yaml에서 code로 찾는다(14.5). 코드에 문구를 직접 쓰지 않는다.
- FastAPI가 내는 입력 검사 오류(422)는 VALIDATION_ERROR로 바꾸고, 틀린 필드를 detail.fields에 담는다.
- 없는 주소·허용되지 않는 메서드·UUID 형식이 아닌 경로 ID는 NOT_FOUND다(11.5, 15.1).
- 예상하지 못한 오류를 500 INTERNAL_ERROR로 바꾸는 일은 main.py의 요청 미들웨어가 한다.

Spring에 빗대면 AppError는 업무 예외이고, handle_* 함수는 @ControllerAdvice의 @ExceptionHandler다.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    """14.1 응답 오류. HTTP 상태는 HTTP_STATUS에서 찾는다."""

    VIDEO_FORMAT = "VIDEO_FORMAT"
    VIDEO_UNREADABLE = "VIDEO_UNREADABLE"
    VIDEO_CODEC = "VIDEO_CODEC"
    VIDEO_PORTRAIT = "VIDEO_PORTRAIT"
    VIDEO_DURATION = "VIDEO_DURATION"
    BASELINE_INVALID = "BASELINE_INVALID"
    COMPARE_INVALID = "COMPARE_INVALID"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    LOGIN_FAILED = "LOGIN_FAILED"
    ACCOUNT_DISABLED = "ACCOUNT_DISABLED"
    FORBIDDEN = "FORBIDDEN"
    FILE_LINK_EXPIRED = "FILE_LINK_EXPIRED"
    NOT_FOUND = "NOT_FOUND"
    SESSION_CLOSED = "SESSION_CLOSED"
    SESSION_ALREADY_OPEN = "SESSION_ALREADY_OPEN"
    SESSION_EMPTY = "SESSION_EMPTY"
    SESSION_NOT_DONE = "SESSION_NOT_DONE"
    SHOT_IN_PROGRESS = "SHOT_IN_PROGRESS"
    SHOT_NOT_FAILED = "SHOT_NOT_FAILED"
    REPORT_IN_PROGRESS = "REPORT_IN_PROGRESS"
    VIDEO_TOO_LARGE = "VIDEO_TOO_LARGE"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.VIDEO_FORMAT: 400,
    ErrorCode.VIDEO_UNREADABLE: 400,
    ErrorCode.VIDEO_CODEC: 400,
    ErrorCode.VIDEO_PORTRAIT: 400,
    ErrorCode.VIDEO_DURATION: 400,
    ErrorCode.BASELINE_INVALID: 400,
    ErrorCode.COMPARE_INVALID: 400,
    ErrorCode.AUTH_REQUIRED: 401,
    ErrorCode.AUTH_EXPIRED: 401,
    ErrorCode.LOGIN_FAILED: 401,
    ErrorCode.ACCOUNT_DISABLED: 403,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.FILE_LINK_EXPIRED: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.SESSION_CLOSED: 409,
    ErrorCode.SESSION_ALREADY_OPEN: 409,
    ErrorCode.SESSION_EMPTY: 409,
    ErrorCode.SESSION_NOT_DONE: 409,
    ErrorCode.SHOT_IN_PROGRESS: 409,
    ErrorCode.SHOT_NOT_FAILED: 409,
    ErrorCode.REPORT_IN_PROGRESS: 409,
    ErrorCode.VIDEO_TOO_LARGE: 413,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.INTERNAL_ERROR: 500,
}


class FailReason(StrEnum):
    """14.2 처리 실패 사유. 응답이 아니라 fail_reason 컬럼에 남고, 상태 조회 때 Reason으로 나간다."""

    ANALYSIS_SUBMIT_FAILED = "ANALYSIS_SUBMIT_FAILED"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    ANALYSIS_TIMEOUT = "ANALYSIS_TIMEOUT"
    VIDEO_RENDER_FAILED = "VIDEO_RENDER_FAILED"
    AGGREGATION_FAILED = "AGGREGATION_FAILED"
    REPORT_CHECK_FAILED = "REPORT_CHECK_FAILED"
    REPORT_FAILED = "REPORT_FAILED"


class JudgeReason(StrEnum):
    """14.3 판정·제외·측정 불가 사유. validity_reason, exclude_reason, unmeasurable_reason에 넣는다."""

    MAT_NOT_FOUND = "MAT_NOT_FOUND"
    NO_VALID_PASS = "NO_VALID_PASS"
    FEW_VALID_PASSES = "FEW_VALID_PASSES"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    SITTING = "SITTING"
    TURNED = "TURNED"
    TOWARD_CAMERA = "TOWARD_CAMERA"
    PARTIAL_PASS = "PARTIAL_PASS"
    NORMALIZATION_LIMIT = "NORMALIZATION_LIMIT"
    NOT_SIDE_VIEW = "NOT_SIDE_VIEW"
    OCCLUDED = "OCCLUDED"
    OVERLAP = "OVERLAP"
    NO_DOG = "NO_DOG"
    GAIT_PACE = "GAIT_PACE"
    GAIT_OTHER = "GAIT_OTHER"
    NO_PASS_FOR_LIMB = "NO_PASS_FOR_LIMB"
    NOT_ENOUGH_CYCLES = "NOT_ENOUGH_CYCLES"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    UNKNOWN_REASON = "UNKNOWN_REASON"


class NoticeCode(StrEnum):
    """14.4 경고·안내. 오류가 아니라 응답의 warnings·notices·note에 Reason으로 담는다."""

    BELOW_MIN_SPEC = "BELOW_MIN_SPEC"
    ASPECT_NOT_16_9 = "ASPECT_NOT_16_9"
    RECOMMENDED_MET = "RECOMMENDED_MET"
    ONE_SIDE_ONLY = "ONE_SIDE_ONLY"
    NO_DATA = "NO_DATA"
    MODEL_CHANGED = "MODEL_CHANGED"
    RANGE_NOT_SET = "RANGE_NOT_SET"


ALL_CODE_ENUMS: tuple[type[StrEnum], ...] = (ErrorCode, FailReason, JudgeReason, NoticeCode)


def all_code_values() -> set[str]:
    """14절의 모든 코드. ko.yaml에 빠짐없이 있는지 테스트가 검사한다(14.5)."""
    return {member.value for enum_cls in ALL_CODE_ENUMS for member in enum_cls}


# ---- 문구 (14.5) ----


class _KeepPlaceholder(dict[str, Any]):
    """detail에 없는 자리는 {이름} 그대로 둔다. 문구 파일의 자리표시자 오타가 500으로 번지지 않게 한다."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


@lru_cache
def _load_messages(path: str) -> dict[str, str]:
    # 설정 파일이라 StorageService를 거치지 않는다(11.3은 저장소 파일 얘기다). 인코딩은 꼭 적는다.
    with Path(path).open(encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    return {str(key): str(value) for key, value in data.items()}


def messages() -> dict[str, str]:
    """코드 → 문구 사전. MESSAGES_FILE(16절)을 처음 쓸 때 한 번 읽는다."""
    return _load_messages(get_settings().MESSAGES_FILE)


def message_for(code: str, detail: dict[str, Any] | None = None) -> str:
    """code의 문구. {max_mb}처럼 중괄호 자리는 detail 값으로 채운다(14.5). 문구가 없으면 코드를 그대로 돌려준다."""
    template = messages().get(code)
    if template is None:
        logger.error("messages file has no text for code %s", code)
        return code
    return template.format_map(_KeepPlaceholder(detail or {}))


def reason_payload(code: str) -> dict[str, str]:
    """15.1 사유 객체 Reason: {"code", "message"}."""
    return {"code": code, "message": message_for(code)}


# ---- 오류 응답 (11.5) ----


class AppError(Exception):
    """업무 규칙 위반. code는 14.1의 값, detail은 응답의 detail(없으면 None). HTTP 상태는 code로 정해진다."""

    def __init__(self, code: ErrorCode, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code.value)
        self.code = code
        self.detail = detail

    @property
    def status_code(self) -> int:
        return HTTP_STATUS[self.code]


def error_body(code: ErrorCode, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    """11.5 오류 응답 본문. detail이 없으면 null이다."""
    return {"error": {"code": code.value, "message": message_for(code.value, detail), "detail": detail}}


def error_response(
    code: ErrorCode, detail: dict[str, Any] | None = None, *, status_code: int | None = None
) -> JSONResponse:
    """오류 응답. status_code를 주지 않으면 14.1 표의 HTTP 상태를 쓴다."""
    return JSONResponse(status_code=status_code or HTTP_STATUS[code], content=error_body(code, detail))


# ---- 예외 처리기 ----

_LOCATION_PREFIXES = ("body", "query", "path", "header", "cookie")


def _field_name(loc: tuple[Any, ...]) -> str:
    """11.5: Pydantic 오류 위치에서 첫 칸(body·query·path)을 빼고 나머지를 '.'로 잇는다."""
    parts = [str(part) for part in loc]
    if parts and parts[0] in _LOCATION_PREFIXES:
        parts = parts[1:]
    if parts:
        return ".".join(parts)
    # TODO(질문: 본문 전체가 빠진 경우처럼 남는 칸이 없으면 11.5 규칙대로는 빈 문자열이다.
    #           지금은 첫 칸 이름("body")을 둔다)
    return str(loc[0]) if loc else ""


def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.code, exc.detail)


def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI의 입력 검사 오류 → 422 VALIDATION_ERROR. 경로(path)의 ID가 UUID 형식이 아니면 404 NOT_FOUND(15.1)."""
    errors = exc.errors()
    if errors and all(error["loc"] and error["loc"][0] == "path" for error in errors):
        return error_response(ErrorCode.NOT_FOUND)
    fields = [{"field": _field_name(tuple(error["loc"])), "type": error["type"]} for error in errors]
    return error_response(ErrorCode.VALIDATION_ERROR, {"fields": fields})


# FastAPI·Starlette가 스스로 내는 HTTPException의 상태 → 14.1 코드. 업무 코드는 HTTPException 대신 AppError를 낸다.
_HTTP_EXCEPTION_CODES: dict[int, ErrorCode] = {
    404: ErrorCode.NOT_FOUND,  # 없는 주소(11.5)
    405: ErrorCode.NOT_FOUND,  # 허용되지 않는 메서드: HTTP 405 그대로, code는 NOT_FOUND(11.5)
    401: ErrorCode.AUTH_REQUIRED,
    403: ErrorCode.FORBIDDEN,
}


def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    code = _HTTP_EXCEPTION_CODES.get(exc.status_code)
    if code is None:
        logger.error("unexpected HTTPException %s", exc.status_code)
        return error_response(ErrorCode.INTERNAL_ERROR)
    return error_response(code, status_code=exc.status_code)


def register_exception_handlers(app: FastAPI) -> None:
    """main.py가 앱을 만들 때 부른다."""
    app.add_exception_handler(AppError, handle_app_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, handle_http_exception)  # type: ignore[arg-type]
