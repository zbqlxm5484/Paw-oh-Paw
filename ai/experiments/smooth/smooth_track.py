import argparse
import json
from pathlib import Path

import numpy as np
from scipy.signal import savgol_filter


def runs(frames, max_gap):
    out, cur, last = [], [], None
    for i, f in enumerate(frames):
        if f is None:
            continue
        if last is not None and i - last > max_gap:
            out.append(cur)
            cur = []
        cur.append(i)
        last = i
    if cur:
        out.append(cur)
    return out


def smooth_video(v, window, order, max_gap, key):
    fr = v["frames"]
    smoothed = 0
    for run in runs(fr, max_gap):
        if len(run) < window:
            for i in run:
                fr[i]["norm"] = [list(p) for p in fr[i].get(key) or fr[i]["kp"]]
            continue
        src = np.array([fr[i].get(key) or fr[i]["kp"] for i in run], dtype=float)
        out = src.copy()
        out[:, :, 0] = savgol_filter(src[:, :, 0], window, order, axis=0, mode="interp")
        out[:, :, 1] = savgol_filter(src[:, :, 1], window, order, axis=0, mode="interp")
        for n, i in enumerate(run):
            fr[i]["norm"] = [[round(float(x), 2), round(float(y), 2), float(c)] for x, y, c in out[n]]
        smoothed += len(run)
    return smoothed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--window", type=int, default=7)
    ap.add_argument("--order", type=int, default=2)
    ap.add_argument("--max-gap", type=int, default=1)
    ap.add_argument("--source", choices=["kp", "norm"], default="kp")
    a = ap.parse_args()
    d = json.loads(Path(a.track).read_text(encoding="utf-8"))
    total = sum(smooth_video(v, a.window, a.order, a.max_gap, a.source) for v in d["videos"])
    d["meta"]["smooth"] = {"method": "savgol", "window": a.window, "order": a.order, "max_gap": a.max_gap, "source": a.source}
    d["meta"]["model"] = dict(d["meta"]["model"], name=d["meta"]["model"]["name"] + f"+sg{a.window}")
    Path(a.out).write_text(json.dumps(d), encoding="utf-8")
    print(f"smoothed frames {total} -> {a.out}")


if __name__ == "__main__":
    main()
