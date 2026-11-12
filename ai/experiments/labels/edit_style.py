"""기업 라벨러 vs 팀 라벨러: 관절별로 오토라벨(fs-v4)을 얼마나 자주·얼마나 멀리·어느 방향으로 옮겼나 (10-26).
기업: 260820 정답의 touched 표시 + fs-v4 예측(정답 상자). 팀: 시험 라벨 96장 vs 오토라벨 덤프. 카메라 쪽만, 몸 길이 단위."""

import json
import os
import sys

import numpy as np

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")
_CVAT = os.environ.get("CVAT_LABELING_DIR", "C:/cvat-labeling")

sys.stdout.reconfigure(encoding="utf-8")
R = f"{_PJT}/"
PART = [
    ("어깨뼈위끝", 3, 8),
    ("어깨", 4, 9),
    ("팔꿈치", 5, 10),
    ("앞발목", 6, 11),
    ("앞발끝", 7, 12),
    ("T13", 2, 2),
    ("장골능", 13, 13),
    ("고관절", 14, 18),
    ("무릎", 15, 19),
    ("뒷발목", 16, 20),
    ("뒷발끝", 17, 21),
]


def axes(A):
    sh, hp = (A[4] + A[9]) / 2, (A[14] + A[18]) / 2
    L = np.linalg.norm(sh - hp)
    u = (sh - hp) / L
    v = np.array([-u[1], u[0]])
    v = -v if v[1] < 0 else v
    return L, u, v, (A[0, 0] + A[1, 0]) / 2 < A[13, 0]


def collect(pairs):  # (사람 점 22x3, 오토 22x2, touched 22 or None)
    out = {p[0]: [] for p in PART}
    for H, A, T in pairs:
        L, u, v, left = axes(A)
        for nm, li, ri in PART:
            i = li if left else ri
            if H[i, 2] == 0:
                continue
            d = H[i, :2] - A[i]
            m = np.linalg.norm(d) / L
            touched = T[i] if T is not None else m > 0.01
            out[nm].append((touched, m, d @ u / L, d @ v / L))
    return out


g = json.load(open(R + "creamoff_data/dataset/keypoints_260820/annotations.json", encoding="utf-8"))
fp = {
    p["ann_id"]: np.array(p["keypoints"], float).reshape(-1, 3)[:, :2]
    for p in json.load(open(R + "creamoff_data/paw_eval/fs-v4.preds.json", encoding="utf-8"))[
        "predictions"
    ]
}
comp = collect(
    [
        (np.array(a["keypoints"], float).reshape(-1, 3), fp[a["id"]], a["attributes"]["touched"])
        for a in g["annotations"]
        if a["id"] in fp
    ]
)
p = json.load(open(R + "splits/pilot100/all.json", encoding="utf-8"))
nm_ = {i["id"]: i["file_name"].split("/")[1] for i in p["images"]}
auto = {}
for l in open(rf"{_CVAT}\dump\kp_dump.jsonl", encoding="utf-8"):
    j = json.loads(l)
    if j["frame_name"] in nm_.values() and j.get("keypoints"):
        auto[j["frame_name"]] = np.array(j["keypoints"], float)[:22, :2]
team = collect(
    [
        (np.array(a["keypoints"], float).reshape(-1, 3), auto[nm_[a["image_id"]]], None)
        for a in p["annotations"]
        if not a["attributes"]["points_only"]
    ]
)
print(
    f"{'':<8}{'기업 고친 비율':>10}{'고친 거리 중앙':>12}{'방향(머리+,아래+)':>18}  |{'팀 고친 비율':>10}{'고친 거리 중앙':>12}{'방향':>16}"
)
for nm, *_ in PART:
    row = ""
    for D in (comp, team):
        X = np.array(D[nm])
        t = X[:, 0] > 0
        Y = X[t]
        row += f"{t.mean()*100:>9.0f}%{np.median(Y[:,1]) if len(Y) else 0:>12.3f}   {Y[:,2].mean() if len(Y) else 0:+.3f},{Y[:,3].mean() if len(Y) else 0:+.3f}    |"
    print(f"{nm:<8}{row}")
