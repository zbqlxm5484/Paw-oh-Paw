"""32 라벨 맞추기 20장 확정: 목록 CSV + CVAT 태스크용 프레임 폴더(라벨러 수만큼) + 확인 그림."""

import csv
import os
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")
_CVAT = os.environ.get("CVAT_LABELING_DIR", "C:/cvat-labeling")

sys.stdout.reconfigure(encoding="utf-8")
CAND = Path(rf"{_CVAT}\pilot\cand")
GT = Path(rf"{_PJT}\creamoff_data\dataset\keypoints_260820\images")
FRAMES = Path(rf"{_CVAT}\frames")
HERE = Path(__file__).parent
LABELERS = ["A", "B", "C"]

# (개, 체급, 장면, 원본) — 원본이 i0 으로 시작하면 기업 정답 사진
PICKS = [
    ("제니", "중형", "깨끗한 옆모습", "i003_main-260820-144421_f000142.jpg"),
    ("제니", "중형", "뒷다리 겹침", "i000_sub1-260820-144127_f000097.jpg"),
    ("제니", "중형", "보통", "i012_sub2-260820-150415_f000128.jpg"),
    ("제니", "중형", "뒷다리 겹침", "i010_sub3-260820-150154_f000125.jpg"),
    ("럭키", "대형", "깨끗한 옆모습", "261001-142529-럭키-29kg-main_f000222.jpg"),
    ("럭키", "대형", "뒷다리 겹침", "261001-142529-럭키-29kg-main_f000246.jpg"),
    ("럭키", "대형", "반대 방향·다리 교차", "261001-142529-럭키-29kg-sub1_f000246.jpg"),
    ("럭키", "대형", "반대 방향·꼬리 흐림", "261001-142529-럭키-29kg-sub1_f000222.jpg"),
    ("아미", "대형", "깨끗한 옆모습", "260827-150618-아미-29kg-main_f000228.jpg"),
    ("아미", "대형", "뒷다리 겹침·교차", "260827-150618-아미-29kg-sub1_f000198.jpg"),
    ("아미", "대형", "뒷다리 가까움", "260827-151312-아미-29kg-sub2_f000150.jpg"),
    ("아미", "대형", "몸 틀기·흐림", "260827-151312-아미-29kg-sub3_f000114.jpg"),
    ("건빵", "소형", "깨끗한 옆모습(사무실)", "260916-143224-건빵-3.9kg-main_f000228.jpg"),
    ("건빵", "소형", "뒷다리 겹침", "260828-114223-건빵-3.9kg-main_f000210.jpg"),
    ("건빵", "소형", "사람 다리 뒤", "260828-114223-건빵-3.9kg-main_f000282.jpg"),
    ("건빵", "소형", "화면 끝 걸림", "260828-114223-건빵-3.9kg-main_f000024.jpg"),
    ("오이", "소형", "깨끗한 옆모습", "260930-154254-오이-2.1kg-main_f000264.jpg"),
    ("오이", "소형", "뒷다리 겹침", "260930-153238-오이-2.1kg-main_f000390.jpg"),
    ("오이", "소형", "뒷다리 겹침", "260930-153238-오이-2.1kg-main_f000462.jpg"),
    ("오이", "소형", "긴 털·앞다리", "260930-154254-오이-2.1kg-main_f000204.jpg"),
]


def source(src):
    if src.startswith("i0"):
        cam, stamp, f = (
            src[5:].removesuffix(".jpg").split("-", 1)[0],
            src[10:23],
            src.rsplit("_f", 1)[1][:-4],
        )
        return GT / src, f"{stamp}-제니-{cam}_f{f}.jpg"
    return CAND / src.rsplit("_f", 1)[0] / src, src


rows, tiles = [], []
for no, (dog, cls, tag, src) in enumerate(PICKS, 1):
    path, name = source(src)
    name = f"p{no:02d}_{name}"  # 순서를 고정하려고 번호를 앞에 붙인다
    rows.append(
        dict(
            no=no,
            file=name,
            dog=dog,
            size_class=cls,
            scene=tag,
            has_company_gt=int(src.startswith("i0")),
            source=src,
        )
    )
    for lab in LABELERS:
        d = FRAMES / f"pilot20-{lab}"
        d.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, d / name)
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), 1)
    t = cv2.resize(img, (384, 216))
    cv2.putText(t, f"{no} {tag}", (6, 26), 0, 0.7, (0, 255, 255), 2)
    tiles.append(t)
with open(HERE / "pilot20.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
cv2.imwrite(sys.argv[1], np.vstack([np.hstack(tiles[i : i + 4]) for i in range(0, 20, 4)]))
print(len(rows), "장 →", ", ".join(f"pilot20-{l}" for l in LABELERS))
