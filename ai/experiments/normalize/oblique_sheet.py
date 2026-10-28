"""oblique.py 결과 확인용: 통과마다 처음·가운데·끝 프레임에 몸통 축을 그려 한 줄로 붙인다 (10-26)."""

import glob
import json
import os
import sys

import cv2
import numpy as np

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")

sys.stdout.reconfigure(encoding="utf-8")
TRACK = rf"{_PJT}/creamoff_data/paw_eval/results/gt_videos.fs-v4-flip.track.json"
RES = rf"{_PJT}/normalize_experiments/oblique_gt72.json"
VID = rf"{_PJT}/creamoff_data/dataset/videos"
tr = {v["video"]: v for v in json.load(open(TRACK, encoding="utf-8"))["videos"]}
res = sorted(json.load(open(RES, encoding="utf-8"))["passes"], key=lambda r: -r["yaw_change"])
pick = res[:5] + res[-3:]
rows = []
for r in pick:
    v = tr[r["video"]]
    path = glob.glob(f"{VID}/**/{r['video']}", recursive=True)[0]
    cap = cv2.VideoCapture(path)
    W = v["width"]
    idx = [
        i
        for i in range(r["start"], r["end"] + 1)
        if v["frames"][i]
        and 0.01 * W < v["frames"][i]["box"][0]
        and v["frames"][i]["box"][2] < 0.99 * W
    ]
    tiles = []
    for i in (idx[0], idx[len(idx) // 2], idx[-1]):
        cap.set(1, i)
        ok, im = cap.read()
        kp = v["frames"][i]["kp"]
        for a, b, c in ((4, 14, (0, 255, 0)), (9, 18, (0, 0, 255))):
            if kp[a][2] > 0.3 and kp[b][2] > 0.3:
                cv2.line(im, tuple(map(int, kp[a][:2])), tuple(map(int, kp[b][:2])), c, 4)
        x0, y0, x1, y1 = map(int, v["frames"][i]["box"])
        cv2.rectangle(im, (x0, y0), (x1, y1), (255, 255, 0), 2)
        tiles.append(cv2.resize(im, (480, 270)))
    row = np.hstack(tiles)
    cv2.putText(
        row,
        f"{r['video'][7:20]} {r['video'].rsplit('-',1)[1][:-4]} yaw {r['yaw_change']:.2f} len {r['len_change']:.2f} h {r['height_change']:.2f}",
        (8, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 255),
        2,
    )
    rows.append(row)
cv2.imwrite(
    rf"{_PJT}/normalize_experiments/oblique_check/top_bottom.jpg",
    np.vstack(rows),
    [cv2.IMWRITE_JPEG_QUALITY, 80],
)
print("ok")
