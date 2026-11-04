"""관절 가동 범위(engine/joint_rom.py) 테스트. 착지 검출 테스트의 가상 보행에 무릎 각도를 정해 넣고 정답과 비교한다."""
import math

from test_gait_events import CYCLE_S, FPS, make_frames

from engine.joint_rom import frame_angles, joint_metrics, percentile_width

MEAN, AMP = 120.0, 20.0                      # 무릎 각도 = 120 + 20 sin(주기마다 한 바퀴)
TRUE_ROM = 2 * AMP * math.sin(math.pi / 2 * 0.9)   # 사인파의 5에서 95백분위 폭 (약 39.5)


def with_stifle(frames, side="right"):
    """무릎(꼭짓점)·고관절(근위)·뒷발목(원위)을 정해진 각도로 놓는다"""
    hip, knee, hock = (18, 19, 20) if side == "right" else (14, 15, 16)
    for i, kp in enumerate(frames):
        theta = math.radians(MEAN + AMP * math.sin(2 * math.pi * (i / FPS) / CYCLE_S))
        vx, vy = kp[13][0], 400.0
        kp[knee] = [vx, vy, 0.9]
        kp[hip] = [vx, vy - 100, 0.9]
        kp[hock] = [vx + 100 * math.sin(theta), vy - 100 * math.cos(theta), 0.9]
    return frames


def test_percentile_width():
    assert percentile_width(list(range(101))) == 90
    assert percentile_width([5.0]) is None


def test_frame_angles_only_camera_side():
    kp = with_stifle(make_frames(n=1))[0]
    right = frame_angles(kp, "right")
    assert "stifle" in right and abs(min(right["stifle"], 360 - right["stifle"]) - MEAN) < 0.5
    assert "stifle" not in frame_angles(kp, "left")        # 왼쪽 무릎 점은 비어 있다


def test_stifle_rom_and_cycle_rom_match_truth():
    for side in ("right", "left"):
        m = joint_metrics(with_stifle(make_frames(side=side), side), FPS, side)
        assert abs(m["rom_stifle"]["value"] - TRUE_ROM) <= 2.0 and m["rom_stifle"]["unit"] == "deg"
        assert abs(min(m["angle_median_stifle"]["value"], 360 - m["angle_median_stifle"]["value"]) - MEAN) <= 2.0
        cycles = m["stifle_cycle_rom"]["values"]
        assert len(cycles) == 5 and all(abs(c - TRUE_ROM) <= 3.0 for c in cycles)
        assert m["stifle_cycle_rom"]["unit"] == "deg"


def test_keys_follow_result_format_v1():
    m = joint_metrics(with_stifle(make_frames()), FPS, "right")
    joints = ("shoulder", "elbow", "carpus", "hip", "stifle", "tarsus")
    assert set(m) == {f"rom_{j}" for j in joints} | {f"angle_median_{j}" for j in joints} | {"stifle_cycle_rom"}


def test_unseen_joint_is_low_confidence_not_zero():
    m = joint_metrics(with_stifle(make_frames()), FPS, "right")
    assert m["rom_shoulder"] == {"value": None, "reason": "LOW_CONFIDENCE"}   # 어깨 점을 넣지 않았다
    assert m["angle_median_elbow"]["reason"] == "LOW_CONFIDENCE"


def test_no_cycle_is_not_enough_cycles():
    m = joint_metrics(with_stifle(make_frames(n=20)), FPS, "right")     # 0.33초: 주기 없음
    assert m["rom_stifle"] == {"value": None, "reason": "NOT_ENOUGH_CYCLES"}
    assert m["stifle_cycle_rom"] == {"value": None, "reason": "NOT_ENOUGH_CYCLES"}
