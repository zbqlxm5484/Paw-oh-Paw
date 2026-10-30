"""테스트 공통 준비.

- .env(또는 환경 변수)의 TEST_DATABASE_URL로 테스트한다. 앱 코드도 이 DB를 보도록 DATABASE_URL을 바꿔 둔다.
- 시작할 때 테스트 DB의 public 스키마를 지우고 alembic upgrade head로 테이블을 새로 만든다.
  실수로 운영 DB를 지우지 않도록 DB 이름이 _test로 끝나야만 실행한다.
- db 픽스처: 테스트 하나가 끝나면 그 안에서 한 일을 모두 되돌리는 DB 세션.
- client 픽스처: FastAPI 앱에 요청을 보내는 클라이언트(Spring의 MockMvc). 앱의 get_db를 위 db 세션으로 바꿔 끼워서
  API가 commit해도 테스트가 끝나면 전부 되돌아간다. 오류 형식을 확인할 테스트 전용 라우트가 붙어 있다.
- staff·auth_headers 픽스처: 기관 하나와 활성 담당자 하나, 그 담당자의 Bearer 헤더.
"""

import logging
import os
import tempfile
import uuid
from collections.abc import Iterator
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine, make_url, pool, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
TABLES = (
    "institution",
    "device_code",
    "staff",
    "dog",
    "measure_session",
    "shot",
    "walk_pass",
    "session_metric",
    "report",
    "purge_log",
)
GOOD_PASSWORD = "pass1234"


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
    # 11.6 인증 캐시는 테스트에서 끈다(요청마다 DB). 캐시 자체 테스트만 TTL을 켠다
    os.environ["AUTH_CACHE_TTL_SEC"] = "0"
    # 파일 저장소·임시 폴더는 실행마다 새 임시 폴더를 쓴다. 개발용 ./data는 건드리지 않는다.
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["STORAGE_ROOT"] = tempfile.mkdtemp(prefix="creamoff-test-files-")
    os.environ["UPLOAD_TMP_DIR"] = tempfile.mkdtemp(prefix="creamoff-test-tmp-")

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


# ---- 계정 ----


@lru_cache
def password_hash_for(password: str) -> str:
    """bcrypt는 0.2초쯤 걸려서 같은 비밀번호의 해시는 한 번만 만든다."""
    from app.core.security import hash_password

    return hash_password(password)


@pytest.fixture
def staff(db: Session):
    """기관 T01(계약 기한 없음)과 활성 담당자 staff1(CLIENT). 비밀번호는 GOOD_PASSWORD."""
    from app.models import Institution, Staff

    institution = Institution(code="T01", name="테스트 병원")
    db.add(institution)
    db.flush()
    row = Staff(
        institution_id=institution.id,
        login_id="staff1",
        password_hash=password_hash_for(GOOD_PASSWORD),
        name="담당자",
        role="CLIENT",
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


@pytest.fixture
def other_staff(db: Session):
    """다른 기관 T02의 담당자 staff2. 기관 분리(11.6) 확인용."""
    from app.models import Institution, Staff

    institution = Institution(code="T02", name="다른 병원")
    db.add(institution)
    db.flush()
    row = Staff(
        institution_id=institution.id,
        login_id="staff2",
        password_hash=password_hash_for(GOOD_PASSWORD),
        name="다른 담당자",
        role="CLIENT",
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


@pytest.fixture
def dog(db: Session, staff):
    """staff 기관의 반려견 보리(골든 리트리버, LARGE)."""
    from app.models import Dog

    row = Dog(
        institution_id=staff.institution_id,
        name="보리",
        breed="골든 리트리버",
        weight_kg=Decimal("28.40"),
        size_class="LARGE",
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


def bearer(staff) -> dict[str, str]:
    """담당자의 Bearer 헤더."""
    from app.core.security import create_access_token

    token, _ = create_access_token(staff_id=staff.id, institution_id=staff.institution_id, role=staff.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers(staff) -> dict[str, str]:
    return bearer(staff)


# ---- API 테스트 ----


class DogIn(BaseModel):
    """422 변환을 확인하기 위한 본문 모델. 실제 반려견 schema는 작업 단위 4에서 만든다."""

    weight_kg: Decimal = Field(le=200)
    name: str


def _test_router() -> APIRouter:
    """오류 형식(11.5)과 의존성을 확인하려고 일부러 오류를 내는 라우트들. 실제 API에는 없다."""
    from app.api.deps import AdminStaff, CreamoffStaff, CurrentStaff
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

    @router.get("/whoami")
    def whoami(staff: CurrentStaff) -> dict[str, str]:
        return {"login_id": staff.login_id}

    @router.get("/admin-only")
    def admin_only(staff: AdminStaff) -> dict[str, str]:
        return {"login_id": staff.login_id}

    @router.get("/creamoff-only")
    def creamoff_only(staff: CreamoffStaff) -> dict[str, str]:
        return {"login_id": staff.login_id}

    return router


@pytest.fixture(scope="session")
def api_app() -> FastAPI:
    """앱 + 테스트 전용 라우트. 세션에 하나만 만든다."""
    from app.main import API_PREFIX, create_app

    app = create_app()
    app.include_router(_test_router(), prefix=API_PREFIX)
    return app


@pytest.fixture(scope="session")
def api_client(api_app: FastAPI) -> Iterator[TestClient]:
    # TestClient 하나가 이벤트 루프 스레드와 loopback 소켓 쌍을 만든다. 테스트마다 새로 만들면 Windows에서
    # 소켓 쌍 생성이 간헐적으로 실패해(WinError 10014) 세션에 하나만 두고, 테스트마다 get_db만 바꿔 끼운다.
    with TestClient(api_app) as client:
        yield client


@pytest.fixture
def client(db: Session, api_app: FastAPI, api_client: TestClient) -> Iterator[TestClient]:
    """앱의 get_db를 테스트의 db 세션으로 바꿔 끼운 클라이언트(commit은 세이브포인트만 확정)."""
    from app.api.deps import get_db

    def test_db() -> Iterator[Session]:
        # 요청마다 세이브포인트 하나. 요청이 실패해도 픽스처가 만든 행은 남고, 요청이 한 일만 되돌아간다.
        request_tx = db.begin_nested()
        try:
            yield db
            request_tx.commit()
        except BaseException:
            request_tx.rollback()
            raise

    api_app.dependency_overrides[get_db] = test_db
    try:
        yield api_client
    finally:
        api_app.dependency_overrides.pop(get_db, None)
