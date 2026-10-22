"""GET /api/v1/health(15.9, BE-20). 지금은 DB만 검사한다. 저장소 검사는 작업 단위 5에서 더한다."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, pool

import app.api.routes.health as health_route
from app import __version__


def test_version_matches_api_document() -> None:
    assert __version__ == "1.0.0"


def test_health_ok_without_token(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "version": "1.0.0"}


def test_health_is_503_with_error_status_when_db_is_down(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    dead = create_engine("postgresql+pg8000://nobody:nothing@127.0.0.1:1/nowhere", poolclass=pool.NullPool)
    monkeypatch.setattr(health_route, "get_engine", lambda: dead)
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "error", "version": "1.0.0"}
