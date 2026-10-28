"""32 라벨 맞추기: 후보 특징(cand_feats.json)에서 개마다 4장을 고르고 확인용 그림을 만든다."""

import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

_CVAT = os.environ.get("CVAT_LABELING_DIR", "C:/cvat-labeling")

sys.stdout.reconfigure(encoding="utf-8")
PILOT = Path(rf"{_CVAT}\pilot")
OUT = Path(sys.argv[1])
rows = json.load(open(PILOT / "cand_feats.json", encoding="utf-8"))
dump = {
    r["frame_name"]: r for r in map(json.loads, open(PILOT / "cand_dump.jsonl", encoding="utf-8"))
}
LARGE = {"럭키", "아미"}


def walking(r):
    """정면·몸 돌림·켄넬 등 걷는 옆모습이 아닌 장을 거른다."""
    x0, y0, x1, y1 = dump[r["name"]]["bbox"]
    w, h = x1 - x0, y1 - y0
    return w / h > 1.2 and r["conf"] >= 0.4 and r["L"] / w > 0.3


rows = [r for r in rows if walking(r)]
print(
    "걷는 옆모습 후보",
    len(rows),
    {d: sum(r["dog"] == d for r in rows) for d in ["럭키", "아미", "건빵", "오이"]},
)


def pick(R, ok, key, used):
    for r in sorted((r for r in R if ok(r)), key=key):
        vid = r["name"].rsplit("_f", 1)[0]
        if any(u["name"].rsplit("_f", 1)[0] == vid and abs(u["f"] - r["f"]) < 60 for u in used):
            continue
        if sum(u["name"].rsplit("_f", 1)[0] == vid for u in used) >= 3:
            continue
        return r
    return None


sel = []
for d in ["럭키", "아미", "건빵", "오이"]:
    R = [r for r in rows if r["dog"] == d]
    used = []
    rules = [
        (
            "깨끗한 옆모습",
            lambda r: r["side"] > 0.85 and not r["edge"] and r["hind"] > 0.25 and not r["cross"],
            lambda r: -r["conf"],
        ),
        (
            "뒷다리 겹침",
            lambda r: r["hind"] < 0.12 and r["side"] > 0.7 and not r["edge"],
            lambda r: r["hind"],
        ),
        (
            "좌우 혼동(교차)",
            lambda r: r["cross"] and r["hind"] >= 0.12 and r["side"] > 0.7 and not r["edge"],
            lambda r: -r["conf"],
        ),
        ("화면 끝 걸림", lambda r: r["edge"] and r["side"] > 0.7, lambda r: -r["conf"])
        if d in LARGE
        else (
            "앞다리 겹침",
            lambda r: r["front"] < 0.12 and r["side"] > 0.7 and not r["edge"],
            lambda r: r["front"],
        ),
    ]
    for tag, ok, key in rules:
        r = pick(R, ok, key, used) or pick(R, lambda r: r["side"] > 0.7, lambda r: -r["conf"], used)
        if r is None:
            print("빈 칸:", d, tag)
            continue
        r = dict(r, tag=tag if ok(r) else tag + "→대체")
        used.append(r)
        sel.append(r)

for r in sel:
    print(
        f'{r["dog"]:3s} {r["tag"]:10s} {r["name"]:45s} conf {r["conf"]:.2f} side {r["side"]:.2f} hind {r["hind"]:.2f} front {r["front"]:.2f} edge {r["edge"]}'
    )
json.dump(
    sel, open(OUT / "pilot_selected_auto.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1
)

tiles = []
for r in sel:
    vid = r["name"].rsplit("_f", 1)[0]
    img = cv2.imdecode(np.fromfile(str(PILOT / "cand" / vid / r["name"]), np.uint8), 1)
    k = np.array(dump[r["name"]]["keypoints"])[:22]
    for i, (x, y, c) in enumerate(k):
        col = (
            (255, 80, 0)
            if i in (0, 3, 4, 5, 6, 7, 14, 15, 16, 17)
            else (0, 0, 255)
            if i not in (2, 13)
            else (0, 255, 0)
        )
        cv2.circle(img, (int(x), int(y)), 9, col, -1)
    x0, y0, x1, y1 = map(int, dump[r["name"]]["bbox"])
    pad = 60
    crop = img[max(0, y0 - pad) : y1 + pad, max(0, x0 - pad) : x1 + pad]
    crop = cv2.resize(crop, (480, 320))
    cv2.putText(crop, f"{len(tiles)+1}", (8, 34), 0, 1.1, (0, 255, 255), 3)
    tiles.append(crop)
tiles += [np.zeros_like(tiles[0])] * (-len(tiles) % 4)
grid = np.vstack([np.hstack(tiles[i : i + 4]) for i in range(0, len(tiles), 4)])
cv2.imwrite(str(OUT / "pilot_auto16.jpg"), grid)
