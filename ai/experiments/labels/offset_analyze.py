r"""96 와우와우 ↔ 기업 기준(260820) 관절별 차이.

입력: CVAT task #16 라벨(사용자가 기업 기준으로 고친 50장) `$CVAT_LABELING_DIR\diag\offset50\task16_labels.json`
      와우와우 원래 점 `splits/wowwow/wowwow_val.json`, 이름 대응 `offset50_list.json`
차이 = 사람(기업 기준) − 와우와우. 몸 축 좌표로 나눈다:
  몸 길이 L = 어깨 가운데(4·9) ↔ 고관절 가운데(14·18) 거리 (pilot_agreement.py 와 같은 정의, 사람 라벨로 계산)
  u = 고관절 가운데 → 어깨 가운데 방향(+ 가 머리 쪽), v = u 에 수직이고 화면 아래쪽이 +
카메라 쪽 = 개가 보는 방향. 귀 가운데가 장골능보다 화면 왼쪽이면 왼다리.
보정식이 쓸 만한지: 한 장을 빼고 나머지로 평균 차이를 구해 그 장에 더했을 때 사람 라벨까지 거리가 줄어드는지(leave-one-out).
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
LAB = Path(rf"{_CVAT}\diag\offset50\task16_labels.json")
VAL = Path(rf"{_PJT}\splits\wowwow\wowwow_val.json")

val = json.load(open(VAL, encoding="utf-8"))
NAMES = val["categories"][0]["keypoints"]
ann = {a["image_id"]: a for a in val["annotations"]}
lst = {r["cvat_name"]: r for r in json.load(open(HERE / "offset50_list.json", encoding="utf-8"))}
shapes = json.load(open(LAB, encoding="utf-8"))["shapes"]
# 오토라벨(현행 모델) 원래 점: 비교 기준
DUMP = Path(rf"{_CVAT}\dump\kp_dump.jsonl")
auto = {}
for line in open(DUMP, encoding="utf-8"):
    j = json.loads(line)
    if j["frame_name"] in lst and j.get("keypoints"):
        auto[j["frame_name"]] = np.array(j["keypoints"], float)[:22, :2]

# 카메라 쪽 점(왼/오) → 같은 부위 이름
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
]
MID = [("T13", 2), ("장골능", 13)]

rows, skipped = [], []
for s in shapes:
    r = lst.get(s["name"])
    if r is None:
        skipped.append((s["name"], "목록에 없음"))
        continue
    if s["attrs"].get("grade") == "unusable":
        skipped.append((s["name"], "unusable"))
        continue
    h = np.array([s["pts"][n]["xy"] for n in NAMES], float)
    hout = np.array([s["pts"][n]["out"] for n in NAMES])
    k = np.array(ann[r["image_id"]]["keypoints"], float).reshape(-1, 3)
    sh, hp = (h[4] + h[9]) / 2, (h[14] + h[18]) / 2
    L = np.linalg.norm(sh - hp)
    if L < 1:
        skipped.append((s["name"], "몸 길이 0"))
        continue
    u = (sh - hp) / L
    v = np.array([-u[1], u[0]])
    if v[1] < 0:
        v = -v
    ear = (h[0] + h[1]) / 2
    left = ear[0] < h[13][0]
    side = "왼" if left else "오른"
    for nm, li, ri in PART + [(m, i, i) for m, i in MID]:
        i = li if left else ri
        if hout[i] or k[i, 2] == 0:
            continue
        d = h[i] - k[i, :2]
        a = auto.get(s["name"])
        da = None if a is None else float(np.linalg.norm(h[i] - a[i]) / L)
        rows.append(
            dict(
                img=s["name"],
                part=nm,
                side=side,
                du=d @ u / L,
                dv=d @ v / L,
                d_auto=da,
                occ=s["pts"][NAMES[i]]["occ"],
                grade=s["attrs"].get("grade"),
            )
        )

print(f"쓴 장 {len({r['img'] for r in rows})} · 뺀 장 {len(skipped)} {skipped}")
print(
    f"카메라 쪽: 왼 {len({r['img'] for r in rows if r['side']=='왼'})}장 · 오른 {len({r['img'] for r in rows if r['side']=='오른'})}장\n"
)
hdr = f"{'부위':<8}{'n':>4}{'머리쪽+ 평균':>12}{'표준편차':>9}{'아래쪽+ 평균':>12}{'표준편차':>9}{'거리 중앙(전)':>14}{'보정 뒤(LOO)':>13}{'줄어듦':>8}{'오토라벨↔사람':>13}"
print(hdr)
summary = {}
for nm in [p[0] for p in PART] + [m for m, _ in MID]:
    R = [r for r in rows if r["part"] == nm and not r["occ"]]
    if len(R) < 5:
        print(f"{nm:<8}{len(R):>4}  (적음)")
        continue
    D = np.array([[r["du"], r["dv"]] for r in R])
    before = np.linalg.norm(D, axis=1)
    loo = np.array([np.linalg.norm(D[j] - np.delete(D, j, 0).mean(0)) for j in range(len(D))])
    mb, ma = np.median(before), np.median(loo)
    summary[nm] = dict(
        n=len(R),
        mean_u=D[:, 0].mean(),
        sd_u=D[:, 0].std(ddof=1),
        mean_v=D[:, 1].mean(),
        sd_v=D[:, 1].std(ddof=1),
        dist_before=mb,
        dist_after=ma,
        dist_auto=float(np.median([r["d_auto"] for r in R if r["d_auto"] is not None])),
    )
    print(
        f"{nm:<8}{len(R):>4}{D[:,0].mean():>12.3f}{D[:,0].std(ddof=1):>9.3f}{D[:,1].mean():>12.3f}{D[:,1].std(ddof=1):>9.3f}{mb:>14.3f}{ma:>13.3f}{(1-ma/mb)*100:>7.0f}%{np.median([r['d_auto'] for r in R if r['d_auto'] is not None]):>13.3f}"
    )
json.dump(
    dict(rows=rows, summary=summary, skipped=skipped),
    open(HERE / "offset50_result.json", "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=1,
)
print("\n단위: 몸 길이(어깨 가운데↔고관절 가운데). Q(가려짐) 표시한 점은 뺐다.")
