r"""96 와우와우 학습용 라벨에 관절별 평균 차이를 더해 기업 기준(260820)에 가깝게 옮긴다.

offset50_result.json 의 summary 중 한 장 빼기 검증(LOO)에서 사람 라벨까지 거리가 15% 넘게 줄어든 부위만 옮긴다.
몸 축은 와우와우 자기 점(어깨 가운데·고관절 가운데)으로 잡는다. 사람 라벨이 없는 장이기 때문.
옮기는 쪽: 개가 보는 방향 기준 카메라 쪽 다리 + 가운데 점. 반대쪽 다리는 건드리지 않는다.
검증셋은 손대지 않는다(사람이 직접 고친다).

    python apply_offset.py  → splits/wowwow/wowwow_train_offset.json
"""

import copy
import json
import os
import sys
from pathlib import Path

import numpy as np

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
SRC = Path(rf"{_PJT}\splits\wowwow\wowwow_train.json")
DST = SRC.with_name("wowwow_train_offset.json")
MIN_GAIN = 0.15
PART = {
    "어깨뼈 위끝": (3, 8),
    "어깨": (4, 9),
    "팔꿈치": (5, 10),
    "앞발목": (6, 11),
    "앞발끝": (7, 12),
    "고관절": (14, 18),
    "무릎": (15, 19),
    "뒷발목": (16, 20),
    "뒷발끝": (17, 21),
    "T13": (2, 2),
    "장골능": (13, 13),
}

summ = json.load(open(HERE / "offset50_result.json", encoding="utf-8"))["summary"]
use = {
    nm: (s["mean_u"], s["mean_v"])
    for nm, s in summ.items()
    if 1 - s["dist_after"] / s["dist_before"] > MIN_GAIN
}
print("옮기는 부위:", {k: (round(a, 3), round(b, 3)) for k, (a, b) in use.items()})

d = json.load(open(SRC, encoding="utf-8"))
out = copy.deepcopy(d)
moved = skipped = 0
for a in out["annotations"]:
    k = np.array(a["keypoints"], float).reshape(-1, 3)
    if k[[4, 9, 14, 18], 2].min() == 0 or k[[0, 1, 13], 2].min() == 0:
        skipped += 1
        continue  # 몸 축·방향을 못 잡는 장은 그대로 둔다
    sh, hp = (k[4, :2] + k[9, :2]) / 2, (k[14, :2] + k[18, :2]) / 2
    L = np.linalg.norm(sh - hp)
    if L < 1:
        skipped += 1
        continue
    u = (sh - hp) / L
    v = np.array([-u[1], u[0]])
    if v[1] < 0:
        v = -v
    left = (k[0, 0] + k[1, 0]) / 2 < k[13, 0]
    for nm, (du, dv) in use.items():
        i = PART[nm][0] if left else PART[nm][1]
        if k[i, 2] > 0:
            k[i, :2] += (du * u + dv * v) * L
            moved += 1
    a["keypoints"] = [float(x) for x in k.reshape(-1)]
    a.setdefault("attributes", {})["offset96"] = True
out["info"] = dict(
    out.get("info", {}),
    offset96=dict(
        parts={k: list(v) for k, v in use.items()}, min_gain=MIN_GAIN, source="offset50_result.json"
    ),
)
json.dump(out, open(DST, "w", encoding="utf-8"), ensure_ascii=False)
print(
    f"장 {len(out['annotations'])} · 옮긴 점 {moved} · 몸 축을 못 잡아 그대로 둔 장 {skipped} → {DST}"
)
