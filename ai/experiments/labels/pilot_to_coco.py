r"""라벨 맞추기 한 사람 결과(labels.json 의 태스크 하나)를 paw_eval 정답 형식(COCO)으로 바꾼다.

    python pilot_to_coco.py pilot20-A $CVAT_LABELING_DIR\pilot\pilotA_gt.json

상자 = 오토라벨 상자(kp_dump). 보임 2 · 가려짐(Q) 1 · 화면 밖 0. touched = 오토라벨에서 0.5px 넘게 옮긴 점.
"""

import json
import os
import sys

import numpy as np

_CVAT = os.environ.get("CVAT_LABELING_DIR", "C:/cvat-labeling")

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import pilot_agreement as pa  # noqa: E402

task, out = sys.argv[1], sys.argv[2]
lab = json.load(open(pa.PILOT / "labels.json", encoding="utf-8"))[task]
dump = {r["frame_name"]: r for r in map(json.loads, open(pa.DUMP, encoding="utf-8"))}
images, anns = [], []
for n, (f, shapes) in enumerate(sorted(lab["frames"].items()), 1):
    k, d = pa.arr(shapes[0]), dump[f]
    x0, y0, x1, y1 = d["bbox"]
    auto = np.array(d["keypoints"])[:22, :2]
    kp = []
    for i in range(22):
        v = 0 if k[i, 3] else 1 if k[i, 2] else 2
        kp += [float(k[i, 0]), float(k[i, 1]), v] if v else [0.0, 0.0, 0]
    images.append({"id": n, "file_name": f, "width": 1920, "height": 1080})
    anns.append(
        {
            "id": n,
            "image_id": n,
            "category_id": 1,
            "bbox": [x0, y0, x1 - x0, y1 - y0],
            "keypoints": kp,
            "attributes": {
                "touched": [int(np.linalg.norm(k[i, :2] - auto[i]) > 0.5) for i in range(22)],
                "grade": shapes[0]["attrs"].get("grade"),
            },
        }
    )
json.dump(
    {
        "images": images,
        "annotations": anns,
        "categories": [{"id": 1, "name": "dog", "keypoints": pa.NAMES}],
    },
    open(out, "w", encoding="utf-8"),
    ensure_ascii=False,
)
print(out, len(images), "장, 고친 점", sum(sum(a["attributes"]["touched"]) for a in anns))
