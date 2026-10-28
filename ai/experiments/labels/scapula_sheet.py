"""어깨뼈 위끝(dorsal scapular spine) 위치 비교 그림: 기업 정답 2장 + 시험 라벨 4장(오토라벨 빨강 → 라벨러 초록), 멘토링 질문용 (10-26)."""

import json
import os
import sys

import cv2
import numpy as np

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")
_CVAT = os.environ.get("CVAT_LABELING_DIR", "C:/cvat-labeling")

sys.stdout.reconfigure(encoding="utf-8")
GT = rf"{_PJT}/creamoff_data/dataset/keypoints_260820/"
P = rf"{_PJT}/splits/pilot100/"
g = json.load(open(GT + "annotations.json", encoding="utf-8"))
p = json.load(open(P + "all.json", encoding="utf-8"))
auto = {}
for l in open(rf"{_CVAT}/dump/kp_dump.jsonl", encoding="utf-8"):
    j = json.loads(l)
    if j.get("keypoints"):
        auto[j["frame_name"]] = np.array(j["keypoints"], float)[:22, :2]


def crop(im, k, lab):
    xs, ys = k[:, 0], k[:, 1]
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    m = 0.15 * max(x1 - x0, y1 - y0)
    x0, y0, x1, y1 = (
        int(max(0, x0 - m)),
        int(max(0, y0 - m)),
        int(min(im.shape[1], x1 + m)),
        int(min(im.shape[0], y1 + m)),
    )
    t = cv2.resize(im[y0:y1, x0:x1], (520, int(520 * (y1 - y0) / (x1 - x0))))
    t = cv2.copyMakeBorder(t, 0, max(0, 400 - t.shape[0]), 0, 0, cv2.BORDER_CONSTANT)[:400]
    cv2.putText(t, lab, (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    return t, (x0, y0, 520 / (x1 - x0))


def dot(t, tf, pt, c):
    x0, y0, s = tf
    cv2.circle(t, (int((pt[0] - x0) * s), int((pt[1] - y0) * s)), 9, c, -1)


tiles = []
ims = {i["id"]: i for i in g["images"]}
for a in g["annotations"][:3]:
    k = np.array(a["keypoints"], float).reshape(-1, 3)[:, :2]
    im = cv2.imdecode(np.fromfile(GT + ims[a["image_id"]]["file_name"], np.uint8), cv2.IMREAD_COLOR)
    left = (k[0, 0] + k[1, 0]) / 2 < k[13, 0]
    t, tf = crop(im, k, "company GT (green)")
    dot(t, tf, k[3 if left else 8], (0, 255, 0))
    dot(t, tf, k[4 if left else 9], (255, 0, 255))
    tiles.append(t)
pim = {i["id"]: i for i in p["images"]}
picked = 0
for a in p["annotations"]:
    n = pim[a["image_id"]]["file_name"].split("/")[1]
    k = np.array(a["keypoints"], float).reshape(-1, 3)
    A = auto[n]
    left = (A[0, 0] + A[1, 0]) / 2 < A[13, 0]
    i = 3 if left else 8
    L = np.linalg.norm((A[4] + A[9]) / 2 - (A[14] + A[18]) / 2)
    if k[i, 2] == 0 or np.linalg.norm(k[i, :2] - A[i]) / L < 0.1:
        continue
    im = cv2.imdecode(np.fromfile(P + pim[a["image_id"]]["file_name"], np.uint8), cv2.IMREAD_COLOR)
    t, tf = crop(im, A, f"{a['attributes']['task']}: auto red -> label green")
    dot(t, tf, A[i], (0, 0, 255))
    dot(t, tf, k[i, :2], (0, 255, 0))
    dot(t, tf, A[4 if left else 9], (255, 0, 255))
    tiles.append(t)
    picked += 1
    if picked == 3:
        break
cv2.imwrite(
    rf"{_PJT}/wowwow_offset50/scapula_compare.jpg",
    np.vstack([np.hstack(tiles[:3]), np.hstack(tiles[3:6])]),
)
print("ok")
