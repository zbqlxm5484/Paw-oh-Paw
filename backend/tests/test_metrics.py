"""GET /metrics(15.9, 16절 METRICS_ENABLED): 켰을 때만 루트에 열리고, 라벨에 식별 정보가 없다."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.metrics import BUCKETS, CONTENT_TYPE, UNMATCHED, RequestMetrics
from app.main import create_app


def _client(enabled: bool) -> TestClient:
    return TestClient(create_app(get_settings().model_copy(update={"METRICS_ENABLED": enabled})))


def test_metrics_path_exists_only_when_enabled() -> None:
    assert _client(False).get("/metrics").status_code == 404
    opened = _client(True).get("/metrics")
    assert opened.status_code == 200
    assert opened.headers["content-type"] == CONTENT_TYPE
    assert 'app_info{version="' in opened.text


def test_metrics_is_at_the_root_and_not_under_the_api_prefix() -> None:
    """nginx는 /api/만 밖으로 넘긴다. 지표가 그 아래에 있으면 인증 없이 밖에 열린다(v1.53)."""
    assert _client(True).get("/api/v1/metrics").status_code == 404


def test_requests_are_counted_by_route_template_without_ids_or_query() -> None:
    client = _client(True)
    client.get("/api/v1/dogs/3f2b1c9e-0000-4000-8000-000000000001")
    client.get("/api/v1/dogs/3f2b1c9e-0000-4000-8000-000000000002")
    client.get("/api/v1/dogs", params={"q": "제니"})
    client.get("/없는/주소")
    text = client.get("/metrics").text
    assert 'http_requests_total{method="GET",path="/api/v1/dogs/{dog_id}",status="401"} 2' in text
    assert 'http_requests_total{method="GET",path="/api/v1/dogs",status="401"} 1' in text
    assert f'http_requests_total{{method="GET",path="{UNMATCHED}",status="404"}} 1' in text
    assert "3f2b1c9e" not in text and "제니" not in text and "없는" not in text  # 11.8: 식별 정보를 남기지 않는다


def test_reading_metrics_is_not_counted() -> None:
    client = _client(True)
    client.get("/metrics")
    assert 'path="/metrics"' not in client.get("/metrics").text


def test_duration_histogram_is_cumulative_and_sums() -> None:
    metrics = RequestMetrics("1.2.3")
    metrics.observe("GET", "/a", 200, 0.03)
    metrics.observe("GET", "/a", 200, 0.3)
    metrics.observe("GET", "/a", 500, 40.0)  # 가장 큰 구간보다 길다
    text = metrics.render()
    labels = 'method="GET",path="/a"'
    assert f'http_request_duration_seconds_bucket{{{labels},le="0.025"}} 0' in text
    assert f'http_request_duration_seconds_bucket{{{labels},le="0.05"}} 1' in text
    assert f'http_request_duration_seconds_bucket{{{labels},le="0.5"}} 2' in text
    assert f'http_request_duration_seconds_bucket{{{labels},le="{BUCKETS[-1]:g}"}} 2' in text
    assert f'http_request_duration_seconds_bucket{{{labels},le="+Inf"}} 3' in text
    assert f"http_request_duration_seconds_count{{{labels}}} 3" in text
    assert f"http_request_duration_seconds_sum{{{labels}}} 40.330000" in text
    assert 'http_requests_total{method="GET",path="/a",status="200"} 2' in text
    assert text.endswith("\n")


def test_label_values_are_escaped() -> None:
    metrics = RequestMetrics('1"0')
    assert 'app_info{version="1\\"0"} 1' in metrics.render()
