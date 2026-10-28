"""기업 정답(260820)에서 관절별 오차(몸 길이 단위, 카메라 쪽만) — 보정 학습이 왜 나빠졌는지 (10-26)."""

import json
import os
import sys

import numpy as np

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")

sys.stdout.reconfigure(encoding="utf-8")
R = rf"{_PJT}/creamoff_data/paw_eval/results/"
gt = json.load(
    open(rf"{_PJT}/creamoff_data/dataset/keypoints_260820/annotations.json", encoding="utf-8")
)
G = {a["id"]: np.array(a["keypoints"], float).reshape(-1, 3) for a in gt["annotations"]}
PART = [
    ("어깨뼈위끝", 3, 8),
    ("어깨", 4, 9),
    ("팔꿈치", 5, 10),
    ("앞발목", 6, 11),
    ("앞발끝", 7, 12),
    ("고관절", 14, 18),
    ("무릎", 15, 19),
    ("뒷발목", 16, 20),
    ("뒷발끝", 17, 21),
    ("T13", 2, 2),
    ("장골능", 13, 13),
]


def load(n):
    return {
        p["ann_id"]: np.array(p["keypoints"], float).reshape(-1, 3)
        for p in json.load(open(R + n, encoding="utf-8"))["predictions"]
    }


models = {
    a: load(b)
    for a, b in [
        ("fs-v4-flip", sys.argv[1]),
        ("원래 학습", "curve/c_n1144_s0.gt.preds.json"),
        ("보정 학습", "curve/c_offset_s0.gt.preds.json"),
    ]
}
print(f"{'':<12}" + "".join(f"{p[0]:>8}" for p in PART))
for name, P in models.items():
    row = []
    for nm, li, ri in PART:
        e = []
        for aid, g in G.items():
            if aid not in P:
                continue
            L = np.linalg.norm((g[4, :2] + g[9, :2]) / 2 - (g[14, :2] + g[18, :2]) / 2)
            left = (g[0, 0] + g[1, 0]) / 2 < g[13, 0]
            i = li if left else ri
            if g[i, 2] > 0 and L > 1:
                e.append(np.linalg.norm(P[aid][i, :2] - g[i, :2]) / L)
        row.append(np.mean(e))
    print(f"{name:<12}" + "".join(f"{v:>8.3f}" for v in row))
