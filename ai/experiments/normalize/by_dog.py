import collections
import copy
import importlib.util
import json
import math
import os
import random
import statistics as st
import sys

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")

sys.path.insert(0, ".")
import numpy as np  # noqa: E402
import video_kpi as K  # noqa: E402
from angles import FLEX_SIDE  # noqa: E402

spec = importlib.util.spec_from_file_location("nm", rf"{_PJT}/S15P31A404/ai/normalize/normalize.py")
nm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nm)
KG = {
    "럭키": 29,
    "아미": 29,
    "빵또아": 22,
    "백설이": 11.8,
    "하쿠": 7.7,
    "건빵": 3.9,
    "오이": 2.1,
    "제니": 17.9,
}


def dog(name):
    return next(k for k in KG if k in name)


def k01k02(vs):
    c, df = [], []
    for v in vs:
        a, b = K.kpi01_02(v, K.find_passes(v))
        c += a
        df += b
    return (st.median(c) if c else None, len(c), st.median(df) if df else None, len(df))


def oracle(vs):
    out = []
    for v in vs:
        for a, b, h in K.find_passes(v):
            side = "right" if h > 0 else "left"
            use = [u for u in (K._usable(f, v) for f in v["frames"][a : b + 1] if f) if u]
            for p, q in K.SEGMENTS[side]:
                r = [
                    (t[2], math.hypot(kp[p][0] - kp[q][0], kp[p][1] - kp[q][1]))
                    for kp, t in use
                    if kp[p][2] >= K.CONF and kp[q][2] >= K.CONF
                ]
                if len(r) < 10:
                    continue
                x = np.array([a for a, _ in r])
                L = np.array([b for _, b in r])
                cc = np.polyfit(x, np.log(L), 1)
                Ld = L / np.exp(np.polyval(cc, x))
                out.append(Ld.std() / Ld.mean())
    return st.median(out) if out else None


def null02(vs, rnd):
    gs = []
    for v in vs:
        W = v["width"]
        for a, b, h in K.find_passes(v):
            side = "right" if h > 0 else "left"
            use = [u for u in (K._usable(f, v) for f in v["frames"][a : b + 1] if f) if u]
            for vx, px, dx, name in K.JOINTS:
                if vx not in K.NEAR[side]:
                    continue
                L, R = [], []
                for kp, t in use:
                    if min(kp[vx][2], kp[px][2], kp[dx][2]) < K.CONF:
                        continue
                    g = K.flexion_angle(
                        kp[vx][:2], kp[px][:2], kp[dx][:2], (h, 0.0), FLEX_SIDE[name]
                    )
                    if g is None:
                        continue
                    (L if t[2] < W / 3 else R if t[2] > 2 * W / 3 else []).append(g)
                if len(L) >= 3 and len(R) >= 3:
                    gs.append((L, R))
    if not gs:
        return None, None
    res = []
    for _ in range(100):
        one = []
        for L, R in gs:
            pool = L + R
            rnd.shuffle(pool)
            one.append(abs(st.median(pool[: len(L)]) - st.median(pool[len(L) :])))
        res.append(st.median(one))
    return st.median(res), st.median(len(L) for L, R in gs)


rnd = random.Random(0)
by = collections.defaultdict(list)
for path in sys.argv[1:]:
    for v in json.load(open(path, encoding="utf-8"))["videos"]:
        by[dog(v["video"])].append(v)
print(
    "개(kg) 영상 통과 | KPI-01 현행 → 세로+기울기 (상한) | KPI-02 현행 → 세로+기울기 · 잡음바닥 (1/3당 프레임)"
)
for name, vs in sorted(by.items(), key=lambda x: -KG[x[0]]):
    b = k01k02(vs)
    d = {"meta": {"model": {"name": "x"}}, "videos": copy.deepcopy(vs)}
    nm.normalize(d, use_x=False, use_y=True, tilt=True)
    n = k01k02(d["videos"])
    np_ = sum(len(K.find_passes(v)) for v in vs)
    z, nf = null02(vs, rnd)
    f = lambda x, p: "-" if x is None else format(x, p)
    red = lambda a, c: "-" if not a or c is None else f"{100*(c/a-1):+.0f}%"
    print(
        f"{name}({KG[name]}) {len(vs)} {np_} | {f(b[0],'.3f')} → {f(n[0],'.3f')} {red(b[0],n[0])} (상한 {red(b[0],oracle(vs))}, n {b[1]})"
        f" | {f(b[2],'.1f')}° → {f(n[2],'.1f')}° {red(b[2],n[2])} · 바닥 {f(z,'.1f')}° ({f(nf,'.0f')}장, n {b[3]})"
    )
