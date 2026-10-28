r"""offset_fold.py 누수 확인 채점: fold f 보정값으로 학습한 모델을 보정값 계산에 안 쓴 반쪽에서만 채점, 원래 라벨 학습과 비교 (10-26)."""

import json
import os
import sys
from pathlib import Path

import numpy as np

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")
_CVAT = os.environ.get("CVAT_LABELING_DIR", "C:/cvat-labeling")

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
PRED = Path(rf"{_CVAT}\train_ww\eval50")
NAMES = json.load(open(rf"{_PJT}\splits\wowwow\wowwow_val.json", encoding="utf-8"))["categories"][
    0
]["keypoints"]
shapes = json.load(open(rf"{_CVAT}\diag\offset50\task16_labels.json", encoding="utf-8"))["shapes"]
fold = json.load(open(HERE / "fold_split.json", encoding="utf-8"))
PART = [("어깨뼈 위끝", 3, 8), ("팔꿈치", 5, 10), ("뒷발끝", 17, 21), ("T13", 2, 2)]
ALL = PART + [
    ("어깨", 4, 9),
    ("앞발목", 6, 11),
    ("앞발끝", 7, 12),
    ("고관절", 14, 18),
    ("무릎", 15, 19),
    ("뒷발목", 16, 20),
    ("장골능", 13, 13),
]


def err(pred, held):
    e = {nm: [] for nm, *_ in ALL}
    for s in shapes:
        if fold[s["name"]] != held:
            continue
        h = np.array([s["pts"][n]["xy"] for n in NAMES], float)
        bad = [s["pts"][n]["occ"] or s["pts"][n]["out"] for n in NAMES]
        L = np.linalg.norm((h[4] + h[9]) / 2 - (h[14] + h[18]) / 2)
        left = (h[0][0] + h[1][0]) / 2 < h[13][0]
        for nm, li, ri in ALL:
            i = li if left else ri
            if not bad[i]:
                e[nm].append(np.linalg.norm(np.array(pred[s["name"]][i][:2]) - h[i]) / L)
    return {k: np.mean(v) for k, v in e.items()} | {"전체": np.mean(sum(e.values(), []))}


P = lambda n: json.load(open(PRED / f"pred_{n}.json", encoding="utf-8"))
for f in (0, 1):
    held = 1 - f
    o = [err(P(f"orig_s{s}"), held) for s in range(3)]
    b = [err(P(f"fold{f}_s{s}"), held) for s in range(3)]
    full = [err(P(f"offset_s{s}"), held) for s in range(3)]
    print(
        f"\n보정값 = 반쪽 {f}({sum(v == f for v in fold.values())}장), 채점 = 반쪽 {held}({sum(v == held for v in fold.values())}장)"
    )
    for k in [p[0] for p in PART] + ["전체"]:
        m = lambda R: np.mean([r[k] for r in R])
        print(
            f"  {k:<8} 원래 {m(o):.3f}  보정(반쪽) {m(b):.3f}  보정(50장 전체, 누수) {m(full):.3f}"
        )
