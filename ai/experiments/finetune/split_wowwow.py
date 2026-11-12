"""keypoints_wowwow 를 학습/검증으로 나눈다(10-22).

    python split_wowwow.py --gt <dataset>/keypoints_wowwow/annotations.json --out <폴더> [--val-share 0.2] [--seed 42]

- 쓰는 라벨: 사람이 확인한 것만(attributes.human_fixed = True 이고 grade 가 unusable 이 아닌 것).
  unusable 4,955장은 대부분 fs-v4 사전라벨 그대로라 가짜 라벨과 같다(10-20 실험에서 기준선보다 나빠짐).
- 나누는 단위: 개 이름이 거의 없어서, 같은 날 앞 촬영과 GAP_S 넘게 떨어지면 새 '묶음'(대략 개 한 마리)으로 본다.
  묶음을 통째로 한쪽에 넣는다. 같은 개가 다른 시각에 다시 걸었다면 누수가 남을 수 있다.
- 출력: wowwow_train.json, wowwow_val.json (원본 형식 그대로, 22점), wowwow_split.json (묶음 → split).
"""

import argparse
import collections
import json
import random
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
GAP_S = 300


def seconds(stamp):
    hms = stamp[7:13]
    return int(hms[:2]) * 3600 + int(hms[2:4]) * 60 + int(hms[4:6])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--val-share", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    doc = json.loads(Path(a.gt).read_text(encoding="utf-8"))
    images = {im["id"]: im for im in doc["images"]}
    anns = [
        an
        for an in doc["annotations"]
        if an["attributes"].get("human_fixed") and an["attributes"].get("grade") != "unusable"
    ]

    bout_of, bouts = {}, collections.defaultdict(list)
    for stamp in sorted({im["session"] for im in doc["images"]}):
        day = stamp[:6]
        last = next((b for b in sorted(bouts, reverse=True) if b[0] == day), None)
        if last is None or seconds(stamp) - seconds(bouts[last][-1]) > GAP_S:
            last = (day, len([b for b in bouts if b[0] == day]))
        bouts[last].append(stamp)
        bout_of[stamp] = last

    n_img = collections.Counter(bout_of[images[an["image_id"]]["session"]] for an in anns)
    used = sorted(b for b in bouts if n_img[b])
    rng = random.Random(a.seed)
    rng.shuffle(used)
    target = a.val_share * sum(n_img.values())
    val, acc = set(), 0
    for b in used:  # 사진 수가 목표에 닿을 때까지 묶음을 val 로
        if acc >= target:
            break
        val.add(b)
        acc += n_img[b]

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for split in ("train", "val"):
        keep = [
            an
            for an in anns
            if (bout_of[images[an["image_id"]]["session"]] in val) == (split == "val")
        ]
        ids = {an["image_id"] for an in keep}
        d = dict(doc, images=[images[i] for i in sorted(ids)], annotations=keep)
        (out / f"wowwow_{split}.json").write_text(
            json.dumps(d, ensure_ascii=False), encoding="utf-8"
        )
        days = collections.Counter(images[i]["date"] for i in ids)
        cams = collections.Counter(images[i]["camera"] for i in ids)
        n_b = len({bout_of[images[i]["session"]] for i in ids})
        print(
            f"{split:5s} 사진 {len(ids):5d}  묶음 {n_b:3d}  날짜 {dict(sorted(days.items()))}  카메라 {dict(cams)}"
        )
    split_map = {
        f"{d}-{i:02d}": {
            "split": "val" if (d, i) in val else "train",
            "sessions": bouts[(d, i)],
            "images": n_img[(d, i)],
        }
        for (d, i) in sorted(bouts)
    }
    (out / "wowwow_split.json").write_text(
        json.dumps(split_map, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"-> {out}  (묶음 {len(bouts)}개 중 라벨 있는 {len(used)}개, 간격 {GAP_S}초)")


if __name__ == "__main__":
    main()
