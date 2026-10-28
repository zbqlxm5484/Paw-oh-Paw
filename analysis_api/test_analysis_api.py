import main
import pytest
from fastapi.testclient import TestClient
from main import JOBS, app

client = TestClient(app)


@pytest.fixture(autouse=True)
def storage(tmp_path, monkeypatch):
    """테스트마다 빈 저장소, 인증 끔"""
    monkeypatch.setattr(main, "STORAGE_DIR", tmp_path)
    monkeypatch.setattr(main, "API_KEY", "")
    return tmp_path


def upload(content_type="video/mp4", meta=None, body=b"fake video", headers=None, name="a.mp4"):
    data = {"meta": meta} if meta is not None else {}
    return client.post("/analyses", files={"video": (name, body, content_type)}, data=data,
                       headers=headers or {})


def code_of(r):
    return r.json()["error"]["code"]


def test_health_has_model():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "version" in body["model"]


def test_create_returns_202_queued_then_done():
    r = upload(meta='{"shot_id": "s-1"}')
    assert r.status_code == 202 and r.json()["status"] == "queued"
    body = client.get(f"/analyses/{r.json()['id']}").json()
    assert body["status"] == "done"        # 테스트 클라이언트는 응답 뒤 작업까지 끝낸 다음 돌아온다
    assert body["shot_id"] == "s-1"
    assert body["created_at"].endswith("+09:00")


def test_result_and_keypoints_when_done():
    job_id = upload(meta='{"shot_id": "s-2"}', name="shot.mov", content_type="video/quicktime").json()["id"]
    result = client.get(f"/analyses/{job_id}/result").json()
    assert result["id"] == job_id and result["shot_id"] == "s-2"
    assert result["input"]["filename"] == "shot.mov"
    assert result["model"]["name"] == "sample-pipeline"
    assert result["files"]["keypoints"] == f"/analyses/{job_id}/files/keypoints"
    assert "frames" in client.get(f"/analyses/{job_id}/files/keypoints").json()


def test_video_is_saved_to_storage(storage):
    job_id = upload(body=b"12345", name="b.mov", content_type="video/quicktime").json()["id"]
    saved = storage / job_id / "video.mov"
    assert saved.read_bytes() == b"12345"


def test_not_ready_is_409():
    job_id = upload().json()["id"]
    JOBS[job_id].update(status="running")
    for path in ("result", "files/keypoints"):
        r = client.get(f"/analyses/{job_id}/{path}")
        assert r.status_code == 409 and code_of(r) == "NOT_READY"


def test_unreadable_video_fails_with_reason():
    job_id = upload(body=b"").json()["id"]
    body = client.get(f"/analyses/{job_id}").json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "DECODE_FAILED"
    assert client.get(f"/analyses/{job_id}/result").status_code == 409


def test_unexpected_error_is_failed_not_500(monkeypatch):
    def boom(path, job):
        raise RuntimeError("bug")
    monkeypatch.setattr(main, "run_pipeline", boom)
    job_id = upload().json()["id"]
    body = client.get(f"/analyses/{job_id}").json()
    assert body["status"] == "failed" and body["error"]["code"] == "INTERNAL"


def test_too_large_is_413_and_leaves_nothing(storage, monkeypatch):
    monkeypatch.setattr(main, "MAX_BYTES", 4)
    r = upload(body=b"12345")
    assert r.status_code == 413 and code_of(r) == "TOO_LARGE"
    assert list(storage.iterdir()) == []


def test_auth_required_when_key_is_set(monkeypatch):
    monkeypatch.setattr(main, "API_KEY", "secret")
    assert code_of(upload()) == "AUTH_REQUIRED"
    assert upload(headers={"X-API-Key": "wrong"}).status_code == 401
    r = upload(headers={"X-API-Key": "secret"})
    assert r.status_code == 202
    assert client.get(f"/analyses/{r.json()['id']}").status_code == 401
    assert client.get("/health").status_code == 200      # 상태 확인은 인증 없이


def test_unknown_id_is_404():
    r = client.get("/analyses/nope")
    assert r.status_code == 404 and code_of(r) == "NOT_FOUND"


def test_non_video_is_415():
    r = upload(content_type="text/plain")
    assert r.status_code == 415 and code_of(r) == "UNSUPPORTED_MEDIA"


def test_bad_meta_is_400():
    assert code_of(upload(meta="not json")) == "INVALID_META"
    assert code_of(upload(meta="[1, 2]")) == "INVALID_META"


def test_missing_video_is_400():
    r = client.post("/analyses")
    assert r.status_code == 400 and code_of(r) == "INVALID_REQUEST"
