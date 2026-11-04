"""보행 수치(engine/gait_metrics.py) 테스트. 착지 검출 테스트의 가상 보행(정답을 아는 걸음)을 그대로 쓴다."""
import random

from test_gait_events import CYCLE_S, FPS, STANCE_S, L, make_frames

from engine.gait_events import PAWS
from engine.gait_metrics import pass_metrics, paw_seen_ratio

SPEED = 2.4 * L                          # make_frames 기본 속도 (px/초)
TRUE_STRIDE = SPEED * CYCLE_S / L * 100  # 한 주기에 발이 나아간 거리, L 대비 % (96.0)
TRUE_STANCE = STANCE_S / CYCLE_S * 100   # 입각기 비율 % (62.5)


def test_clean_walk_matches_truth():
    for side in ("right", "left"):
        m = pass_metrics(make_frames(side=side), FPS, side)
        for paw in ("front", "hind"):
            assert abs(m[f"stride_length_{paw}"]["value"] - TRUE_STRIDE) <= 2.0
            assert m[f"stride_length_{paw}"]["unit"] == "pct_body"
            # 착지 검출이 1프레임 늦게 잡혀(KPI-05 허용 안) 디딤이 1프레임 짧게 나온다. 1프레임 차이까지 허용
            assert abs(m[f"stance_ratio_{paw}"]["value"] - TRUE_STANCE) <= 100 / (CYCLE_S * FPS) + 0.1
            assert m[f"stance_ratio_{paw}"]["unit"] == "pct"
        assert abs(m["walk_speed"]["value"] - 2.4) <= 0.05 and m["walk_speed"]["unit"] == "body_per_sec"
        assert m["gait_cycles"] == {"value": 5, "unit": "count"}     # 2.5초 / 0.4초 → 착지 6번, 주기 5번


def test_keys_follow_result_format_v1():
    m = pass_metrics(make_frames(), FPS, "right")
    assert set(m) == {"stride_length_front", "stride_length_hind", "stance_ratio_front", "stance_ratio_hind",
                      "walk_speed", "gait_cycles"}


def test_jitter_keeps_values_close():
    rng = random.Random(3)
    frames = make_frames(noise=lambda i: (rng.gauss(0, 1.5), rng.gauss(0, 1.5)))
    m = pass_metrics(frames, FPS, "right")
    for paw in ("front", "hind"):
        assert abs(m[f"stride_length_{paw}"]["value"] - TRUE_STRIDE) <= 5.0
        assert abs(m[f"stance_ratio_{paw}"]["value"] - TRUE_STANCE) <= 8.0


def test_too_short_pass_is_not_enough_cycles_not_zero():
    m = pass_metrics(make_frames(n=20), FPS, "right")       # 0.33초: 착지를 두 번 못 봄
    for key in ("stride_length_front", "stance_ratio_hind"):
        assert m[key] == {"value": None, "reason": "NOT_ENOUGH_CYCLES"}
    assert m["gait_cycles"] == {"value": 0, "unit": "count"}


def test_hidden_paw_is_low_confidence():
    frames = make_frames()
    hind = PAWS["right"]["hind"]
    for kp in frames:
        kp[hind][2] = 0.1                                    # 뒷발끝 확신도가 바닥 아래
    assert paw_seen_ratio(frames, hind) == 0.0
    m = pass_metrics(frames, FPS, "right")
    assert m["stride_length_hind"] == {"value": None, "reason": "LOW_CONFIDENCE"}
    assert m["stance_ratio_hind"]["reason"] == "LOW_CONFIDENCE"
    assert m["stride_length_front"]["value"] is not None    # 앞발은 그대로 잰다


def test_no_body_is_low_confidence():
    m = pass_metrics([None] * 60, FPS, "right")
    assert m["walk_speed"] == {"value": None, "reason": "LOW_CONFIDENCE"}
    assert m["stride_length_front"]["reason"] == "LOW_CONFIDENCE"
