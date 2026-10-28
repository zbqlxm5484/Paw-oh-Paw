"""260820 나란히 보기 (10-28): 왼쪽 = 오토라벨(fs-v4)만, 오른쪽 = 기업 정답만. 같은 사진, 같은 자르기.
기업이 고친 점(touched)은 양쪽 모두 노란 원과 이름으로 표시해서 어디가 바뀌었는지 바로 찾게 한다.
굵은 선 = 카메라 쪽 다리. 고친 점 많은 장부터 번호(make_overlays.py 와 같은 순서)."""

import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")

sys.stdout.reconfigure(encoding="utf-8")
R = Path(f"{_PJT}")
GT = R / "creamoff_data/dataset/keypoints_260820"
OUT = R / "gt_vs_auto/side_by_side"
OUT.mkdir(exist_ok=True)
g = json.load(open(GT / "annotations.json", encoding="utf-8"))
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
    for p in json.load(open(R / "creamoff_data/paw_eval/fs-v4.preds.json", encoding="utf-8"))[
        "predictions"
    ]
}
ims = {i["id"]: i for i in g["images"]}


def panel(im, K, vis, T, cam, color, title, box):
    x0, y0, x1, y1 = box
    s = 900 / (x1 - x0)
    c = cv2.resize(im[y0:y1, x0:x1], (900, int((y1 - y0) * s)))
    P = lambda p: (int((p[0] - x0) * s), int((p[1] - y0) * s))
    for i, j in SK:
        if vis[i] and vis[j]:
            cv2.line(c, P(K[i]), P(K[j]), color, 3 if i in cam else 1)
    for i in range(22):
        if not vis[i]:
            continue
        big = i in cam or i in (0, 1, 2, 13)
        cv2.circle(c, P(K[i]), 6 if big else 3, color, -1)
        if T[i]:
            cv2.circle(c, P(K[i]), 14, (0, 255, 255), 2)
            cv2.putText(
                c,
                EN[i],
                (P(K[i])[0] + 12, P(K[i])[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
            )
    bar = np.zeros((44, 900, 3), np.uint8)
    cv2.putText(bar, title, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    return np.vstack([bar, c])


anns = sorted(g["annotations"], key=lambda a: -a["attributes"]["n_touched"])
for no, a in enumerate(anns, 1):
    if a["id"] not in fp:
        continue
    im = cv2.imdecode(
        np.fromfile(str(GT / ims[a["image_id"]]["file_name"]), np.uint8), cv2.IMREAD_COLOR
    )
    G = np.array(a["keypoints"], float).reshape(-1, 3)
    A = fp[a["id"]]
    T = a["attributes"]["touched"]
    left = (G[0, 0] + G[1, 0]) / 2 < G[13, 0]
    cam = set(range(3, 8)) | {14, 15, 16, 17} if left else set(range(8, 13)) | {18, 19, 20, 21}
    x, y, w, h = a["bbox"]
    m = 0.12 * max(w, h)
    box = (
        int(max(0, x - m)),
        int(max(0, y - m)),
        int(min(im.shape[1], x + w + m)),
        int(min(im.shape[0], y + h + m)),
    )
    name = Path(ims[a["image_id"]]["file_name"]).name
    lp = panel(im, A, [1] * 22, T, cam, (0, 0, 255), f"#{no} AUTO (fs-v4)", box)
    rp = panel(
        im,
        G[:, :2],
        G[:, 2] > 0,
        T,
        cam,
        (0, 220, 0),
        f"COMPANY 260820   touched {a['attributes']['n_touched']}",
        box,
    )
    img = np.hstack([lp, np.full((lp.shape[0], 12, 3), 255, np.uint8), rp])
    cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tofile(
        str(OUT / f"{no:03d}_{name}")
    )
print(len(list(OUT.glob("*.jpg"))))
