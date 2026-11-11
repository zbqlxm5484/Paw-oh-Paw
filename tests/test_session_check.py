"""회차 묶음 검증 도구(engine/session_check.py) 테스트. S15P31A404-261"""
import pytest

pytest.importorskip("yaml")

from test_gait_events import FPS, make_frames  # noqa: E402
from test_validity import walk  # noqa: E402

from engine.gait_events import detect_pass  # noqa: E402
from engine.session_check import check_session, swing_peaks  # noqa: E402


def test_session_counts_valid_passes_by_side():
    valid, short = walk(), walk(seconds=1.4)          # 두 번째는 화면 가운데서 끝나 무효(PARTIAL_PASS)
    s = check_session({"videos": [dict(valid, video="a.mp4"), dict(short, video="b.mp4")]})
    assert s["videos"] == 2 and s["passes"] == 1 and s["by_side"] == {"right": 1}
    assert s["invalid"] == {"b.mp4": "PARTIAL_PASS"}
    assert s["session"][("right", "walk_speed")]["n"] == 1
    assert s["session"][("right", "walk_speed")]["cv"] is None     # 통과 하나로는 변동계수가 없다


def test_swing_peaks_match_virtual_lift():
    """가상 보행은 들림 때 발끝을 20px(몸통 길이 200px의 10%) 올린다. 가장 높은 프레임은 10% 근처, 그다음은 그 아래"""
    frames = make_frames()
    events = detect_pass(frames, FPS, "right")
    peaks = swing_peaks(frames, events["front"], 200.0)
    assert len(peaks) >= 4
    for top, second in peaks:
        assert abs(top - 10.0) <= 0.5 and second <= top
