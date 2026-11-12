"""분석 파이프라인(pipeline.py) 테스트. 가상 개 한 마리의 관절점 파일로 엔진 연결을 확인한다."""
import hashlib
import json

import main
import pipeline
import pytest
from conftest import client  # 세션 동안 열어 둔 클라이언트 (conftest.py)

pytest.importorskip("yaml")   # 유효 판별 기준값(engine/validity.yaml)을 읽는 데 필요

FPS, W, H, L = 30, 1920, 1080, 150.0
VIDEO = b"fake video bytes"


def dog(cx):
    """몸통 가운데가 cx이고 오른쪽을 보는 개. 화면 밖이면 None"""
    box = [cx - 160, 380, cx + 160, 680]
    if box[2] < 0 or box[0] > W:
        return None
    box = [max(0.0, box[0]), box[1], min(float(W), box[2]), box[3]]
    kp = [[cx, 450.0, 0.9] for _ in range(22)]
    kp[2] = [cx + L / 2, 500.0, 0.9]      # T13
    kp[13] = [cx - L / 2, 500.0, 0.9]     # 장골능
    kp[18], kp[19], kp[20], kp[21] = [cx - 60, 520.0, 0.9], [cx - 50, 580.0, 0.9], [cx - 65, 620.0, 0.9], [cx - 60, 650.0, 0.9]
    for toe in (7, 12, 17):
        kp[toe] = [cx, 650.0, 0.9]
    return {"box": box, "kp": kp}


def track_file(tmp_path, sha=None, name="shot.mp4"):
    """3초 동안 1000px/초로 오른쪽으로 걷는 영상 하나가 든 관절점 파일 (기업 video_kpi.py track 형식)"""
    frames = [dog(-250.0 + 1000.0 * i / FPS) for i in range(3 * FPS)]
    video = {"video": f"videos/{name}", "sha256": sha or hashlib.sha256(VIDEO).hexdigest(),
             "width": W, "height": H, "fps": FPS, "frames": frames}
    path = tmp_path / "test.track.json"
    path.write_text(json.dumps({"meta": {"model": {"name": "fs-test"}}, "videos": [video]}), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def track_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "STORAGE_DIR", tmp_path / "storage")
    monkeypatch.setattr(main, "API_KEY", "")
    monkeypatch.setenv("ANALYSIS_POSE_SOURCE", "track")
    monkeypatch.setenv("ANALYSIS_MODEL", "fs-test")      # 가상 관절점 파일 meta의 모델 이름과 같게
    monkeypatch.setenv("ANALYSIS_WEIGHTS_SHA256", "a4261a10" + "0" * 56)
    pipeline.load_tracks.cache_clear()


def analyze(name="shot.mp4", body=VIDEO):
    job_id = client.post("/analyses", files={"video": (name, body, "video/mp4")},
                         data={"meta": '{"shot_id": "s-1"}'}).json()["id"]
    return job_id, client.get(f"/analyses/{job_id}").json()


def test_track_result_is_v1(tmp_path, monkeypatch):
    monkeypatch.setenv("ANALYSIS_TRACK_FILE", str(track_file(tmp_path)))
    job_id, status = analyze()
    assert status["status"] == "done"
    assert status["model"] == {"name": "fs-test", "version": f"{pipeline.API_VERSION}/v1/a4261a10"}
    r = client.get(f"/analyses/{job_id}/result").json()
    assert r["shot_id"] == "s-1" and r["validity"] == "valid" and r["validity_reason"] is None
    assert r["versions"] == {"angle_def": "v1", "gait_events": "v1", "validity": "v1", "gait_metrics": "v2",
                             "joint_rom": "v1"}
    assert r["input"] == {"filename": "shot.mp4", "codec": None, "fps": FPS, "width": W, "height": H,
                          "frames": 3 * FPS}
    p = r["passes"][0]
    assert p["index"] == 1 and p["camera_side"] == "right" and p["valid"]
    assert {"stride_length_front", "stance_ratio_hind", "walk_speed", "gait_cycles",
            "rom_stifle", "angle_median_shoulder", "stifle_cycle_rom"} <= set(p["metrics"])
    assert abs(p["metrics"]["walk_speed"]["value"] - 1000 / 150) < 0.1      # 가상 개: 1000px/초, 몸통 150px
    assert "validity_reason_text" in r and r["validity_reason_text"] is None
    for key in ("measure_start", "measure_end", "checks", "reason_code", "reason", "reason_detail", "gait"):
        assert key in p


def test_keypoints_angles_on_camera_side_only(tmp_path, monkeypatch):
    monkeypatch.setenv("ANALYSIS_TRACK_FILE", str(track_file(tmp_path)))
    job_id, _ = analyze()
    kp = client.get(f"/analyses/{job_id}/files/keypoints").json()
    assert kp["angle_def"] == "v1" and kp["fps"] == FPS and len(kp["frames"]) == 3 * FPS
    assert [f["frame"] for f in kp["frames"]] == list(range(3 * FPS))     # 0부터, 빠짐 없이
    first = kp["frames"][0]
    assert first["points"] is None and first["camera_side"] is None and first["angles"] is None
    inside = [f for f in kp["frames"] if f["camera_side"]]
    assert inside and all(len(f["points"]) == 22 for f in inside)
    keys = set().union(*(f["angles"] for f in inside))
    assert keys and all(k.endswith("_r") for k in keys)     # 카메라 쪽(오른쪽) 다리만
    assert all(0 <= v <= 360 for f in inside for v in f["angles"].values())


def test_found_by_filename_when_hash_differs(tmp_path, monkeypatch):
    monkeypatch.setenv("ANALYSIS_TRACK_FILE", str(track_file(tmp_path, sha="0" * 64, name="jenny_01.mp4")))
    assert analyze(name="jenny_01.mp4")[1]["status"] == "done"


@pytest.mark.parametrize("setup", ["no_file", "no_match"])
def test_pose_unavailable(tmp_path, monkeypatch, setup):
    if setup == "no_file":
        monkeypatch.setenv("ANALYSIS_TRACK_FILE", str(tmp_path / "none.json"))
    else:
        monkeypatch.setenv("ANALYSIS_TRACK_FILE", str(track_file(tmp_path, sha="0" * 64, name="other.mp4")))
    status = analyze()[1]
    assert status["status"] == "failed" and status["error"]["code"] == "POSE_UNAVAILABLE"


def test_sample_mode_is_default(monkeypatch):
    monkeypatch.delenv("ANALYSIS_POSE_SOURCE")
    job_id, status = analyze()
    assert status["model"]["name"] == "sample-pipeline"
    r = client.get(f"/analyses/{job_id}/result").json()
    assert r["versions"]["validity"] == "v1"
