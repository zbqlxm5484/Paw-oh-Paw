r"""36: 개마다 후보 촬영을 고르고 영상을 $CVAT_LABELING_DIR\pool\videos 로 복사한다."""

import collections
import csv
import json
import os
import random
import shutil
import sys
from pathlib import Path

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")
_CVAT = os.environ.get("CVAT_LABELING_DIR", "C:/cvat-labeling")

sys.stdout.reconfigure(encoding="utf-8")
DATA = Path(rf"{_PJT}\creamoff_data\dataset")
POOL = Path(rf"{_CVAT}\pool\videos")
SPLIT = json.load(open(rf"{_PJT}\splits\creamoff_dog_split.json", encoding="utf-8"))
PER_DOG = 3  # 개마다 촬영 수
GOOD = ["trot", "pace", "not_trot", ""]  # 걷는 촬영 우선(dist·disease 등은 뒤로)
rng = random.Random(42)
rows = list(csv.DictReader(open(DATA / "videos" / "manifest.csv", encoding="utf-8-sig")))
split_of = {d["dog"]: d["split"] for d in SPLIT["dogs"]}
POOL.mkdir(parents=True, exist_ok=True)
out = []
for dog in sorted(split_of):
    if split_of[dog] not in ("train", "val"):
        continue
    ss = [r for r in rows if r["dog"] == dog and r["label"] in GOOD and r["cam_broken"] == ""]
    rng.shuffle(ss)
    ss.sort(key=lambda r: GOOD.index(r["label"]))
    for r in ss[:PER_DOG]:
        cams = r["cameras"].split()
        cams = [c for c in ("main", "sub1") if c in cams] or cams[:1]  # 4대면 서로 반대편 main·sub1
        folder = DATA / r["path"]
        for cam in cams:
            src = next(
                iter(sorted(folder.glob(f"*-{cam}.mp4")) + sorted(folder.glob(f"*-{cam}-*.mp4"))),
                None,
            )
            if src is None:
                print("영상 없음", r["stamp"], cam)
                continue
            name = f"{r['stamp']}-{dog}-{cam}.mp4"
            if not (POOL / name).exists():
                shutil.copyfile(src, POOL / name)
            out.append(
                dict(
                    video=name[:-4],
                    stamp=r["stamp"],
                    dog=dog,
                    split=split_of[dog],
                    cam=cam,
                    label=r["label"],
                    fps=r[f"fps_{cam}"],
                    site=r["site"],
                )
            )
with open(Path(__file__).parent / "pool_videos.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0]))
    w.writeheader()
    w.writerows(out)

print(
    len(out),
    "영상",
    collections.Counter(o["split"] for o in out),
    collections.Counter(o["fps"] for o in out),
)
