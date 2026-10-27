import json
import sys

SELF = "tr_f{f}_self_occ0_boxgt_untkeep.json"
GT = "tr_f{f}_gt_occ0_boxgt_untkeep.json"
PARK = {"train": "head", "lr": 5e-5, "epochs": 100, "batch": 32, "rot": 15, "scale": [0.8, 1.2]}

jobs = [
    ("B0", "기준", "fs-v4 그대로", None),
    ("C0", "원인", "오토라벨 전체 학습 (E-083 재현)", {"data": SELF}),
    ("C0h", "원인", "오토라벨 머리만 학습", {"data": SELF, "train": "head"}),
    ("C1", "원인", "C0 + 학습 상자를 채점과 같게(+15%, 1.25배)", {"data": "tr_f{f}_self_occ0_boxeval_untkeep.json", "padding": 1.25}),
    ("C2", "원인", "C0 + 가려진 점 포함", {"data": "tr_f{f}_self_occ1_boxgt_untkeep.json"}),
    ("C3a", "원인", "C0 + 회전 30에서 10으로", {"data": SELF, "rot": 10}),
    ("C3b", "원인", "C0 + 회전 끔", {"data": SELF, "rot": 0}),
    ("C4", "원인", "C0 + lr 1e-5, wd 0.01", {"data": SELF, "lr": 1e-5, "wd": 0.01}),
    ("C4b", "원인", "C0 + 좌우 반전 증강 끔", {"data": SELF, "flip-aug": 0}),
    ("Call", "원인", "C1 + C2 + 회전 10", {"data": "tr_f{f}_self_occ1_boxeval_untkeep.json", "padding": 1.25, "rot": 10}),
    ("G0", "기업라벨", "기업 정답 전체 학습", {"data": GT}),
    ("G1", "기업라벨", "기업 정답 머리만 (박규원 설정, E-095~098 재현)", {"data": GT, **PARK}),
    ("G2", "기업라벨", "G1 + 가려진 점 포함", {**PARK, "data": "tr_f{f}_gt_occ1_boxgt_untkeep.json"}),
    ("G3", "기업라벨", "G1 + 학습 상자를 채점과 같게", {**PARK, "data": "tr_f{f}_gt_occ0_boxeval_untkeep.json", "padding": 1.25}),
    ("G4", "기업라벨", "G1 + 안 옮긴 점 빼기", {**PARK, "data": "tr_f{f}_gt_occ0_boxgt_untdrop.json"}),
    ("G5", "기업라벨", "G1 + 마지막 단계(stage4)도 학습", {**PARK, "data": GT, "train": "stage4"}),
    ("G6", "기업라벨", "기업 정답 전체 학습 + 원인 후보 모두", {"data": "tr_f{f}_gt_occ1_boxeval_untkeep.json", "padding": 1.25, "rot": 10}),
    ("G7", "기업라벨", "G2 + G3 (가려진 점, 채점 상자)", {**PARK, "data": "tr_f{f}_gt_occ1_boxeval_untkeep.json", "padding": 1.25}),
]

out = []
for jid, group, desc, train in jobs:
    for f in (0, 1):
        j = {"id": f"{jid}_f{f}", "group": group, "desc": desc, "fold": f}
        if train:
            j["train"] = train
        if jid in ("G0", "G6"):
            j["keep_weights"] = 1
        out.append(j)
for src in ("G0", "G6"):
    for alpha in (0.3, 0.5):
        for f in (0, 1):
            out.append({"id": f"W_{src}_{alpha}_f{f}", "group": "가중치섞기", "desc": f"fs-v4와 {src}를 {alpha} 비율로 섞기", "fold": f,
                        "wise": {"from": f"{src}_f{f}", "alpha": alpha}})

open(sys.argv[1], "w", encoding="utf-8").write("\n".join(json.dumps(j, ensure_ascii=False) for j in out) + "\n")
print(len(out), "jobs")
