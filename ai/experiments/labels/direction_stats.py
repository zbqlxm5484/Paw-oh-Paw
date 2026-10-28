"""260820(기업) vs 와우와우: 오토라벨(fs-v4, 정답 상자 +15%, flip 없음)에서 사람이 관절을 어느 방향으로 옮겼나 (10-28).
카메라 쪽 다리만. 거리·방향은 몸 길이(어깨 가운데↔고관절 가운데) 단위.
앞 = 머리 쪽(+), 아래 = 몸통에 수직, 화면 아래쪽(+). 일관성 = |평균 벡터| / 평균 |벡터| (1 이면 전부 같은 방향, 0 이면 제각각)."""

import json
import os
import sys

import numpy as np

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")

sys.stdout.reconfigure(encoding="utf-8")
R = f"{_PJT}/creamoff_data/"
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
]
MID = [("귀L", 0), ("귀R", 1), ("T13", 2), ("장골능", 13)]


def axes(A):
    sh, hp = (A[4] + A[9]) / 2, (A[14] + A[18]) / 2
    L = np.linalg.norm(sh - hp)
    u = (sh - hp) / L
    v = np.array([-u[1], u[0]])
    v = -v if v[1] < 0 else v
    return L, u, v, (A[0, 0] + A[1, 0]) / 2 < A[13, 0]


def collect(gt_path, pred_path, only_fixed):
    g = json.load(open(gt_path, encoding="utf-8"))
    fp = {
        p["ann_id"]: np.array(p["keypoints"], float).reshape(-1, 3)[:, :2]
        for p in json.load(open(pred_path, encoding="utf-8"))["predictions"]
    }
    out = {nm: [] for nm, *_ in PART + [(m, 0, 0) for m, _ in MID]}
    n = 0
    for a in g["annotations"]:
        at = a["attributes"]
        if a["id"] not in fp or (only_fixed and not at["human_fixed"]):
            continue
        H = np.array(a["keypoints"], float).reshape(-1, 3)
        A = fp[a["id"]]
        T = at["touched"]
        L, u, v, left = axes(A)
        if L < 1:
            continue
        n += 1
        idx = [(nm, li if left else ri) for nm, li, ri in PART] + MID
        for nm, i in idx:
            if H[i, 2] == 0:
                continue
            d = H[i, :2] - A[i]
            dist = np.linalg.norm(d) / L
            if (
                dist > 0.5
            ):  # 오토라벨이 아예 실패한 점(와우와우 1번 장 같은 것)은 방향 통계에서 뺀다
                continue
            out[nm].append((T[i], dist, d @ u / L, d @ v / L))
    return n, out


def table(D):
    rows = []
    for nm in D:
        X = np.array(D[nm])
        if not len(X):
            continue
        t = X[:, 0] > 0
        Y = X[t]
        if len(Y) < 3:
            rows.append((nm, t.mean(), len(Y), np.nan, np.nan, np.nan, np.nan, np.nan))
            continue
        mv = Y[:, 2:4].mean(0)
        rows.append(
            (
                nm,
                t.mean(),
                len(Y),
                np.median(Y[:, 1]),
                mv[0],
                mv[1],
                np.linalg.norm(mv) / Y[:, 1].mean(),
                (Y[:, 3] > 0).mean(),
            )
        )
    return rows


def arrow(f, dn):
    if np.isnan(f):
        return "-"
    s = []
    if abs(dn) >= 0.01:
        s.append(f"아래 {dn:+.3f}" if dn > 0 else f"위 {dn:+.3f}")
    if abs(f) >= 0.01:
        s.append(f"머리쪽 {f:+.3f}" if f > 0 else f"꼬리쪽 {f:+.3f}")
    return ", ".join(s) or "거의 0"


sets = [
    (
        "260820 기업 정답",
        R + "dataset/keypoints_260820/annotations.json",
        R + "paw_eval/fs-v4.preds.json",
        False,
    ),
    (
        "와우와우 (human_fixed 만)",
        R + "dataset_1021/keypoints_wowwow/annotations.json",
        R + "paw_eval/results/ww_hf.fs-v4.preds.json",
        True,
    ),
]
res = {}
for name, gp, pp, only in sets:
    n, D = collect(gp, pp, only)
    res[name] = (n, table(D))
    print(f"\n## {name} ({n}장)\n")
    print("| 관절 | 고친 비율 | 고친 수 | 거리 중앙 | 평균 이동 | 일관성 | 아래로 옮긴 비율 |")
    print("|---|---:|---:|---:|---|---:|---:|")
    for nm, r, k, md, f, dn, c, down in res[name][1]:
        print(
            f"| {nm} | {r*100:.0f}% | {k} | {md:.3f} | {arrow(f, dn)} | {c:.2f} | {down*100:.0f}% |"
            if k >= 3
            else f"| {nm} | {r*100:.0f}% | {k} | - | - | - | - |"
        )
