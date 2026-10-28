"""tiny 탐지기 증류용 데이터 2판(10-22, S15P31A404-74 (2/2)).

1판(det_teacher.py)과 다른 점: 카메라 4대 전부, 개·날짜를 고르게(개×날짜마다 최대 SESS_PER 촬영), 와우와우 포레스트
(30fps·720p) 촬영 포함. 제니는 KPI-23 평가 영상이라 뺀다. 정답은 기업 탐지기(RTMDet-m)의 개 상자(점수 0.25 이상 최고 하나).

    python diag/det_teacher2.py      # 컨테이너 안, /data = dataset_1021
"""

import csv
import json
import random
from collections import defaultdict
from pathlib import Path

import cv2
import torch
from mmdet.apis import inference_detector, init_detector

STEP, H, CONF, DOG = 8, 768, 0.25, 16
SESS_PER = 3
SESS_PER_WW = 10  # 와우와우는 개 이름이 없어 날짜 하나가 한 묶음. 30fps·720p 를 늘리려고 더 뽑는다
VAL_SHARE = 0.15
R = Path("/work/det_train2")
IMG = R / "img"
IMG.mkdir(parents=True, exist_ok=True)
D = Path("/data")  # dataset_1021 (manifest 의 path 는 videos/... 로 시작)
V = D / "videos"

rows = [
    r
    for r in csv.DictReader(open(V / "manifest.csv", encoding="utf-8-sig"))
    if r["label"] not in ("calib", "weight") and r["dog"] != "제니"
]
by = defaultdict(list)
for r in rows:
    key = (r["dog"] or r["stamp"][:6] + "-ww", r["date"])
    by[key].append(r)
rng = random.Random(42)
pick = []
for key in sorted(by):
    ss = sorted(by[key], key=lambda r: r["stamp"])
    rng.shuffle(ss)
    pick += ss[: SESS_PER_WW if key[0].endswith("-ww") else SESS_PER]
# 촬영 단위로 val 을 뗀다(같은 촬영의 프레임이 학습·검증에 같이 들어가지 않게)
stamps = sorted({r["stamp"] for r in pick})
rng.shuffle(stamps)
val_st = set(stamps[: int(len(stamps) * VAL_SHARE)])

det = init_detector("/work/model/det.py", "/work/model/det.pth", device="cuda:0")
COCO = json.load(open("/work/det_train/coco_categories.json"))
out = {s: {"images": [], "annotations": [], "categories": COCO} for s in ("train", "val")}
n = 0
for r in pick:
    folder = D / r["path"] if r.get("path") else None
    vids = (
        sorted(folder.glob("*.mp4")) + sorted(folder.glob("*.mov"))
        if folder and folder.exists()
        else []
    )
    s = "val" if r["stamp"] in val_st else "train"
    for v in vids:
        cap = cv2.VideoCapture(str(v))
        i, batch = 0, []
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            if i % STEP == 0:
                h, w = fr.shape[:2]
                if h > H:
                    fr = cv2.resize(fr, (round(w * H / h / 2) * 2, H), interpolation=cv2.INTER_AREA)
                batch.append((f"{v.stem}_f{i:06d}.jpg", fr))
            i += 1
        for k in range(0, len(batch), 16):
            chunk = batch[k : k + 16]
            res = inference_detector(det, [f for _, f in chunk])
            for (name, fr), p in zip(chunk, res):
                n += 1
                cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tofile(str(IMG / name))
                out[s]["images"].append(
                    {
                        "id": n,
                        "file_name": name,
                        "width": fr.shape[1],
                        "height": fr.shape[0],
                        "site": r["site"],
                        "stamp": r["stamp"],
                    }
                )
                q = p.pred_instances
                keep = (q.labels == DOG) & (q.scores >= CONF)
                if keep.any():
                    j = int(torch.argmax(torch.where(keep, q.scores, torch.zeros_like(q.scores))))
                    x0, y0, x1, y1 = q.bboxes[j].tolist()
                    out[s]["annotations"].append(
                        {
                            "id": n,
                            "image_id": n,
                            "category_id": 18,
                            "bbox": [x0, y0, x1 - x0, y1 - y0],
                            "area": (x1 - x0) * (y1 - y0),
                            "iscrowd": 0,
                        }
                    )
        print(r["site"], v.stem, len(batch), flush=True)
for s, d in out.items():
    json.dump(d, open(R / f"{s}.json", "w", encoding="utf-8"), ensure_ascii=False)
    sites = defaultdict(int)
    for im in d["images"]:
        sites[im["site"]] += 1
    print(s, "images", len(d["images"]), "dog boxes", len(d["annotations"]), dict(sites))
