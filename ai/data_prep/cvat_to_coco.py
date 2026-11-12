"""CVAT 시험 라벨(백업 zip 또는 'CVAT for images' XML zip) -> COCO 22점 학습 형식. 10-26, S15P31A404-93.

    python cvat_to_coco.py --zip a.zip=pilot100-2 b.zip=pilot100-3 ... --split-csv pilot100.csv --out-dir <폴더>
        [--override pilot100-4_grade_override.json] [--ref-names 정답.json]

- 백업 zip: annotations.json + data/manifest.jsonl (프레임 번호 -> 이미지 이름). XML zip: annotations.xml + images/.
  XML 에는 태스크 이름이 없어서 `zip=태스크` 로 붙여 준다.
- 관절점 가시성: O(화면 밖) -> 0 (좌표도 0), Q(가려짐) -> 1, 나머지 -> 2.
- grade `unusable` 은 뺀다. `ambiguous` 는 attributes.grade 로 남긴다. `unreviewed` 가 남아 있으면 실패로 본다
  (--override 로 grade 를 정한 태스크 제외).
- --override(태스크 하나): grade_by_frame 으로 grade 를 덮어쓰고, "점 위치만 사용" 정책이면 Q 는 무시하고
  반대쪽 다리 점은 가시성 0 으로 둔다. 카메라 쪽 = 머리(귀 가운데)가 장골능보다 화면 왼쪽이면 개의 왼쪽 다리
  (check_sides.py 와 같은 규칙).
- 분할: --split-csv(라벨 프레임 고르기 결과, 개 단위 분할 split_by_dog 를 따름)의 split 을 쓴다.
- 결과: <out-dir>/images/*.jpg, all.json, train.json, val.json, report.json. 자료는 레포에 올리지 않는다.
"""

import argparse
import csv
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

NAMES = [
    "left_ear",
    "right_ear",
    "t13_spinous_process",
    "left_dorsal_scapular_spine",
    "left_acromion_greater_tubercle",
    "left_lateral_humeral_epicondyle",
    "left_ulnar_styloid_process",
    "left_fifth_metacarpal_distal",
    "right_dorsal_scapular_spine",
    "right_acromion_greater_tubercle",
    "right_lateral_humeral_epicondyle",
    "right_ulnar_styloid_process",
    "right_fifth_metacarpal_distal",
    "iliac_crest",
    "left_femoral_greater_trochanter",
    "left_femorotibial_joint",
    "left_lateral_malleolus",
    "left_fifth_metatarsal_distal",
    "right_femoral_greater_trochanter",
    "right_femorotibial_joint",
    "right_lateral_malleolus",
    "right_fifth_metatarsal_distal",
]
LEFT_LEG = [i for i, n in enumerate(NAMES) if n.startswith("left_") and n != "left_ear"]
RIGHT_LEG = [i for i, n in enumerate(NAMES) if n.startswith("right_") and n != "right_ear"]
MARGIN = 0.15

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _frame(name, size, grade, reason, pts):
    """pts: {관절 이름: (x, y, occluded, outside)}"""
    return {
        "name": name,
        "width": size[0],
        "height": size[1],
        "grade": grade,
        "reason": reason,
        "pts": pts,
    }


def read_backup(z):
    man = [
        json.loads(l)
        for l in z.read("data/manifest.jsonl").decode("utf-8").splitlines()
        if l.strip()
    ]
    man = [m for m in man if "name" in m]
    task = json.loads(z.read("task.json"))
    out = []
    for job in json.loads(z.read("annotations.json")):
        for s in job["shapes"]:
            if s["type"] != "skeleton" or s["label"] != "dog":
                continue
            m = man[s["frame"]]
            at = {a["name"]: a["value"] for a in s["attributes"]}
            pts = {
                e["label"]: (e["points"][0], e["points"][1], e["occluded"], e["outside"])
                for e in s["elements"]
            }
            out.append(
                _frame(
                    m["name"] + m["extension"],
                    (m["width"], m["height"]),
                    at.get("grade"),
                    at.get("reason"),
                    pts,
                )
            )
            out[-1]["frame"] = s["frame"]
    return (
        task["name"],
        out,
        {m["name"] + m["extension"]: "data/" + m["name"] + m["extension"] for m in man},
    )


def read_xml(z):
    root = ET.fromstring(z.read("annotations.xml"))
    out = []
    for im in root.iter("image"):
        for sk in im.iter("skeleton"):
            if sk.get("label") != "dog":
                continue
            at = {a.get("name"): (a.text or "") for a in sk.findall("attribute")}
            pts = {}
            for p in sk.findall("points"):
                x, y = map(float, p.get("points").split(";")[0].split(","))
                pts[p.get("label")] = (x, y, p.get("occluded") == "1", p.get("outside") == "1")
            out.append(
                _frame(
                    im.get("name"),
                    (int(im.get("width")), int(im.get("height"))),
                    at.get("grade"),
                    at.get("reason"),
                    pts,
                )
            )
            out[-1]["frame"] = int(im.get("id"))
    return None, out, {n.split("/", 1)[1]: n for n in z.namelist() if n.startswith("images/")}


def camera_side_left(pts):
    ear = [pts[n][0] for n in ("left_ear", "right_ear") if n in pts and not pts[n][3]]
    if not ear or "iliac_crest" not in pts or pts["iliac_crest"][3]:
        return None
    return sum(ear) / len(ear) < pts["iliac_crest"][0]


def to_ann(f, points_only=False):
    """-> (keypoints 66개, 문제 목록)"""
    kp, bad = [], []
    left = camera_side_left(f["pts"]) if points_only else None
    if points_only and left is None:
        bad.append("카메라 쪽 판정 불가")
    far = set(RIGHT_LEG if left else LEFT_LEG) if points_only and left is not None else set()
    for i, n in enumerate(NAMES):
        if n not in f["pts"]:
            bad.append(f"{n} 없음")
            kp += [0, 0, 0]
            continue
        x, y, occ, out = f["pts"][n]
        if out or i in far:
            kp += [0, 0, 0]
            continue
        if not (0 <= x < f["width"] and 0 <= y < f["height"]):
            bad.append(f"{n} 화면 밖 좌표 ({x:.0f},{y:.0f})")
        kp += [round(x, 2), round(y, 2), 2 if points_only or not occ else 1]
    return kp, bad


def bbox(kp, w, h):
    xs = [kp[3 * i] for i in range(22) if kp[3 * i + 2] > 0]
    ys = [kp[3 * i + 1] for i in range(22) if kp[3 * i + 2] > 0]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    mx, my = (x1 - x0) * MARGIN, (y1 - y0) * MARGIN
    x0, y0, x1, y1 = max(0, x0 - mx), max(0, y0 - my), min(w, x1 + mx), min(h, y1 + my)
    return [round(x0, 2), round(y0, 2), round(x1 - x0, 2), round(y1 - y0, 2)]


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--zip",
        nargs="+",
        required=True,
        help="zip 경로[=태스크 이름] (XML zip 은 태스크 이름 필수)",
    )
    ap.add_argument("--split-csv", required=True)
    ap.add_argument("--override", nargs="*", default=[])
    ap.add_argument("--ref-names", help="키포인트 이름·순서를 비교할 정답 COCO (기업 260820)")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()

    if a.ref_names:
        ref = json.loads(Path(a.ref_names).read_text(encoding="utf-8"))["categories"][0][
            "keypoints"
        ]
        if ref != NAMES:
            sys.exit("키포인트 이름·순서가 정답과 다르다")
    ov = {}
    for p in a.override:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        ov[d["task"]] = d
    split, dog = {}, {}
    for r in csv.DictReader(open(a.split_csv, encoding="utf-8-sig")):
        n = f"{r['video']}_f{int(r['frame']):06d}.jpg"
        split[n], dog[n] = r["split"], r["dog"]

    out = Path(a.out_dir)
    (out / "images").mkdir(parents=True, exist_ok=True)
    images, anns, report, problems = [], [], {}, []
    for spec in a.zip:
        path, _, name = spec.partition("=")
        z = zipfile.ZipFile(path)
        task, frames, files = read_xml(z) if "annotations.xml" in z.namelist() else read_backup(z)
        task = name or task
        if not task:
            sys.exit(f"{path}: 태스크 이름이 없다 (zip=태스크 로 준다)")
        o = ov.get(task)
        points_only = bool(o and "점 위치만" in o.get("policy", ""))
        grades = Counter()
        for f in frames:
            g = f["grade"]
            if o and str(f["frame"]) in o.get("grade_by_frame", {}):
                g = o["grade_by_frame"][str(f["frame"])]
            if o and f["frame"] in o.get("unusable_frames", []):
                g = "unusable"
            grades[g] += 1
            if g in (None, "", "unreviewed"):
                problems.append(f"{task} {f['name']}: grade 미검토")
                continue
            if g == "unusable":
                continue
            kp, bad = to_ann(f, points_only)
            problems += [f"{task} {f['name']}: {b}" for b in bad]
            if f["name"] not in split:
                problems.append(f"{task} {f['name']}: 분할 목록에 없음")
                continue
            iid = len(images) + 1
            (out / "images" / f["name"]).write_bytes(z.read(files[f["name"]]))
            images.append(
                {
                    "id": iid,
                    "file_name": "images/" + f["name"],
                    "width": f["width"],
                    "height": f["height"],
                    "task": task,
                    "dog": dog[f["name"]],
                    "split": split[f["name"]],
                }
            )
            box = bbox(kp, f["width"], f["height"])
            anns.append(
                {
                    "id": iid,
                    "image_id": iid,
                    "category_id": 1,
                    "keypoints": kp,
                    "num_keypoints": sum(1 for i in range(22) if kp[3 * i + 2] > 0),
                    "bbox": box,
                    "area": round(box[2] * box[3], 2),
                    "iscrowd": 0,
                    "attributes": {
                        "task": task,
                        "grade": g,
                        "reason": f["reason"],
                        "points_only": points_only,
                    },
                }
            )
        report[task] = {"frames": len(frames), "grades": dict(grades), "points_only": points_only}

    names = [im["file_name"] for im in images]
    dup = [n for n, c in Counter(names).items() if c > 1]
    problems += [f"중복 이미지 {n}" for n in dup]
    dogs = {s: {im["dog"] for im in images if im["split"] == s} for s in ("train", "val")}
    if dogs["train"] & dogs["val"]:
        problems.append(f"train·val 에 같은 개: {sorted(dogs['train'] & dogs['val'])}")
    cat = [{"id": 1, "name": "dog", "keypoints": NAMES, "skeleton": []}]
    doc = lambda ims: {
        "images": ims,
        "annotations": [an for an in anns if an["image_id"] in {i["id"] for i in ims}],
        "categories": cat,
    }
    for nm, ims in (
        ("all", images),
        ("train", [i for i in images if i["split"] == "train"]),
        ("val", [i for i in images if i["split"] == "val"]),
    ):
        (out / f"{nm}.json").write_text(json.dumps(doc(ims), ensure_ascii=False), encoding="utf-8")
    report = {
        "tasks": report,
        "images": len(images),
        "split": {
            s: {"images": sum(i["split"] == s for i in images), "dogs": sorted(dogs[s])}
            for s in dogs
        },
        "problems": problems,
    }
    (out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    for t, r in report["tasks"].items():
        print(
            f"{t}: {r['frames']}장 grade {r['grades']}"
            + (" (점 위치만)" if r["points_only"] else "")
        )
    print(
        f"-> {out}  사진 {len(images)} (train {report['split']['train']['images']} · val {report['split']['val']['images']}), 문제 {len(problems)}"
    )
    for p in problems:
        print("  !", p)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
