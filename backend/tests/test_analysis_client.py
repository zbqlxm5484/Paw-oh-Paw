"""분석 클라이언트(명세 6절, 16절 ANALYSIS_*, 17.3 BE-06의 Mock 줄). DB 없이 돈다."""

import json
import uuid
from pathlib import Path

import httpx
import pytest

from app.clients.analysis import (
    FIXTURES_DIR,
    MOCK_CASES,
    AnalysisClientError,
    HttpAnalysisClient,
    MockAnalysisClient,
    SubmitInfo,
    build_analysis_client,
    load_fixture,
)
from app.core.config import get_settings

SHOT_ID = uuid.UUID("3f2a9c1e-5b7d-4e8a-9c21-7d4e5f6a8b90")
INFO = SubmitInfo(shot_id=SHOT_ID, size_class="MEDIUM")


@pytest.fixture
def video(tmp_path: Path) -> Path:
    path = tmp_path / "original.mp4"
    path.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    return path


# ---- 견본 파일 ----


def test_fixture_files_match_the_analysis_api_shape() -> None:
    for case in ("valid", "partial", "invalid"):
        result = load_fixture(f"result_{case}")
        assert result["status"] == "done" and result["validity"] == case
        assert set(result) >= {"id", "shot_id", "model", "input", "summary", "passes", "files", "created_at"}
        assert result["model"]["version"] == "0.1.0/v1/a4261a10"
        for walk_pass in result["passes"]:
            assert set(walk_pass) >= {"index", "start_frame", "end_frame", "camera_side", "valid", "reason_code"}
    failed = load_fixture("status_failed")
    assert failed["status"] == "failed" and failed["error"]["code"] == "DECODE_FAILED"
    keypoints = load_fixture("keypoints")
    assert keypoints["fps"] == 59.94 and len(keypoints["frames"][0]["points"]) == 22


def test_load_fixture_returns_a_fresh_copy_each_time() -> None:
    first = load_fixture("result_valid")
    first["validity"] = "changed"
    assert load_fixture("result_valid")["validity"] == "valid"


def test_missing_fixture_is_a_client_error() -> None:
    with pytest.raises(AnalysisClientError):
        load_fixture("nope")
    assert sorted(p.stem for p in FIXTURES_DIR.glob("*.json")) == [
        "keypoints",
        "result_invalid",
        "result_partial",
        "result_valid",
        "status_failed",
    ]


# ---- Mock ----


def test_mock_submit_encodes_case_time_and_shot_in_the_job_id(video: Path) -> None:
    job_id = MockAnalysisClient(delay_sec=5, case="partial").submit(video, INFO)
    case, submitted_at, shot_id = MockAnalysisClient.parse_job_id(job_id)
    assert case == "partial" and shot_id == SHOT_ID and submitted_at > 0
    assert len(job_id) <= 100  # shot.job_id VARCHAR(100)


def test_mock_submit_needs_an_existing_file(tmp_path: Path) -> None:
    with pytest.raises(AnalysisClientError):
        MockAnalysisClient(delay_sec=0).submit(tmp_path / "missing.mp4", INFO)


def test_mock_progresses_queued_running_done_by_elapsed_time(video: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [1_000.0]
    monkeypatch.setattr("app.clients.analysis.time.time", lambda: clock[0])
    client = MockAnalysisClient(delay_sec=10)
    job_id = client.submit(video, INFO)
    assert client.get_status(job_id).state == "queued"
    with pytest.raises(AnalysisClientError):
        client.get_result(job_id)
    clock[0] += 6
    assert client.get_status(job_id).state == "running"
    clock[0] += 5
    status = client.get_status(job_id)
    assert status.state == "done" and status.error_code is None
    assert status.model_name == "fs-v4" and status.model_version == "0.1.0/v1/a4261a10"


def test_mock_result_is_the_fixture_tagged_with_job_and_shot(video: Path) -> None:
    client = MockAnalysisClient(delay_sec=0)
    job_id = client.submit(video, INFO)
    result = client.get_result(job_id)
    assert result["id"] == job_id and result["shot_id"] == str(SHOT_ID)
    assert result["validity"] == "valid" and result["summary"] == {"passes": 4, "used": 4, "excluded": 0}
    assert client.get_keypoints(job_id)["frames"][-1]["points"] is None


def test_mock_failed_case_reports_the_analysis_error(video: Path) -> None:
    client = MockAnalysisClient(delay_sec=0, case="failed")
    job_id = client.submit(video, INFO)
    status = client.get_status(job_id)
    assert status.state == "failed" and status.error_code == "DECODE_FAILED"
    assert status.error_message == "영상을 읽을 수 없습니다"
    with pytest.raises(AnalysisClientError):
        client.get_result(job_id)


def test_mock_is_stateless_so_a_new_instance_answers_the_same(video: Path) -> None:
    # 워커를 껐다 켜도 진행 중이던 작업이 이어진다(17.3 BE-06)
    job_id = MockAnalysisClient(delay_sec=0, case="invalid").submit(video, INFO)
    fresh = MockAnalysisClient(delay_sec=0)
    assert fresh.get_status(job_id).state == "done"
    assert fresh.get_result(job_id)["validity_reason"] == "NO_DOG"


@pytest.mark.parametrize(
    "job_id", ["", "abc", "mock-weird-1-x", "mock-valid-notatime-" + str(SHOT_ID), "mock-valid-1-nope"]
)
def test_mock_rejects_job_ids_it_did_not_make(job_id: str) -> None:
    with pytest.raises(AnalysisClientError):
        MockAnalysisClient(delay_sec=0).get_status(job_id)


def test_mock_case_must_be_known() -> None:
    with pytest.raises(ValueError):
        MockAnalysisClient(delay_sec=0, case="bogus")
    assert MOCK_CASES == ("valid", "partial", "invalid", "failed")


# ---- HTTP ----


def _http(handler) -> HttpAnalysisClient:
    return HttpAnalysisClient(
        "http://analysis.test", api_key="k1", timeout_sec=5, transport=httpx.MockTransport(handler)
    )


def test_http_submit_sends_multipart_video_and_meta_and_returns_the_job_id(video: Path) -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"], seen["path"] = request.method, request.url.path
        seen["api_key"] = request.headers.get("x-api-key")
        body = request.read()
        seen["has_video"] = b'name="video"; filename="original.mp4"' in body and b"video/mp4" in body
        seen["meta"] = json.loads(body.split(b'name="meta"\r\n\r\n')[1].split(b"\r\n")[0])
        return httpx.Response(202, json={"id": "job-1", "status": "queued"})

    assert _http(handler).submit(video, INFO) == "job-1"
    assert seen["method"] == "POST" and seen["path"] == "/analyses" and seen["api_key"] == "k1"
    assert seen["has_video"] and seen["meta"] == {"shot_id": str(SHOT_ID), "size_class": "MEDIUM"}


def test_http_submit_uses_quicktime_for_mov(tmp_path: Path) -> None:
    mov = tmp_path / "original.mov"
    mov.write_bytes(b"mov")
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["quicktime"] = b"video/quicktime" in request.read()
        return httpx.Response(202, json={"id": "job-2", "status": "queued"})

    _http(handler).submit(mov, INFO)
    assert seen["quicktime"]


def _rejection(status: int, code: str) -> httpx.Response:
    return httpx.Response(status, json={"error": {"code": code, "message": "거부", "detail": None}})


@pytest.mark.parametrize(
    ("response", "message_part", "retryable"),
    [
        (_rejection(415, "UNSUPPORTED_MEDIA"), "UNSUPPORTED_MEDIA", False),
        (_rejection(413, "TOO_LARGE"), "TOO_LARGE", False),
        (_rejection(400, "INVALID_META"), "INVALID_META", False),
        (_rejection(401, "AUTH_REQUIRED"), "AUTH_REQUIRED", True),  # 키 문제. 거부가 아니라 auth_failed
        (_rejection(403, "FORBIDDEN"), "FORBIDDEN", True),
        (httpx.Response(429, text="slow down"), "429", True),
        (httpx.Response(500, text="boom"), "500", True),
        (httpx.Response(202, text="not json"), "JSON", True),
        (httpx.Response(202, json={"status": "queued"}), "작업 ID", True),
    ],
)
def test_http_submit_turns_bad_responses_into_client_errors(
    video: Path, response: httpx.Response, message_part: str, retryable: bool
) -> None:
    with pytest.raises(AnalysisClientError, match=message_part) as caught:
        _http(lambda request: response).submit(video, INFO)
    # 4xx는 다시 보내도 같으므로 retryable=False, 나머지는 다시 보낼 수 있다(87 MR 리뷰 제안 A). 401·403은 예외다
    assert caught.value.retryable is retryable


def test_http_errors_flag_auth_and_missing_jobs() -> None:
    # 워커가 따로 다루는 두 가지: 401·403은 auth_failed(키 문제), 404·410은 job_gone(작업 없음)
    with pytest.raises(AnalysisClientError) as caught:
        _http(lambda request: _rejection(404, "NOT_FOUND")).get_status("job-x")
    assert caught.value.status_code == 404 and caught.value.job_gone and not caught.value.auth_failed
    with pytest.raises(AnalysisClientError) as caught:
        _http(lambda request: _rejection(403, "FORBIDDEN")).get_result("job-x")
    assert caught.value.auth_failed and caught.value.retryable and not caught.value.job_gone
    with pytest.raises(AnalysisClientError) as caught:
        _http(lambda request: _rejection(409, "NOT_READY")).get_result("job-x")
    assert caught.value.status_code == 409 and not caught.value.job_gone and not caught.value.auth_failed


def test_http_connection_failure_is_a_client_error(video: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(AnalysisClientError, match="ConnectError") as caught:
        _http(handler).submit(video, INFO)
    assert caught.value.retryable and caught.value.status_code is None
    with pytest.raises(AnalysisClientError):
        _http(handler).get_status("job-1")


def test_http_status_maps_queued_running_done_and_failed() -> None:
    payloads = {
        "q": {"status": "queued", "error": None, "model": {"name": "fs-v4", "version": "0.1.0/v1/a4261a10"}},
        "r": {"status": "running", "error": None, "model": {"name": "fs-v4", "version": "0.1.0/v1/a4261a10"}},
        "d": {"status": "done", "error": None, "model": {"name": "fs-v4", "version": "0.1.0/v1/a4261a10"}},
        "f": {"status": "failed", "error": {"code": "NO_DOG", "message": "개 미검출", "detail": None}, "model": None},
        "x": {"status": "weird"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payloads[request.url.path.rsplit("/", 1)[1]])

    client = _http(handler)
    assert [client.get_status(k).state for k in "qrd"] == ["queued", "running", "done"]
    failed = client.get_status("f")
    assert failed.state == "failed" and failed.error_code == "NO_DOG" and failed.error_message == "개 미검출"
    assert client.get_status("d").model_version == "0.1.0/v1/a4261a10"
    with pytest.raises(AnalysisClientError, match="상태값"):
        client.get_status("x")


def test_http_result_and_keypoints_paths_and_not_ready() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/analyses/job-1/result":
            return httpx.Response(200, json=load_fixture("result_partial"))
        if request.url.path == "/analyses/job-1/files/keypoints":
            return httpx.Response(200, json=load_fixture("keypoints"))
        return httpx.Response(409, json={"error": {"code": "NOT_READY", "message": "아직", "detail": None}})

    client = _http(handler)
    assert client.get_result("job-1")["validity"] == "partial"
    assert client.get_keypoints("job-1")["angle_def"] == "v1"
    with pytest.raises(AnalysisClientError, match="NOT_READY"):
        client.get_result("job-2")


# ---- 설정값으로 고르기 ----


def test_build_client_follows_analysis_api_mode() -> None:
    settings = get_settings()
    assert isinstance(
        build_analysis_client(settings.model_copy(update={"ANALYSIS_API_MODE": "mock"})), MockAnalysisClient
    )
    http_settings = settings.model_copy(
        update={"ANALYSIS_API_MODE": "http", "ANALYSIS_API_BASE_URL": "http://analysis:8000"}
    )
    client = build_analysis_client(http_settings)
    assert isinstance(client, HttpAnalysisClient)
    client.close()
