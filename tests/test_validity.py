"""유효 판별(engine/validity.py) 테스트. 화면을 가로지르는 가상 개로 사유마다 하나씩 확인한다."""
import pytest

pytest.importorskip("yaml")   # 기준값 파일을 읽는 데 필요 (루트 requirements-dev.txt에 있음, CI reproduce 잡이 설치)

from engine.validity import judge_shot, load_config  # noqa: E402

FPS = 30
W, H = 1920, 1080
L = 150.0          # 몸통 길이(px)


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def frame(cx, head=1, iliac_y=500.0):
    """몸통 가운데가 cx인 개 한 마리. 화면 밖이면 None"""
    box = [cx - 160, 380, cx + 160, 680]
    if box[2] < 0 or box[0] > W:
        return None
    box = [max(0.0, box[0]), box[1], min(float(W), box[2]), box[3]]
    kp = [[cx, 450.0, 0.9] for _ in range(22)]
    kp[2] = [cx + head * L / 2, 500.0, 0.9]      # T13
    kp[13] = [cx - head * L / 2, iliac_y, 0.9]   # 장골능
    for toe in (7, 12, 17, 21):
        kp[toe] = [cx, 650.0, 0.9]
    return {"box": box, "kp": kp}


def walk(speed=1000.0, seconds=3.0, start=-250.0, plan=None):
    """speed(px/초)로 오른쪽으로 걷는 영상. plan(t) → (속도 배율, 머리 방향, 장골능 y)로 구간마다 바꾼다"""
    frames, cx = [], start
    for i in range(round(seconds * FPS)):
        t = i / FPS
        mult, head, iliac_y = plan(t) if plan else (1.0, 1, 500.0)
        frames.append(frame(cx, head, iliac_y))
        cx += speed * mult / FPS
    return {"fps": FPS, "width": W, "height": H, "frames": frames}


def test_normal_walk_is_valid(cfg):
    r = judge_shot(walk(), cfg)
    assert r["validity"] == "valid" and r["validity_reason"] is None
    assert r["summary"] == {"passes": 1, "used": 1, "excluded": 0}
    p = r["passes"][0]
    assert p["heading"] == "right" and p["camera_side"] == "right" and p["valid"]


def test_no_dog(cfg):
    r = judge_shot({"fps": FPS, "width": W, "height": H, "frames": [None] * 90}, cfg)
    assert r["validity"] == "invalid" and r["validity_reason"] == "NO_DOG"


def test_running(cfg):
    r = judge_shot(walk(speed=2200.0, seconds=1.5), cfg)      # 약 14.7 몸통 길이/초
    assert r["validity"] == "invalid" and r["validity_reason"] == "RUNNING"
    assert r["passes"][0]["reason"]


def test_stopped(cfg):
    plan = lambda t: (0.0 if 1.0 <= t < 2.0 else 1.0, 1, 500.0)   # 1초 멈춤
    r = judge_shot(walk(seconds=4.0, plan=plan), cfg)
    assert r["validity_reason"] == "STOPPED"


def test_sitting(cfg):
    plan = lambda t: (0.0 if 1.0 <= t < 2.0 else 1.0, 1, 620.0 if 1.0 <= t < 2.0 else 500.0)
    r = judge_shot(walk(seconds=4.0, plan=plan), cfg)
    assert r["validity_reason"] == "SITTING"      # 앉음이 멈춤보다 우선


def test_turned(cfg):
    plan = lambda t: (-1.0, -1, 500.0) if 1.0 <= t < 1.6 else (1.0, 1, 500.0)   # 0.6초 뒤돌아 걸음
    r = judge_shot(walk(seconds=4.0, plan=plan), cfg)
    assert r["validity_reason"] == "TURNED"


def test_video_ends_before_leaving(cfg):
    r = judge_shot(walk(seconds=1.4), cfg)       # 화면 가운데쯤에서 영상이 끝남
    assert r["validity"] == "invalid" and r["validity_reason"] == "PARTIAL_PASS"


def test_measure_range_inside_pass(cfg):
    p = judge_shot(walk(), cfg)["passes"][0]
    for key in ("measure_start", "measure_end"):
        assert p[key] is None or p["start_frame"] <= p[key] <= p["end_frame"]
