import json
import math
import sys

base = json.load(open("/exp/results/base.track.json", encoding="utf-8"))
FEET = (7, 12, 17, 21)
T13, ILIAC = 2, 13


def trunk(kp):
    return math.dist(kp[T13][:2], kp[ILIAC][:2])


for name in sys.argv[1:]:
    sm = json.load(open(f"/exp/results/{name}.track.json", encoding="utf-8"))
    d_feet, d_all = [], []
    for va, vb in zip(base["videos"], sm["videos"]):
        for fa, fb in zip(va["frames"], vb["frames"]):
            if fa is None or fb is None or not fb.get("norm"):
                continue
            L = trunk(fa["kp"])
            if L < 1e-6:
                continue
            for i in range(22):
                e = math.dist(fa["kp"][i][:2], fb["norm"][i][:2]) / L
                d_all.append(e)
                if i in FEET:
                    d_feet.append(e)
    d_feet.sort()
    d_all.sort()
    q = lambda v, p: v[int(p * (len(v) - 1))]
    print(f"{name:8s} 모든 점 중앙 {q(d_all, .5):.4f} 상위5% {q(d_all, .95):.4f} | 발끝 중앙 {q(d_feet, .5):.4f} 상위5% {q(d_feet, .95):.4f} 최대 {d_feet[-1]:.3f} (몸통 길이 비율)")
