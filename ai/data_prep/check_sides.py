"""aihub_to_coco.py 가 정한 좌우가 맞는지 확인한다.

1) 숫자 확인 (옆 촬영만): 개의 왼쪽 몸통을 찍었다면 개는 화면 왼쪽을 향한다.
   귀(머리)와 장골능(엉덩이)의 x 를 비교해 Left 폴더는 머리가 왼쪽, Right 폴더는 머리가 오른쪽인 비율을 센다.
2) 눈 확인: 촬영 방향별로 무작위 사진에 관절점을 그린다. 파랑 = left, 빨강 = right, 노랑 = 가운데 점.
   - Back(뒤에서): 파랑이 화면 왼쪽에 있어야 한다.
   - Front(앞에서, 마주 봄): 파랑이 화면 오른쪽에 있어야 한다.
   - Left(옆): 파랑만, 머리가 화면 왼쪽. Right(옆): 빨강만, 머리가 화면 오른쪽.

사용
  python check_sides.py --coco <aihub71878_val.json> --out sides.jpg [--per-view 4] [--seed 0]
"""
import argparse
import collections
import json
import os
import random

from PIL import Image, ImageDraw

TILE = 400


def head_direction(doc):
    names = doc["categories"][0]["keypoints"]
    ear = [names.index("left_ear"), names.index("right_ear")]
    hip = [names.index("iliac_crest"), names.index("left_femoral_greater_trochanter"),
           names.index("right_femoral_greater_trochanter")]
    imgs = {i["id"]: i for i in doc["images"]}
    count = collections.Counter()
    for a in doc["annotations"]:
        view = imgs[a["image_id"]].get("view")
        if view not in ("Left", "Right"):
            continue
        k = a["keypoints"]
        ex = [k[3 * i] for i in ear if k[3 * i + 2]]
        hx = [k[3 * i] for i in hip if k[3 * i + 2]]
        if ex and hx:
            count[(view, "head_left" if ex[0] < hx[0] else "head_right")] += 1
    for view, want in (("Left", "head_left"), ("Right", "head_right")):
        n = count[(view, "head_left")] + count[(view, "head_right")]
        if n:
            print(f"{view}: 머리 방향이 예상과 맞음 {count[(view, want)]}/{n} ({count[(view, want)] / n:.1%})")


def draw_sheet(doc, out, per_view, seed):
    root = doc["info"]["image_root"]
    names = doc["categories"][0]["keypoints"]
    skeleton = doc["categories"][0]["skeleton"]
    imgs = {i["id"]: i for i in doc["images"]}
    by_view = collections.defaultdict(list)
    for a in doc["annotations"]:
        by_view[imgs[a["image_id"]].get("view", "all")].append(a)

    def color(i):
        if names[i].startswith("left"):
            return (40, 110, 240)
        if names[i].startswith("right"):
            return (230, 40, 40)
        return (250, 200, 0)

    rng = random.Random(seed)
    tiles = []
    for view in sorted(by_view):
        for a in rng.sample(by_view[view], min(per_view, len(by_view[view]))):
            info = imgs[a["image_id"]]
            im = Image.open(os.path.join(root, info["file_name"])).convert("RGB")
            dr = ImageDraw.Draw(im)
            k = a["keypoints"]
            pts = {i: (k[3 * i], k[3 * i + 1]) for i in range(len(names)) if k[3 * i + 2]}
            for s, t in skeleton:
                if s - 1 in pts and t - 1 in pts:
                    dr.line([pts[s - 1], pts[t - 1]], fill=color(t - 1), width=6)
            for i, (x, y) in pts.items():
                dr.ellipse([x - 10, y - 10, x + 10, y + 10], fill=color(i), outline=(255, 255, 255))
            x, y, w, h = a["bbox"]
            dr.rectangle([x, y, x + w, y + h], outline=(0, 200, 0), width=4)
            half = max(w, h) * 0.75 + 40
            cx, cy = x + w / 2, y + h / 2
            im = im.crop((int(cx - half), int(cy - half), int(cx + half), int(cy + half))).resize((TILE, TILE))
            ImageDraw.Draw(im).text((6, 6), f"{view}  {os.path.basename(info['file_name'])}", fill=(255, 255, 255))
            tiles.append(im)
    cols = per_view
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * TILE, rows * TILE), (30, 30, 30))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * TILE, (i // cols) * TILE))
    sheet.save(out)
    print(f"그림 저장: {out} (한 줄 = 촬영 방향 하나)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--coco", required=True, help="aihub_to_coco.py 산출 JSON (예: aihub71878_val.json)")
    ap.add_argument("--out", default="sides.jpg")
    ap.add_argument("--per-view", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0, help="바꾸면 다른 사진이 뽑힌다")
    args = ap.parse_args()
    doc = json.load(open(args.coco, encoding="utf-8"))
    head_direction(doc)
    draw_sheet(doc, args.out, args.per_view, args.seed)


if __name__ == "__main__":
    main()
