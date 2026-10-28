"""와우와우 30장을 기업(260820) 방식으로 다시 라벨링할 표본 고르기 (10-28).

목적: 기업 기준 라벨이 제니 한 마리뿐이라, 다른 개에서도 기업 기준 정답을 조금 만든다.
   → 260820 으로 학습한 모델이 다른 개에서도 좋아지는지 채점할 때 쓴다.
와우와우 전체에서 사람이 고친(human_fixed) grade good 장만. 정원님 50장(offset50)과 같은 촬영 묶음은 통째로 뺀다
(검증 288장의 29묶음은 offset50 이 전부 썼다).
날짜순으로 늘어놓은 묶음에서 고르게 N개 묶음, 묶음마다 1장. 고관절·무릎이 한쪽이라도 둘 다 보이는(v=2) 장만.
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
PJT = Path(rf"{_PJT}")
IMG = PJT / "creamoff_data/dataset_1021/keypoints_wowwow"
OUT_FRAMES = Path(rf"{_CVAT}\frames\ww-company30")
HERE = Path(__file__).parent
N = 30
HIP_KNEE = [(14, 15), (18, 19)]

d = json.load(open(IMG / "annotations.json", encoding="utf-8"))
ann = {a["image_id"]: a for a in d["annotations"]}
used = json.load(open(PJT / "wowwow_offset50/offset50_list.json", encoding="utf-8"))
used_sessions = {r["session"] for r in used}


def session(im):
    return Path(im["file_name"]).name.split("_")[0].split("-", 1)[1]


def ok(im):
    k = ann[im["id"]]["keypoints"]
    return any(k[h * 3 + 2] == 2 and k[n * 3 + 2] == 2 for h, n in HIP_KNEE)


by = collections.defaultdict(list)
for im in d["images"]:
    at = ann[im["id"]]["attributes"]
    if at["human_fixed"] and at["grade"] == "good" and session(im) not in used_sessions and ok(im):
        by[session(im)].append(im)
rng = random.Random(1028)
for v in by.values():
    rng.shuffle(v)
keys = sorted(by)  # 날짜순 묶음에서 고르게 N개
pick = [by[keys[round(i * (len(keys) - 1) / (N - 1))]][0] for i in range(N)]
print(f"후보 묶음 {len(by)}개 (offset50 묶음 {len(used_sessions)}개 제외) → {len(pick)}장")

OUT_FRAMES.mkdir(
    parents=True, exist_ok=False
)  # 이미 있으면 멈춘다: 라벨 작업 중인 태스크를 덮지 않게
rows = []
for no, im in enumerate(sorted(pick, key=lambda im: Path(im["file_name"]).name), 1):
    name = f"c{no:02d}_{Path(im['file_name']).name}"
    shutil.copy2(IMG / im["file_name"], OUT_FRAMES / name)
    rows.append(
        dict(
            no=no,
            cvat_name=name,
            image_id=im["id"],
            file_name=im["file_name"],
            session=session(im),
            camera=Path(im["file_name"]).name.split("-")[0],
        )
    )
json.dump(
    rows, open(HERE / "ww_company30_list.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1
)
print(collections.Counter(r["camera"] for r in rows), "묶음", len({r["session"] for r in rows}))
