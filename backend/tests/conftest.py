"""테스트 공통 준비.

- .env(또는 환경 변수)의 TEST_DATABASE_URL로 테스트한다. 앱 코드도 이 DB를 보도록 DATABASE_URL을 바꿔 둔다.
- 시작할 때 테스트 DB의 public 스키마를 지우고 alembic upgrade head로 테이블을 새로 만든다.
  실수로 운영 DB를 지우지 않도록 DB 이름이 _test로 끝나야만 실행한다.
- db 픽스처: 테스트 하나가 끝나면 그 안에서 한 일을 모두 되돌리는 DB 세션.
- client 픽스처: FastAPI 앱에 요청을 보내는 클라이언트(Spring의 MockMvc).
  오류 형식을 확인할 테스트 전용 라우트가 붙어 있다.
"""

import logging
import os
import uuid
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine, make_url, pool, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
TABLES = (
    "institution",
    "staff",
    "dog",
    "measure_session",
    "shot",
    "walk_pass",
    "session_metric",
    "report",
    "purge_log",
)


class _TestDbSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", env_ignore_empty=True)

    TEST_DATABASE_URL: str | None = None


def pytest_configure(config: pytest.Config) -> None:
    url = _TestDbSettings().TEST_DATABASE_URL
    if not url:
        raise pytest.UsageError("TEST_DATABASE_URL이 없습니다. .env에 테스트용 DB 주소를 적으세요(.env.example 참고)")
    database = make_url(url).database or ""
    if not database.endswith("_test"):
        raise pytest.UsageError(
            f"TEST_DATABASE_URL의 DB 이름이 _test로 끝나야 합니다(지금: {database}). 테스트가 이 DB의 테이블을 지웁니다"
        )
    # 환경 변수가 .env보다 먼저 읽히므로, 앱 코드(get_db_settings, SessionLocal)도 테스트 DB를 본다.
    os.environ["DATABASE_URL"] = url
    # API 서버 설정의 필수 값(16절). 테스트에서만 쓰는 값이고, 셸에 이미 있으면 그 값을 쓴다.
    os.environ.setdefault("JWT_SECRET", "test-jwt-secret-" + "0" * 24)
    os.environ.setdefault("FILE_URL_SECRET", "test-file-url-secret-" + "1" * 24)

    from app.core.config import get_db_settings, get_settings
    from app.core.db import get_engine

    get_db_settings.cache_clear()
    get_settings.cache_clear()
    get_engine.cache_clear()


def alembic_config() -> Config:
    return Config(str(ROOT / "alembic.ini"))


@pytest.fixture(scope="session")
def migrated() -> None:
    """테스트 DB를 비우고 마이그레이션으로 테이블을 새로 만든다. 테스트 실행마다 한 번."""
    url = os.environ["DATABASE_URL"]
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    command.upgrade(alembic_config(), "head")


@pytest.fixture(scope="session")
def engine(migrated: None) -> Engine:
    from app.core.db import get_engine

    return get_engine()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """테스트 하나용 DB 세션. 안에서 commit해도 테스트가 끝나면 모두 되돌린다."""
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def clean_tables(engine: Engine) -> Iterator[None]:
    """정말로 commit하는 테스트(스크립트 실행 등)가 끝나면 모든 행을 지운다."""
    yield
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))


# ---- API 테스트 ----


class DogIn(BaseModel):
    """422 변환을 확인하기 위한 본문 모델. 실제 반려견 schema는 작업 단위 4에서 만든다."""

    weight_kg: Decimal = Field(le=200)
    name: str


def _test_router() -> APIRouter:
    """오류 형식(11.5)을 확인하려고 일부러 오류를 내는 라우트들. 실제 API에는 없다."""
    from app.core.errors import AppError, ErrorCode

    router = APIRouter(prefix="/_test")

    @router.post("/dogs")
    def create_dog(body: DogIn) -> dict[str, str]:
        return {"name": body.name}

    @router.get("/items/{item_id}")
    def get_item(item_id: uuid.UUID) -> dict[str, str]:
        return {"id": str(item_id)}

    @router.get("/search")
    def search(page: int = 1) -> dict[str, int]:
        return {"page": page}

    @router.get("/conflict")
    def conflict() -> None:
        raise AppError(ErrorCode.SESSION_ALREADY_OPEN, {"session_id": "3f2a9c1e-5b7d-4e8a-9c21-7d4e5f6a8b90"})

    @router.get("/forbidden")
    def forbidden() -> None:
        raise AppError(ErrorCode.FORBIDDEN)

    @router.get("/too-large")
    def too_large() -> None:
        raise AppError(ErrorCode.VIDEO_TOO_LARGE, {"max_mb": 100})

    @router.get("/boom")
    def boom() -> None:
        raise RuntimeError("예상하지 못한 오류 (테스트)")

    @router.get("/log")
    def log_line() -> dict[str, bool]:
        logging.getLogger("app.test").info("inside route")
        return {"ok": True}

    return router


@pytest.fixture
def client() -> Iterator[TestClient]:
    """앱 + 테스트 전용 라우트. 앱 import는 pytest_configure가 환경 변수를 채운 뒤여야 해서 여기서 한다."""
    from app.main import API_PREFIX, create_app

    app = create_app()
    app.include_router(_test_router(), prefix=API_PREFIX)
    with TestClient(app) as client:
        yield client
