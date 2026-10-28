"""와우와우 사람 교정 라벨 vs 오토라벨(fs-v4) 겹쳐 보기 — 수요일 눈 확인용 (10-28). gt_vs_auto/make_overlays.py 와 같은 그림.
빨강 = fs-v4 예측(정답 상자 +15%, flip 없음), 초록 = 와우와우 라벨. 와우와우가 고친 점(touched)은 빨강→초록 화살표와 이름.
human_fixed 1,556장 중 grade good(710장)만, 촬영(stamp)마다 가운데 프레임 1장씩, 최대 60장.
와우와우는 거의 모든 점에 touched 가 있어 "고친 점 많은 순"은 몸 트는 이상한 장면만 뽑힌다."""

import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")

sys.stdout.reconfigure(encoding="utf-8")
R = Path(f"{_PJT}")
GT = R / "creamoff_data/dataset_1021/keypoints_wowwow"
OUT = R / "ww_vs_auto"
(OUT / "images").mkdir(exist_ok=True)
g = json.load(open(GT / "annotations.json", encoding="utf-8"))
SHORT = [
    "L귀",
    "R귀",
    "T13",
    "L어깨뼈위끝",
    "L어깨",
    "L팔꿈치",
    "L앞발목",
    "L앞발끝",
    "R어깨뼈위끝",
    "R어깨",
    "R팔꿈치",
    "R앞발목",
    "R앞발끝",
    "장골능",
    "L고관절",
    "L무릎",
    "L뒷발목",
    "L뒷발끝",
    "R고관절",
    "R무릎",
    "R뒷발목",
    "R뒷발끝",
]
EN = [
    "Lear",
    "Rear",
    "T13",
    "Lscap",
    "Lsho",
    "Lelb",
    "Lwri",
    "Lftoe",
    "Rscap",
    "Rsho",
    "Relb",
    "Rwri",
    "Rftoe",
    "iliac",
    "Lhip",
    "Lknee",
    "Lank",
    "Lhtoe",
    "Rhip",
    "Rknee",
    "Rank",
    "Rhtoe",
]
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
fp = {
    p["ann_id"]: np.array(p["keypoints"], float).reshape(-1, 3)[:, :2]
    for p in json.load(
        open(R / "creamoff_data/paw_eval/results/ww_hf.fs-v4.preds.json", encoding="utf-8")
    )["predictions"]
}
ims = {i["id"]: i for i in g["images"]}
best = {}
for a in g["annotations"]:
    if (
        not a["attributes"]["human_fixed"]
        or a["attributes"]["grade"] != "good"
        or a["id"] not in fp
    ):
        continue
    stamp = Path(ims[a["image_id"]]["file_name"]).name.split("_")[0].split("-", 1)[1]
    best.setdefault(stamp, []).append(a)
best = {k: sorted(v, key=lambda a: a["image_id"])[len(v) // 2] for k, v in best.items()}
anns = [best[k] for k in sorted(best)][:60]
rows = []
for no, a in enumerate(anns, 1):
    im = cv2.imdecode(
        np.fromfile(str(GT / ims[a["image_id"]]["file_name"]), np.uint8), cv2.IMREAD_COLOR
    )
    G = np.array(a["keypoints"], float).reshape(-1, 3)
    A = fp[a["id"]]
    T = a["attributes"]["touched"]
    left = (A[0, 0] + A[1, 0]) / 2 < A[13, 0]
    cam = set(range(3, 8)) | {14, 15, 16, 17} if left else set(range(8, 13)) | {18, 19, 20, 21}
    x, y, w, h = a["bbox"]
    m = 0.12 * max(w, h)
    x0, y0, x1, y1 = (
        int(max(0, x - m)),
        int(max(0, y - m)),
        int(min(im.shape[1], x + w + m)),
        int(min(im.shape[0], y + h + m)),
    )
    s = 1400 / (x1 - x0)
    c = cv2.resize(im[y0:y1, x0:x1], (1400, int((y1 - y0) * s)))
    P = lambda p: (int((p[0] - x0) * s), int((p[1] - y0) * s))
    for i, j in SK:
        if G[i, 2] and G[j, 2]:
            cv2.line(c, P(G[i]), P(G[j]), (0, 200, 0), 3 if i in cam else 1)
    for i in range(22):
        big = i in cam or i in (0, 1, 2, 13)
        cv2.circle(c, P(A[i]), 7 if big else 4, (0, 0, 255), -1)
        if G[i, 2]:
            cv2.circle(c, P(G[i]), 7 if big else 4, (0, 220, 0), 2)
        if T[i] and G[i, 2]:
            cv2.arrowedLine(c, P(A[i]), P(G[i]), (0, 255, 255), 3, tipLength=0.25)
            cv2.putText(
                c,
                EN[i],
                (P(G[i])[0] + 8, P(G[i])[1] - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 255),
                2,
            )
    name = Path(ims[a["image_id"]]["file_name"]).name
    cv2.putText(
        c,
        f"#{no} {name}  touched {a['attributes']['n_touched']}  cam={'L' if left else 'R'}",
        (12, 36),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        3,
    )
    out = f"{no:03d}_{name}"
    cv2.imencode(".jpg", c, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tofile(str(OUT / "images" / out))
    L = np.linalg.norm((A[4] + A[9]) / 2 - (A[14] + A[18]) / 2)
    moved = [
        f"{SHORT[i]} {np.linalg.norm(G[i,:2]-A[i])/L:.2f}" for i in range(22) if T[i] and G[i, 2]
    ]
    rows.append(
        f"| {no} | `{out}` | {'왼' if left else '오른'} | {a['attributes']['n_touched']} | {', '.join(moved) or '-'} |"
    )
(OUT / "rows.md").write_text("\n".join(rows), encoding="utf-8")
print(len(best), len(rows))
