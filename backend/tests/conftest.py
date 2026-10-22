"""테스트 공통 준비.

- .env(또는 환경 변수)의 TEST_DATABASE_URL로 테스트한다. 앱 코드도 이 DB를 보도록 DATABASE_URL을 바꿔 둔다.
- 시작할 때 테스트 DB의 public 스키마를 지우고 alembic upgrade head로 테이블을 새로 만든다.
  실수로 운영 DB를 지우지 않도록 DB 이름이 _test로 끝나야만 실행한다.
- db 픽스처: 테스트 하나가 끝나면 그 안에서 한 일을 모두 되돌리는 DB 세션.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
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

    from app.core.config import get_db_settings
    from app.core.db import get_engine

    get_db_settings.cache_clear()
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
