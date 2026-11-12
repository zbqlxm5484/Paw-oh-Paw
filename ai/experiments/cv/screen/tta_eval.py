import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

PAW = Path("@HOME@/work/ssafy/paw_eval")
sys.path.insert(0, str(PAW))
from predict import MMPose, input_box, load_boxes, read_image  # noqa: E402

N = 22


def unrotate(kp, c, deg):
    th = math.radians(deg)
    cs, sn = math.cos(th), math.sin(th)
    d = kp - c
    return np.stack([c[0] + cs * d[:, 0] - sn * d[:, 1], c[1] + sn * d[:, 0] + cs * d[:, 1]], 1)


def run(config, weights, gt, images, scales, rots, out, limit=0):
    model = MMPose({"config": str(config), "weights": str(weights)}, PAW, "cuda:0")
    ims, anns, _ = load_boxes(str(gt))
    if limit:
        anns = anns[:limit]
    by_id = {im["id"]: im for im in ims}
    preds = []
    for ann in anns:
        im = by_id[ann["image_id"]]
        img = read_image(Path(images) / im["file_name"])
        box = np.array(input_box(ann["bbox"], im), float)
        c = (box[:2] + box[2:]) / 2
        outs, base_sc = [], None
        for s in scales:
            half = (box[2:] - box[:2]) * s / 2
            kp, sc = model(img, [float(v) for v in (*(c - half), *(c + half))])
            if base_sc is None or s == 1.0:
                base_sc = sc[:N]
            outs.append(np.asarray(kp[:N], float))
        for d in rots:
            m = cv2.getRotationMatrix2D((float(c[0]), float(c[1])), d, 1.0)
            rot = cv2.warpAffine(img, m, (img.shape[1], img.shape[0]), borderMode=cv2.BORDER_REPLICATE)
            kp, _ = model(rot, [float(v) for v in box])
            outs.append(unrotate(np.asarray(kp[:N], float), c, d))
        mean = np.mean(outs, axis=0)
        preds.append({"ann_id": ann["id"], "image_id": ann["image_id"], "category_id": ann.get("category_id", 1),
                      "keypoints": [float(v) for k, s in zip(mean, base_sc) for v in (k[0], k[1], s)],
                      "score": float(np.mean(base_sc))})
    meta = {"tta": {"scales": scales, "rots": rots}, "config": str(config), "weights": str(weights)}
    Path(out).write_text(json.dumps({"meta": meta, "predictions": preds}), encoding="utf-8")
    return len(preds)
