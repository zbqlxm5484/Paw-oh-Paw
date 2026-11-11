"""model 모드(영상 → 모델 → 관절점 → 엔진) 테스트. 모델 추론(extract_track)은 가짜로 바꿔 끼워 GPU 없이 돈다."""
import json
from pathlib import Path

import main
import pipeline
import pytest
from conftest import client


@pytest.fixture(autouse=True)
def model_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ANALYSIS_POSE_SOURCE", "model")
    monkeypatch.setenv("ANALYSIS_MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setattr(main, "API_KEY", "")
    pipeline._pose_sha.cache_clear()
    return tmp_path / "models"


def fake_models(d: Path, pose_bytes=b"pose-weights"):
    d.mkdir(parents=True, exist_ok=True)
    for name in pipeline.MODEL_FILES:
        (d / name).write_bytes(pose_bytes if name == "pose.pth" else b"x")


def test_health_reports_missing_model_files(model_env):
    body = client.get("/health").json()
    assert body["pose_source"] == "model" and body["model_known"] is False


def test_health_ok_with_files_and_version_uses_pose_sha(model_env):
    fake_models(model_env)
    body = client.get("/health").json()
    sha = pipeline.sha256_of(model_env / "pose.pth")
    assert body["model_known"] is True
    assert body["model"]["version"].endswith("/" + sha[:8])


def test_run_model_without_files_fails_cleanly(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"not empty")
    with pytest.raises(pipeline.AnalysisFailed) as e:
        pipeline.run(video, {"id": "a", "shot_id": "s", "filename": "v.mp4"})
    assert e.value.code in ("POSE_UNAVAILABLE", "DECODE_FAILED")


def test_run_model_uses_extracted_track(model_env, tmp_path, monkeypatch):
    """extract_track 결과가 track과 같은 형식이면 엔진이 돌고 결과 model.version 끝에 pose.pth 해시가 붙는다"""
    fake_models(model_env)
    src = json.loads((pipeline.SAMPLES_DIR / "keypoints.json").read_text(encoding="utf-8"))
    frames = [{"kp": f["points"]} if f["points"] else None for f in src["frames"]]
    video = {"video": "v.mp4", "fps": src["fps"], "width": src["width"], "height": src["height"], "frames": frames}
    monkeypatch.setattr(pipeline, "extract_track", lambda path: video)
    f = tmp_path / "v.mp4"
    f.write_bytes(b"not empty")
    result, keypoints = pipeline.run(f, {"id": "a", "shot_id": "s", "filename": "v.mp4"})
    sha = pipeline.sha256_of(model_env / "pose.pth")
    assert result["model"]["version"].endswith("/" + sha[:8])
    assert result["model"]["weights_sha256"] == sha
    assert len(keypoints["frames"]) == len(frames)


def test_frame_entry_has_box_and_kp_for_engine():
    """엔진(validity)이 box를 읽는다. 빠지면 KeyError('box')로 실서버에서 죽는다(11-06 GPU 서버 시험에서 발견)"""
    kps = [(float(i), float(i + 1)) for i in range(22)]
    entry = pipeline.frame_entry([10, 20, 300, 400], 0.8, kps, [0.9] * 22)
    assert entry["box"] == [10.0, 20.0, 300.0, 400.0] and entry["det_score"] == 0.8
    assert len(entry["kp"]) == 22 and entry["kp"][3] == [3.0, 4.0, 0.9]


def test_model_workers_env(monkeypatch):
    """ANALYSIS_MODEL_WORKERS: 없거나 잘못된 값이면 1(기존 동작), 숫자면 그 수"""
    monkeypatch.delenv("ANALYSIS_MODEL_WORKERS", raising=False)
    assert pipeline.model_workers() == 1
    monkeypatch.setenv("ANALYSIS_MODEL_WORKERS", "16")
    assert pipeline.model_workers() == 16
    monkeypatch.setenv("ANALYSIS_MODEL_WORKERS", "abc")
    assert pipeline.model_workers() == 1
    monkeypatch.setenv("ANALYSIS_MODEL_WORKERS", "0")
    assert pipeline.model_workers() == 1


def test_analysis_failed_survives_pickle():
    """워커 프로세스의 AnalysisFailed가 code·message를 지닌 채 프로세스 경계를 건넌다"""
    import pickle
    e = pickle.loads(pickle.dumps(pipeline.AnalysisFailed("DECODE_FAILED", "영상을 읽을 수 없습니다")))
    assert (e.code, e.message) == ("DECODE_FAILED", "영상을 읽을 수 없습니다")


def test_single_worker_uses_local(monkeypatch):
    """워커 1개면 풀을 만들지 않고 이 프로세스에서 추론한다"""
    monkeypatch.delenv("ANALYSIS_MODEL_WORKERS", raising=False)
    monkeypatch.setattr(pipeline, "extract_track_local", lambda path: {"video": "x"})
    monkeypatch.setattr(pipeline, "_get_pool", lambda: (_ for _ in ()).throw(AssertionError("풀 사용 안 함")))
    assert pipeline.extract_track("a.mp4") == {"video": "x"}
