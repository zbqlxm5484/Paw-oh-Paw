"""착지·이지 검출(engine/gait_events.py) 단위 테스트. 가상 보행 데이터로 정답 시점을 알고 비교한다."""
import math

from engine.gait_events import PAWS, body_length, detect_pass, detect_paw

FPS = 60
L = 200.0                  # 몸통 길이(px)
STANCE_S, SWING_S = 0.25, 0.15
CYCLE_S = STANCE_S + SWING_S


def paw_position(t, phase, speed):
    """디딤 동안은 제자리, 들림 동안은 다음 착지 자리로 움직이며 살짝 들린다"""
    tt = t + phase
    k = math.floor(tt / CYCLE_S)
    r = tt - k * CYCLE_S
    land_x = speed * k * CYCLE_S
    if r < STANCE_S:
        return land_x, 500.0
    f = (r - STANCE_S) / SWING_S
    return land_x + speed * CYCLE_S * f, 500.0 - 20 * math.sin(math.pi * f)


def make_frames(n=150, side="right", phases=(0.0, 0.2), speed=2.4 * L, noise=None):
    """머리가 진행 방향인 개 한 마리. noise(i)는 프레임마다 좌표에 더할 흔들림"""
    front, hind = PAWS[side]["front"], PAWS[side]["hind"]
    sign = 1 if side == "right" else -1
    frames = []
    for i in range(n):
        t = i / FPS
        cx = 1000 + sign * speed * t
        kp = [[0.0, 0.0, 1.0] for _ in range(22)]
        kp[2] = [cx + sign * L / 2, 300.0, 0.9]
        kp[13] = [cx - sign * L / 2, 300.0, 0.9]
        for slot, phase in ((front, phases[0]), (hind, phases[1])):
            x, y = paw_position(t, phase, speed)
            kp[slot] = [1000 + sign * x, y, 0.9]
        if noise:
            for p in kp:
                dx, dy = noise(i)
                p[0] += dx
                p[1] += dy
        frames.append(kp)
    return frames


def true_events(n, phase):
    """정답 착지(디딤 시작)와 이지(들림 시작) 프레임"""
    def in_stance(i):
        return ((i / FPS + phase) % CYCLE_S) < STANCE_S
    td = [i for i in range(1, n) if in_stance(i) and not in_stance(i - 1)]
    lo = [i for i in range(1, n) if not in_stance(i) and in_stance(i - 1)]
    return td, lo


def close(found, truth, tol=1):
    """찾은 시점마다 tol 프레임 안에 정답이 있어야 하고, 정답을 대부분(1개 빼고) 찾아야 한다"""
    assert all(any(abs(f - t) <= tol for t in truth) for f in found)
    assert len(found) >= len(truth) - 1


def test_events_match_truth_within_one_frame():
    n = 150
    events = detect_pass(make_frames(n), FPS, "right")
    for paw, phase in (("front", 0.0), ("hind", 0.2)):
        td, lo = true_events(n, phase)
        close(events[paw].touchdowns(), td)
        close(events[paw].liftoffs(), lo)


def test_small_noise_does_not_break_events():
    jitter = [(-1.0, 0.5), (1.0, -0.5), (0.5, 1.0), (-0.5, -1.0)]
    n = 150
    events = detect_pass(make_frames(n, noise=lambda i: jitter[i % 4]), FPS, "right")
    td, _ = true_events(n, 0.0)
    close(events["front"].touchdowns(), td)


def test_stride_and_stance_ratio():
    events = detect_pass(make_frames(), FPS, "right")
    strides = events["front"].strides
    assert strides
    for s in strides:
        assert abs((s.end - s.start) - CYCLE_S * FPS) <= 1          # 한 주기 24프레임
        assert 0.5 <= s.stance_ratio <= 0.7                          # 정답 0.625


def test_stance_cut_at_pass_edge_has_no_touchdown():
    # 0초부터 디딤 중이면 착지 순간은 영상에 없다
    events = detect_pass(make_frames(phases=(0.0, 0.2)), FPS, "right")
    first = events["front"].stances[0]
    assert first.first_frame == 0 and first.touchdown is None
    last = events["front"].stances[-1]
    assert last.liftoff is None or last.liftoff < 150


def test_missing_points_inside_stance_are_bridged():
    frames = make_frames()
    slot = PAWS["right"]["front"]
    td, _ = true_events(150, 0.0)
    mid = td[1] + 5                                   # 두 번째 디딤 한가운데
    frames[mid][slot][2] = 0.1                        # 한 프레임 확신도 낮음
    events = detect_paw(frames, FPS, slot)
    covering = [s for s in events.stances if s.first_frame <= mid <= s.last_frame]
    assert len(covering) == 1                         # 디딤이 둘로 쪼개지지 않음


def test_left_pass_uses_left_paws():
    events = detect_pass(make_frames(side="left"), FPS, "left")
    assert events["front"].slot == 7 and events["hind"].slot == 17
    td, _ = true_events(150, 0.0)
    close(events["front"].touchdowns(), td)


def test_no_body_length_gives_empty_result():
    frames = make_frames()
    for f in frames:
        f[2][2] = 0.0                                 # T13 확신도 0
    assert body_length(frames) is None
    assert detect_pass(frames, FPS, "right") == {}


def test_standing_still_has_no_events():
    # 몸통도 발도 안 움직이면 계속 디딤이라 착지·이지를 볼 수 없다
    frames = make_frames()
    for f in frames:
        f[2][:2], f[13][:2] = [1100.0, 300.0], [900.0, 300.0]
        for slot in PAWS["right"].values():
            f[slot][:2] = [1000.0, 500.0]
    events = detect_pass(frames, FPS, "right")
    for paw in ("front", "hind"):
        assert events[paw].touchdowns() == [] and events[paw].liftoffs() == []
