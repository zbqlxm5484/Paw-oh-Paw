"""main.py: 요청 ID와 요청 로그(11.8), CORS(16절), 필수 환경 변수 검사(16절, 17.1)."""

import logging
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import SettingsError, get_settings
from app.main import create_app

HEX32 = re.compile(r"^[0-9a-f]{32}$")


def test_every_response_has_a_fresh_request_id(client: TestClient) -> None:
    first = client.get("/api/v1/health").headers["x-request-id"]
    second = client.get("/api/v1/health").headers["x-request-id"]
    assert HEX32.match(first) and HEX32.match(second)
    assert first != second


def test_request_log_has_method_path_status_time_and_id_but_no_query(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.request")
    response = client.get("/api/v1/_test/search", params={"page": 1, "q": "초코", "sig": "abc123"})
    assert response.status_code == 200
    records = [record for record in caplog.records if record.name == "app.request"]
    assert len(records) == 1
    line = records[0].getMessage()
    assert re.fullmatch(r"GET /api/v1/_test/search 200 \d+ms", line)
    assert "초코" not in line and "sig" not in line and "abc123" not in line
    assert records[0].request_id == response.headers["x-request-id"]


def test_logs_written_inside_a_route_carry_the_request_id(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.test")
    response = client.get("/api/v1/_test/log")
    record = next(record for record in caplog.records if record.name == "app.test")
    assert record.request_id == response.headers["x-request-id"]


def test_cors_allows_only_configured_origins(client: TestClient) -> None:
    allowed = get_settings().CORS_ORIGINS[0]
    preflight = {"Access-Control-Request-Method": "GET"}
    ok = client.options("/api/v1/health", headers={"Origin": allowed, **preflight})
    assert ok.status_code == 200
    assert ok.headers["access-control-allow-origin"] == allowed
    assert "x-request-id" in ok.headers  # 사전 요청(preflight)에도 요청 ID가 붙는다

    bad = client.options("/api/v1/health", headers={"Origin": "http://evil.test", **preflight})
    assert "access-control-allow-origin" not in bad.headers


def test_cors_exposes_request_id_header(client: TestClient) -> None:
    allowed = get_settings().CORS_ORIGINS[0]
    response = client.get("/api/v1/health", headers={"Origin": allowed})
    assert response.headers["access-control-allow-origin"] == allowed
    assert "x-request-id" in response.headers["access-control-expose-headers"].lower()


def test_missing_required_env_stops_startup_and_names_it(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)  # .env 파일도 보이지 않게 한다
    monkeypatch.delenv("JWT_SECRET", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(SettingsError) as caught:
            create_app()
    finally:
        get_settings.cache_clear()
    assert "JWT_SECRET" in str(caught.value)
    assert "FILE_URL_SECRET" not in str(caught.value)  # 문제 있는 값만 알려 준다
