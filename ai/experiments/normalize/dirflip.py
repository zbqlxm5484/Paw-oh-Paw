"""같은 카메라·같은 개에서 진행 방향별로 (왼쪽 1/3 중앙 - 오른쪽 1/3 중앙) 부호 있는 차이를 본다.
카메라 기하면 방향과 무관하게 같은 부호, 개의 실제 변화(출발·도착)면 방향에 따라 부호가 뒤집힌다."""

import collections
import json
import re
import statistics as st
import sys

sys.path.insert(0, ".")
import video_kpi as K
from angles import FLEX_SIDE

res = collections.defaultdict(list)  # (개, 뷰, 관절, heading) -> [L-R]
seen = set()
for path in sys.argv[1:]:
    for v in json.load(open(path, encoding="utf-8"))["videos"]:
        if v["sha256"] in seen:
            continue
        seen.add(v["sha256"])
        dog = re.search(r"[가-힣]+", v["video"]).group(0)
        view = re.search(r"(main|sub\d)", v["video"]).group(1)
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
                    res[(dog, view, name, h)].append(st.median(L) - st.median(R))
print("개 뷰 관절: 머리 왼쪽(h-1) L-R 중앙 [n] | 머리 오른쪽(h+1) L-R 중앙 [n] -> 판정")
same = flip = 0
for dog, view, name in sorted({k[:3] for k in res}):
    m, p = res.get((dog, view, name, -1), []), res.get((dog, view, name, 1), [])
    if len(m) < 2 or len(p) < 2:
        continue
    a, b = st.median(m), st.median(p)
    big = max(abs(a), abs(b)) >= 5
    verdict = "-" if not big else ("같은 부호=기하" if a * b > 0 else "뒤집힘=개 변화")
    same += big and a * b > 0
    flip += big and a * b < 0
    print(f"{dog} {view} {name}: {a:+6.1f}° [{len(m)}] | {b:+6.1f}° [{len(p)}] -> {verdict}")
print(f"\n큰 차이(5° 이상) 중 같은 부호 {same}건, 뒤집힘 {flip}건")
