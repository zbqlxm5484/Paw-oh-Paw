"""AI-Hub 반려견 데이터를 크림오프 22점 COCO Keypoints 로 바꾼다.

대상
  - 71878 반려견 보행영상 기반 건강관리 데이터: 관절 이름 12개가 크림오프 22점과 같은 해부학 지점이다.
    좌우 표시만 없어서 촬영 방향으로 좌우를 정한다.
  - 59 반려동물 구분을 위한 동물 영상(DOG/WALKRUN): 관절 정의가 달라 8곳만 근사로 옮긴다.
    개 위치 박스는 정확하므로 주로 탐지기 학습용이다.

산출물(--out)
  aihub71878_{train,val,test}.json   크림오프 22점, 세션 단위로 다시 나눔
  aihub59_walkrun_{train,val,test}.json  근사 8점 + 원본 박스, 영상 단위로 나눔
  report.json                        건수·버린 이유·좌우 판정 진단

이미지는 복사하지 않는다. file_name 은 각 데이터 루트 기준 상대 경로이고 루트는 info.image_root 에 적는다.
산출물에는 기업 자료와 같은 정의가 들어가므로 저장소에 올리지 않는다(.gitignore 의 data/, outputs/).

사용
  python aihub_to_coco.py --aihub71878 <71878 루트> --aihub59 <59 의 01.데이터> --out <출력 폴더>
"""
import argparse
import collections
import json
import math
import os
import random
import re

from PIL import Image

# 크림오프 22점 순서. 정답 파일 categories[0].keypoints 와 같다.
KEYPOINTS = [
    "left_ear", "right_ear", "t13_spinous_process",
    "left_dorsal_scapular_spine", "left_acromion_greater_tubercle", "left_lateral_humeral_epicondyle",
    "left_ulnar_styloid_process", "left_fifth_metacarpal_distal",
    "right_dorsal_scapular_spine", "right_acromion_greater_tubercle", "right_lateral_humeral_epicondyle",
    "right_ulnar_styloid_process", "right_fifth_metacarpal_distal",
    "iliac_crest",
    "left_femoral_greater_trochanter", "left_femorotibial_joint", "left_lateral_malleolus",
    "left_fifth_metatarsal_distal",
    "right_femoral_greater_trochanter", "right_femorotibial_joint", "right_lateral_malleolus",
    "right_fifth_metatarsal_distal",
]
SKELETON = [[1, 3], [2, 3], [3, 14], [3, 4], [4, 5], [5, 6], [6, 7], [7, 8], [3, 9], [9, 10], [10, 11],
            [11, 12], [12, 13], [14, 15], [15, 16], [16, 17], [17, 18], [14, 19], [19, 20], [20, 21], [21, 22]]
SLOT = {name: i for i, name in enumerate(KEYPOINTS)}

# 71878 라벨 이름 → 좌우를 뺀 부위 이름. None 이면 몸 가운데 점(좌우 없음).
NAME_71878 = {
    "Ear": "ear",
    "T13 Spinous precess": None,
    "Dorsal scapular spine": "dorsal_scapular_spine",
    "Acromion/Greater tubercle": "acromion_greater_tubercle",
    "Lateral humeral epicondyle": "lateral_humeral_epicondyle",
    "Ulnar styloid process": "ulnar_styloid_process",
    "Distal lateral aspect of fifth metacarpal bone": "fifth_metacarpal_distal",
    "Iliac crest": None,
    "Femoral greater trochanter": "femoral_greater_trochanter",
    "Femorotibial joint": "femorotibial_joint",
    "Lateral malleolus of the distal tibia": "lateral_malleolus",
    "Distal lateral aspect of the fifth metatarsus": "fifth_metatarsal_distal",
}
MIDLINE_71878 = {"T13 Spinous precess": "t13_spinous_process", "Iliac crest": "iliac_crest"}

# 59 키포인트 번호 → 크림오프 슬롯(근사). 59 정의: 6/7 앞다리 시작점, 8/9 앞발목점,
# 10/11 대퇴골점, 12/13 뒷발목점 (짝수 오른쪽, 홀수 왼쪽). 머리·목·꼬리는 대응 없음.
MAP_59 = {
    "6": "right_acromion_greater_tubercle", "7": "left_acromion_greater_tubercle",
    "8": "right_ulnar_styloid_process", "9": "left_ulnar_styloid_process",
    "10": "right_femoral_greater_trochanter", "11": "left_femoral_greater_trochanter",
    "12": "right_lateral_malleolus", "13": "left_lateral_malleolus",
}

# 앞뒤 촬영에서 좌우를 이어 붙일 다리 사슬(몸 쪽 → 발 쪽)
LIMB_CHAINS = [
    ["dorsal_scapular_spine", "acromion_greater_tubercle", "lateral_humeral_epicondyle",
     "ulnar_styloid_process", "fifth_metacarpal_distal"],
    ["femoral_greater_trochanter", "femorotibial_joint", "lateral_malleolus", "fifth_metatarsal_distal"],
]
SPLITS = ("train", "val", "test")


def coco_doc(desc, image_root):
    return {
        "info": {"description": desc, "image_root": image_root},
        "images": [], "annotations": [],
        "categories": [{"id": 1, "name": "dog", "supercategory": "animal",
                        "keypoints": KEYPOINTS, "skeleton": SKELETON}],
    }


def keypoint_bbox(pts, w, h, margin):
    """관절점을 감싸는 상자에 여백을 붙인다. 머리·꼬리 끝은 관절점이 없어 상자 밖으로 나갈 수 있다."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    bw, bh = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
    x0, x1 = max(0.0, x0 - bw * margin), min(w, x1 + bw * margin)
    y0, y1 = max(0.0, y0 - bh * margin), min(h, y1 + bh * margin)
    return [round(x0, 2), round(y0, 2), round(x1 - x0, 2), round(y1 - y0, 2)]


def split_groups(groups_by_strata, ratios, seed):
    """층(반)마다 묶음(세션·영상)을 섞어 비율대로 나눈다. 같은 묶음은 한 split 에만 들어간다."""
    rng = random.Random(seed)
    assign = {}
    for strata in sorted(groups_by_strata):
        groups = sorted(groups_by_strata[strata])
        rng.shuffle(groups)
        n = len(groups)
        n_train = round(n * ratios[0])
        n_val = round(n * ratios[1])
        for i, g in enumerate(groups):
            assign[g] = "train" if i < n_train else "val" if i < n_train + n_val else "test"
    return assign


# ---------------------------------------------------------------- 71878

def _dist(p, q, aspect):
    return math.hypot((p[0] - q[0]) * aspect, p[1] - q[1])


def assign_sides_71878(ann, view, side_view_map, stats, aspect=16 / 9):
    """71878 라벨 한 장을 {슬롯: (x, y)} 로. 좌우를 정할 수 없는 점은 버리고 이유를 센다.

    - Left/Right (옆): 카메라 쪽 다리만 라벨돼 있다. 어느 쪽인지는 side_view_map 으로 정한다.
      같은 이름이 두 번 나오면 어느 것이 카메라 쪽인지 몰라 둘 다 버린다.
    - Back (뒤): 개의 왼쪽이 화면 왼쪽 → x 가 작은 쪽이 left.
    - Front (앞): 마주 보므로 반대 → x 가 작은 쪽이 right.
      한 번만 나온 이름은 어느 쪽인지 몰라 버린다.
      다리 사슬은 맨 위 관절만 x 로 정하고, 아래 관절은 바로 위 관절과 이어지는 쪽으로 붙인다.
      관절마다 x 로 정하면 다리가 겹칠 때 아래 관절의 좌우가 뒤집혀 X 자로 엇갈린다.
    """
    by_name = collections.defaultdict(list)
    for a in ann:
        by_name[a["label"]].append((float(a["x"]), float(a["y"])))
    out = {}
    if view in ("Back", "Front"):
        by_base = {NAME_71878[k]: v for k, v in by_name.items() if NAME_71878.get(k)}
        for chain in LIMB_CHAINS:
            prev = None   # (left, right) 바로 위 관절
            for base in chain:
                pts = by_base.get(base)
                if not pts:
                    continue
                if len(pts) != 2:
                    continue          # 아래에서 drop_front_back_unpaired 로 센다
                lo, hi = sorted(pts)
                left, right = (lo, hi) if view == "Back" else (hi, lo)
                if prev is not None:
                    keep = _dist(left, prev[0], aspect) + _dist(right, prev[1], aspect)
                    swap = _dist(right, prev[0], aspect) + _dist(left, prev[1], aspect)
                    if swap < keep:
                        left, right = right, left
                        stats["diag_chain_overrode_x"] += 1
                out[SLOT[f"left_{base}"]] = left
                out[SLOT[f"right_{base}"]] = right
                prev = (left, right)
    for label, pts in by_name.items():
        if label not in NAME_71878:
            stats["drop_unknown_label"] += len(pts)
            continue
        if label in MIDLINE_71878:
            if len(pts) == 1:
                out[SLOT[MIDLINE_71878[label]]] = pts[0]
            else:
                stats["drop_midline_duplicate"] += len(pts)
            continue
        base = NAME_71878[label]
        if view in side_view_map:
            if len(pts) == 1:
                out[SLOT[f"{side_view_map[view]}_{base}"]] = pts[0]
            else:
                stats["drop_side_view_duplicate"] += len(pts)
        elif view in ("Back", "Front"):
            if len(pts) == 2:
                if SLOT[f"left_{base}"] not in out:      # 사슬 밖(귀)은 x 로만 정한다
                    lo, hi = sorted(pts)
                    left, right = (lo, hi) if view == "Back" else (hi, lo)
                    out[SLOT[f"left_{base}"]] = left
                    out[SLOT[f"right_{base}"]] = right
                # 진단: 라벨 파일 안 순서(먼저 나온 것)가 좌우 정보를 담고 있는지
                stats["diag_pair_total"] += 1
                stats["diag_pair_first_is_left"] += int(pts[0] == out[SLOT[f"left_{base}"]])
            else:
                stats["drop_front_back_unpaired"] += len(pts)
        else:
            stats["drop_unknown_view"] += len(pts)
    return out


def convert_71878(root, args, report):
    parts = [("Training", "01.원천데이터/TS", "02.라벨링데이터/TL"),
             ("Validation", "01.원천데이터/VS", "02.라벨링데이터/VL")]
    side_view_map = dict(kv.split("=") for kv in args.side_view_map.split(","))
    stats = collections.Counter()
    samples = []          # (group, record)
    seen = set()          # 같은 사진이 Training·Validation 에 함께 있으면 하나만
    size_checked = 0
    for part, img_dir, lab_dir in parts:
        lab_root = os.path.join(root, part, lab_dir)
        if not os.path.isdir(lab_root):
            continue
        for dp, _, files in os.walk(lab_root):
            for f in files:
                if not f.endswith(".json"):
                    continue
                rel = os.path.relpath(os.path.join(dp, f), lab_root)
                cls, session, view = rel.split(os.sep)[:3]
                img_rel = os.path.join(part, img_dir, rel[:-5] + ".jpg")
                key = (cls, session, view, f)
                stats["labels_read"] += 1
                if key in seen:
                    stats["drop_duplicate_image"] += 1
                    continue
                seen.add(key)
                if not os.path.exists(os.path.join(root, img_rel)):
                    stats["drop_missing_image"] += 1
                    continue
                d = json.load(open(os.path.join(dp, f), encoding="utf-8"))
                w, h = (int(v) for v in d["image_info"]["resolution"].upper().split("X"))
                if size_checked < 200:   # 해상도 필드가 실제 사진과 같은지 표본 확인
                    with Image.open(os.path.join(root, img_rel)) as im:
                        if im.size != (w, h):
                            stats["warn_resolution_mismatch"] += 1
                    size_checked += 1
                slots = assign_sides_71878(d.get("annotation_info", []), view, side_view_map, stats, aspect=w / h)
                kps = [0] * (3 * len(KEYPOINTS))
                pts = []
                for s, (nx, ny) in slots.items():
                    x, y = nx * w, ny * h
                    if not (0 <= x < w and 0 <= y < h):
                        stats["drop_out_of_image"] += 1
                        continue
                    kps[3 * s:3 * s + 3] = [round(x, 2), round(y, 2), 2]
                    pts.append((x, y))
                if len(pts) < args.min_points:
                    stats["drop_too_few_points"] += 1
                    continue
                samples.append(((cls, session), {
                    "image": {"file_name": img_rel.replace(os.sep, "/"), "width": w, "height": h,
                              "class": cls, "session": session, "view": view,
                              "severity": d.get("severity"), "source_split": part},
                    "ann": {"keypoints": kps, "num_keypoints": len(pts),
                            "bbox": keypoint_bbox(pts, w, h, args.bbox_margin),
                            "bbox_source": "keypoints+margin"},
                }))
    groups = collections.defaultdict(set)
    for (cls, session), _ in samples:
        groups[cls].add((cls, session))
    assign = split_groups(groups, args.ratios, args.seed)
    docs = {s: coco_doc("AI-Hub 71878 -> creamoff 22kp", os.path.abspath(root)) for s in SPLITS}
    write_split(docs, samples, assign)
    report["aihub71878"] = summarize(stats, docs, assign, extra={"side_view_map": side_view_map})
    return docs


# ---------------------------------------------------------------- 59 WALKRUN

def convert_59(root, args, report):
    """root = 01.데이터 폴더. 1.Training 과 2.Validation 을 합쳐 영상 단위로 다시 나눈다.

    Training 은 영상당 사진이 최대 13장이고, Validation 은 라벨 프레임마다 사진이 다 있다(0.2초 간격).
    """
    parts = [p for p in ("1.Training", "2.Validation") if os.path.isdir(os.path.join(root, p, "원천데이터_09"))]
    stats = collections.Counter()
    samples = []
    for part in parts:
        img_rel = os.path.join(part, "원천데이터_09", "DOG", "WALKRUN")
        lab_root = os.path.join(root, part, "라벨링데이터_09", "DOG", "WALKRUN")
        convert_59_part(root, img_rel, lab_root, part, stats, samples)
    groups = {"all": {g for g, _ in samples}}
    assign = split_groups(groups, args.ratios, args.seed)
    docs = {s: coco_doc("AI-Hub 59 WALKRUN -> creamoff 22kp (approx 8 slots)", os.path.abspath(root)) for s in SPLITS}
    write_split(docs, samples, assign)
    report["aihub59_walkrun"] = summarize(stats, docs, assign, extra={"mapping": MAP_59, "parts": parts})
    return docs


def convert_59_part(root, img_rel, lab_root, part, stats, samples):
    img_root = os.path.join(root, img_rel)
    for video in sorted(os.listdir(img_root)):
        lab_path = os.path.join(lab_root, video + ".json")
        if not os.path.exists(lab_path):
            stats["drop_missing_label"] += 1
            continue
        d = json.load(open(lab_path, encoding="utf-8"))
        meta = d["metadata"]
        ann = {a["frame_number"]: a for a in d["annotations"]}
        frames = sorted(os.listdir(os.path.join(img_root, video)))
        if not frames:
            continue
        with Image.open(os.path.join(img_root, video, frames[0])) as im:
            w, h = im.size
        # 라벨 좌표는 metadata 해상도 기준. 사진 크기가 다르면 비율로 맞춘다.
        sx, sy = w / meta["width"], h / meta["height"]
        if abs(sx - 1) > 1e-3 or abs(sy - 1) > 1e-3:
            stats["rescaled_videos"] += 1
        for f in frames:
            m = re.match(r"frame_(\d+)_timestamp_(\d+)\.jpg$", f)
            if not m:
                stats["drop_bad_filename"] += 1
                continue
            a = ann.get(int(m.group(1)))
            stats["images_read"] += 1
            if a is None:
                stats["drop_no_label_for_frame"] += 1
                continue
            kps = [0] * (3 * len(KEYPOINTS))
            n = 0
            for k, name in MAP_59.items():
                p = a["keypoints"].get(k)
                if not p:
                    continue
                x, y = p["x"] * sx, p["y"] * sy
                if not (0 <= x < w and 0 <= y < h):
                    stats["drop_out_of_image"] += 1
                    continue
                kps[3 * SLOT[name]:3 * SLOT[name] + 3] = [round(x, 2), round(y, 2), 2]
                n += 1
            b = a.get("bounding_box")
            if not b:
                stats["drop_no_bbox"] += 1
                continue
            bbox = [round(b["x"] * sx, 2), round(b["y"] * sy, 2), round(b["width"] * sx, 2), round(b["height"] * sy, 2)]
            samples.append(((video,), {
                "image": {"file_name": f"{img_rel}/{video}/{f}".replace(os.sep, "/"), "width": w, "height": h,
                          "video": video, "frame_number": int(m.group(1)), "timestamp_ms": int(m.group(2)),
                          "source_split": part},
                "ann": {"keypoints": kps, "num_keypoints": n, "bbox": bbox, "bbox_source": "label",
                        "keypoints_approx": True},
            }))


# ---------------------------------------------------------------- 공통

def write_split(docs, samples, assign):
    for group, rec in samples:
        doc = docs[assign[group]]
        img_id = len(doc["images"]) + 1
        doc["images"].append({"id": img_id, **rec["image"]})
        ann = {"id": img_id, "image_id": img_id, "category_id": 1, "iscrowd": 0, **rec["ann"]}
        ann["area"] = round(ann["bbox"][2] * ann["bbox"][3], 2)
        doc["annotations"].append(ann)


def summarize(stats, docs, assign, extra):
    split_groups_n = collections.Counter(assign.values())
    per_split = {}
    for s, doc in docs.items():
        slot_counts = [0] * len(KEYPOINTS)
        for a in doc["annotations"]:
            for i in range(len(KEYPOINTS)):
                slot_counts[i] += int(a["keypoints"][3 * i + 2] > 0)
        per_split[s] = {
            "images": len(doc["images"]),
            "groups": split_groups_n.get(s, 0),
            "by_class": dict(collections.Counter(i.get("class", "-") for i in doc["images"])),
            "by_view": dict(collections.Counter(i.get("view", "-") for i in doc["images"])),
            "keypoints_per_slot": dict(zip(KEYPOINTS, slot_counts)),
        }
    return {"counts": dict(stats), "splits": per_split, **extra}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aihub71878", help="71878 루트 (Training/, Validation/ 가 있는 폴더)")
    ap.add_argument("--aihub59", help="59 의 01.데이터 폴더 (1.Training/, 2.Validation/ 이 있는 폴더)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--side-view-map", default="Left=left,Right=right",
                    help="옆 촬영 폴더 → 개의 어느 쪽 다리인지. 검증 전 가정값")
    ap.add_argument("--ratios", type=float, nargs=3, default=(0.8, 0.1, 0.1))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-points", type=int, default=4, help="이보다 점이 적은 사진은 버린다")
    ap.add_argument("--bbox-margin", type=float, default=0.15, help="관절점 상자에 붙일 여백(변 길이 비율)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    report = {"args": vars(args)}
    if args.aihub71878:
        for s, doc in convert_71878(args.aihub71878, args, report).items():
            json.dump(doc, open(os.path.join(args.out, f"aihub71878_{s}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    if args.aihub59:
        for s, doc in convert_59(args.aihub59, args, report).items():
            json.dump(doc, open(os.path.join(args.out, f"aihub59_walkrun_{s}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(report, open(os.path.join(args.out, "report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
