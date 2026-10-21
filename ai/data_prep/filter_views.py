"""aihub_to_coco.py 가 만든 COCO 파일에서 촬영 방향(view)으로 사진을 골라 낸다.

크림오프는 카메라 한 대로 옆에서 좌우 반복 촬영하므로, AI-Hub 71878 은 옆 촬영(Left/Right)만 학습에 쓴다.
앞·뒤 촬영(Front/Back)은 뺀다.

사용
  python filter_views.py --coco aihub71878_train.json --out aihub71878_train_side.json [--views Left,Right]
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coco", required=True, help="aihub_to_coco.py 출력 (images[].view 가 있는 파일)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--views", default="Left,Right", help="남길 촬영 방향, 쉼표로 구분")
    a = ap.parse_args()

    keep = set(a.views.split(","))
    doc = json.loads(Path(a.coco).read_text(encoding="utf-8"))
    images = [im for im in doc["images"] if im.get("view") in keep]
    ids = {im["id"] for im in images}
    anns = [an for an in doc["annotations"] if an["image_id"] in ids]
    counts = collections.Counter(im["view"] for im in images)

    info = dict(doc.get("info", {}), views=sorted(keep), source=Path(a.coco).name)
    out = dict(doc, info=info, images=images, annotations=anns)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"-> {a.out}  사진 {len(images)}/{len(doc['images'])}  라벨 {len(anns)}  방향별 {dict(counts)}")


if __name__ == "__main__":
    main()
