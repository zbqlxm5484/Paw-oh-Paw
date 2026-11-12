"""작업 기록(store.py)과 모델 전환(models.yaml) 테스트. 분석 API를 다시 켠 것처럼 메모리를 비우고 확인한다."""
import json

import main
import pipeline
import pytest
import store
from conftest import client  # 세션 동안 열어 둔 클라이언트 (conftest.py)
from test_pipeline import VIDEO, track_file

pytest.importorskip("yaml")


@pytest.fixture(autouse=True)
def storage(tmp_path, monkeypatch):
    root = tmp_path / "storage"
    monkeypatch.setattr(main, "STORAGE_DIR", root)
    monkeypatch.setattr(main, "API_KEY", "")
    monkeypatch.delenv("ANALYSIS_POSE_SOURCE", raising=False)
    monkeypatch.delenv("ANALYSIS_MODEL", raising=False)
    monkeypatch.delenv("ANALYSIS_TRACK_FILE", raising=False)
    monkeypatch.delenv("ANALYSIS_WEIGHTS_SHA256", raising=False)
    pipeline.load_tracks.cache_clear()
    main.JOBS.clear()
    return root


def upload(body=VIDEO, name="shot.mp4"):
    r = client.post("/analyses", files={"video": (name, body, "video/mp4")}, data={"meta": '{"shot_id": "s-9"}'})
    return r.json()["id"]


def restart():
    """분석 API를 다시 켠 것과 같게: 메모리를 비우고 시작할 때 하는 일을 한다"""
    main.JOBS.clear()
    return main.recover_unfinished()


def test_done_job_survives_restart():
    job_id = upload()
    before = client.get(f"/analyses/{job_id}/result").json()
    restart()
    status = client.get(f"/analyses/{job_id}").json()
    assert status["status"] == "done" and status["shot_id"] == "s-9"
    assert client.get(f"/analyses/{job_id}/result").json() == before
    assert "frames" in client.get(f"/analyses/{job_id}/files/keypoints").json()


def test_failed_job_survives_restart():
    job_id = upload(body=b"")
    restart()
    body = client.get(f"/analyses/{job_id}").json()
    assert body["status"] == "failed" and body["error"]["code"] == "DECODE_FAILED"


def test_job_interrupted_by_restart_is_failed(storage, monkeypatch):
    monkeypatch.setattr(main, "analyze", lambda job_id: None)      # 분석이 끝나기 전에 꺼진 것처럼
    job_id = upload()
    assert json.loads((storage / job_id / store.JOB_FILE).read_text(encoding="utf-8"))["status"] == "queued"
    assert restart() == 1
    body = client.get(f"/analyses/{job_id}").json()
    assert body["status"] == "failed" and body["error"]["code"] == "INTERRUPTED"
    assert restart() == 0                                            # 한 번 정리한 것은 다시 건드리지 않는다


def test_unknown_id_is_still_404_and_paths_are_not_followed():
    restart()
    for job_id in ("nope", "..", ".hidden"):
        assert client.get(f"/analyses/{job_id}").status_code == 404
    assert store.load_job(main.STORAGE_DIR, "../x") is None


def test_finished_jobs_are_logged(storage):
    ok, bad = upload(), upload(body=b"")
    log = {row["id"]: row for row in store.read_log(storage)}
    assert set(log) == {ok, bad}
    assert log[ok]["status"] == "done" and log[ok]["validity"] == "partial"
    assert log[ok]["model"]["name"] == "sample-pipeline" and log[ok]["versions"]["validity"] == "v1"
    assert len(log[ok]["video_sha256"]) == 64 and log[ok]["elapsed_ms"] >= 0
    assert log[bad]["status"] == "failed" and log[bad]["error_code"] == "DECODE_FAILED"


# ---- 모델 전환 ----


def test_models_yaml_default_is_listed():
    models = pipeline.load_models()
    assert models["default"] in models["models"]
    for entry in models["models"].values():
        assert {"config", "weights_sha256", "track_file"} <= set(entry)


def test_model_is_picked_from_models_yaml(tmp_path, monkeypatch):
    yaml_file = tmp_path / "models.yaml"
    path = track_file(tmp_path)                       # meta 모델 이름 fs-test
    yaml_file.write_text(
        "default: fs-test\n"
        f"models:\n  fs-test:\n    config: x.toml\n    weights_sha256: 'b1c2d3e4ffff'\n    track_file: '{path.as_posix()}'\n",
        encoding="utf-8")
    monkeypatch.setattr(pipeline, "MODELS_FILE", yaml_file)
    monkeypatch.setenv("ANALYSIS_POSE_SOURCE", "track")
    health = client.get("/health").json()
    assert health["model"] == {"name": "fs-test", "version": f"{pipeline.API_VERSION}/v1/b1c2d3e4"}
    assert health["model_known"] is True
    job_id = upload()
    result = client.get(f"/analyses/{job_id}/result").json()
    assert result["model"]["name"] == "fs-test" and result["model"]["weights_sha256"] == "b1c2d3e4ffff"


def test_track_made_by_another_model_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("ANALYSIS_POSE_SOURCE", "track")
    monkeypatch.setenv("ANALYSIS_MODEL", "fs-v4")
    monkeypatch.setenv("ANALYSIS_TRACK_FILE", str(track_file(tmp_path)))    # meta 모델 이름 fs-test
    body = client.get(f"/analyses/{upload()}").json()
    assert body["status"] == "failed" and body["error"]["code"] == "POSE_UNAVAILABLE"
    assert "fs-test" in body["error"]["message"]


def test_unknown_model_is_not_silently_replaced(monkeypatch):
    monkeypatch.setenv("ANALYSIS_POSE_SOURCE", "track")
    monkeypatch.setenv("ANALYSIS_MODEL", "no-such-model")
    health = client.get("/health").json()
    assert health["model"]["name"] == "no-such-model" and health["model_known"] is False
    body = client.get(f"/analyses/{upload()}").json()
    assert body["status"] == "failed" and body["error"]["code"] == "POSE_UNAVAILABLE"
