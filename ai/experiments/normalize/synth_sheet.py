"""synth_camera.py 샘플 확인: 원본 + 종류별 합성 영상의 같은 프레임에 변환한 관절점을 그린다 (10-26)."""

import glob
import json
import os

import cv2
import numpy as np

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")

D = rf"{_PJT}/normalize_experiments/synth_sample"
SRC = glob.glob(
    rf"{_PJT}/creamoff_data/dataset/videos/**/260820-144421-*-sub3.mp4", recursive=True
)[0]
TR = json.load(
    open(
        rf"{_PJT}/creamoff_data/paw_eval/results/gt_videos.fs-v4-flip.track.json", encoding="utf-8"
    )
)
v0 = next(
    v for v in TR["videos"] if v["video"].startswith("260820-144421") and "sub3" in v["video"]
)
FR = 110


def tile(path, frames, label):
    cap = cv2.VideoCapture(path)
    cap.set(1, FR)
    ok, im = cap.read()
    f = frames[FR]
    for x, y, c in f["kp"]:
        if c > 0.3:
            cv2.circle(im, (int(x), int(y)), 9, (0, 255, 255), -1)
    x0, y0, x1, y1 = map(int, f["box"])
    cv2.rectangle(im, (x0, y0), (x1, y1), (255, 0, 255), 3)
    cv2.putText(im, label, (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 2.2, (0, 255, 0), 5)
    return cv2.resize(im, (640, 360))


tiles = [tile(SRC, v0["frames"], "original")]
for t in sorted(glob.glob(D + "/*.track.json")):
    v = json.load(open(t, encoding="utf-8"))["videos"][0]
    tiles.append(
        tile(t.replace(".track.json", ".mp4"), v["frames"], v["video"].split(".", 1)[1][:-4])
    )
tiles += [np.zeros_like(tiles[0])] * (-len(tiles) % 3)
rows = [np.hstack(tiles[i : i + 3]) for i in range(0, len(tiles), 3)]
cv2.imwrite(D + "/check.jpg", np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])
print("ok")
