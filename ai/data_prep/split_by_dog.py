"""크림오프 촬영을 개 단위로 학습/검증에 나눈다 (S15P31A404-35).

    python split_by_dog.py --manifest <dataset>/videos/manifest.csv --out <밖의 폴더>
    python split_by_dog.py ... --apply 정답.json   # COCO 파일을 split 별 파일로 나눈다

같은 개의 인접 프레임·다른 카메라 영상이 학습과 검증에 함께 들어가면 검증 점수가 부풀어서, 개를 통째로
한쪽에만 넣는다. 결과(개 이름·촬영 목록)는 기업 자료에서 나온 것이라 레포 밖에 쓴다.

규칙
- 제니: gt_eval 고정. 기업 정답 205장(keypoints_260820)이 전부 제니라 재현·비교용으로 남기고, 학습에 섞지 않으려고
  제니의 다른 영상도 학습에서 뺀다.
- dogA(질환견 가명): disease. 정상 보행 학습·검증과 섞지 않는다.
- 나머지: 체급(<10 소형, 10~25 중형, >=25 대형, manifest weight_kg)마다 개 수의 VAL_SHARE 를 검증으로 보낸다
  (최소 1마리). 촬영 수가 아니라 개 수로 맞추는 건, 보려는 것이 "처음 보는 개"에서의 성능이고 학습 라벨은 개마다
  골라 만들기 때문이다. 촬영이 가장 많은 개는 학습 데이터를 위해 train 에 둔다. 나머지는 시드로 섞어 고른다.
- calib·weight·_discard 촬영은 뺀다(개가 걷지 않음). 단 정답이 있는 촬영(has_keypoint_gt=1)은 _discard 여도 둔다.

AI-Hub 71878 과 합칠 때: AI-Hub 는 aihub_to_coco.py 의 세션 단위 분할을 그대로 쓴다(크림오프와 개가 겹치지 않음).
학습 = 크림오프 train + AI-Hub train, 검증은 출처별로 따로 보고하고 KPI 판단은 크림오프 val 로 한다.
"""
import argparse
import collections
import csv
import json
import random
import re
from pathlib import Path

FIXED = {"제니": "gt_eval", "dogA": "disease"}
NOT_WALKING = {"calib", "weight", "_discard"}
VAL_SHARE = 0.3
STAMP = re.compile(r"(\d{6}-\d{6})")


def size_class(kg):
    return "소형" if kg < 10 else "중형" if kg < 25 else "대형"


def load_sessions(manifest):
    rows = [r for r in csv.DictReader(open(manifest, encoding="utf-8-sig"))
            if r["label"] not in NOT_WALKING or r["has_keypoint_gt"] == "1"]
    return [dict(r, kg=float(r["weight_kg"])) for r in rows]


def split_dogs(sessions, seed, val_share):
    by_dog = collections.defaultdict(list)
    for s in sessions:
        by_dog[s["dog"]].append(s)
    assign = {d: FIXED[d] for d in by_dog if d in FIXED}
    by_class = collections.defaultdict(list)
    for d, ss in by_dog.items():
        if d not in assign:
            by_class[size_class(ss[0]["kg"])].append(d)
    rng = random.Random(seed)
    for cls in sorted(by_class):
        dogs = sorted(by_class[cls], key=lambda d: (-len(by_dog[d]), d))
        biggest, rest = dogs[0], dogs[1:]
        rng.shuffle(rest)
        k = min(max(1, round(val_share * len(dogs))), len(rest))
        for d in dogs:
            assign[d] = "val" if d in rest[:k] else "train"
    return assign, by_dog


def stats(assign, by_dog):
    out = collections.defaultdict(lambda: collections.Counter())
    for d, split in assign.items():
        ss = by_dog[d]
        key = (split, size_class(ss[0]["kg"]) if d not in FIXED else "-")
        out[key]["dogs"] += 1
        out[key]["sessions"] += len(ss)
        out[key]["videos"] += sum(int(s["n_files"]) for s in ss)
        for site in {s["site"] for s in ss}:
            out[key][f"site:{site}"] += 1
    return out


def apply_split(coco_path, stamp_to_split, out_dir):
    """COCO 파일의 이미지를 촬영 stamp(images[].session 또는 파일 이름)로 split 에 나눈다."""
    doc = json.load(open(coco_path, encoding="utf-8"))
    where = {}
    for im in doc["images"]:
        m = STAMP.search(im.get("session") or im["file_name"])
        where[im["id"]] = stamp_to_split.get(m[1]) if m else None
    missing = [i for i, s in where.items() if s is None]
    if missing:
        raise SystemExit(f"{coco_path}: 촬영을 못 찾은 이미지 {len(missing)}장 (예: id {missing[:3]})")
    for split in sorted(set(where.values())):
        part = dict(doc, images=[im for im in doc["images"] if where[im["id"]] == split],
                    annotations=[a for a in doc["annotations"] if where[a["image_id"]] == split])
        dst = Path(out_dir) / f"{Path(coco_path).stem}_{split}.json"
        json.dump(part, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"{dst.name}: 이미지 {len(part['images'])} · annotation {len(part['annotations'])}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--val-share", type=float, default=VAL_SHARE)
    ap.add_argument("--apply", nargs="*", default=[], help="split 별로 나눌 COCO 파일")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sessions = load_sessions(args.manifest)
    assign, by_dog = split_dogs(sessions, args.seed, args.val_share)

    dogs = [{"dog": d, "split": assign[d], "size_class": size_class(by_dog[d][0]["kg"]), "weight_kg": by_dog[d][0]["kg"],
             "sessions": len(by_dog[d]), "sites": sorted({s["site"] for s in by_dog[d]})} for d in sorted(assign)]
    stamp_to_split = {s["stamp"]: assign[s["dog"]] for s in sessions}
    meta = {"seed": args.seed, "val_share": args.val_share, "fixed": FIXED, "excluded_labels": sorted(NOT_WALKING)}
    json.dump({**meta, "dogs": dogs, "sessions": stamp_to_split},
              open(out / "creamoff_dog_split.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"{'split':8s} {'체급':4s} {'개':>3s} {'촬영':>5s} {'영상':>5s}  장소")
    for (split, cls), c in sorted(stats(assign, by_dog).items()):
        sites = ", ".join(f"{k[5:]} {v}" for k, v in sorted(c.items()) if k.startswith("site:"))
        print(f"{split:8s} {cls:4s} {c['dogs']:>3d} {c['sessions']:>5d} {c['videos']:>5d}  {sites}")
    for d in dogs:
        print(f"  {d['split']:8s} {d['size_class']} {d['dog']:6s} {d['weight_kg']:5.1f}kg 촬영 {d['sessions']:>3d} {','.join(d['sites'])}")

    for p in args.apply:
        apply_split(p, stamp_to_split, out)


if __name__ == "__main__":
    main()
