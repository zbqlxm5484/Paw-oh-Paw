import json
import sys

src, out, win = sys.argv[1], sys.argv[2], int(sys.argv[3])
d = json.load(open(src, encoding="utf-8"))
h = win // 2
for v in d["videos"]:
    fr = v["frames"]
    for i, f in enumerate(fr):
        if not f:
            continue
        nb = [fr[j] for j in range(i - h, i + h + 1) if 0 <= j < len(fr) and fr[j]]
        kp = []
        for s in range(len(f["kp"])):
            pts = [g["kp"][s] for g in nb if g["kp"][s][2] >= 0.3] or [f["kp"][s]]
            xs = sorted(p[0] for p in pts)
            ys = sorted(p[1] for p in pts)
            kp.append([xs[len(xs) // 2], ys[len(ys) // 2], f["kp"][s][2]])
        f["norm"] = kp
d["meta"]["model"]["name"] += f"+med{win}"
json.dump(d, open(out, "w", encoding="utf-8"))
