"""비스듬한 진행 감지 (정규화 고도화 1단계). 검토용 구현이며 기업 확인 전이다.

    python oblique.py --track fs-v4.track.json [--out oblique.json] [--csv oblique.csv]
    python oblique.py --self-test

개가 카메라 화면과 평행하지 않게 걸으면 2차원 정규화 값이 틀어진다. 통과(normalize.find_passes 와 같은 규칙)마다
몸통 축(어깨 가운데 - 고관절 가운데)으로 아래 값을 재고 문턱을 넘으면 "비스듬함" 으로 표시한다.

들어오고 나가는 프레임(상자가 화면 끝에 닿음)은 몸이 잘려 몸통이 짧아 보이므로 뺀다.

- path_deg: 몸통 가운데 궤적의 화면 수평 대비 기울기(Theil-Sen). 카메라 쪽으로 다가오거나 멀어지면 화면 위아래로 흐른다.
- axis_deg: 몸통 축이 화면 수평과 이루는 각(통과 중앙값). 머리를 숙이는 자세에도 바뀌므로 참고 값이다.
- len_change: 통과 처음과 끝의 몸통 길이 비(로그 직선 맞춤, 1 = 변화 없음).
- height_change: 상자 높이 비. 카메라와의 거리만 바뀌면 몸통 길이와 상자 높이가 같은 비율로 변한다.
- yaw_change: len_change / height_change. 거리 변화로는 설명되지 않는 몸통 길이 변화 = 진행 방향이 화면과
  이루는 각이 통과 중에 바뀐 정도. 비스듬히 걸을 때의 핵심 신호다.

비(ratio)는 모두 1 이상으로 접는다(큰 쪽 / 작은 쪽). 문턱(THRESH)은 10-26 초안: 현행 모델 관절점의 분포에서 정했다
(docs/normalize/oblique.md). 기업 기준·유효 판별 규칙(S15P31A404-21)과 겹치지 않게 이 함수는 표시만 하고 버리지 않는다.
"""

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from normalize import CONF, MIN_FRAMES, find_passes, theil_sen  # noqa: E402

SHOULDER, HIP = (4, 9), (14, 18)
EDGE = 0.01  # 상자가 화면 왼쪽·오른쪽 끝 이 비율 안에 닿으면 몸이 잘린 프레임으로 보고 뺀다
# 10-26 초안. 넘으면 비스듬함. path_deg 는 절댓값.
THRESH = {"path_deg": 5.0, "yaw_change": 1.25, "len_change": 1.6}

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _mid(kp, idx):
    pts = [kp[i] for i in idx if kp[i][2] >= CONF]
    if not pts:
        return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def body_axis(kp):
    """-> {dx, dy, len, cx, cy} (어깨 가운데 - 고관절 가운데). 점이 없으면 None."""
    s, h = _mid(kp, SHOULDER), _mid(kp, HIP)
    if s is None or h is None:
        return None
    dx, dy = s[0] - h[0], s[1] - h[1]
    L = math.hypot(dx, dy)
    return (
        {"dx": dx, "dy": dy, "len": L, "cx": (s[0] + h[0]) / 2, "cy": (s[1] + h[1]) / 2}
        if L > 1e-6
        else None
    )


def _ratio(fit, lo, hi):
    a, b = fit[0] * lo + fit[1], fit[0] * hi + fit[1]
    return math.exp(abs(a - b))


def measure_pass(v, a, b, heading):
    rows, W = [], v["width"]
    for f in v["frames"][a : b + 1]:
        if not f or f["box"][0] <= EDGE * W or f["box"][2] >= (1 - EDGE) * W:
            continue
        t = body_axis(f["kp"])
        bh = f["box"][3] - f["box"][1]
        if t and bh > 1:
            rows.append((t, bh))
    if len(rows) < MIN_FRAMES:
        return None
    xs = [t["cx"] for t, _ in rows]
    lo, hi = min(xs), max(xs)
    fl = theil_sen(xs, [math.log(t["len"]) for t, _ in rows])
    fh = theil_sen(xs, [math.log(bh) for _, bh in rows])
    fp = theil_sen(xs, [t["cy"] for t, _ in rows])
    if not (fl and fh and fp):
        return None
    # 몸통 길이와 상자 높이의 비를 직접 맞춘다(두 비를 나누면 방향이 엇갈릴 때 상쇄되지 않는다)
    fr = theil_sen(xs, [math.log(t["len"]) - math.log(bh) for t, bh in rows])
    axis = statistics.median(math.degrees(math.atan2(-t["dy"], t["dx"] * heading)) for t, _ in rows)
    m = {
        "start": a,
        "end": b,
        "heading": heading,
        "n": len(rows),
        "x_range": [round(lo, 1), round(hi, 1)],
        "path_deg": round(math.degrees(math.atan(fp[0])), 2),
        "axis_deg": round(axis, 2),
        "len_change": round(_ratio(fl, lo, hi), 4),
        "height_change": round(_ratio(fh, lo, hi), 4),
        "yaw_change": round(_ratio(fr, lo, hi), 4),
    }
    why = []
    if abs(m["path_deg"]) > THRESH["path_deg"]:
        why.append("path")
    if m["yaw_change"] > THRESH["yaw_change"]:
        why.append("yaw")
    if m["len_change"] > THRESH["len_change"]:
        why.append("len")
    m["oblique"] = bool(why)
    m["reasons"] = why
    return m


def detect(d):
    out = []
    for v in d["videos"]:
        for a, b, h in find_passes(v):
            m = measure_pass(v, a, b, h)
            if m:
                out.append(dict(video=v["video"], **m))
    return out


def self_test():
    W, H = 1000, 600

    def fake(len_k, h_k, dy_per_x):
        frames = []
        for x in range(150, 860, 10):
            u = (x - 150) / 700
            L, bh = 100 * math.exp(len_k * u), 200 * math.exp(h_k * u)
            y = 300 + dy_per_x * (x - 150)
            kp = [[x, y, 0.9] for _ in range(22)]
            for i in SHOULDER:
                kp[i] = [x + L / 2, y, 0.9]
            for i in HIP:
                kp[i] = [x - L / 2, y, 0.9]
            kp[2], kp[13] = [x + L / 2, y - 10, 0.9], [x - L / 2, y - 10, 0.9]
            frames.append({"box": [x - 120, y - bh / 2, x + 120, y + bh / 2], "kp": kp})
        return {"video": "t", "width": W, "height": H, "fps": 30, "frames": frames}

    flat = detect({"videos": [fake(0, 0, 0)]})[0]
    assert not flat["oblique"] and flat["yaw_change"] < 1.01 and abs(flat["path_deg"]) < 0.1, flat
    near = detect({"videos": [fake(-0.3, -0.3, 0)]})[0]  # 거리만 변함: 몸통·상자 같은 비율
    assert (
        near["yaw_change"] < 1.01 and near["height_change"] > 1.3 and "yaw" not in near["reasons"]
    ), near
    yaw = detect({"videos": [fake(-0.4, 0, 0)]})[0]  # 몸통만 짧아짐: 비스듬함
    assert yaw["oblique"] and "yaw" in yaw["reasons"], yaw
    down = detect({"videos": [fake(0, 0, 0.25)]})[0]  # 화면 아래로 흐름(약 14°)
    assert down["oblique"] and "path" in down["reasons"], down
    print("self-test OK")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--track", nargs="+")
    ap.add_argument("--out")
    ap.add_argument("--csv")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.track:
        ap.error("--track 이 필요하다")
    res = []
    for p in a.track:
        res += detect(json.loads(Path(p).read_text(encoding="utf-8")))
    n = len(res)
    print(
        f"통과 {n}개, 비스듬함 {sum(r['oblique'] for r in res)}개 "
        + " ".join(f"{k} {sum(k in r['reasons'] for r in res)}" for k in ("path", "yaw", "len"))
    )
    for k in ("path_deg", "axis_deg", "len_change", "height_change", "yaw_change"):
        vals = sorted(abs(r[k]) if k == "path_deg" else r[k] for r in res)
        q = lambda p: vals[min(n - 1, int(p * n))]
        print(f"  {k:<14} 중앙 {q(0.5):.3f}  90% {q(0.9):.3f}  최대 {vals[-1]:.3f}")
    if a.out:
        Path(a.out).write_text(
            json.dumps({"thresh": THRESH, "passes": res}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        print(f"-> {a.out}")
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(
                fh, fieldnames=[k for k in res[0] if k != "x_range"], extrasaction="ignore"
            )
            w.writeheader()
            for r in res:
                w.writerow(dict(r, reasons="|".join(r["reasons"])))
        print(f"-> {a.csv}")


if __name__ == "__main__":
    main()
