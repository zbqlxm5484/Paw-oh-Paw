import json
import sys

PARK = {"train": "head", "lr": 5e-5, "epochs": 100, "batch": 32, "rot": 15, "scale": [0.8, 1.2]}
PIMG = {"img-dir": "/ssafy/pilot100_1027"}
BOX = "tr_fpilot_gt_occ0_boxeval_untkeep.json"
OLD = "tr_fpilot_gt_occ0_boxgt_untkeep.json"

jobs = [
    ("X_pilot_head_box", "팀 라벨 93장으로 머리만 + 채점 상자 → 제니 채점", {**PARK, **PIMG, "data": BOX, "padding": 1.25}, 0),
    ("X_pilot_head_old", "팀 라벨 93장으로 머리만, 옛 상자 (E-089 재현) → 제니 채점", {**PARK, **PIMG, "data": OLD}, 0),
    ("X_pilot_full_box", "팀 라벨 93장으로 전체 + 채점 상자 → 제니 채점", {**PIMG, "data": BOX, "padding": 1.25}, 1),
    ("X_pilot_full_box_lr", "팀 라벨 93장으로 전체 + 채점 상자, lr 3e-5 → 제니 채점", {**PIMG, "data": BOX, "padding": 1.25, "lr": 3e-5}, 0),
]
out = []
for jid, desc, t, keep in jobs:
    out.append({"id": jid, "group": "다른개로학습", "desc": desc, "fold": "pilot", "tests": ["fall", "ww"], "train": t, "keep_weights": keep})
for a in (0.3, 0.5):
    out.append({"id": f"X_pilot_wise_{a}", "group": "다른개로학습", "desc": f"fs-v4와 X_pilot_full_box를 {a} 비율로 섞기 → 제니 채점", "fold": "pilot",
                "tests": ["fall", "ww"], "wise": {"from": "X_pilot_full_box", "alpha": a}})

open(sys.argv[1], "w", encoding="utf-8").write("\n".join(json.dumps(j, ensure_ascii=False) for j in out) + "\n")
print(len(out), "jobs")
