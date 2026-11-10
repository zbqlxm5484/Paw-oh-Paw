"""점검 스크립트(check_server.py)의 결과 모양 확인·관절점 비교 테스트. 실제 track 결과를 만들어 넣는다."""
import copy

import check_server
import main
import pipeline
import pytest
from conftest import client
from test_pipeline import track_file

pytest.importorskip("yaml")


@pytest.fixture
def done(tmp_path, monkeypatch):
    """가상 개 한 마리 track 결과 (result, keypoints, 관절점 파일의 영상)"""
    monkeypatch.setattr(main, "STORAGE_DIR", tmp_path / "storage")
    monkeypatch.setattr(main, "API_KEY", "")
    monkeypatch.setenv("ANALYSIS_POSE_SOURCE", "track")
    monkeypatch.setenv("ANALYSIS_MODEL", "fs-test")
    path = track_file(tmp_path)
    monkeypatch.setenv("ANALYSIS_TRACK_FILE", str(path))
    pipeline.load_tracks.cache_clear()
    job_id = client.post("/analyses", files={"video": ("shot.mp4", b"fake video bytes", "video/mp4")}).json()["id"]
    result = client.get(f"/analyses/{job_id}/result").json()
    keypoints = client.get(f"/analyses/{job_id}/files/keypoints").json()
    video = pipeline.load_tracks(str(path))["shot.mp4"]
    return result, keypoints, video


def test_real_result_passes_all_checks(done):
    result, keypoints, _ = done
    assert check_server.check_result(result, keypoints) == []


def test_broken_results_are_caught(done):
    result, keypoints, _ = done
    bad = copy.deepcopy(result)
    bad["model"]["version"] = "0.6/v1"
    bad["summary"]["used"] += 1
    bad["passes"][0]["metrics"]["walk_speed"] = {"value": None, "reason": "WHATEVER"}
    del bad["versions"]["joint_rom"]
    kp = copy.deepcopy(keypoints)
    kp["frames"] = kp["frames"][1:]
    problems = " / ".join(check_server.check_result(bad, kp))
    for word in ("model.version", "summary", "측정 불가 사유", "versions", "프레임 수", "frame 번호"):
        assert word in problems


def test_angles_on_wrong_side_are_caught(done):
    result, keypoints, _ = done
    kp = copy.deepcopy(keypoints)
    f = next(f for f in kp["frames"] if f["angles"])
    f["camera_side"] = "left"
    assert any("각도 키" in p for p in check_server.check_result(result, kp))


def test_compare_with_same_track_is_zero(done):
    result, keypoints, video = done
    c = check_server.compare_with_track(result, keypoints, video)
    assert c["frames"][0] == c["frames"][1] and c["dog_found"][0] == c["dog_found"][1]
    assert c["point_diff_px_median"] < 0.1     # 관절점 파일은 좌표를 0.1px로 반올림해 낸다
