"""KPI-02 화면 위치 효과가 개의 속도 변화 때문인지 본다.
통과마다 들어오는 쪽 1/3 과 나가는 쪽 1/3 의 속도(몸통 길이/초)와 관절 각도 중앙값을 비교한다.
- 속도: 몸통 가운데 x 이동을 통과 중앙 몸통 길이로 나눔(통과 안 한 값이라 위치별 원근 영향은 작다)
- 각도 차: 나가는 쪽 - 들어오는 쪽 (부호 유지)
"""

import collections
import json
import math
import os
import re
import statistics as st
import sys

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")

sys.path.insert(0, rf"{_PJT}/creamoff_data/paw_eval")
import numpy as np  # noqa: E402
import video_kpi as K  # noqa: E402
from angles import FLEX_SIDE  # noqa: E402

rows = []  # (개, 뷰, 관절, Δ속도비, Δ각도, |L-R|)
passes = []  # (개, 뷰, v_in, v_out)
frame_rows = collections.defaultdict(list)  # (개, 관절) -> [(국소 속도, 각도)]
seen = set()
for path in sys.argv[1:]:
    for v in json.load(open(path, encoding="utf-8"))["videos"]:
        if v["sha256"] in seen:
            continue
        seen.add(v["sha256"])
        dog = re.search(r"[가-힣]+", v["video"]).group(0)
        view = re.search(r"(main|sub\d)", v["video"]).group(1)
        W, fps = v["width"], v["fps"]
        for a, b, h in K.find_passes(v):
            side = "right" if h > 0 else "left"
            fr = [
                (i, f) for i, f in enumerate(v["frames"][a : b + 1], a) if f and K._trunk(f["kp"])
            ]
            if len(fr) < 20:
                continue
            body = st.median(K._trunk(f["kp"])[1] for _, f in fr)
            xs = np.array([K._trunk(f["kp"])[2] for _, f in fr])
            ts = np.array([i for i, _ in fr]) / fps
            k = max(3, int(0.1 * fps))  # 0.1초 창으로 국소 속도
            spd = {}
            for j in range(len(fr)):
                lo, hi = max(0, j - k), min(len(fr) - 1, j + k)
                if ts[hi] > ts[lo]:
                    spd[fr[j][0]] = abs(xs[hi] - xs[lo]) / (ts[hi] - ts[lo]) / body
            use = [(i, *u) for i, f in fr for u in [K._usable(f, v)] if u]
            third = lambda x: "L" if x < W / 3 else "R" if x > 2 * W / 3 else None
            enter, leave = ("L", "R") if h > 0 else ("R", "L")  # 머리 방향 = 진행 방향
            vin = [spd[i] for i, kp, t in use if third(t[2]) == enter and i in spd]
            vout = [spd[i] for i, kp, t in use if third(t[2]) == leave and i in spd]
            if len(vin) < 3 or len(vout) < 3:
                continue
            passes.append((dog, view, st.median(vin), st.median(vout)))
            for vx, px, dx, name in K.JOINTS:
                if vx not in K.NEAR[side]:
                    continue
                g = {"L": [], "R": []}
                for i, kp, t in use:
                    if min(kp[vx][2], kp[px][2], kp[dx][2]) < K.CONF:
                        continue
                    ang = K.flexion_angle(
                        kp[vx][:2], kp[px][:2], kp[dx][:2], (h, 0.0), FLEX_SIDE[name]
                    )
                    if ang is None:
                        continue
                    if i in spd:
                        frame_rows[(dog, name)].append((spd[i], ang))
                    th = third(t[2])
                    if th:
                        g[th].append(ang)
                if len(g["L"]) >= 3 and len(g["R"]) >= 3:
                    d = st.median(g[leave]) - st.median(g[enter])
                    rows.append(
                        (
                            dog,
                            view,
                            name,
                            math.log(st.median(vout) / st.median(vin)),
                            d,
                            abs(st.median(g["L"]) - st.median(g["R"])),
                        )
                    )

print("1) 들어올 때와 나갈 때 속도 (몸통 길이/초)")
by = collections.defaultdict(list)
for dog, view, a, b in passes:
    by[dog].append((a, b))
for dog, x in sorted(by.items()):
    print(
        f"  {dog}: 통과 {len(x)} · 들어올 때 {st.median(a for a, _ in x):.2f} · 나갈 때 {st.median(b for _, b in x):.2f}"
        f" · 나갈 때/들어올 때 중앙 {st.median(b / a for a, b in x):.2f}"
    )
allr = [b / a for _, _, a, b in passes]
print(
    f"  전체 통과 {len(passes)} · 나갈 때/들어올 때 중앙 {st.median(allr):.2f} (사분위 {np.percentile(allr, 25):.2f}~{np.percentile(allr, 75):.2f})"
)

print(
    "\n2) 관절별: 속도 변화(로그비)와 각도 변화(나갈 때-들어올 때)의 상관, 그리고 각도-속도 기울기로 설명되는 몫"
)
for name in FLEX_SIDE:
    r = [x for x in rows if x[2] == name]
    if len(r) < 8:
        continue
    dv = np.array([x[3] for x in r])
    da = np.array([x[4] for x in r])
    kp02 = np.array([x[5] for x in r])
    cor = np.corrcoef(dv, da)[0, 1]
    # 개별 개 안에서 프레임 단위 각도~속도 기울기(도 / (몸통길이/초)), 개 평균
    slopes = []
    for (dog, nm), fr in frame_rows.items():
        if nm == name and len(fr) > 50:
            s, a = np.array(fr).T
            if s.std() > 0.05:
                slopes.append(np.polyfit(s, a, 1)[0])
    print(
        f"  {name}: 통과 {len(r)} · 상관 r={cor:+.2f} · KPI-02 중앙 {np.median(kp02):.1f}° · 각도 변화 중앙 {np.median(da):+.1f}°"
        f" · 각도-속도 기울기 중앙 {np.median(slopes) if slopes else float('nan'):+.1f}°/(몸통/초)"
    )

print("\n3) 속도가 거의 일정한 통과 vs 많이 바뀐 통과의 KPI-02 (관절 전체 중앙)")
grp = collections.defaultdict(list)
for dog, view, name, lr, d, k02 in rows:
    r = math.exp(lr)
    key = (
        "일정 (0.9~1.1)"
        if 0.9 <= r <= 1.1
        else "조금 (0.75~0.9, 1.1~1.33)"
        if 0.75 <= r <= 1.33
        else "많이 (그 밖)"
    )
    grp[key].append(k02)
for k in ["일정 (0.9~1.1)", "조금 (0.75~0.9, 1.1~1.33)", "많이 (그 밖)"]:
    x = grp[k]
    print(f"  {k}: (통과,관절) {len(x)} · KPI-02 중앙 {np.median(x):.1f}°")
