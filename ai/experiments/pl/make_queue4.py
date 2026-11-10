import json
import sys

PARK = {"train": "head", "lr": 5e-5, "epochs": 30, "batch": 32, "rot": 15, "scale": [0.8, 1.2], "padding": 1.25}
jobs = []
for name, desc in (("set_vith", "의사 라벨(뒷다리 비터비)"), ("set_raw", "의사 라벨(비터비 없음)")):
    jobs.append({"id": f"PL_{name}_head", "group": "의사라벨", "desc": f"{desc} 1,423장으로 머리만 학습 + 채점 상자 → 제니, 와우와우 채점", "fold": "pl",
                 "tests": ["fall", "ww"], "train": {**PARK, "data": f"tr_fpl_{name}.json", "img-dir": f"/exp/pl/{name}/images"}, "keep_weights": 1})
jobs.append({"id": "PL_set_vith_full", "group": "의사라벨", "desc": "의사 라벨(뒷다리 비터비)로 전체 학습 lr 3e-5 + 채점 상자", "fold": "pl", "tests": ["fall", "ww"],
             "train": {"data": "tr_fpl_set_vith.json", "img-dir": "/exp/pl/set_vith/images", "padding": 1.25, "lr": 3e-5, "epochs": 15}})
open(sys.argv[1], "w", encoding="utf-8").write("\n".join(json.dumps(j, ensure_ascii=False) for j in jobs) + "\n")
print(len(jobs), "jobs")
