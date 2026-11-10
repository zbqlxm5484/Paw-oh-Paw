import copy
import json
import sys
from pathlib import Path

D = Path("/exp/cv/data")
SRC = "tr_fpilot_gt_occ0_boxeval_untkeep.json"
SHOULDER = [3, 4, 8, 9]
MASK = {"cyw": SHOULDER + [14, 18], "cyj": SHOULDER + [7, 12, 17, 21]}
PARK = {"train": "head", "lr": 5e-5, "epochs": 100, "batch": 32, "rot": 15, "scale": [0.8, 1.2], "img-dir": "/ssafy/pilot100_1027", "padding": 1.25}

base = json.loads((D / SRC).read_text(encoding="utf-8"))
lab = {im["id"]: im["labeler"] for im in base["images"]}

mask = copy.deepcopy(base)
cut = 0
for a in mask["annotations"]:
    for i in MASK.get(lab[a["image_id"]], []):
        if a["keypoints"][3 * i + 2] > 0:
            cut += 1
        a["keypoints"][3 * i:3 * i + 3] = [0, 0, 0]
    a["num_keypoints"] = sum(1 for i in range(len(a["keypoints"]) // 3) if a["keypoints"][3 * i + 2] > 0)
(D / "tr_fpilot_212_mask.json").write_text(json.dumps(mask, ensure_ascii=False), encoding="utf-8")

drop = copy.deepcopy(base)
keep = {i for i, l in lab.items() if l not in MASK}
drop["images"] = [im for im in drop["images"] if im["id"] in keep]
drop["annotations"] = [a for a in drop["annotations"] if a["image_id"] in keep]
(D / "tr_fpilot_212_drop.json").write_text(json.dumps(drop, ensure_ascii=False), encoding="utf-8")
print("mask: 뺀 점", cut, "/ drop: 남은 사진", len(drop["images"]), "/ 전체", len(base["images"]))

V = [("all", SRC, "팀 라벨 93장 그대로"), ("mask", "tr_fpilot_212_mask.json", "조영운, 조유진 라벨의 갈리는 관절만 뺌"), ("drop", "tr_fpilot_212_drop.json", "조영운, 조유진 사진을 통째로 뺌")]
jobs = []
for seed in (42, 7):
    for k, data, desc in V:
        jobs.append({"id": f"P212_{k}_s{seed}", "group": "미세조정3차", "desc": f"-212 {desc}, 머리만 G3 설정, 시드 {seed} → 제니, 와우와우 채점",
                     "fold": "pilot", "tests": ["fall", "ww"], "train": {**PARK, "data": data, "seed": seed}})
Path(sys.argv[1]).write_text("\n".join(json.dumps(j, ensure_ascii=False) for j in jobs) + "\n", encoding="utf-8")
print(len(jobs), "jobs")
