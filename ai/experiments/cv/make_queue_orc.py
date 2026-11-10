import json
import sys
from pathlib import Path

G3 = {"train": "head", "lr": 5e-5, "epochs": 100, "batch": 32, "rot": 15, "scale": [0.8, 1.2], "padding": 1.25}
DESC = {0: "오토라벨 그대로", 1: "틀린 점 표시만(제외)", 2: "틀린 점을 TTA 재예측으로 교체", 3: "틀린 점을 정답으로 교체(상한)", 4: "모든 점 TTA 예측(TTA 선생)"}
seeds = [int(s) for s in sys.argv[2:]] or [42]
jobs = []
for seed in seeds:
    for v in DESC:
        for f in (0, 1):
            tag = "" if seed == 42 else f"_s{seed}"
            jobs.append({"id": f"OR_V{v}{tag}_f{f}", "group": "오라클", "desc": f"오라클 V{v} {DESC[v]} (G3 설정, 시드 {seed})", "fold": f,
                         "train": {**G3, "data": "tr_f{f}_orc_v" + str(v) + ".json", "seed": seed}})
Path(sys.argv[1]).write_text("\n".join(json.dumps(j, ensure_ascii=False) for j in jobs) + "\n", encoding="utf-8")
print(len(jobs), "jobs")
