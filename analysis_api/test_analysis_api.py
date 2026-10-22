from fastapi.testclient import TestClient

from main import JOBS, app

client = TestClient(app)


def upload(content_type="video/mp4", meta=None):
    data = {"meta": meta} if meta is not None else {}
    return client.post("/analyses", files={"video": ("a.mp4", b"fake", content_type)}, data=data)


def code_of(r):
    return r.json()["error"]["code"]


def test_health_has_model():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "version" in body["model"]


def test_create_returns_202_queued():
    r = upload()
    assert r.status_code == 202
    assert r.json()["status"] == "queued"


def test_status_keeps_shot_id_and_kst_time():
    job_id = upload(meta='{"shot_id": "s-1"}').json()["id"]
    body = client.get(f"/analyses/{job_id}").json()
    assert body["shot_id"] == "s-1"
    assert body["created_at"].endswith("+09:00")


def test_result_not_ready_is_409():
    job_id = upload().json()["id"]
    r = client.get(f"/analyses/{job_id}/result")
    assert r.status_code == 409 and code_of(r) == "NOT_READY"


def test_keypoints_not_ready_is_409():
    job_id = upload().json()["id"]
    assert client.get(f"/analyses/{job_id}/files/keypoints").status_code == 409


def test_result_when_done():
    job_id = upload().json()["id"]
    JOBS[job_id].update(status="done", result={"validity": "valid"})
    r = client.get(f"/analyses/{job_id}/result")
    assert r.status_code == 200 and r.json() == {"validity": "valid"}


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