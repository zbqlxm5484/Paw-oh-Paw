import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
files = sys.argv[1:]
sys.argv = [sys.argv[0], str(Path(__file__).parent / "key")]
import compare as C  # noqa: E402

labs = {Path(f).stem.replace("_calib", ""): C.read_xml(f) for f in files}
who = list(labs)


def dist(pts, i, k, L):
    return math.hypot(pts[i][0] - k[3 * i], pts[i][1] - k[3 * i + 1]) / L


rows = []
for i in range(22):
    if i in C.SKIP:
        continue
    model = {w: [] for w in ["모델"] + who}
    between = []
    for name, im in C.by_name.items():
        a = C.anns[im["id"]]
        k, p = a["keypoints"], C.pre[a["id"]]
        if int(k[3 * i + 2]) == 0:
            continue
        L = math.hypot(k[3 * C.T13] - k[3 * C.ILIAC], k[3 * C.T13 + 1] - k[3 * C.ILIAC + 1]) or 1
        model["모델"].append(math.hypot(p[3 * i] - k[3 * i], p[3 * i + 1] - k[3 * i + 1]) / L)
        pts = [labs[w].get(name) for w in who]
        for w, q in zip(who, pts):
            if q and q[i][2]:
                model[w].append(dist(q, i, k, L))
        if len(who) >= 2 and all(q and q[i][2] for q in pts[:2]):
            between.append(math.hypot(pts[0][i][0] - pts[1][i][0], pts[0][i][1] - pts[1][i][1]) / L)
    rows.append((C.names[i], *[C.median(model[w]) for w in ["모델"] + who], C.median(between)))

head = ["관절", "모델 vs 기업"] + [f"{w} vs 기업" for w in who] + ([f"{who[0]} vs {who[1]}"] if len(who) >= 2 else [])
print("| " + " | ".join(head) + " |")
print("| :--- |" + " ---: |" * (len(head) - 1))
for r in sorted(rows, key=lambda r: -(r[1] or 0)):
    vals = [f"{v:.3f}" if v is not None else "-" for v in r[1:len(head)]]
    print(f"| {r[0]} | " + " | ".join(vals) + " |")
