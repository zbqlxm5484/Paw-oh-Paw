"""자가 학습용 가짜 라벨: 고른 프레임을 영상에서 꺼내고(차례로 읽기), fs-v4 + flip test 로 46점을 찍어 COCO 로 쓴다."""

import collections
import json
from pathlib import Path

import cv2
import numpy as np
from mmengine.config import Config
from mmpose.apis import inference_topdown, init_model

R = Path("/work/train_pseudo")
IMG = R / "img"
IMG.mkdir(exist_ok=True)
sel = json.load(open(R / "select.json", encoding="utf-8"))
cfg = Config.fromfile("/work/model/pose.py")
cfg.model.test_cfg = dict(flip_test=True)
model = init_model(cfg, "/work/model/pose.pth", device="cuda:0")
want = collections.defaultdict(dict)
for s in sel:
    want[s["video"]][s["frame"]] = s
images, anns, n = [], [], 0
for v, frames in want.items():
    cap = cv2.VideoCapture(f"/work/pool/videos/{v}.mp4")
    i = 0
    while i <= max(frames):
        ok, fr = cap.read()
        if not ok:
            break
        if i in frames:
            n += 1
            name = f"{v}_f{i:06d}.jpg"
            cv2.imencode(".jpg", fr)[1].tofile(str(IMG / name))
            x0, y0, x1, y1 = frames[i]["bbox"]
            p = inference_topdown(model, fr, [[x0, y0, x1, y1]], bbox_format="xyxy")[
                0
            ].pred_instances
            kp, sc = p.keypoints[0], p.keypoint_scores[0]
            flat = []
            for (x, y), c in zip(kp, sc):
                flat += [float(x), float(y), 2] if c >= 0.3 else [0.0, 0.0, 0]
            images.append(
                {
                    "id": n,
                    "file_name": name,
                    "width": fr.shape[1],
                    "height": fr.shape[0],
                    "dog": frames[i]["dog"],
                }
            )
            anns.append(
                {
                    "id": n,
                    "image_id": n,
                    "category_id": 1,
                    "iscrowd": 0,
                    "bbox": [x0, y0, x1 - x0, y1 - y0],
                    "area": (x1 - x0) * (y1 - y0),
                    "keypoints": flat,
                    "num_keypoints": sum(f > 0 for f in flat[2::3]),
                }
            )
        i += 1
names = [model.dataset_meta["keypoint_id2name"][k] for k in range(46)]
json.dump(
    {
        "images": images,
        "annotations": anns,
        "categories": [{"id": 1, "name": "dog", "keypoints": names}],
    },
    open(R / "pseudo46.json", "w", encoding="utf-8"),
    ensure_ascii=False,
)
print("images", len(images), "points/img", np.mean([a["num_keypoints"] for a in anns]))
