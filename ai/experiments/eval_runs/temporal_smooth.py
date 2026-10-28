"""정답 사진의 앞뒤 프레임 예측으로 점을 다듬는 시험(10-22). 기업 도구는 안 건드린다.

    python temporal_smooth.py --track results/gt_videos.fs-v4-flip.track.json --gt <정답> --pred center.preds.json \
        --out smooth.preds.json [--k 1] [--w 0.5]

정답 사진은 영상의 한 프레임이다. 그 프레임의 예측(--pred, 정답 상자로 추론)에 앞뒤 k 프레임의 예측(--track)을
가중 평균한다(가운데 1, 이웃 w). 이웃 프레임은 앞다리·뒷다리마다 좌우를 가운데에 더 가깝게 맞춘 뒤 더한다.
확신도가 CONF 미만인 이웃 점은 뺀다.
"""

import argparse
import json
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
CONF = 0.3
LEGS = (((4, 5, 6, 7), (9, 10, 11, 12)), ((14, 15, 16, 17), (18, 19, 20, 21)))
TRUNK = (
    2,
    3,
    4,
    8,
    9,
    13,
    14,
    18,
)  # 몸통에 붙은 점: 이웃 프레임을 이 점들의 가운데로 맞춰 개의 이동을 뺀다


def shift_to(center, nb):
    """이웃 kp 를 몸통 가운데가 가운데 프레임과 겹치도록 평행 이동한 사본(개가 걸어간 만큼 빼기)."""
    cx = sum(center[i][0] for i in TRUNK) / len(TRUNK)
    cy = sum(center[i][1] for i in TRUNK) / len(TRUNK)
    nx = sum(nb[i][0] for i in TRUNK) / len(TRUNK)
    ny = sum(nb[i][1] for i in TRUNK) / len(TRUNK)
    return [[p[0] + cx - nx, p[1] + cy - ny, p[2]] for p in nb]


def align(center, nb):
    """이웃 kp 를 가운데에 맞춰 다리별 좌우를 바꾼 사본."""
    nb = [list(p) for p in nb]
    for left, right in LEGS:
        keep = sum(math.dist(center[i][:2], nb[i][:2]) for i in left + right)
        swap = sum(math.dist(center[i][:2], nb[j][:2]) for i, j in zip(left + right, right + left))
        if swap < keep:
            for i, j in zip(left, right):
                nb[i], nb[j] = nb[j], nb[i]
    return nb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--gt", required=True)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--w", type=float, default=0.5)
    ap.add_argument(
        "--move", action="store_true", help="이웃 프레임을 몸통 위치에 맞춰 옮긴 뒤 평균"
    )
    a = ap.parse_args()

    gt = json.loads(Path(a.gt).read_text(encoding="utf-8"))
    images = {im["id"]: im for im in gt["images"]}
    doc = json.loads(Path(a.pred).read_text(encoding="utf-8"))
    preds = {r["ann_id"]: r for r in doc["predictions"]}
    tracks = {}
    for v in json.loads(Path(a.track).read_text(encoding="utf-8"))["videos"]:
        stem = Path(v["video"]).stem
        tracks[(stem[:13], stem.rsplit("-", 1)[1])] = v
    used = miss = 0
    for an in gt["annotations"]:
        im = images[an["image_id"]]
        v = tracks.get((im["session"], im["camera"]))
        if v is None or an["id"] not in preds:
            miss += 1
            continue
        kp = preds[an["id"]]["keypoints"]
        center = [kp[3 * i : 3 * i + 3] for i in range(22)]
        acc = [[c[0], c[1], 1.0] for c in center]  # (x 합, y 합, 가중치 합)
        f = im["frame_idx"]
        for d in range(1, a.k + 1):
            for g in (f - d, f + d):
                if 0 <= g < len(v["frames"]) and v["frames"][g] is not None:
                    nb = v["frames"][g]["kp"]
                    if a.move:
                        nb = shift_to(center, nb)
                    nb = align(center, nb)
                    w = a.w / d
                    for i in range(22):
                        if nb[i][2] >= CONF:
                            acc[i][0] += w * nb[i][0]
                            acc[i][1] += w * nb[i][1]
                            acc[i][2] += w
        for i in range(22):
            kp[3 * i], kp[3 * i + 1] = acc[i][0] / acc[i][2], acc[i][1] / acc[i][2]
        used += 1
    doc["meta"] = dict(
        doc.get("meta", {}), temporal_smooth={"track": a.track, "k": a.k, "w": a.w, "move": a.move}
    )
    Path(a.out).write_text(json.dumps(doc), encoding="utf-8")
    print(f"-> {a.out}  다듬은 예측 {used} · 영상 못 찾음 {miss}")


if __name__ == "__main__":
    main()
