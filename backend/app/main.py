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

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import __version__
from app.api.routes import admin, auth, chart, dogs, health, history, images, reports, sessions, shots
from app.core.config import Settings, get_settings
from app.core.errors import ErrorCode, error_response, register_exception_handlers
from app.core.metrics import CONTENT_TYPE as METRICS_CONTENT_TYPE
from app.core.metrics import UNMATCHED, RequestMetrics

API_PREFIX = "/api/v1"
# 15.9: 지표는 /api/v1 아래가 아니라 루트다. nginx가 /api/만 넘기므로 밖에서는 닿지 않는다(v1.53)
METRICS_PATH = "/metrics"
REQUEST_ID_HEADER = "X-Request-ID"
LOG_FORMAT = "%(asctime)s %(levelname)s %(request_id)s %(message)s"
# INFO를 찍지 않을 바깥 라이브러리(11.8). httpx는 워커가 분석 API를 부를 때마다 한 줄씩 찍는다. weasyprint와 fontTools는
# 보고서 한 건마다 수십 줄을 찍고, 그중 글리프 목록은 보고서에 쓰인 글자(반려견 이름 등)를 드러낸다
QUIET_LOGGERS = ("httpx", "weasyprint", "fontTools")

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
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    _logging_ready = True


class RequestContextMiddleware:
    """요청마다: 요청 ID 발급 → 응답 헤더 X-Request-ID → 요청 로그 한 줄.

    예상하지 못한 오류는 500 INTERNAL_ERROR로 바꾼다(11.5).
    순수 ASGI 미들웨어라 async로 쓴다(11.3의 예외). 이 안에서 DB·파일 작업은 하지 않는다.
    로그에는 쿼리 문자열(반려견 이름 q, 서명 sig)을 남기지 않는다(11.8).
    """

    def __init__(self, app: ASGIApp, metrics: RequestMetrics | None = None) -> None:
        self.app = app
        self.metrics = metrics  # METRICS_ENABLED일 때만 있다(15.9)

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
            elapsed = time.perf_counter() - started
            request_logger.info("%s %s %d %.0fms", scope["method"], scope["path"], status_code, elapsed * 1000)
            if self.metrics is not None and scope["path"] != METRICS_PATH:  # 지표를 읽는 요청은 세지 않는다
                self.metrics.observe(scope["method"], _route_template(scope), status_code, elapsed)
            request_id_var.reset(token)


def _route_template(scope: Scope) -> str:
    """지표 라벨로 쓸 라우트 틀(`/api/v1/dogs/{dog_id}`). 실제 주소(ID)는 쓰지 않는다(11.8).

    라우터가 맞는 라우트를 찾으면 scope에 넣어 둔다. 없으면(404, 사전 요청 등) 모두 한 이름으로 센다.
    """
    route = scope.get("route")
    path = getattr(route, "path", None)
    if not isinstance(path, str):
        return UNMATCHED
    # include_router로 붙인 라우트는 틀에 접두어가 없다. 실제 주소가 /api/v1로 시작하면 붙여 준다
    if scope["path"].startswith(API_PREFIX) and not path.startswith(API_PREFIX):
        return f"{API_PREFIX}{path}"
    return path


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
    # 16절 METRICS_ENABLED: 켰을 때만 요청을 세고 루트 /metrics를 연다(15.9). 끄면 경로도 없다(404)
    metrics = RequestMetrics(__version__) if settings.METRICS_ENABLED else None
    app.add_middleware(RequestContextMiddleware, metrics=metrics)

    register_exception_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(dogs.router, prefix=API_PREFIX)
    app.include_router(chart.router, prefix=API_PREFIX)
    app.include_router(images.router, prefix=API_PREFIX)
    app.include_router(sessions.router, prefix=API_PREFIX)
    app.include_router(history.router, prefix=API_PREFIX)
    app.include_router(shots.router, prefix=API_PREFIX)
    app.include_router(reports.router, prefix=API_PREFIX)
    app.include_router(admin.router, prefix=API_PREFIX)
    if metrics is not None:

        @app.get(METRICS_PATH, tags=["운영"], include_in_schema=False)
        def read_metrics() -> Response:
            """요청 수와 처리 시간(Prometheus 텍스트). 인증이 없다. 내부망의 Prometheus만 읽는다(15.9)."""
            return Response(metrics.render(), media_type=METRICS_CONTENT_TYPE)

    return app


app = create_app()
