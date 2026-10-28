"""96 와우와우 기준 차이 측정용 50장 고르기 (검증 288장에서).

촬영 묶음과 카메라가 고루 섞이게 묶음마다 상한을 두고 돌아가며 뽑는다.
고관절·무릎이 한쪽이라도 둘 다 보이는(v=2) 장만 후보로 둔다.
"""

import collections
import json
import os
import random
import shutil
import sys
from pathlib import Path

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")
_CVAT = os.environ.get("CVAT_LABELING_DIR", "C:/cvat-labeling")

sys.stdout.reconfigure(encoding="utf-8")

VAL = Path(rf"{_PJT}\splits\wowwow\wowwow_val.json")
IMG = Path(rf"{_PJT}\creamoff_data\dataset_1021\keypoints_wowwow")
OUT_FRAMES = Path(rf"{_CVAT}\frames\wowwow-offset50")
HERE = Path(__file__).parent
N, BIG_CAP, CAP = 50, 12, 3
HIP_KNEE = [(14, 15), (18, 19)]

d = json.load(open(VAL, encoding="utf-8"))
ann = {a["image_id"]: a for a in d["annotations"]}


def ok(im):
    k = ann[im["id"]]["keypoints"]
    return any(k[h * 3 + 2] == 2 and k[n * 3 + 2] == 2 for h, n in HIP_KNEE)


by = collections.defaultdict(list)
for im in d["images"]:
    if ok(im):
        by[im["session"]].append(im)
rng = random.Random(0)
for v in by.values():
    rng.shuffle(v)
    v.sort(key=lambda im: im["camera"])  # main·sub1 번갈아 나오게 아래에서 섞는다
    m = [x for x in v if x["camera"] == "main"]
    s = [x for x in v if x["camera"] == "sub1"]
    v[:] = [x for pair in zip(m, s) for x in pair] + m[len(s) :] + s[len(m) :]

picked, cap = [], {k: (BIG_CAP if len(v) > 50 else CAP) for k, v in by.items()}
r = 0
while len(picked) < N:
    added = False
    for k in sorted(by, key=lambda k: -len(by[k])):
        if r < min(cap[k], len(by[k])) and len(picked) < N:
            picked.append(by[k][r])
            added = True
    if not added:
        break
    r += 1

OUT_FRAMES.mkdir(parents=True, exist_ok=True)
rows = []
for no, im in enumerate(
    sorted(picked, key=lambda im: (im["session"], im["camera"], im["frame_idx"])), 1
):
    name = f"w{no:02d}_{Path(im['file_name']).name}"
    shutil.copyfile(IMG / im["file_name"], OUT_FRAMES / name)
    rows.append(
        dict(
            no=no,
            cvat_name=name,
            image_id=im["id"],
            file_name=im["file_name"],
            session=im["session"],
            camera=im["camera"],
        )
    )
json.dump(
    rows, open(HERE / "offset50_list.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1
)
print(
    len(rows),
    "장 ·",
    len({r["session"] for r in rows}),
    "묶음 ·",
    collections.Counter(r["camera"] for r in rows),
)
print("후보", sum(len(v) for v in by.values()), "/", len(d["images"]))
