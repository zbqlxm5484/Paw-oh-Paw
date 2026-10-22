import copy
import importlib.util
import math
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "normalize", Path(__file__).resolve().parents[1] / "ai" / "normalize" / "normalize.py")
nz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nz)

W, H = 1000, 600


def make_pass(heading=1, shrink=0.75, box_shrink=1.0, n=71, conf=0.9, rise=0.0):
    """화면 왼쪽에서 오른쪽으로 걷는 가짜 통과. 오른쪽으로 갈수록 몸통 가로가 shrink 배, 상자 높이가 box_shrink 배가 된다."""
    frames = []
    for i in range(n):
        x = 150 + 700 * i / (n - 1)
        u = (x - 150) / 700
        kx = math.exp(math.log(shrink) * u)
        ky = math.exp(math.log(box_shrink) * u)
        y = 300 + rise * (x - 150)
        kp = [[x, y + 50 * ky, conf] for _ in range(22)]
        # rise: 카메라가 기울어 궤적과 몸통이 같은 기울기로 기운 경우
        kp[nz.T13] = [x + heading * 100 * kx, y + rise * heading * 100 * kx, conf]
        kp[nz.ILIAC] = [x - heading * 100 * kx, y - rise * heading * 100 * kx, conf]
        frames.append({"box": [x - 120, y - 100 * ky, x + 120, y + 100 * ky], "kp": kp})
    return {"meta": {"model": {"name": "t"}},
            "videos": [{"video": "a", "width": W, "height": H, "fps": 30, "frames": frames}]}


def trunk_lens(frames, key):
    return [nz._trunk(f[key])["len"] for f in frames if f and key in f]


def test_horizontal_shrink_is_corrected():
    d = nz.normalize(make_pass(shrink=0.75))
    lens = trunk_lens(d["videos"][0]["frames"], "norm")
    assert len(lens) == 71
    assert max(lens) - min(lens) < 0.5


def test_screen_position_is_kept():
    # KPI-02 는 화면 왼쪽·오른쪽 1/3 을 나눠 재므로 몸통 가운데는 움직이면 안 된다
    d = nz.normalize(make_pass(shrink=0.75))
    for f in d["videos"][0]["frames"]:
        a, b = nz._trunk(f["kp"]), nz._trunk(f["norm"])
        assert abs(a["cx"] - b["cx"]) < 0.01 and abs(a["cy"] - b["cy"]) < 0.01


def test_original_kp_is_untouched():
    src = make_pass(shrink=0.75)
    before = copy.deepcopy([f["kp"] for f in src["videos"][0]["frames"]])
    d = nz.normalize(src)
    assert [f["kp"] for f in d["videos"][0]["frames"]] == before


def test_heading_sets_camera_side():
    right = nz.normalize(make_pass(heading=1))["videos"][0]["passes"]
    left = nz.normalize(make_pass(heading=-1))["videos"][0]["passes"]
    assert [p["camera_side"] for p in right] == ["right"]
    assert [p["camera_side"] for p in left] == ["left"]


def test_side_view_without_change_stays_put():
    d = nz.normalize(make_pass(shrink=1.0))
    for f in d["videos"][0]["frames"]:
        for (x0, y0, _), (x1, y1, _) in zip(f["kp"], f["norm"]):
            assert abs(x0 - x1) < 0.02 and abs(y0 - y1) < 0.02


def test_vertical_scale_follows_box_height():
    # 카메라에서 멀어져 상자 높이가 줄면 세로를 늘린다. 다리 점(몸통 가운데에서 아래로 50*ky)이 일정해져야 한다
    d = nz.normalize(make_pass(shrink=1.0, box_shrink=0.8))
    drops = [f["norm"][0][1] - nz._trunk(f["norm"])["cy"] for f in d["videos"][0]["frames"]]
    assert max(drops) - min(drops) < 0.5
    off = nz.normalize(make_pass(shrink=1.0, box_shrink=0.8), use_y=False)
    drops_off = [f["norm"][0][1] - nz._trunk(f["norm"])["cy"] for f in off["videos"][0]["frames"]]
    assert max(drops_off) - min(drops_off) > 5


def test_large_stretch_is_flagged():
    p = nz.normalize(make_pass(shrink=0.5))["videos"][0]["passes"][0]
    assert p["stretch_x"] > nz.MAX_STRETCH and p["limit_exceeded"]
    q = nz.normalize(make_pass(shrink=0.75))["videos"][0]["passes"][0]
    assert not q["limit_exceeded"]


def test_short_or_standing_pass_is_skipped():
    assert nz.normalize(make_pass(n=8))["videos"][0]["passes"] == []
    d = make_pass()
    for f in d["videos"][0]["frames"]:                      # 제자리: 가로로 움직이지 않음
        dx = f["kp"][0][0] - 500
        for p in f["kp"]:
            p[0] -= dx
        f["box"] = [380, f["box"][1], 620, f["box"][3]]
    assert nz.normalize(d)["videos"][0]["passes"] == []


def test_low_confidence_frame_gets_no_norm():
    d = make_pass()
    d["videos"][0]["frames"][35]["kp"][nz.T13][2] = 0.1
    v = nz.normalize(d)["videos"][0]
    assert "norm" not in v["frames"][35]
    assert all("norm" in f for i, f in enumerate(v["frames"]) if i != 35)


def test_tilt_option_levels_the_path():
    d = nz.normalize(make_pass(shrink=1.0, rise=0.1), tilt=True)
    p = d["videos"][0]["passes"][0]
    assert abs(p["tilt_deg"] - math.degrees(math.atan(0.1))) < 0.1
    for f in d["videos"][0]["frames"]:                      # 몸통 앞뒤 점이 같은 높이로 돌아온다
        a, b = f["norm"][nz.T13], f["norm"][nz.ILIAC]
        assert abs(a[1] - b[1]) < 0.5
