import json
import sys

PARK = {"train": "head", "lr": 5e-5, "epochs": 100, "batch": 32, "rot": 15, "scale": [0.8, 1.2]}
G3 = {**PARK, "data": "tr_f{f}_gt_occ0_boxeval_untkeep.json", "padding": 1.25}
G8 = {"data": "tr_f{f}_gt_occ0_boxeval_untkeep.json", "padding": 1.25}
G6 = {"data": "tr_f{f}_gt_occ1_boxeval_untkeep.json", "padding": 1.25, "rot": 10}

out = []
for jid, desc, train, keep in [
    ("WW_B0", "fs-v4 그대로", None, 0),
    ("WW_G3", "제니 205장 전부로 G3(머리만 + 채점 상자)", G3, 1),
    ("WW_G8", "제니 205장 전부로 전체 학습 + 채점 상자", G8, 1),
    ("WW_G6", "제니 205장 전부로 G6(전체 + 상자, 가려진 점, 회전 10)", G6, 1),
    ("WW_G1", "제니 205장 전부로 G1(머리만, 옛 상자)", {**PARK, "data": "tr_f{f}_gt_occ0_boxgt_untkeep.json"}, 0),
    ("WW_Call", "제니 205장 오토라벨로 Call(학습 자체가 해치지 않는지)", {"data": "tr_f{f}_self_occ1_boxeval_untkeep.json", "padding": 1.25, "rot": 10}, 0),
]:
    j = {"id": jid, "group": "와우와우", "desc": desc, "fold": "all", "tests": ["pilot", "ww"], "keep_weights": keep}
    if train:
        j["train"] = train
    out.append(j)
WWIMG = "/ssafy/dataset/keypoints_wowwow"
for jid, desc, train in [
    ("WWT_old", "와우와우 806장 전체 학습, 옛 상자(E-022, E-023 재현)", {"data": "tr_fww_gt_occ0_boxgt_untkeep.json", "images": WWIMG}),
    ("WWT_box", "와우와우 806장 전체 학습 + 채점 상자", {"data": "tr_fww_gt_occ0_boxeval_untkeep.json", "images": WWIMG, "padding": 1.25}),
    ("WWT_head", "와우와우 806장 머리만 학습 + 채점 상자", {**G3, "data": "tr_fww_gt_occ0_boxeval_untkeep.json", "images": WWIMG}),
]:
    out.append({"id": jid, "group": "와우와우학습", "desc": desc, "fold": "ww", "tests": ["fall", "pilot"], "train": train})
for f in (0, 1):
    out.append({"id": f"G8_f{f}", "group": "기업라벨", "desc": "기업 정답 전체 학습 + 채점 상자", "fold": f, "train": G8})
for seed in (1, 2):
    for jid, t in (("G3", G3), ("G8", G8)):
        for f in (0, 1):
            out.append({"id": f"{jid}s{seed}_f{f}", "group": "시드", "desc": f"{jid} 시드 {seed}", "fold": f, "train": {**t, "seed": seed}})

open(sys.argv[1], "w", encoding="utf-8").write("\n".join(json.dumps(j, ensure_ascii=False) for j in out) + "\n")
print(len(out), "jobs")
