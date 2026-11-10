import copy
import json
from pathlib import Path

import numpy as np

D = Path("/exp/cv/data")
OUT = Path("/exp/results/orc_1102")
N = 22
T13, ILIAC = 2, 13
TAU = 0.10
KINDS = {0: "오토라벨 그대로", 1: "틀린 점 표시만(학습에서 제외)", 2: "틀린 점을 TTA 재예측으로 교체", 3: "틀린 점을 정답으로 교체(사람이 고침, 상한)", 4: "모든 점을 TTA 예측으로(TTA 선생)"}


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def pts(kp):
    return np.array(kp, float).reshape(-1, 3)[:N, :2]


gt_all = load(D / "gt_fall.json")
names = gt_all["categories"][0]["keypoints"][:N]
gt = {a["id"]: np.array(a["keypoints"], float).reshape(-1, 3)[:N] for a in gt_all["annotations"]}
single = {p["ann_id"]: pts(p["keypoints"]) for p in load(D / "fs-v4.preds.json")["predictions"]}
tta = {p["ann_id"]: pts(p["keypoints"]) for p in load(D / "fs-v4.tta.preds.json")["predictions"]}
body = {}
for i, g in gt.items():
    if g[T13, 2] > 0 and g[ILIAC, 2] > 0:
        L = float(np.linalg.norm(g[T13, :2] - g[ILIAC, :2]))
        if L > 0:
            body[i] = L

OUT.mkdir(parents=True, exist_ok=True)
stat = {"tau": TAU, "n": 0, "flag": 0, "fixed": 0, "broken": 0, "unflag": 0, "err_s": [], "err_t": [], "per_joint": [[0, 0] for _ in range(N)], "pck_s": 0, "pck_t": 0}
label_q = {k: [0, 0] for k in KINDS}


def update_stats(aid, g, k):
    L = body.get(aid)
    if L is None:
        return
    for i in range(N):
        if k[3 * i + 2] != 2:
            continue
        ds = float(np.linalg.norm(single[aid][i] - g[i, :2])) / L
        dt = float(np.linalg.norm(tta[aid][i] - g[i, :2])) / L
        stat["n"] += 1
        stat["pck_s"] += ds <= TAU
        stat["pck_t"] += dt <= TAU
        stat["per_joint"][i][1] += 1
        if ds > TAU:
            stat["flag"] += 1
            stat["per_joint"][i][0] += 1
            stat["fixed"] += dt <= TAU
            stat["err_s"].append(ds)
            stat["err_t"].append(dt)
        else:
            stat["unflag"] += 1
            stat["broken"] += dt > TAU


def variant(slf, gtr, kind, first):
    out = copy.deepcopy(slf)
    for a in out["annotations"]:
        aid = a["id"]
        k = a["keypoints"]
        g = gt[aid]
        if first and kind == 0:
            update_stats(aid, g, k)
        L = body.get(aid)
        for i in range(N):
            if k[3 * i + 2] != 2:
                continue
            flag = L is not None and float(np.linalg.norm(single[aid][i] - g[i, :2])) / L > TAU
            if kind == 1 and flag:
                k[3 * i], k[3 * i + 1], k[3 * i + 2] = 0, 0, 0
            elif kind == 2 and flag:
                k[3 * i], k[3 * i + 1] = float(tta[aid][i][0]), float(tta[aid][i][1])
            elif kind == 3 and flag:
                k[3 * i], k[3 * i + 1] = float(g[i, 0]), float(g[i, 1])
            elif kind == 4:
                k[3 * i], k[3 * i + 1] = float(tta[aid][i][0]), float(tta[aid][i][1])
            if k[3 * i + 2] == 2 and L is not None:
                label_q[kind][1] += 1
                label_q[kind][0] += float(np.linalg.norm(np.array(k[3 * i:3 * i + 2]) - g[i, :2])) / L <= TAU
        a["num_keypoints"] = sum(1 for i in range(46) if k[3 * i + 2] > 0)
    return out


for f in (0, 1):
    slf = load(D / f"tr_f{f}_self_occ0_boxeval_untkeep.json")
    gtr = load(D / f"tr_f{f}_gt_occ0_boxeval_untkeep.json")
    for kind in KINDS:
        v = variant(slf, gtr, kind, True)
        (D / f"tr_f{f}_orc_v{kind}.json").write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
        print(f"tr_f{f}_orc_v{kind}.json", len(v["images"]), "images", sum(a["num_keypoints"] for a in v["annotations"]), "points")

res = {
    "기준(몸통 길이 대비)": TAU,
    "보이는 점": stat["n"],
    "틀린 점(오토라벨이 정답에서 10% 넘게 벗어남)": stat["flag"],
    "틀린 점 비율": round(stat["flag"] / stat["n"], 4),
    "틀린 점 중 TTA 재예측이 맞게 고친 비율": round(stat["fixed"] / max(1, stat["flag"]), 4),
    "맞던 점 중 TTA 재예측이 오히려 틀어진 비율": round(stat["broken"] / max(1, stat["unflag"]), 4),
    "틀린 점 평균 오차 단일 예측": round(float(np.mean(stat["err_s"])), 4),
    "틀린 점 평균 오차 TTA 재예측": round(float(np.mean(stat["err_t"])), 4),
    "전체 PCK@0.10 단일 예측": round(stat["pck_s"] / stat["n"], 4),
    "전체 PCK@0.10 TTA 평균": round(stat["pck_t"] / stat["n"], 4),
    "라벨 품질(학습 라벨 중 정답 10% 안에 든 비율)": {KINDS[k]: round(v[0] / max(1, v[1]), 4) for k, v in label_q.items()},
    "관절별 틀린 점 비율 상위": sorted([(names[i], round(c[0] / max(1, c[1]), 3), c[1]) for i, c in enumerate(stat["per_joint"])], key=lambda x: -x[1])[:8],
}
(OUT / "stats.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False, indent=1))
