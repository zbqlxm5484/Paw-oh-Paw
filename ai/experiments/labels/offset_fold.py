r"""96 보정 학습의 누수 확인: 50장을 촬영 묶음 단위로 둘로 나눠, 한쪽 평균 차이로 학습셋을 옮기고 다른 쪽에서 채점한다 (10-26).

    python offset_fold.py  → splits/wowwow/wowwow_train46_offset_fold{0,1}.json, fold_split.json
옮기는 부위는 전체 50장으로 고른 4부위 그대로(apply_offset.py 와 같은 계산).
"""

import copy
import json
import os
import sys
from pathlib import Path

import numpy as np

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
SPL = Path(rf"{_PJT}\splits\wowwow")
PART = {"어깨뼈 위끝": (3, 8), "팔꿈치": (5, 10), "뒷발끝": (17, 21), "T13": (2, 2)}
rows = json.load(open(HERE / "offset50_result.json", encoding="utf-8"))["rows"]
lst = json.load(open(HERE / "offset50_list.json", encoding="utf-8"))
sess = sorted({r["session"] for r in lst})
fold_of = {s: i % 2 for i, s in enumerate(sess)}
img_fold = {r["cvat_name"]: fold_of[r["session"]] for r in lst}
json.dump(
    img_fold, open(HERE / "fold_split.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1
)
src = json.load(open(SPL / "wowwow_train46.json", encoding="utf-8"))
for f in (0, 1):
    R = [r for r in rows if img_fold[r["img"]] == f and not r["occ"]]
    use = {
        nm: (
            np.mean([r["du"] for r in R if r["part"] == nm]),
            np.mean([r["dv"] for r in R if r["part"] == nm]),
        )
        for nm in PART
    }
    print(
        f"fold{f}: 장 {sum(v == f for v in img_fold.values())} 로 계산",
        {k: (round(a, 3), round(b, 3)) for k, (a, b) in use.items()},
    )
    out = copy.deepcopy(src)
    for a in out["annotations"]:
        k = np.array(a["keypoints"], float).reshape(-1, 3)
        if k[[4, 9, 14, 18], 2].min() == 0 or k[[0, 1, 13], 2].min() == 0:
            continue
        sh, hp = (k[4, :2] + k[9, :2]) / 2, (k[14, :2] + k[18, :2]) / 2
        L = np.linalg.norm(sh - hp)
        if L < 1:
            continue
        u = (sh - hp) / L
        v = np.array([-u[1], u[0]])
        if v[1] < 0:
            v = -v
        left = (k[0, 0] + k[1, 0]) / 2 < k[13, 0]
        for nm, (du, dv) in use.items():
            i = PART[nm][0] if left else PART[nm][1]
            if k[i, 2] > 0:
                k[i, :2] += (du * u + dv * v) * L
        a["keypoints"] = [float(x) for x in k.reshape(-1)]
    json.dump(
        out,
        open(SPL / f"wowwow_train46_offset_fold{f}.json", "w", encoding="utf-8"),
        ensure_ascii=False,
    )
