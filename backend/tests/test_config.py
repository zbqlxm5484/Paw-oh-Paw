"""환경 변수 읽기(16절). DB 없이 돈다."""

import pytest
from pydantic import ValidationError

from app.core.config import DbSettings, Settings

URL = "postgresql+pg8000://u:p@localhost:5432/creamoff"
SECRET_A = "a" * 32
SECRET_B = "b" * 32


def _settings(**values: object) -> Settings:
    base = {"DATABASE_URL": URL, "JWT_SECRET": SECRET_A, "FILE_URL_SECRET": SECRET_B}
    base.update(values)
    return Settings(_env_file=None, **base)


def test_defaults_follow_section_16(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTH_CACHE_TTL_SEC", raising=False)  # conftest가 테스트용으로 0을 넣어 둔다
    settings = _settings()
    assert settings.JWT_EXPIRE_HOURS == 12
    assert settings.STORAGE_BACKEND == "local"
    assert settings.ANALYSIS_API_MODE == "mock"
    assert settings.CORS_ORIGINS == ["http://localhost:5173"]
    assert settings.AUTH_CACHE_TTL_SEC == 60
    assert settings.DEVICE_CODE_MAX_ACCOUNTS == 10


@pytest.mark.parametrize(
    "name", ["WORKER_MAX_IN_FLIGHT", "WORKER_MAX_IN_FLIGHT_PER_INSTITUTION", "WORKER_RENDER_CONCURRENCY"]
)
def test_worker_caps_must_be_at_least_one(name: str) -> None:
    # 16절: 0이면 워커가 오류 없이 아무것도 가져가지 않으므로(결과 영상은 영영 PENDING) 시작 때 막는다
    with pytest.raises(ValidationError, match=name):
        _settings(**{name: 0})


def test_device_code_max_accounts_is_at_least_one() -> None:
    with pytest.raises(ValidationError, match="DEVICE_CODE_MAX_ACCOUNTS"):
        _settings(DEVICE_CODE_MAX_ACCOUNTS=0)


def test_auth_cache_ttl_cannot_be_negative() -> None:
    with pytest.raises(ValidationError, match="AUTH_CACHE_TTL_SEC"):
        _settings(AUTH_CACHE_TTL_SEC=-1)


def test_database_url_must_use_pg8000() -> None:
    with pytest.raises(ValidationError, match="postgresql\\+pg8000"):
        DbSettings(_env_file=None, DATABASE_URL="mysql+pymysql://u:p@localhost/db")


def test_cors_origins_are_split_by_comma(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    assert _settings().CORS_ORIGINS == ["http://a.test", "http://b.test"]


def test_cors_wildcard_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(ValidationError, match="\\*"):
        _settings()


def test_empty_value_means_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S3_BUCKET", "")
    monkeypatch.setenv("JWT_EXPIRE_HOURS", "")
    settings = _settings()
    assert settings.S3_BUCKET is None
    assert settings.JWT_EXPIRE_HOURS == 12


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"JWT_SECRET": "short"}, "32자"),
        ({"FILE_URL_SECRET": SECRET_A}, "달라야"),
        ({"STORAGE_BACKEND": "s3"}, "S3_BUCKET"),
        ({"ANALYSIS_API_MODE": "http"}, "ANALYSIS_API_BASE_URL"),
    ],
)
def test_invalid_combinations(values: dict, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        _settings(**values)
