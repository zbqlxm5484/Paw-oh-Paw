import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, "/work/ssafy/paw_eval")
from predict import MMPose, input_box, load_boxes, read_image

PAW = Path("/work/ssafy/paw_eval")
GT = "/ssafy/dataset/keypoints_260820/annotations.json"
ROOT = Path("/ssafy/dataset/keypoints_260820")
OUT = Path("/exp/cv/data/fs-v4.tta.preds.json")
SCALES = [0.85, 0.9, 1.0, 1.1, 1.15]
ROTS = [8.0, -8.0]
N = 22
T13, ILIAC = 2, 13


def unrotate(kp, c, deg):
    th = math.radians(deg)
    cs, sn = math.cos(th), math.sin(th)
    d = kp - c
    return np.stack([c[0] + cs * d[:, 0] - sn * d[:, 1], c[1] + sn * d[:, 0] + cs * d[:, 1]], 1)


cfg = {"config": "/exp/cv/pose_flip.py", "weights": "models/fs-v4/pose.pth"}
model = MMPose(cfg, PAW, "cuda:0")
images, anns, _ = load_boxes(GT)
by_id = {im["id"]: im for im in images}
gt = {a["id"]: np.array(a["keypoints"], float).reshape(-1, 3)[:N] for a in json.loads(Path(GT).read_text(encoding="utf-8"))["annotations"]}

preds, drift = [], []
for n, ann in enumerate(anns, 1):
    im = by_id[ann["image_id"]]
    img = read_image(ROOT / im["file_name"])
    box = np.array(input_box(ann["bbox"], im), float)
    c = (box[:2] + box[2:]) / 2
    outs, base_kp, base_sc = [], None, None
    for s in SCALES:
        half = (box[2:] - box[:2]) * s / 2
        kp, sc = model(img, [float(v) for v in (*(c - half), *(c + half))])
        if s == 1.0:
            base_kp, base_sc = kp[:N], sc[:N]
        outs.append(kp[:N])
    for d in ROTS:
        m = cv2.getRotationMatrix2D((float(c[0]), float(c[1])), d, 1.0)
        rot = cv2.warpAffine(img, m, (img.shape[1], img.shape[0]), borderMode=cv2.BORDER_REPLICATE)
        kp, _ = model(rot, [float(v) for v in box])
        outs.append(unrotate(kp[:N], c, d))
    mean = np.mean(outs, axis=0)
    g = gt[ann["id"]]
    if g[T13, 2] > 0 and g[ILIAC, 2] > 0:
        L = float(np.linalg.norm(g[T13, :2] - g[ILIAC, :2]))
        if L > 0:
            drift.append(float(np.median(np.linalg.norm(mean - base_kp, axis=1))) / L)
    preds.append({"ann_id": ann["id"], "image_id": ann["image_id"], "category_id": ann["category_id"],
                  "keypoints": [float(v) for k, s in zip(mean, base_sc) for v in (k[0], k[1], s)],
                  "score": float(base_sc.mean())})
    if n % 50 == 0:
        print(f"  {n}/{len(anns)}", flush=True)

OUT.write_text(json.dumps({"meta": {"tta": {"scales": SCALES, "rots": ROTS, "flip": True}}, "predictions": preds}, ensure_ascii=False), encoding="utf-8")
print(f"-> {OUT} {len(preds)}건, 기본 예측과 TTA 평균의 점별 중앙 차이 {np.median(drift):.4f} (몸통 길이 대비)")
