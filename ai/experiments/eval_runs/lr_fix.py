"""영상 앞뒤 프레임으로 다리 좌우를 바로잡는 후처리 시험(10-20). paw_eval 원본 도구는 건드리지 않는다.

    python lr_fix.py --track results/gt_videos.fs-v4.track.json --gt <정답> --pred results/fs-v4.gpu.preds.json \
        --out results/fs-v4.lrfix.preds.json [--penalty 0.05] [--gap 3]

영상마다 앞다리·뒷다리를 따로, 프레임마다 '그대로 / 좌우 바꿈' 상태를 고른다. 이웃 프레임의 같은 다리끼리
거리(점당 몸통 길이 대비)의 합이 가장 작은 상태열을 비터비로 찾는다. 바꿈에는 penalty 를 매겨 이유 없이
바꾸지 않게 하고, 그래서 영상 전체를 통째로 뒤집는 답은 나오지 않는다.
정답 사진 프레임은 그 사진의 예측(--pred, 정답 상자로 추론한 것)으로 갈아 끼운 뒤 계산하고, 그 프레임의
상태가 '바꿈'이면 예측의 해당 다리를 맞바꿔 --out 에 쓴다. 채점은 score.py 그대로.
"""

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
LEGS = {"front": ((4, 5, 6, 7), (9, 10, 11, 12)), "hind": ((14, 15, 16, 17), (18, 19, 20, 21))}
# 10-22: 앞다리는 원래 뒤바뀜이 드물어(3.96%) 바꾸면 오히려 틀린다. 몸통에 붙은 어깨·고관절도 헷갈릴 일이 적다
LEG_SETS = {
    "all": LEGS,
    "distal": {"front": ((5, 6, 7), (10, 11, 12)), "hind": ((15, 16, 17), (19, 20, 21))},
    "hind": {"hind": ((14, 15, 16, 17), (18, 19, 20, 21))},
    "hind-distal": {"hind": ((15, 16, 17), (19, 20, 21))},
}


def body_len(kp):
    sx, sy = (kp[4][0] + kp[9][0]) / 2, (kp[4][1] + kp[9][1]) / 2
    hx, hy = (kp[14][0] + kp[18][0]) / 2, (kp[14][1] + kp[18][1]) / 2
    return math.hypot(sx - hx, sy - hy)


def leg_cost(a, b, legs, sa, sb):
    """프레임 a(상태 sa)와 b(상태 sb)의 같은 다리끼리 점당 거리 합."""
    la, ra = (legs[1], legs[0]) if sa else legs
    lb, rb = (legs[1], legs[0]) if sb else legs
    d = sum(math.dist(a[i][:2], b[j][:2]) for i, j in zip(la, lb)) + sum(
        math.dist(a[i][:2], b[j][:2]) for i, j in zip(ra, rb)
    )
    return d / (2 * len(legs[0]))


def viterbi(seq, legs, penalty, gap):
    """seq: [(frame, kp)] 프레임 순. → {frame: 0|1}. gap 넘게 끊기면 새 구간."""
    out = {}
    seg = []
    for item in seq + [(None, None)]:
        if seg and (item[0] is None or item[0] - seg[-1][0] > gap):
            cost = [[0.0, penalty]]
            back = []
            for n in range(1, len(seg)):
                (_, a), (_, b) = seg[n - 1], seg[n]
                L = max(body_len(b), 1.0)
                row, bk = [], []
                for s in (0, 1):
                    c = [cost[-1][p] + leg_cost(a, b, legs, p, s) / L for p in (0, 1)]
                    p = 0 if c[0] <= c[1] else 1
                    row.append(c[p] + penalty * s)
                    bk.append(p)
                cost.append(row)
                back.append(bk)
            s = 0 if cost[-1][0] <= cost[-1][1] else 1
            states = [s]
            for bk in reversed(back):
                s = bk[s]
                states.append(s)
            for (f, _), st in zip(seg, reversed(states)):
                out[f] = st
            seg = []
        if item[0] is not None:
            seg.append(item)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--gt", required=True)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--penalty", type=float, default=0.05)
    ap.add_argument("--gap", type=int, default=3)
    ap.add_argument("--legs", choices=sorted(LEG_SETS), default="all")
    a = ap.parse_args()
    legs_set = LEG_SETS[a.legs]

    gt = json.loads(Path(a.gt).read_text(encoding="utf-8"))
    images = {im["id"]: im for im in gt["images"]}
    pred_doc = json.loads(Path(a.pred).read_text(encoding="utf-8"))
    preds = {r["ann_id"]: r for r in pred_doc["predictions"]}
    tracks = {}
    for v in json.loads(Path(a.track).read_text(encoding="utf-8"))["videos"]:
        stem = v["video"].rsplit(".", 1)[0]
        tracks[(stem[:13], stem.rsplit("-", 1)[1])] = v
    by_video = defaultdict(list)
    for ann in gt["annotations"]:
        im = images[ann["image_id"]]
        by_video[(im["session"], im["camera"])].append((im["frame_idx"], ann["id"]))

    changed = defaultdict(int)
    for key, items in by_video.items():
        v = tracks[key]
        base = {f: r["kp"] for f, r in enumerate(v["frames"]) if r is not None}
        for frame, ann_id in items:
            kp = preds[ann_id]["keypoints"]
            seq = dict(base)
            seq[frame] = [kp[3 * i : 3 * i + 3] for i in range(22)]
            ordered = sorted(seq.items())
            for name, legs in legs_set.items():
                if viterbi(ordered, legs, a.penalty, a.gap).get(frame):
                    for i, j in zip(*legs):
                        kp[3 * i : 3 * i + 3], kp[3 * j : 3 * j + 3] = (
                            kp[3 * j : 3 * j + 3],
                            kp[3 * i : 3 * i + 3],
                        )
                    changed[name] += 1
    pred_doc["meta"] = dict(
        pred_doc.get("meta", {}),
        lr_fix={
            "track": a.track,
            "penalty": a.penalty,
            "gap": a.gap,
            "legs": a.legs,
            "swapped": dict(changed),
        },
    )
    Path(a.out).write_text(json.dumps(pred_doc), encoding="utf-8")
    print(f"-> {a.out}  바꾼 예측: {dict(changed)} / {len(preds)}")


if __name__ == "__main__":
    main()
