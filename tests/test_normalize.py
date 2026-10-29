import copy
import importlib.util
import math
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "normalize", Path(__file__).resolve().parents[1] / "ai" / "normalize" / "normalize.py")
nz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nz)

W, H = 1000, 600


def make_pass(heading=1, shrink=0.75, box_shrink=1.0, n=71, conf=0.9, rise=0.0, body=False):
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
        if body:   # 어깨(4·9)를 T13, 고관절(14·18)을 장골능 자리에 둬 oblique.py 의 몸통 축이 몸통과 같게
            for i in (4, 9):
                kp[i] = list(kp[nz.T13])
            for i in (14, 18):
                kp[i] = list(kp[nz.ILIAC])
        frames.append({"box": [x - 120, y - 100 * ky, x + 120, y + 100 * ky], "kp": kp})
    return {"meta": {"model": {"name": "t"}},
            "videos": [{"video": "a", "width": W, "height": H, "fps": 30, "frames": frames}]}


def trunk_lens(frames, key):
    return [nz._trunk(f[key])["len"] for f in frames if f and key in f]


def test_horizontal_shrink_is_corrected_only_with_stretch_x():
    # v0 방식(가로 늘리기)은 몸통 길이를 펴고, v1 기본은 가로를 늘리지 않는다(S15P31A404-102)
    d = nz.normalize(make_pass(shrink=0.75), use_x=True, iso=False)
    lens = trunk_lens(d["videos"][0]["frames"], "norm")
    assert len(lens) == 71
    assert max(lens) - min(lens) < 0.5
    v1 = trunk_lens(nz.normalize(make_pass(shrink=0.75))["videos"][0]["frames"], "norm")
    assert min(v1) / max(v1) < 0.8


def test_default_scales_x_and_y_together():
    # 카메라에서 멀어지면(상자 높이 0.8 배) 가로·세로를 같은 비율로 키워 몸통 길이도 펴진다
    d = nz.normalize(make_pass(shrink=0.8, box_shrink=0.8))
    lens = trunk_lens(d["videos"][0]["frames"], "norm")
    assert max(lens) - min(lens) < 0.5
    assert d["meta"]["normalize"]["version"] == "v1" and d["meta"]["normalize"]["iso"]


def test_oblique_is_recorded_not_dropped():
    # 몸통만 짧아지고 상자 높이는 그대로 = 비스듬한 진행. 표시만 하고 norm 은 그대로 만든다
    d = nz.normalize(make_pass(shrink=0.6, body=True))
    p = d["videos"][0]["passes"][0]
    assert p["oblique"]["oblique"] and "yaw" in p["oblique"]["reasons"]
    assert all("norm" in f for f in d["videos"][0]["frames"])
    flat = nz.normalize(make_pass(shrink=1.0, body=True))["videos"][0]["passes"][0]
    assert not flat["oblique"]["oblique"]


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
