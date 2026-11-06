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
    assert (settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_USER, settings.SMTP_FROM) == ("", 587, "", "")
    assert settings.SMTP_PASSWORD.get_secret_value() == ""
    assert settings.FRONTEND_BASE_URL == "http://localhost:5173"


@pytest.mark.parametrize(
    "name", ["WORKER_MAX_IN_FLIGHT", "WORKER_MAX_IN_FLIGHT_PER_INSTITUTION", "WORKER_RENDER_CONCURRENCY"]
)
def test_worker_caps_must_be_at_least_one(name: str) -> None:
    # 16절: 0이면 워커가 오류 없이 아무것도 가져가지 않으므로(결과 영상은 영영 PENDING) 시작 때 막는다
    with pytest.raises(ValidationError, match=name):
        _settings(**{name: 0})


def test_smtp_host_requires_from_address() -> None:
    with pytest.raises(ValidationError, match="SMTP_FROM"):
        _settings(SMTP_HOST="smtp.example.com")
    assert _settings(SMTP_HOST="smtp.example.com", SMTP_FROM="no-reply@example.com").SMTP_HOST == "smtp.example.com"


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


def test_the_sweep_time_limit_is_sixty_seconds_and_must_be_positive() -> None:
    # 16절: 휴지통 비우기·계약 종료 뒤 파기 한 차례가 워커의 주 반복을 붙잡는 시간의 상한(12.4)
    assert _settings().WORKER_SWEEP_MAX_SEC == 60
    with pytest.raises(ValidationError, match="WORKER_SWEEP_MAX_SEC"):
        _settings(WORKER_SWEEP_MAX_SEC=0)
