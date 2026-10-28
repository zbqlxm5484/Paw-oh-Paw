"""KPI-02 잡음 바닥: 왼쪽·오른쪽 1/3 프레임의 위치 표시를 무작위로 섞어도 나오는 값."""

import json
import random
import statistics as st
import sys

sys.path.insert(0, ".")
import video_kpi as K
from angles import FLEX_SIDE


def groups(v):
    out = []
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
                ang = K.flexion_angle(kp[vx][:2], kp[px][:2], kp[dx][:2], (h, 0.0), FLEX_SIDE[name])
                if ang is None:
                    continue
                (L if t[2] < W / 3 else R if t[2] > 2 * W / 3 else []).append(ang)
            if len(L) >= 3 and len(R) >= 3:
                out.append((name, L, R))
    return out


rnd = random.Random(0)
for path in sys.argv[1:]:
    d = json.load(open(path, encoding="utf-8"))
    gs = [g for v in d["videos"] for g in groups(v)]
    real = [abs(st.median(L) - st.median(R)) for _, L, R in gs]
    null = []
    for _ in range(200):
        one = []
        for _, L, R in gs:
            pool = L + R
            rnd.shuffle(pool)
            one.append(abs(st.median(pool[: len(L)]) - st.median(pool[len(L) :])))
        null.append(st.median(one))
    nL = st.median(len(L) for _, L, R in gs)
    nR = st.median(len(R) for _, L, R in gs)
    print(
        f"{path.split('/')[-1]}: KPI-02 실제 {st.median(real):.2f}° · 섞었을 때(잡음 바닥) {st.median(null):.2f}°"
        f" [{sorted(null)[10]:.2f}~{sorted(null)[189]:.2f}] · (통과,관절) {len(gs)}개, 1/3당 프레임 중앙 {nL:.0f}/{nR:.0f}"
    )
    by = {}
    for (name, L, R), r in zip(gs, real):
        by.setdefault(name, []).append(r)
    print("   관절별 실제:", {k: round(st.median(x), 1) for k, x in by.items()})
