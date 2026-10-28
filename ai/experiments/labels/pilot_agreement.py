r"""32 라벨 맞추기 일치도.

    (컨테이너) docker compose run --rm autolabel python diag/pilot_fetch.py
    python pilot_agreement.py [--times pilot_times.csv]

입력: C:at-labelingpilotabels.json(라벨러별 태스크), dumpkp_dump.jsonl(오토라벨 원본), 기업 정답(제니 4장).
거리는 모두 그 장의 몸길이(어깨 가운데-고관절 가운데, 세 사람 평균)로 나눈 값이다. 화면 밖(O) 점은 뺀다.
"""

import argparse
import csv
import itertools
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")
_CVAT = os.environ.get("CVAT_LABELING_DIR", "C:/cvat-labeling")

sys.stdout.reconfigure(encoding="utf-8")

PILOT = Path(rf"{_CVAT}\pilot")
DUMP = Path(rf"{_CVAT}\dump\kp_dump.jsonl")
GT = Path(rf"{_PJT}\creamoff_data\dataset\keypoints_260820\annotations.json")
HERE = Path(__file__).parent
NAMES = json.load(open(GT, encoding="utf-8"))["categories"][0]["keypoints"]
EVAL_SKIP = {2, 13}  # T13·장골능: 평가 제외(기준서 1장)
LEGS = [((3, 4, 5, 6, 7), (8, 9, 10, 11, 12)), ((14, 15, 16, 17), (18, 19, 20, 21))]


def arr(shape):
    """22×4: x, y, occluded, outside"""
    return np.array(
        [[*shape["kp"][n][:2], shape["kp"][n][2], shape["kp"][n][3]] for n in NAMES], float
    )


def body_len(k):
    return np.linalg.norm((k[4, :2] + k[9, :2]) / 2 - (k[14, :2] + k[18, :2]) / 2)


def swapped(a, b, L):
    """한쪽 다리 묶음을 좌우 바꿔 맞춘 쪽이 훨씬 가까우면 좌우를 바꿔 찍은 것으로 본다."""
    n = 0
    for left, right in LEGS:
        li, ri = list(left), list(right)
        same = (
            np.linalg.norm(a[li, :2] - b[li, :2], axis=1).sum()
            + np.linalg.norm(a[ri, :2] - b[ri, :2], axis=1).sum()
        )
        cross = (
            np.linalg.norm(a[li, :2] - b[ri, :2], axis=1).sum()
            + np.linalg.norm(a[ri, :2] - b[li, :2], axis=1).sum()
        )
        n += same / (2 * len(li)) / L > 0.15 and cross < 0.5 * same
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--times")
    args = ap.parse_args()
    labels = json.load(open(PILOT / "labels.json", encoding="utf-8"))
    meta = {r["file"]: r for r in csv.DictReader(open(HERE / "pilot20.csv", encoding="utf-8-sig"))}
    auto = {
        r["frame_name"]: np.array(r["keypoints"])[:22, :2]
        for r in map(json.loads, open(DUMP, encoding="utf-8"))
        if r["frame_name"] in meta and r["keypoints"]
    }
    who = {t: (v["assignee"][0] or t[-1]) for t, v in labels.items()}
    print("라벨러:", who, " job 상태:", {t: v["state"] for t, v in labels.items()})

    dist = defaultdict(list)
    dist_vis = defaultdict(list)
    q_same = defaultdict(list)
    moved = defaultdict(list)
    grade_same = []
    swaps = []
    per_img = []
    for f, m in meta.items():
        K = {}
        for t, v in labels.items():
            s = v["frames"].get(f, [])
            if len(s) != 1:
                print(f"  주의: {t} {f} 골격 {len(s)}개")
                continue
            K[who[t]] = (arr(s[0]), s[0]["attrs"])
        if len(K) < 2:
            continue
        L = np.mean([body_len(k) for k, _ in K.values()])
        grades = [a.get("grade") for _, a in K.values()]
        grade_same.append(len(set(grades)) == 1)
        img_d = []
        for (wa, (a, _)), (wb, (b, _)) in itertools.combinations(K.items(), 2):
            sw = swapped(a, b, L)
            if sw:
                swaps.append((m["no"], m["dog"], wa, wb, sw))
            for i in range(22):
                if i in EVAL_SKIP or a[i, 3] or b[i, 3]:
                    continue
                d = np.linalg.norm(a[i, :2] - b[i, :2]) / L
                dist[i].append(d)
                img_d.append(d)
                if not a[i, 2] and not b[i, 2]:
                    dist_vis[i].append(d)
        for i in range(22):
            if i in EVAL_SKIP:
                continue
            flags = [(k[i, 3], k[i, 2]) for k, _ in K.values()]
            if any(o for o, _ in flags):
                continue
            q_same[i].append(len({q for _, q in flags}) == 1)
        if f in auto:
            for w, (k, _) in K.items():
                for i in range(22):
                    if i not in EVAL_SKIP and not k[i, 3]:
                        moved[i].append(np.linalg.norm(k[i, :2] - auto[f][i]) / L)
        per_img.append(
            (int(m["no"]), m["dog"], m["scene"], np.median(img_d) if img_d else np.nan, grades)
        )

    print(
        f"\n장 {len(per_img)} · 등급 셋 다 같음 {sum(grade_same)}/{len(grade_same)} · 좌우 바꿔 찍음 {len(swaps)}건"
    )
    for s in swaps:
        print("   좌우:", s)
    print(
        f"\n{'번호':>3} {'점':34s} {'사람 간 중앙':>9} {'90%':>7} {'둘 다 보임 중앙':>13} {'Q 일치':>7} {'오토라벨→사람 중앙':>15}"
    )
    for i in range(22):
        if i in EVAL_SKIP or not dist[i]:
            continue
        dv = f"{np.median(dist_vis[i]):.3f}" if dist_vis[i] else "-"
        print(
            f"{i:>3} {NAMES[i]:34s} {np.median(dist[i]):9.3f} {np.percentile(dist[i], 90):7.3f} {dv:>13} "
            f"{np.mean(q_same[i]):7.0%} {np.median(moved[i]) if moved[i] else np.nan:15.3f}"
        )
    print("\n장별 사람 간 차이 중앙값(몸길이 대비)")
    for no, dog, scene, d, g in sorted(per_img):
        print(f"  {no:>2} {dog} {scene:14s} {d:.3f}  grade {g}")

    gt = json.load(open(GT, encoding="utf-8"))
    gt_img = {im["file_name"].split("/")[-1]: im["id"] for im in gt["images"]}
    gt_ann = {a["image_id"]: a for a in gt["annotations"] if a["attributes"]["source"] == "eval"}
    print("\n제니 4장: 기업 정답(보임 점만)과의 차이 중앙값")
    for f, m in meta.items():
        if m["has_company_gt"] != "1":
            continue
        g = np.array(gt_ann[gt_img[m["source"]]]["keypoints"]).reshape(22, 3)
        for t, v in labels.items():
            s = v["frames"].get(f)
            if not s:
                continue
            k = arr(s[0])
            L = body_len(g)
            d = [
                np.linalg.norm(k[i, :2] - g[i, :2]) / L
                for i in range(22)
                if i not in EVAL_SKIP and g[i, 2] == 2 and not k[i, 3]
            ]
            q = sum(
                bool(k[i, 2]) == (g[i, 2] == 1)
                for i in range(22)
                if i not in EVAL_SKIP and g[i, 2] > 0
            )
            print(f"  {m['no']:>2} {who[t]:10s} 차이 {np.median(d):.3f}  Q 표시 일치 {q}/20")

    if args.times:
        print("\n장당 시간")
        for r in csv.DictReader(open(args.times, encoding="utf-8-sig")):
            mins = float(r["minutes"])
            n = int(r["images"])
            print(
                f"  {r['labeler']}: {mins / n:.1f}분/장 → 하루 4시간이면 {240 / (mins / n):.0f}장, 주 5일 {1200 / (mins / n):.0f}장"
            )


if __name__ == "__main__":
    main()
