"""tiny 탐지기 증류용 데이터: pool 영상에서 STEP 프레임마다 높이 768 로 줄여 저장하고, 기업 탐지기(RTMDet-m)의
개 상자(COCO dog, 점수 0.25 이상 최고 하나 — 서비스와 같은 규칙)를 정답으로 쓴다. 못 찾은 장은 '개 없음'으로 둔다."""

import csv
import json
from pathlib import Path

import cv2
import torch
from mmdet.apis import inference_detector, init_detector

STEP, H, CONF, DOG = 4, 768, 0.25, 16
R = Path("/work/det_train")
IMG = R / "img"
IMG.mkdir(exist_ok=True)
det = init_detector("/work/model/det.py", "/work/model/det.pth", device="cuda:0")
split = {
    r["video"]: r["split"]
    for r in csv.DictReader(open("/work/pool/pool_videos.csv", encoding="utf-8-sig"))
}
COCO = json.load(open("/work/det_train/coco_categories.json"))
out = {s: {"images": [], "annotations": [], "categories": COCO} for s in ("train", "val")}
n = 0
for v in sorted((Path("/work/pool/videos")).glob("*.mp4")):
    s = split[v.stem]
    cap = cv2.VideoCapture(str(v))
    i = 0
    batch = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if i % STEP == 0:
            h, w = fr.shape[:2]
            fr = cv2.resize(fr, (round(w * H / h / 2) * 2, H), interpolation=cv2.INTER_AREA)
            batch.append((f"{v.stem}_f{i:06d}.jpg", fr))
        i += 1
    for k in range(0, len(batch), 16):
        chunk = batch[k : k + 16]
        res = inference_detector(det, [f for _, f in chunk])
        for (name, fr), r in zip(chunk, res):
            n += 1
            cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tofile(str(IMG / name))
            out[s]["images"].append(
                {"id": n, "file_name": name, "width": fr.shape[1], "height": fr.shape[0]}
            )
            p = r.pred_instances
            keep = (p.labels == DOG) & (p.scores >= CONF)
            if keep.any():
                j = int(torch.argmax(torch.where(keep, p.scores, torch.zeros_like(p.scores))))
                x0, y0, x1, y1 = p.bboxes[j].tolist()
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
    print(v.stem, len(batch), flush=True)
for s, d in out.items():
    json.dump(d, open(R / f"{s}.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(s, "images", len(d["images"]), "dog boxes", len(d["annotations"]))
