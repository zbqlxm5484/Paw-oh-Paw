"""Mock 견본 = 조유진 분석 API의 견본(결과 JSON v1). 실제 분석 API 연동(S15P31A404-189).

견본이 analysis_api/samples/와 같은지, 그 모양을 결과 저장(parse_result)과 결과 영상(parse_keypoints)이 그대로 읽는지
본다. 형식은 docs/analysisApi/resultFormat.md. 분석 API 쪽이 견본을 바꾸면 여기서 먼저 걸린다. DB 없이 돈다.
"""

import json
import uuid
from pathlib import Path

import pytest

from app.clients.analysis import _status_from_payload, load_fixture
from app.core.errors import JudgeReason
from app.services.analysis_results import parse_result
from app.video.render import CAMERA_RIGHT, parse_keypoints

# 저장소 안에서 돌 때만 있다. 백엔드 폴더만 받은 환경에서는 사본 비교를 건너뛴다
SAMPLES_DIR = Path(__file__).resolve().parents[2] / "analysis_api" / "samples"
SHARED_SAMPLES = ("keypoints", "result_invalid", "result_partial", "status_failed")
MODEL_VERSION = "0.4.0/v1/a4261a10"
PASS_KEYS = {
    "index",
    "start_frame",
    "end_frame",
    "heading",
    "camera_side",
    "gait",
    "valid",
    "reason_code",
    "reason",
    "measure_start",
    "measure_end",
    "metrics",
    "checks",
}
SHOT_ID = uuid.UUID("6a1d2c3b-4e5f-4a6b-8c7d-9e0f1a2b3c4d")


@pytest.mark.parametrize("name", SHARED_SAMPLES)
def test_fixture_is_a_copy_of_the_analysis_api_sample(name: str) -> None:
    sample = SAMPLES_DIR / f"{name}.json"
    if not sample.is_file():
        pytest.skip("analysis_api/samples 없음")
    assert load_fixture(name) == json.loads(sample.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", ("valid", "partial", "invalid"))
def test_result_sample_follows_v1_and_parses_without_unknown_reasons(case: str) -> None:
    result = load_fixture(f"result_{case}")
    assert result["status"] == "done" and result["validity"] == case
    assert result["versions"] == {"angle_def": "v1", "gait_events": "v1", "validity": "v1"}
    assert result["model"]["version"] == MODEL_VERSION and len(MODEL_VERSION) <= 50
    # HttpAnalysisClient.get_keypoints가 부르는 경로와 같다
    assert result["files"]["keypoints"] == f"/analyses/{result['id']}/files/keypoints"
    used = sum(1 for p in result["passes"] if p["valid"])
    assert result["summary"] == {
        "passes": len(result["passes"]),
        "used": used,
        "excluded": len(result["passes"]) - used,
    }
    for walk_pass in result["passes"]:
        assert PASS_KEYS <= set(walk_pass), walk_pass["index"]
        assert walk_pass["valid"] == (walk_pass["reason_code"] is None)

    parsed = parse_result(result, shot_id=SHOT_ID)
    assert parsed.validity == case.upper() and parsed.model_version == MODEL_VERSION
    assert len(parsed.passes) == len(result["passes"])
    reasons = {parsed.validity_reason, *(row.exclude_reason for row in parsed.passes)}
    assert JudgeReason.UNKNOWN_REASON.value not in reasons
    # v1: gait가 null인 통과는 빼지 않고 OTHER로 둔다
    expected_gaits = ["OTHER" if p["gait"] is None else p["gait"].upper() for p in result["passes"]]
    assert [row.gait_type for row in parsed.passes] == expected_gaits


def test_failed_status_sample_maps_to_a_failed_state() -> None:
    status = _status_from_payload(load_fixture("status_failed"))
    assert status.state == "failed" and status.error_code == "DECODE_FAILED" and status.error_message
    assert status.model_name == "fs-v4" and status.model_version == MODEL_VERSION


def test_keypoints_sample_parses_for_rendering() -> None:
    data = load_fixture("keypoints")
    assert data["angle_def"] == "v1"
    keypoints = parse_keypoints(data)
    assert (keypoints.width, keypoints.height, keypoints.fps) == (1920, 1080, 59.94)
    # 개를 못 찾은 프레임(points null)은 빠지고, 프레임마다 카메라 쪽이 있다
    assert sorted(keypoints.frames) == [40, 41]
    assert {frame.camera_side for frame in keypoints.frames.values()} == {CAMERA_RIGHT}
    assert all(len(frame.points) == 22 for frame in keypoints.frames.values())
