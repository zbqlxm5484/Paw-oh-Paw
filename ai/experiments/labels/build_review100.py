r"""시험 라벨 100장 검수 태스크 준비 (10-26, 허정원 검수용).

    python build_review100.py

- 5묶음 라벨(팀원이 찍은 점)을 시작점으로 CVAT XML 을 만든다. 오토라벨이 아니라 팀원 점에서 시작한다.
- 장마다 확인할 곳을 골라 우선순위 순으로 줄 세운다(확인할 게 많은 장이 앞). 이미지 이름 앞에 r001_ 순번.
- 결과: $CVAT_LABELING_DIR\frames_review\review100\*.jpg, $CVAT_LABELING_DIR\dump\review100_annotations.xml,
        이 폴더 review100_checklist.json · review100_checklist.md (가이드 표)
"""

import json
import os
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")
_CVAT = os.environ.get("CVAT_LABELING_DIR", "C:/cvat-labeling")
_OUT = os.environ.get("CREAMOFF_OUT", "C:/Users/SSAFY/Downloads")

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, rf"{_PJT}\S15P31A404\ai\data_prep")
from cvat_to_coco import NAMES, read_backup, read_xml  # noqa: E402

D = Path(rf"{_OUT}")
ZIPS = [
    (D / "labeling-1-hjw.zip", None, "허정원"),
    (D / "김지윤 라벨링.zip", None, "김지윤"),
    (D / "장준환_라벨링.zip", "pilot100-3", "장준환"),
    (D / "조영운 라벨링 (1).zip", None, "조영운"),
    (D / "조유진_라벨링_1차.zip", "pilot100-5", "조유진"),
]
OV = json.load(open(Path(__file__).parent / "pilot100-4_grade_override.json", encoding="utf-8"))
OUT_IMG = Path(rf"{_CVAT}\frames_review\review100")
OUT_XML = Path(rf"{_CVAT}\dump\review100_annotations.xml")
BIG = float(
    os.environ.get("BIG", 0.20)
)  # 오토라벨에서 몸 길이 20% 넘게 옮긴 점 = 확인 대상 (실험 18번: 크게 틀린 점이 오차의 43%)
HOLD = {"left_dorsal_scapular_spine", "right_dorsal_scapular_spine"}  # 멘토 답 전까지 검수 안 함
KO = {
    "left_ear": "왼귀",
    "right_ear": "오른귀",
    "t13_spinous_process": "T13",
    "iliac_crest": "장골능",
}
for side, s in (("left", "왼"), ("right", "오른")):
    KO |= {
        f"{side}_dorsal_scapular_spine": f"{s}어깨뼈위끝",
        f"{side}_acromion_greater_tubercle": f"{s}어깨",
        f"{side}_lateral_humeral_epicondyle": f"{s}팔꿈치",
        f"{side}_ulnar_styloid_process": f"{s}앞발목",
        f"{side}_fifth_metacarpal_distal": f"{s}앞발끝",
        f"{side}_femoral_greater_trochanter": f"{s}고관절",
        f"{side}_femorotibial_joint": f"{s}무릎",
        f"{side}_lateral_malleolus": f"{s}뒷발목",
        f"{side}_fifth_metatarsal_distal": f"{s}뒷발끝",
    }
FRONT = [
    [
        f"{s}_{p}"
        for p in ("lateral_humeral_epicondyle", "ulnar_styloid_process", "fifth_metacarpal_distal")
    ]
    for s in ("left", "right")
]
HIND = [
    [f"{s}_{p}" for p in ("femorotibial_joint", "lateral_malleolus", "fifth_metatarsal_distal")]
    for s in ("left", "right")
]

auto = {}
for l in open(rf"{_CVAT}\dump\kp_dump.jsonl", encoding="utf-8"):
    j = json.loads(l)
    if j.get("keypoints"):
        auto[j["frame_name"]] = np.array(j["keypoints"], float)[:22, :2]

items = []
for path, task, who in ZIPS:
    z = zipfile.ZipFile(path)
    t, frames, files = read_xml(z) if "annotations.xml" in z.namelist() else read_backup(z)
    task = task or t
    for f in frames:
        grade = f["grade"]
        if task == OV["task"]:
            grade = OV["grade_by_frame"].get(str(f["frame"]), grade)
        A = auto[f["name"]]
        idx = {n: i for i, n in enumerate(NAMES)}
        L = np.linalg.norm((A[4] + A[9]) / 2 - (A[14] + A[18]) / 2)
        left = (A[0, 0] + A[1, 0]) / 2 < A[13, 0]
        cam = "left" if left else "right"
        checks, score = [], 0
        if task == OV["task"]:
            checks.append("Q(가려짐)·grade 를 라벨러가 안 봄 → 카메라 쪽 Q 와 grade 전체 확인")
            score += 3
        if grade == "unusable":
            checks.append("unusable 판정이 맞는지")
            score += 2
        big = []
        for n, (x, y, occ, out) in f["pts"].items():
            if (
                out
                or n in HOLD
                or not (n.startswith(cam) or n in ("t13_spinous_process", "iliac_crest"))
            ):
                continue
            if np.linalg.norm(np.array([x, y]) - A[idx[n]]) / L > BIG:
                big.append(KO[n])
        if big:
            checks.append("크게 옮긴 점이 맞는 자리인지: " + ", ".join(big))
            score += len(big)
        for nm, (lt, rt) in (("앞다리", FRONT), ("뒷다리", HIND)):
            p = lambda ns: np.mean([f["pts"][n][:2] for n in ns], 0)
            a = lambda ns: np.mean([A[idx[n]] for n in ns], 0)
            same = np.linalg.norm(p(lt) - a(lt)) + np.linalg.norm(p(rt) - a(rt))
            swap = np.linalg.norm(p(lt) - a(rt)) + np.linalg.norm(p(rt) - a(lt))
            if swap < same * 0.5 and same / L > 0.15:
                checks.append(f"{nm} 왼·오른을 바꿨음 → 개 기준 좌우가 맞는지")
                score += 2
        items.append(
            dict(
                name=f["name"],
                task=task,
                labeler=who,
                grade=grade,
                reason=f["reason"] or "",
                camera_side="왼" if left else "오른",
                checks=checks,
                score=score,
                f=f,
                img=z.read(files[f["name"]]),
            )
        )

if os.environ.get("DRY"):
    print(
        BIG,
        sum(bool(r["checks"]) for r in items),
        sum(c.count(",") + 1 for r in items for c in r["checks"] if c.startswith("크게")),
    )
    sys.exit()
items.sort(key=lambda r: (-r["score"], r["task"], r["name"]))
OUT_IMG.mkdir(parents=True, exist_ok=True)
xml = ['<?xml version="1.0" encoding="utf-8"?>', "<annotations>", "  <version>1.1</version>"]
for k, r in enumerate(items):
    r["no"] = k + 1
    r["file"] = f"r{k + 1:03d}_{r['name']}"
    (OUT_IMG / r["file"]).write_bytes(r["img"])
    f = r["f"]
    xml.append(
        f'  <image id="{k}" name="{escape(r["file"])}" width="{f["width"]}" height="{f["height"]}">'
    )
    xml.append('    <skeleton label="dog" source="manual" z_order="0">')
    for n in NAMES:
        x, y, occ, out = f["pts"][n]
        xml.append(
            f'      <points label="{n}" source="manual" outside="{int(out)}" occluded="{int(occ)}" points="{x:.2f},{y:.2f}"></points>'
        )
    xml.append(f'      <attribute name="grade">{escape(r["grade"])}</attribute>')
    xml.append(f'      <attribute name="reason">{escape(r["reason"] or "-")}</attribute>')
    xml += ["    </skeleton>", "  </image>"]
xml.append("</annotations>")
OUT_XML.write_text("\n".join(xml), encoding="utf-8")

keep = [{k: v for k, v in r.items() if k not in ("f", "img")} for r in items]
json.dump(
    keep,
    open(Path(__file__).parent / "review100_checklist.json", "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=1,
)
md = ["| 장 | 라벨러 | 카메라 쪽 | grade | 확인할 것 |", "|---:|---|---|---|---|"]
for r in keep:
    md.append(
        f"| {r['no']} | {r['labeler']} | {r['camera_side']} | {r['grade']} | {' / '.join(r['checks']) or '훑어보기만'} |"
    )
(Path(__file__).parent / "review100_checklist.md").write_text("\n".join(md), encoding="utf-8")
n_chk = sum(bool(r["checks"]) for r in keep)
print(
    f"{len(keep)}장, 확인할 곳 있는 장 {n_chk}, 크게 옮긴 점 {sum(len(c.split(': ')[1].split(', ')) for r in keep for c in r['checks'] if c.startswith('크게'))}개,"
    f" 좌우 바꿈 {sum('바꿨음' in c for r in keep for c in r['checks'])}, unusable {sum(r['grade'] == 'unusable' for r in keep)}"
)
