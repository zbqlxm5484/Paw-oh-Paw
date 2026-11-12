"""기업 정답(260820) vs 오토라벨(fs-v4) 겹쳐 보기 — 수요일 눈 확인용 (10-26).
빨강 = fs-v4 예측(정답 상자, flip 없음 — 사전라벨 근사), 초록 = 기업 정답. 기업이 고친 점(touched)은 빨강→초록 화살표와 이름.
카메라 쪽 다리는 굵게, 반대쪽은 작게. 고친 점이 많은 장부터 번호."""

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
OUT = R / "gt_vs_auto"
g = json.load(open(GT / "annotations.json", encoding="utf-8"))
NAMES = g["categories"][0]["keypoints"]
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
    for p in json.load(open(R / "creamoff_data/paw_eval/fs-v4.preds.json", encoding="utf-8"))[
        "predictions"
    ]
}
ims = {i["id"]: i for i in g["images"]}
rows = []
anns = sorted(g["annotations"], key=lambda a: -a["attributes"]["n_touched"])
for no, a in enumerate(anns, 1):
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
        if T[i]:
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
    moved = [f"{SHORT[i]} {np.linalg.norm(G[i,:2]-A[i])/L:.2f}" for i in range(22) if T[i]]
    rows.append(
        f"| {no} | `{out}` | {'왼' if left else '오른'} | {a['attributes']['n_touched']} | {', '.join(moved) or '-'} |"
    )
md = [
    "# 기업 정답 vs 오토라벨 (260820, 205장 + 같은 사진 다른 annotation 포함 221개)",
    "",
    "- 사진: `images/`. **빨강 점 = 오토라벨(fs-v4)**, **초록 원 = 기업 정답**, **노란 화살표 = 기업 라벨러가 고친 점**(정답 파일의 touched 표시)과 영어 약어",
    "- 굵은 선·큰 점 = 카메라 쪽 다리. 고친 점이 많은 장부터 번호",
    "- 오토라벨은 지금 fs-v4 를 정답 상자로 다시 돌린 값이라 기업이 실제로 받은 사전라벨과 1~2% 다를 수 있음(안 고친 점이 빨강·초록 거의 겹치면 정상)",
    "- 거리 = 몸 길이(어깨 가운데↔고관절 가운데) 대비",
    "",
    "약어: scap 어깨뼈 위끝, sho 어깨, elb 팔꿈치, wri 앞발목, ftoe 앞발끝, hip 고관절, knee 무릎, ank 뒷발목, htoe 뒷발끝 (L/R = 개 기준 왼/오른)",
    "",
    "## 볼 것",
    "",
    "1. 어깨뼈 위끝·어깨·T13·장골능은 기업이 거의 안 고쳤다(0~5%). 오토라벨 자리가 해부학적으로 어디인지",
    "2. 발끝을 고친 장(36~38%)에서 어디로 옮겼는지 — 바닥 쪽인지, 발가락 끝인지",
    "3. 고친 거리가 작다(중앙 0.03~0.05). 어떤 경우에만 고쳤는지 — 크게 틀린 점만인지",
    "",
    "## 장별 목록",
    "",
    "| 번호 | 파일 | 카메라 쪽 | 고친 점 수 | 고친 점 (거리) |",
    "|---:|---|---|---:|---|",
] + rows
(OUT / "README.md").write_text("\n".join(md), encoding="utf-8")
print(len(rows))
