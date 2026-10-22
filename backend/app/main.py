"""앱 생성(11.2 main.py): 설정 읽기, 로그, CORS, 요청 ID·요청 로그 미들웨어, 오류 처리기, 라우터.

실행:  uvicorn app.main:app --no-access-log
(접근 로그는 끈다(11.8). 대신 아래 미들웨어가 메서드, 쿼리를 뺀 경로, 상태 코드, 처리 시간, 요청 ID만 남긴다.)

Spring에 빗대면 이 파일이 @SpringBootApplication이고, CORS는 WebMvcConfigurer, 요청 ID 미들웨어는 서블릿 필터다.
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import __version__
from app.api.routes import auth, health
from app.core.config import Settings, get_settings
from app.core.errors import ErrorCode, error_response, register_exception_handlers

API_PREFIX = "/api/v1"
REQUEST_ID_HEADER = "X-Request-ID"
LOG_FORMAT = "%(asctime)s %(levelname)s %(request_id)s %(message)s"

# 지금 처리 중인 요청의 ID. 라우트·서비스가 남기는 모든 로그 줄에 붙는다(11.8). 요청 밖에서는 "-".
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
request_logger = logging.getLogger("app.request")

_logging_ready = False


def configure_logging(level: str) -> None:
    """표준 logging(11.8): 한 줄에 시각, 레벨, 요청 ID, 메시지. 여러 번 불러도 핸들러는 하나만 둔다."""
    global _logging_ready
    root = logging.getLogger()
    root.setLevel(level.upper())
    if _logging_ready:
        return

    make_record = logging.getLogRecordFactory()

    def make_record_with_request_id(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = make_record(*args, **kwargs)
        record.request_id = request_id_var.get()
        return record

    logging.setLogRecordFactory(make_record_with_request_id)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S"))
    root.addHandler(handler)
    _logging_ready = True


class RequestContextMiddleware:
    """요청마다: 요청 ID 발급 → 응답 헤더 X-Request-ID → 요청 로그 한 줄.

    예상하지 못한 오류는 500 INTERNAL_ERROR로 바꾼다(11.5).
    순수 ASGI 미들웨어라 async로 쓴다(11.3의 예외). 이 안에서 DB·파일 작업은 하지 않는다.
    로그에는 쿼리 문자열(반려견 이름 q, 서명 sig)을 남기지 않는다(11.8).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex  # 16진수 32자(11.8)
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_started = True
                message.setdefault("headers", [])
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            # 자세한 내용은 로그에만 남기고, 화면에는 500 INTERNAL_ERROR만 보낸다(11.5)
            request_logger.exception("unhandled error")
            if response_started:
                raise
            await error_response(ErrorCode.INTERNAL_ERROR)(scope, receive, send_with_request_id)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            request_logger.info("%s %s %d %.0fms", scope["method"], scope["path"], status_code, elapsed_ms)
            request_id_var.reset(token)


def create_app(settings: Settings | None = None) -> FastAPI:
    """앱을 만든다. 필수 환경 변수가 비면 SettingsError가 나서 서버가 켜지지 않고 어느 값이 문제인지 알려 준다(16절)."""
    settings = settings or get_settings()
    configure_logging(settings.LOG_LEVEL)

    # 16절 API_DOCS_ENABLED: 시험 화면(/docs·/redoc)과 생성 명세(/openapi.json)는 개발 환경에서만 연다.
    # 배포에서는 끄고, 기업·화면과 맞춘 공식 명세는 docs/openapi.yaml 하나만 둔다(64 MR 리뷰).
    docs_enabled = settings.API_DOCS_ENABLED
    app = FastAPI(
        title="크림오프 팀 서비스 API",
        version=__version__,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    # 미들웨어는 나중에 더한 것이 바깥쪽이다. 요청 ID를 가장 바깥에 두어 CORS 사전 요청(OPTIONS)에도 ID와 로그가 붙는다.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,  # 16절: 목록의 주소만 허용한다. *는 설정에서부터 막혀 있다
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    return app


app = create_app()
