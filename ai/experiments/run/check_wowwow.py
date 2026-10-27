import json
import os
import random

import cv2
import numpy as np

ROOT = "/work/ssafy/dataset/keypoints_wowwow"
VID = "/work/ssafy/dataset/videos/wowwow-forest"
d = json.load(open(f"{ROOT}/annotations.json", encoding="utf-8"))
ims = {i["id"]: i for i in d["images"]}

random.seed(7)
bad = 0
sample = random.sample(d["images"], 8)
for im in sample:
    stamp = im["session"]
    date = stamp.split("-")[0]
    path = f"{VID}/{date}/{stamp}/{stamp}-{im['camera']}.mp4"
    if not os.path.exists(path):
        print("영상 없음", path)
        bad += 1
        continue
    cap = cv2.VideoCapture(path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, im["frame_idx"])
    ok, fr = cap.read()
    img = cv2.imread(f"{ROOT}/{im['file_name']}")
    if not ok or img is None or fr.shape != img.shape:
        print("읽기 실패", im["file_name"], None if not ok else fr.shape, None if img is None else img.shape)
        bad += 1
        continue
    diff = float(np.abs(fr.astype(int) - img.astype(int)).mean())
    print(f"{im['file_name']}  프레임 {im['frame_idx']}  평균 화소 차이 {diff:.2f}")
print("영상 연결 실패", bad, "/", len(sample))

stamps = {i["session"] for i in d["images"]}
have = set()
for date in os.listdir(VID):
    for s in os.listdir(f"{VID}/{date}"):
        have.add(s)
print("정답 촬영", len(stamps), "| 영상 폴더 촬영", len(have), "| 정답에 있고 영상에 없는 촬영", len(stamps - have), "| 영상에만 있는 촬영", len(have - stamps))

keep = {"gm": ("good", "ambiguous"), "good": ("good",)}
for name, grades in keep.items():
    a = [x for x in d["annotations"] if (x.get("attributes") or {}).get("grade") in grades]
    ids = {x["image_id"] for x in a}
    dd = dict(d, images=[i for i in d["images"] if i["id"] in ids], annotations=a)
    json.dump(dd, open(f"/tmp/gt_{name}.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(name, "annotations", len(a))
