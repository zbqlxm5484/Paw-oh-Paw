"""보행 수치(engine/gait_metrics.py) 테스트. 착지 검출 테스트의 가상 보행(정답을 아는 걸음)을 그대로 쓴다."""
import random

from test_gait_events import CYCLE_S, FPS, STANCE_S, L, make_frames

from engine.gait_events import PAWS
from engine.gait_metrics import pass_metrics, paw_seen_ratio
from engine.reasons import metric_reason_detail

SPEED = 2.4 * L                          # make_frames 기본 속도 (px/초)
TRUE_STRIDE = SPEED * CYCLE_S / L * 100  # 한 주기에 발이 나아간 거리, L 대비 % (96.0)
TRUE_STANCE = STANCE_S / CYCLE_S * 100   # 입각기 비율 % (62.5)
TRUE_LIFT = 20 / L * 100                 # 들림 때 발끝이 20px 올라간다 (paw_position), L 대비 % (10.0)


def missing(item: dict) -> str:
    """측정 불가 수치의 사유 코드. 값은 null, 문장(reason_detail)이 꼭 붙는다"""
    assert item["value"] is None and item["reason_detail"], item
    return item["reason"]


def test_clean_walk_matches_truth():
    for side in ("right", "left"):
        m = pass_metrics(make_frames(side=side), FPS, side)
        for paw in ("front", "hind"):
            assert abs(m[f"stride_length_{paw}"]["value"] - TRUE_STRIDE) <= 2.0
            assert m[f"stride_length_{paw}"]["unit"] == "pct_body"
            # 이 가상 보행에서는 착지가 1프레임 늦게 잡혀 디딤이 1프레임 짧다. 1프레임 차이까지 허용
            # (실제 영상은 착지는 맞고 이지를 약 2프레임 일찍 잡는다: docs/engine/gaitMetrics.md 4절)
            assert abs(m[f"stance_ratio_{paw}"]["value"] - TRUE_STANCE) <= 100 / (CYCLE_S * FPS) + 0.1
            assert m[f"stance_ratio_{paw}"]["unit"] == "pct"
        assert abs(m["walk_speed"]["value"] - 2.4) <= 0.05 and m["walk_speed"]["unit"] == "body_per_sec"
        assert m["gait_cycles"] == {"value": 5, "unit": "count"}     # 2.5초 / 0.4초 → 착지 6번, 주기 5번


def test_keys_follow_result_format_v1():
    m = pass_metrics(make_frames(), FPS, "right")
    assert set(m) == {"stride_length_front", "stride_length_hind", "stance_ratio_front", "stance_ratio_hind",
                      "paw_lift_front", "paw_lift_hind", "walk_speed", "gait_cycles"}


def test_jitter_keeps_values_close():
    rng = random.Random(3)
    frames = make_frames(noise=lambda i: (rng.gauss(0, 1.5), rng.gauss(0, 1.5)))
    m = pass_metrics(frames, FPS, "right")
    for paw in ("front", "hind"):
        assert abs(m[f"stride_length_{paw}"]["value"] - TRUE_STRIDE) <= 5.0
        assert abs(m[f"stance_ratio_{paw}"]["value"] - TRUE_STANCE) <= 8.0


def test_too_short_pass_is_not_enough_cycles_not_zero():
    m = pass_metrics(make_frames(n=20), FPS, "right")       # 0.33초: 착지를 두 번 못 봄
    for key in ("stride_length_front", "stance_ratio_hind", "paw_lift_front"):
        assert missing(m[key]) == "NOT_ENOUGH_CYCLES"
    assert "0.3초" in m["stride_length_front"]["reason_detail"]          # 몸이 보인 시간과 착지 수를 적는다
    assert m["gait_cycles"] == {"value": 0, "unit": "count"}


def test_hidden_paw_is_low_confidence():
    frames = make_frames()
    hind = PAWS["right"]["hind"]
    for kp in frames:
        kp[hind][2] = 0.1                                    # 뒷발끝 확신도가 바닥 아래
    assert paw_seen_ratio(frames, hind) == 0.0
    m = pass_metrics(frames, FPS, "right")
    assert missing(m["stride_length_hind"]) == "LOW_CONFIDENCE"
    assert m["stance_ratio_hind"]["reason"] == "LOW_CONFIDENCE"
    assert missing(m["paw_lift_hind"]) == "LOW_CONFIDENCE"
    assert "0%로 기준(50%)" in m["paw_lift_hind"]["reason_detail"]
    assert m["stride_length_front"]["value"] is not None    # 앞발은 그대로 잰다


def test_no_body_is_low_confidence():
    m = pass_metrics([None] * 60, FPS, "right")
    assert missing(m["walk_speed"]) == "LOW_CONFIDENCE"
    assert m["stride_length_front"]["reason"] == "LOW_CONFIDENCE"
    assert "몸통 길이" in m["paw_lift_front"]["reason_detail"]


def test_paw_lift_matches_truth():
    for side in ("right", "left"):
        m = pass_metrics(make_frames(side=side), FPS, side)
        for paw in ("front", "hind"):
            assert abs(m[f"paw_lift_{paw}"]["value"] - TRUE_LIFT) <= 0.5
            assert m[f"paw_lift_{paw}"]["unit"] == "pct_body"


def test_paw_lift_follows_tilted_ground():
    """바닥(또는 카메라)이 기울어 디딤 자리가 오른쪽으로 갈수록 낮아져도 앞뒤 디딤을 이은 선에서 잰다"""
    frames = make_frames()
    for kp in frames:
        for p in kp:
            p[1] += 0.05 * p[0]                       # x 1000px마다 50px 내려감
    m = pass_metrics(frames, FPS, "right")
    for paw in ("front", "hind"):
        assert abs(m[f"paw_lift_{paw}"]["value"] - TRUE_LIFT) <= 1.0


def test_paw_lift_with_jitter():
    rng = random.Random(5)
    frames = make_frames(noise=lambda i: (rng.gauss(0, 1.5), rng.gauss(0, 1.5)))
    m = pass_metrics(frames, FPS, "right")
    for paw in ("front", "hind"):
        assert abs(m[f"paw_lift_{paw}"]["value"] - TRUE_LIFT) <= 2.5     # 최댓값이라 흔들림만큼 커질 수 있다


def test_every_missing_metric_has_detail():
    """측정 불가로 나오는 경우를 모두 만들어, 수치마다 문장이 붙는지 본다"""
    hidden = make_frames()
    for kp in hidden:
        kp[PAWS["right"]["hind"]][2] = 0.1
    cases = (make_frames(n=20), hidden, [None] * 60)
    count = 0
    for frames in cases:
        for item in pass_metrics(frames, FPS, "right").values():
            if item.get("value") is None:
                missing(item)
                count += 1
    assert count >= 15


def test_metric_detail_texts_avoid_report_forbidden_words():
    from test_reasons import FORBIDDEN

    facts = ({"kind": "no_body_length"}, {"kind": "paw_hidden", "paw": "front", "ratio": 0.3, "min": 0.5},
             {"kind": "few_touchdowns", "paw": "hind", "seen_s": 0.8, "touchdowns": 1},
             {"kind": "few_touchdowns", "paw": "hind", "seen_s": 0.8, "touchdowns": 1, "metric": "stifle_cycle_rom"},
             {"kind": "no_swing", "paw": "front", "seen_s": 0.8, "stances": 1}, {"kind": "no_trunk"},
             {"kind": "joint_hidden", "joint": "carpus", "ratio": 0.2, "min": 0.5})
    for f in facts:
        text = metric_reason_detail(f)
        assert text and not FORBIDDEN.search(text), (f, text)


def test_summarize_track_uses_only_valid_passes(tmp_path):
    """관절점 파일 요약(문서 4절 재현 명령): 유효 통과만 세고, 보행 속도는 늘 나온다"""
    import json

    import pytest
    pytest.importorskip("yaml")
    from test_validity import walk

    from engine.gait_metrics import summarize_track
    valid, short = walk(), walk(seconds=1.4)          # 두 번째는 화면 가운데서 끝나 무효(PARTIAL_PASS)
    path = tmp_path / "t.track.json"
    path.write_text(json.dumps({"meta": {}, "videos": [dict(valid, video="a.mp4"), dict(short, video="b.mp4")]}),
                    encoding="utf-8")
    s = summarize_track(str(path))
    assert s["videos"] == 2 and s["valid_passes"] == 1
    assert len(s["values"]["walk_speed"]) == 1
