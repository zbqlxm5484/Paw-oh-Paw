r"""96 보정 학습 효과: 50장 사람 라벨(기업 기준) 대비 모델 예측 오차 (10-26).

예측: $CVAT_LABELING_DIR\train_ww\eval50\pred_<모델>.json (infer50.py, 정답 상자 방식)
채점: 카메라 쪽 다리 + 가운데 점, 사람이 가려짐·화면 밖 표시 안 한 점만. 오차 = 거리 / 몸 길이(offset_analyze.py 와 같은 정의).
orig_s* = 원래 와우와우 1,144장 학습, offset_s* = 4부위 보정 1,144장 학습. 시드 3개 평균과 폭.
"""

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
LAB = Path(rf"{_CVAT}\diag\offset50\task16_labels.json")
VAL = Path(rf"{_PJT}\splits\wowwow\wowwow_val.json")
val = json.load(open(VAL, encoding="utf-8"))
NAMES = val["categories"][0]["keypoints"]
ann = {a["image_id"]: a for a in val["annotations"]}
lst = {r["cvat_name"]: r for r in json.load(open(HERE / "offset50_list.json", encoding="utf-8"))}
shapes = json.load(open(LAB, encoding="utf-8"))["shapes"]
PART = [
    ("어깨뼈 위끝", 3, 8),
    ("어깨", 4, 9),
    ("팔꿈치", 5, 10),
    ("앞발목", 6, 11),
    ("앞발끝", 7, 12),
    ("고관절", 14, 18),
    ("무릎", 15, 19),
    ("뒷발목", 16, 20),
    ("뒷발끝", 17, 21),
    ("T13", 2, 2),
    ("장골능", 13, 13),
]
MOVED = {"어깨뼈 위끝", "팔꿈치", "뒷발끝", "T13"}

# 채점 대상 (장, 부위, 점 번호, 사람 좌표, 몸 길이)
items = []
for s in shapes:
    h = np.array([s["pts"][n]["xy"] for n in NAMES], float)
    bad = [s["pts"][n]["occ"] or s["pts"][n]["out"] for n in NAMES]
    L = np.linalg.norm((h[4] + h[9]) / 2 - (h[14] + h[18]) / 2)
    left = (h[0][0] + h[1][0]) / 2 < h[13][0]
    for nm, li, ri in PART:
        i = li if left else ri
        if not bad[i]:
            items.append((s["name"], nm, i, h[i], L))


def errs(pred):
    return np.array(
        [np.linalg.norm(np.array(pred[img][i][:2]) - xy) / L for img, nm, i, xy, L in items]
    )


ref = {}
for img, nm, i, xy, L in items:
    k = np.array(ann[lst[img]["image_id"]]["keypoints"], float).reshape(-1, 3)
    ref.setdefault(img, [[0, 0]] * 22)
    ref[img] = [list(k[j, :2]) for j in range(22)]
models = {"와우와우 원래 점": errs(ref)}
for p in sorted(PRED.glob("pred_*.json")):
    models[p.stem[5:]] = errs(json.load(open(p, encoding="utf-8")))
parts = np.array([nm for _, nm, *_ in items])


def row(e):
    return [np.mean(e[parts == nm]) for nm, *_ in PART] + [e.mean(), (e < 0.05).mean() * 100]


print(f"채점 점 {len(items)}개 · 50장\n")
hdr = "".join(f"{nm:>7}" for nm, *_ in PART) + f"{'전체평균':>8}{'0.05안%':>8}"
print(f"{'':<14}" + hdr)
table = {}
for name, e in models.items():
    table[name] = row(e)
    print(
        f"{name:<14}" + "".join(f"{v:>7.3f}" for v in table[name][:-1]) + f"{table[name][-1]:>8.1f}"
    )
for g in ("orig", "offset"):
    R = np.array([table[k] for k in table if k.startswith(g + "_s")])
    if len(R):
        print(
            f"{g+' 평균(폭)':<14}"
            + "".join(f"{m:>7.3f}" for m in R.mean(0)[:-1])
            + f"{R.mean(0)[-1]:>8.1f}"
            + f"   전체평균 폭 {R[:, -2].min():.3f}~{R[:, -2].max():.3f}"
        )
o = np.array([table[k] for k in table if k.startswith("orig_s")])
f = np.array([table[k] for k in table if k.startswith("offset_s")])
if len(o) and len(f):
    print("\n보정 − 원래 (음수 = 보정이 나음, * = 옮긴 부위):")
    for j, (nm, *_) in enumerate(PART):
        print(
            f"  {nm}{'*' if nm in MOVED else ' '} {f[:, j].mean() - o[:, j].mean():+.4f}  (원래 시드 폭 {o[:, j].min():.3f}~{o[:, j].max():.3f}, 보정 {f[:, j].min():.3f}~{f[:, j].max():.3f})"
        )
json.dump(
    {
        k: dict(zip([p[0] for p in PART] + ["mean", "pck005"], map(float, v)))
        for k, v in table.items()
    },
    open(HERE / "score50_result.json", "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=1,
)
