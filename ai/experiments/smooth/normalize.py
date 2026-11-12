"""관절점 정규화 v0 (F-01) — 2차원 기하 보정. 검토용 구현이며 기업 확인 전이다.

    python normalize.py --track fs-v4.track.json --out fs-v4.norm.track.json [--no-scale-x] [--no-scale-y] [--iso] [--tilt]

입력·출력은 paw_eval video_kpi 의 track 형식이다. 프레임마다 원본 "kp" 는 그대로 두고(PR-F01-05)
보정한 좌표를 "norm" 에 넣는다. 영상마다 "passes" 에 통과별 진행 방향·카메라 쪽 다리·보정 값을 적는다.

보정 (통과 단위)
- 진행 방향: 몸통(T13 - 장골능)이 옆으로 누운 프레임의 다수결. +1 = 머리가 화면 오른쪽.
  카메라 쪽 다리: 머리가 오른쪽이면 개의 오른쪽 다리가 카메라 쪽이다(PR-F01-04).
- 가로 크기: 비스듬히 걸으면 화면 위치에 따라 몸통이 짧아 보인다. 몸통 길이의 로그를 몸통 가운데 x 에
  대한 직선으로 맞추고(Theil-Sen), 통과 안에서 가장 긴 쪽(가장 옆모습에 가까운 쪽)에 맞춰 가로를 늘린다.
- 세로 크기: 카메라와의 거리 변화. 상자 높이의 로그를 같은 방식으로 맞춰 세로를 늘린다.
- 기울기(--tilt, 기본 끔): 통과 안 몸통 가운데 궤적의 기울기만큼 몸통 가운데를 축으로 돌린다.
- 보정은 몸통 가운데를 고정점으로 하므로 화면 위치(KPI-02 의 왼쪽·오른쪽 1/3)는 바뀌지 않는다.
- 맞춘 직선은 통과 전체에서 하나라 프레임별 흔들림을 키우지 않는다. 체절(다리) 길이는 쓰지 않는다.
- 가로 보정 비율이 MAX_STRETCH 를 넘는 통과는 보정 한계 초과로 표시만 한다(F-03 으로 넘길 후보).
"""
import argparse
import json
import math
import statistics
import sys
from pathlib import Path

NORM_VERSION = "v0"
T13, ILIAC = 2, 13
CONF = 0.3                     # paw_eval 과 같은 확신도 바닥
SIDE_MIN = 0.5                 # 옆모습 판정
GAP_S = 0.5
MIN_TRAVEL = 1 / 3
MIN_FRAMES = 10
MAX_STRETCH = 1.6              # 통과 안 가로 보정 최대 비율. 넘으면 limit_exceeded

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _trunk(kp):
    (ax, ay, ac), (bx, by, bc) = kp[T13][:3], kp[ILIAC][:3]
    if ac < CONF or bc < CONF:
        return None
    L = math.hypot(ax - bx, ay - by)
    return {"dx": ax - bx, "len": L, "cx": (ax + bx) / 2, "cy": (ay + by) / 2} if L > 1e-6 else None


def find_passes(v):
    """-> [(시작, 끝, heading)]. paw_eval video_kpi.find_passes 와 같은 규칙."""
    fr, W = v["frames"], v["width"]
    gap = max(1, round(GAP_S * v["fps"]))
    runs, cur, last = [], [], None
    for i, f in enumerate(fr):
        if f is None:
            continue
        if last is not None and i - last > gap:
            runs.append(cur)
            cur = []
        cur.append(i)
        last = i
    if cur:
        runs.append(cur)
    out = []
    for run in runs:
        tr = [_trunk(fr[i]["kp"]) for i in run]
        xs = [t["cx"] for t in tr if t]
        signs = [1 if t["dx"] > 0 else -1 for t in tr if t and abs(t["dx"]) / t["len"] >= SIDE_MIN]
        if len(xs) < MIN_FRAMES or not signs:
            continue
        if abs(statistics.median(xs[-5:]) - statistics.median(xs[:5])) / W >= MIN_TRAVEL:
            out.append((run[0], run[-1], 1 if sum(signs) > 0 else -1))
    return out


def theil_sen(xs, ys):
    """-> (기울기, 절편). 점이 2개 미만이면 None."""
    if len(xs) < 2:
        return None
    sl = [(ys[j] - ys[i]) / (xs[j] - xs[i]) for i in range(len(xs)) for j in range(i + 1, len(xs))
          if abs(xs[j] - xs[i]) > 1e-6]
    if not sl:
        return None
    b = statistics.median(sl)
    return b, statistics.median(y - b * x for x, y in zip(xs, ys))


def fit_pass(v, a, b, heading):
    fr = v["frames"]
    side = [(t, f) for f in fr[a:b + 1] if f for t in [_trunk(f["kp"])] if t and abs(t["dx"]) / t["len"] >= SIDE_MIN]
    xs = [t["cx"] for t, _ in side]
    fx = theil_sen(xs, [math.log(t["len"]) for t, _ in side])
    fy = theil_sen(xs, [math.log(f["box"][3] - f["box"][1]) for _, f in side])
    ft = theil_sen(xs, [t["cy"] for t, _ in side])
    lo, hi = min(xs), max(xs)
    ref = lambda fit: max(fit[0] * lo + fit[1], fit[0] * hi + fit[1])        # 통과 안 가장 큰 값(로그)
    stretch = math.exp(ref(fx) - min(fx[0] * lo + fx[1], fx[0] * hi + fx[1]))
    return {"start": a, "end": b, "heading": heading, "camera_side": "right" if heading > 0 else "left",
            "n_fit": len(side), "x_range": [round(lo, 1), round(hi, 1)],
            "fit_x": [fx[0], fx[1], ref(fx)], "fit_y": [fy[0], fy[1], ref(fy)],
            "tilt_deg": math.degrees(math.atan(ft[0])), "stretch_x": stretch,
            "limit_exceeded": stretch > MAX_STRETCH}


def apply(kp, p, use_x=True, use_y=True, tilt=False, iso=False):
    t = _trunk(kp)
    if t is None:
        return None
    cx, cy = t["cx"], t["cy"]
    ky = math.exp(p["fit_y"][2] - (p["fit_y"][0] * cx + p["fit_y"][1])) if use_y else 1.0
    kx = math.exp(p["fit_x"][2] - (p["fit_x"][0] * cx + p["fit_x"][1])) if use_x else ky if iso else 1.0
    th = -math.radians(p["tilt_deg"]) if tilt else 0.0
    c, s = math.cos(th), math.sin(th)
    out = []
    for x, y, conf in kp:
        dx, dy = x - cx, y - cy
        dx, dy = c * dx - s * dy, s * dx + c * dy
        out.append([round(cx + kx * dx, 2), round(cy + ky * dy, 2), conf])
    return out


def normalize(d, use_x=True, use_y=True, tilt=False, iso=False):
    for v in d["videos"]:
        passes = []
        for a, b, h in find_passes(v):
            p = fit_pass(v, a, b, h)
            if p["n_fit"] < MIN_FRAMES:
                continue
            passes.append(p)
            for f in v["frames"][a:b + 1]:
                if f:
                    n = apply(f["kp"], p, use_x, use_y, tilt, iso)
                    if n:
                        f["norm"] = n
        v["passes"] = passes
    d["meta"]["normalize"] = {"version": NORM_VERSION, "scale_x": use_x, "scale_y": use_y, "iso": iso, "tilt": tilt,
                              "max_stretch": MAX_STRETCH}
    d["meta"]["model"] = dict(d["meta"]["model"], name=d["meta"]["model"]["name"] + "+norm")
    return d


def self_test():
    # 머리 오른쪽, 오른쪽으로 갈수록 가로만 약 0.75 배까지 줄어드는 가짜 통과 -> 보정 후 몸통 길이 일정
    W = 1000
    frames = []
    for i, x in enumerate(range(150, 860, 10)):
        k = math.exp(-0.29 * (x - 150) / 700)
        kp = [[x, 300, 0.9] for _ in range(22)]
        kp[T13], kp[ILIAC] = [x + 100 * k, 250, .9], [x - 100 * k, 250, .9]
        frames.append({"box": [x - 120, 200, x + 120, 400], "kp": kp})
    d = {"meta": {"model": {"name": "t"}}, "videos": [{"video": "a", "width": W, "height": 600, "fps": 30,
                                                     "frames": frames}]}
    normalize(d)
    v = d["videos"][0]
    assert len(v["passes"]) == 1 and v["passes"][0]["camera_side"] == "right", v["passes"]
    lens = [_trunk(f["norm"])["len"] for f in v["frames"]]
    assert max(lens) - min(lens) < 0.5, (min(lens), max(lens))
    assert all(abs(_trunk(f["norm"])["cx"] - _trunk(f["kp"])["cx"]) < 0.01 for f in v["frames"])   # 화면 위치 그대로
    print("self-test OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--track")
    ap.add_argument("--out")
    ap.add_argument("--no-scale-x", action="store_true")
    ap.add_argument("--no-scale-y", action="store_true")
    ap.add_argument("--tilt", action="store_true")
    ap.add_argument("--iso", action="store_true", help="--no-scale-x 와 함께: 세로 비율을 가로에도 똑같이 적용(거리 변화만 보정)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not (a.track and a.out):
        ap.error("--track 과 --out 이 필요하다")
    d = json.loads(Path(a.track).read_text(encoding="utf-8"))
    normalize(d, not a.no_scale_x, not a.no_scale_y, a.tilt, a.iso)
    ps = [p for v in d["videos"] for p in v["passes"]]
    print(f"통과 {len(ps)}개, 가로 보정 비율 중앙 {statistics.median(p['stretch_x'] for p in ps):.3f}"
          f" (최대 {max(p['stretch_x'] for p in ps):.3f}), 한계 초과 {sum(p['limit_exceeded'] for p in ps)}개,"
          f" 기울기 중앙 {statistics.median(p['tilt_deg'] for p in ps):.2f}°")
    Path(a.out).write_text(json.dumps(d), encoding="utf-8")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
