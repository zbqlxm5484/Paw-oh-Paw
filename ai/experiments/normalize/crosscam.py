"""같은 쪽 카메라 두 대로 KPI-02 의 화면 위치 효과가 카메라 기하인지 개의 실제 변화인지 가른다.
모형: 각도_카메라(t) = 실제(t) + g(화면 x). 같은 순간 두 카메라 차이 = g(xA) - g(xB).
- 한 카메라만 보면 각도의 화면 x 기울기 s = (실제 변화) + (g 기울기)
- 두 카메라 차이를 xA - xB 로 회귀한 기울기 k = g 기울기만
k / s 가 1 에 가까우면 카메라 기하, 0 에 가까우면 개의 실제 변화.
"""

import collections
import json
import re
import statistics as st
import sys

sys.path.insert(0, ".")
import numpy as np
import video_kpi as K
from angles import FLEX_SIDE


def series(v):
    a, b, h = max(K.find_passes(v), key=lambda p: p[1] - p[0])
    side = "right" if h > 0 else "left"
    out = {}
    for i in range(a, b + 1):
        f = v["frames"][i]
        u = f and K._usable(f, v)
        if not u:
            continue
        kp, t = u
        row = {"x": t[2] / v["width"]}
        for vx, px, dx, name in K.JOINTS:
            if vx in K.NEAR[side] and min(kp[vx][2], kp[px][2], kp[dx][2]) >= K.CONF:
                g = K.flexion_angle(kp[vx][:2], kp[px][:2], kp[dx][:2], (h, 0.0), FLEX_SIDE[name])
                if g is not None:
                    row[name] = g
        out[i] = row
    return h, out


def best_lag(A, B):
    best = None
    for L in range(-150, 151):
        cs = []
        for j in FLEX_SIDE:
            pa = [(A[i][j], B[i + L][j]) for i in A if i + L in B and j in A[i] and j in B[i + L]]
            if len(pa) >= 40:
                x, y = np.array(pa).T
                if x.std() > 1 and y.std() > 1:
                    cs.append(np.corrcoef(x, y)[0, 1])
        if len(cs) >= 4 and (best is None or np.mean(cs) > best[1]):
            best = (L, float(np.mean(cs)))
    return best


d = json.load(open(sys.argv[1], encoding="utf-8"))
sess = collections.defaultdict(dict)
for v in d["videos"]:
    view = re.search(r"(main|sub\d)", v["video"]).group(1)
    sess[v["video"][:13]][view] = v
rows = []
for s, views in sess.items():
    ser = {k: series(v) for k, v in views.items()}
    for A, B in [
        ("main", "sub2"),
        ("sub1", "sub3"),
        ("main", "sub1"),
        ("main", "sub3"),
        ("sub2", "sub1"),
        ("sub2", "sub3"),
    ]:
        if A not in ser or B not in ser or ser[A][0] != ser[B][0]:
            continue
        hA, SA = ser[A]
        hB, SB = ser[B]
        bl = best_lag(SA, SB)
        if not bl or bl[1] < 0.6:
            print(f"{s} {A}-{B}: 시간 맞추기 실패 {bl}")
            continue
        L, r = bl
        for j in FLEX_SIDE:
            pa = [
                (SA[i]["x"], SB[i + L]["x"], SA[i][j], SB[i + L][j])
                for i in SA
                if i + L in SB and j in SA[i] and j in SB[i + L]
            ]
            if len(pa) < 30:
                continue
            xa, xb, aa, ab = np.array(pa).T
            k = np.polyfit(xa - xb, aa - ab, 1)[0]
            single = [(SA[i]["x"], SA[i][j]) for i in SA if j in SA[i]]
            sx, sa = np.array(single).T
            sA = np.polyfit(sx, sa, 1)[0]
            rows.append((s, A, B, j, L, r, len(pa), float(np.ptp(xa - xb)), k, sA))
        print(f"{s} {A}-{B}: 시차 {L}프레임, 상관 {r:.2f}")
print()
print("관절별 (쌍 수): 카메라 기하 기울기 k 중앙 · 한 카메라 기울기 s 중앙 (도/화면 폭) · k/s 중앙")
by = collections.defaultdict(list)
for r in rows:
    by[r[3]].append(r)
for j, rs in by.items():
    ratios = [r[8] / r[9] for r in rs if abs(r[9]) > 5]
    print(
        f"  {j} ({len(rs)}): k {st.median(r[8] for r in rs):+.1f} · s {st.median(r[9] for r in rs):+.1f} · k/s {st.median(ratios) if ratios else float('nan'):.2f} (|s|>5 인 {len(ratios)}쌍)"
    )
allr = [r[8] / r[9] for r in rows if abs(r[9]) > 5]
print(
    f"전체 k/s 중앙 {st.median(allr):.2f} (n {len(allr)}), xA-xB 변화 폭 중앙 {st.median(r[7] for r in rows):.2f}"
)
