import argparse
import json
import math
from pathlib import Path

T13, ILIAC = 2, 13
SKIP = {T13, ILIAC}


def median(v):
    v = sorted(v)
    n = len(v)
    return None if not n else (v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2)


def analyse(gt, pred):
    g = json.loads(Path(gt).read_text(encoding="utf-8"))
    p = {x["ann_id"]: x["keypoints"] for x in json.loads(Path(pred).read_text(encoding="utf-8"))["predictions"]}
    names = g["categories"][0]["keypoints"]
    err = {i: [] for i in range(22) if i not in SKIP}
    for a in g["annotations"]:
        k = a["keypoints"]
        if a["id"] not in p or not (k[3 * T13 + 2] and k[3 * ILIAC + 2]):
            continue
        tx, ty, ix, iy = k[3 * T13], k[3 * T13 + 1], k[3 * ILIAC], k[3 * ILIAC + 1]
        L = math.hypot(tx - ix, ty - iy)
        if L <= 0:
            continue
        s = 1 if tx > ix else -1
        q = p[a["id"]]
        for i in err:
            if int(k[3 * i + 2]) != 2:
                continue
            dx, dy = (q[3 * i] - k[3 * i]) / L * s, (q[3 * i + 1] - k[3 * i + 1]) / L
            err[i].append((dx, dy))
    rows = {}
    for i, e in err.items():
        if not e:
            continue
        mx, my = sum(x for x, _ in e) / len(e), sum(y for _, y in e) / len(e)
        raw = median([math.hypot(x, y) for x, y in e])
        res = median([math.hypot(x - mx, y - my) for x, y in e])
        rows[names[i]] = {"n": len(e), "bias_dx": round(mx, 4), "bias_dy": round(my, 4),
                          "bias": round(math.hypot(mx, my), 4), "raw_median": round(raw, 4), "residual_median": round(res, 4)}
    allraw = median([r["raw_median"] for r in rows.values()])
    allres = median([r["residual_median"] for r in rows.values()])
    return {"joints": rows, "raw_median_of_joints": allraw, "residual_median_of_joints": allres}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    r = analyse(a.gt, a.pred)
    Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print("raw", r["raw_median_of_joints"], "residual", r["residual_median_of_joints"])


if __name__ == "__main__":
    main()
