"""후보 덤프에서 장면 유형을 매겨 개마다 4장 고른다(제니 제외)."""

import json
import re
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
W, H = 1920, 1080
rows = []
for r in map(json.loads, open("/work/pilot/cand_dump.jsonl", encoding="utf-8")):
    if not r["detected"] or r["keypoints"] is None:
        continue
    k = np.array(r["keypoints"])[:22]
    xy, c = k[:, :2], k[:, 2]
    x0, y0, x1, y1 = r["bbox"]
    sh = (xy[4] + xy[9]) / 2
    hp = (xy[14] + xy[18]) / 2
    L = np.linalg.norm(sh - hp)
    if L < 50:
        continue
    side = abs(sh[0] - hp[0]) / L  # 1 = 완전 옆모습
    hind = np.mean([np.linalg.norm(xy[a] - xy[b]) for a, b in [(15, 19), (16, 20), (17, 21)]]) / L
    front = np.mean([np.linalg.norm(xy[a] - xy[b]) for a, b in [(5, 10), (6, 11), (7, 12)]]) / L
    # 위(무릎)와 아래(뒷발끝)에서 좌우 x 순서가 뒤바뀌면 X 자 교차
    cross = np.sign(xy[15, 0] - xy[19, 0]) != np.sign(xy[17, 0] - xy[21, 0])
    edge = min(x0, y0, W - x1, H - y1) < 8
    m = re.match(r"(\d{6}-\d{6})-(.+?)-[\d.]+kg-(\w+)_f(\d+)", r["frame_name"])
    rows.append(
        dict(
            name=r["frame_name"],
            stamp=m[1],
            dog=m[2],
            cam=m[3],
            f=int(m[4]),
            conf=float(np.median(c)),
            side=side,
            hind=hind,
            front=front,
            cross=bool(cross),
            edge=bool(edge),
            L=L,
        )
    )
print("검출 장수", len(rows))
for d in sorted({r["dog"] for r in rows}):
    R = [r for r in rows if r["dog"] == d]
    print(
        d,
        len(R),
        "겹침(<0.12)",
        sum(r["hind"] < 0.12 for r in R),
        "교차",
        sum(r["cross"] for r in R),
        "끝",
        sum(r["edge"] for r in R),
        "옆모습>0.85",
        sum(r["side"] > 0.85 for r in R),
    )
json.dump(rows, open("/work/pilot/cand_feats.json", "w", encoding="utf-8"), ensure_ascii=False)
