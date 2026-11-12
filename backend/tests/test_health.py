"""GET /api/v1/health(15.9, BE-20): DB 접속과 저장소 쓰기 검사."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, pool

import app.api.routes.health as health_route
from app import __version__


class _BrokenStorage:
    def check_writable(self) -> None:
        raise PermissionError("disk is read-only")


def test_version_matches_api_document() -> None:
    assert __version__ == "1.0.0"


def test_health_ok_without_token(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "storage": "ok", "version": "1.0.0"}


def test_health_is_503_with_error_status_when_db_is_down(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    dead = create_engine("postgresql+pg8000://nobody:nothing@127.0.0.1:1/nowhere", poolclass=pool.NullPool)
    monkeypatch.setattr(health_route, "get_engine", lambda: dead)
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "error", "storage": "ok", "version": "1.0.0"}


def test_health_is_503_when_storage_is_not_writable(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_route, "get_storage", lambda: _BrokenStorage())
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "ok", "storage": "error", "version": "1.0.0"}
