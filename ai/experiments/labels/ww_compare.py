"""관절별 나란히 보기 (10-28): 왼쪽 = 기업 260820, 오른쪽 = 와우와우. 같은 관절을 고친 장을 짝지어 한 장으로.
각 데이터에서 그 관절을 평균 이동 방향 쪽으로 고친 장 중, 이동 거리가 중앙값에 가까운 장(=전형적인 고침)부터 6쌍.
빨강 = 오토라벨(fs-v4), 초록 = 사람 라벨, 노란 굵은 화살표 = 보는 관절, 얇은 회색 화살표 = 나머지 고친 점."""

import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")

sys.stdout.reconfigure(encoding="utf-8")
R = Path(f"{_PJT}")
OUT = R / "ww_vs_auto/compare"
OUT.mkdir(exist_ok=True)
SK = [
    (3, 4),
    (4, 5),
    (5, 6),
    (6, 7),
    (8, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (14, 15),
    (15, 16),
    (16, 17),
    (18, 19),
    (19, 20),
    (20, 21),
    (2, 13),
]
JOINTS = [
    ("knee", 15, 19),
    ("hind_ankle", 16, 20),
    ("hind_toe", 17, 21),
    ("hip", 14, 18),
    ("elbow", 5, 10),
    ("front_toe", 7, 12),
]
N = 6
SETS = {
    "COMPANY 260820": (
        R / "creamoff_data/dataset/keypoints_260820",
        R / "creamoff_data/paw_eval/fs-v4.preds.json",
        False,
    ),
    "WOWWOW": (
        R / "creamoff_data/dataset_1021/keypoints_wowwow",
        R / "creamoff_data/paw_eval/results/ww_hf.fs-v4.preds.json",
        True,
    ),
}


def load(gt_dir, pred, only_good):
    g = json.load(open(gt_dir / "annotations.json", encoding="utf-8"))
    fp = {
        p["ann_id"]: np.array(p["keypoints"], float).reshape(-1, 3)[:, :2]
        for p in json.load(open(pred, encoding="utf-8"))["predictions"]
    }
    ims = {i["id"]: i for i in g["images"]}
    rows = []
    for a in g["annotations"]:
        at = a["attributes"]
        if a["id"] not in fp or (only_good and (not at["human_fixed"] or at["grade"] != "good")):
            continue
        A = fp[a["id"]]
        sh, hp = (A[4] + A[9]) / 2, (A[14] + A[18]) / 2
        L = np.linalg.norm(sh - hp)
        if L < 1:
            continue
        u = (sh - hp) / L
        v = np.array([-u[1], u[0]])
        v = -v if v[1] < 0 else v
        left = (A[0, 0] + A[1, 0]) / 2 < A[13, 0]
        rows.append(
            dict(
                a=a,
                A=A,
                G=np.array(a["keypoints"], float).reshape(-1, 3),
                L=L,
                u=u,
                v=v,
                left=left,
                path=gt_dir / ims[a["image_id"]]["file_name"],
            )
        )
    return rows


def pick(rows, li, ri):
    c = []
    for r in rows:
        i = li if r["left"] else ri
        if not r["a"]["attributes"]["touched"][i] or r["G"][i, 2] == 0:
            continue
        d = (r["G"][i, :2] - r["A"][i]) / r["L"]
        if np.linalg.norm(d) > 0.5:
            continue
        c.append((r, i, np.array([d @ r["u"], d @ r["v"]])))
    if not c:
        return []
    mean = np.mean([x[2] for x in c], 0)
    md = mean / (np.linalg.norm(mean) + 1e-9)
    c = [x for x in c if x[2] @ md > 0]
    med = np.median([np.linalg.norm(x[2]) for x in c])
    c.sort(key=lambda x: abs(np.linalg.norm(x[2]) - med))
    seen, out = set(), []
    for x in c:  # 같은 촬영 중복 피하기
        k = x[0]["path"].name.split("_")[0]
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
        if len(out) == N:
            break
    return out


def draw(r, i, d, title):
    im = cv2.imdecode(np.fromfile(str(r["path"]), np.uint8), cv2.IMREAD_COLOR)
    G, A, T = r["G"], r["A"], r["a"]["attributes"]["touched"]
    x, y, w, h = r["a"]["bbox"]
    m = 0.12 * max(w, h)
    x0, y0, x1, y1 = (
        int(max(0, x - m)),
        int(max(0, y - m)),
        int(min(im.shape[1], x + w + m)),
        int(min(im.shape[0], y + h + m)),
    )
    s = 900 / (x1 - x0)
    c = cv2.resize(im[y0:y1, x0:x1], (900, int((y1 - y0) * s)))
    P = lambda p: (int((p[0] - x0) * s), int((p[1] - y0) * s))
    for a_, b_ in SK:
        if G[a_, 2] and G[b_, 2]:
            cv2.line(c, P(G[a_]), P(G[b_]), (0, 200, 0), 1)
    for k in range(22):
        if k == i:
            continue
        cv2.circle(c, P(A[k]), 4, (0, 0, 255), -1)
        if G[k, 2]:
            cv2.circle(c, P(G[k]), 4, (0, 220, 0), 1)
            if T[k]:
                cv2.arrowedLine(c, P(A[k]), P(G[k]), (170, 170, 170), 1, tipLength=0.3)
    cv2.circle(c, P(A[i]), 9, (0, 0, 255), -1)
    cv2.circle(c, P(G[i]), 11, (0, 255, 0), 3)
    cv2.arrowedLine(c, P(A[i]), P(G[i]), (0, 255, 255), 4, tipLength=0.3)
    head = "head" if d[0] > 0 else "tail"
    vert = "down" if d[1] > 0 else "up"
    bar = np.zeros((70, 900, 3), np.uint8)
    cv2.putText(bar, title, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(
        bar,
        f"{r['path'].name}   {head} {abs(d[0]):.3f} / {vert} {abs(d[1]):.3f}",
        (10, 58),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 255),
        1,
    )
    return np.vstack([bar, c])


data = {k: load(*v) for k, v in SETS.items()}
for order, (jn, li, ri) in enumerate(JOINTS, 1):
    picks = {k: pick(rows, li, ri) for k, rows in data.items()}
    for n in range(N):
        tiles = []
        for k in SETS:
            if n < len(picks[k]):
                r, i, d = picks[k][n]
                tiles.append(draw(r, i, d, f"{k}  [{jn}]"))
            else:
                tiles.append(np.zeros((400, 900, 3), np.uint8))
        hgt = max(t.shape[0] for t in tiles)
        tiles = [np.vstack([t, np.zeros((hgt - t.shape[0], 900, 3), np.uint8)]) for t in tiles]
        img = np.hstack([tiles[0], np.full((hgt, 12, 3), 255, np.uint8), tiles[1]])
        cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tofile(
            str(OUT / f"{order}_{jn}_{n+1}.jpg")
        )
    print(jn, {k: len(v) for k, v in picks.items()})
