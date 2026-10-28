"""22점 COCO 라벨을 fs-v4 출력 46점 형식으로 늘린다(aux 24점은 0, 가시성 0 → 손실에 안 들어감). 10-22.

    python to46.py --coco train.json --out train46.json [--keep-images ids.json]

- 22점 순서는 CVAT/기업 정답과 같아야 한다(0 left_ear … 21 right_fifth_metatarsal_distal).
- 상자(bbox)가 없거나 0 이면 보이는 관절점 상자에 여백 15% 를 붙여 만든다.
"""

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
N22, N46 = 22, 46


def bbox_from_kp(kp, w, h, margin=0.15):
    xs = [kp[3 * i] for i in range(N22) if kp[3 * i + 2] > 0]
    ys = [kp[3 * i + 1] for i in range(N22) if kp[3 * i + 2] > 0]
    if not xs:
        return None
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    mx, my = (x1 - x0) * margin, (y1 - y0) * margin
    x0, y0 = max(0, x0 - mx), max(0, y0 - my)
    x1, y1 = min(w, x1 + mx), min(h, y1 + my)
    return [x0, y0, x1 - x0, y1 - y0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coco", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--keep-images", help="남길 image id 목록 JSON (split_by_dog 결과 등)")
    a = ap.parse_args()

    doc = json.loads(Path(a.coco).read_text(encoding="utf-8"))
    keep = (
        set(json.loads(Path(a.keep_images).read_text(encoding="utf-8"))) if a.keep_images else None
    )
    images = {im["id"]: im for im in doc["images"] if keep is None or im["id"] in keep}
    anns, dropped = [], 0
    for an in doc["annotations"]:
        if an["image_id"] not in images:
            continue
        kp = list(an["keypoints"])
        if len(kp) != 3 * N22:
            sys.exit(f"annotation {an['id']}: 관절점 {len(kp) // 3}개 — 22점 라벨이 아니다")
        im = images[an["image_id"]]
        box = an.get("bbox")
        if not box or box[2] <= 0 or box[3] <= 0:
            box = bbox_from_kp(kp, im["width"], im["height"])
        n_vis = sum(1 for i in range(N22) if kp[3 * i + 2] > 0)
        if box is None or n_vis == 0:
            dropped += 1
            continue
        anns.append(
            dict(
                an,
                keypoints=kp + [0] * (3 * (N46 - N22)),
                num_keypoints=n_vis,
                bbox=box,
                area=an.get("area") or box[2] * box[3],
                iscrowd=an.get("iscrowd", 0),
                category_id=1,
            )
        )
    used = {an["image_id"] for an in anns}
    out = dict(
        images=[im for i, im in images.items() if i in used],
        annotations=anns,
        categories=[dict(id=1, name="dog", keypoints=[f"kp{i}" for i in range(N46)], skeleton=[])],
    )
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"-> {a.out}  사진 {len(out['images'])}  라벨 {len(anns)}  (관절점 없어 버림 {dropped})")


if __name__ == "__main__":
    main()
