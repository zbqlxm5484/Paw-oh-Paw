r"""36: 후보 영상 추론 결과(pool_dump.jsonl)에서 1차 라벨 프레임을 고르고 CVAT 태스크용 폴더를 만든다.

    python select_batch1.py            # 목록 batch1_frames.csv + 확인 그림
    python select_batch1.py --make     # $CVAT_LABELING_DIR\frames\batch1-* 에 프레임 저장(make_tasks 용)

정답이 없으니 연속 프레임의 앞뒤 일관성으로 모델 오류를 찾는다(30Hz 간격).
- 좌우 뒤바뀜: 바로 앞 장과 비교해 왼·오른 다리 묶음을 바꿔 맞춘 쪽이 훨씬 가까우면(뒷다리·앞다리 따로)
- 발끝 튐: 발끝이 앞뒤 장의 가운데에서 몸길이의 JUMP 이상 JUMP_MAX 미만 벗어나면. 더 크면 골격이 통째로 무너진
  장(개가 반쯤 걸림·카메라에 붙음)이라 라벨러가 unusable 만 누르게 돼서 뺀다. 발끝 확신도 낮음은 너무 흔해 안 쓴다
- 모든 종류 공통: 화면 끝에 안 걸리고, 상자 가로/세로 MIN_ASPECT 이상, 확신도 중앙값 MIN_CONF 이상
- 깨끗함: 앞뒤 3장 안에 뒤바뀜이 없고, 튐이 작고, 확신도가 높고, 화면 끝에 걸리지 않음
"""

import argparse
import collections
import csv
import json
import os
import sys
from pathlib import Path

import numpy as np

_CVAT = os.environ.get("CVAT_LABELING_DIR", "C:/cvat-labeling")

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
POOL = Path(rf"{_CVAT}\pool")
FRAMES = Path(rf"{_CVAT}\frames")
W, H = 1920, 1080
LEGS = {"hind": ((14, 15, 16, 17), (18, 19, 20, 21)), "front": ((4, 5, 6, 7), (9, 10, 11, 12))}
PAWS = (7, 12, 17, 21)
JUMP, JUMP_MAX, GAP, PER_VIDEO = 0.25, 1.0, 15, 6
MIN_ASPECT, MIN_CONF = 1.1, 0.35
QUOTA = {"train": {"flip": 5, "paw": 3, "clean": 3}, "val": {"flip": 2, "paw": 2, "clean": 7}}


def load():
    vids = {
        r["video"]: r for r in csv.DictReader(open(HERE / "pool_videos.csv", encoding="utf-8-sig"))
    }
    by_vid = collections.defaultdict(dict)
    for r in map(json.loads, open(POOL / "pool_dump.jsonl", encoding="utf-8")):
        v, f = r["frame_name"].rsplit("_f", 1)
        if r["detected"] and r["keypoints"]:
            by_vid[v][int(f[:-4])] = r
    return vids, by_vid


def features(frames):
    idx = sorted(frames)
    k = {f: np.array(frames[f]["keypoints"])[:22] for f in idx}
    out = {}
    for n, f in enumerate(idx):
        xy, c = k[f][:, :2], k[f][:, 2]
        L = np.linalg.norm((xy[4] + xy[9]) / 2 - (xy[14] + xy[18]) / 2)
        x0, y0, x1, y1 = frames[f]["bbox"]
        if L < 40 or abs(((xy[4] + xy[9]) / 2 - (xy[14] + xy[18]) / 2)[0]) < 0.7 * L:
            continue  # 옆모습 아님
        if (
            min(x0, y0, W - x1, H - y1) < 8
            or (x1 - x0) / (y1 - y0) < MIN_ASPECT
            or np.median(c) < MIN_CONF
        ):
            continue  # 화면 끝·정면·자신 없는 장
        prev = idx[n - 1] if n and f - idx[n - 1] <= 4 else None
        nxt = idx[n + 1] if n + 1 < len(idx) and idx[n + 1] - f <= 4 else None
        flip = []
        if prev is not None:
            p = k[prev][:, :2]
            for name, (l, r) in LEGS.items():
                l, r = list(l), list(r)
                same = (
                    np.linalg.norm(xy[l] - p[l], axis=1).sum()
                    + np.linalg.norm(xy[r] - p[r], axis=1).sum()
                )
                cross = (
                    np.linalg.norm(xy[l] - p[r], axis=1).sum()
                    + np.linalg.norm(xy[r] - p[l], axis=1).sum()
                )
                if same / (2 * len(l)) / L > 0.1 and cross < 0.6 * same:
                    flip.append(name)
        jump = 0.0
        if prev is not None and nxt is not None:
            mid = (k[prev][:, :2] + k[nxt][:, :2]) / 2
            jump = max(np.linalg.norm(xy[i] - mid[i]) / L for i in PAWS)
        out[f] = dict(
            L=L,
            conf=float(np.median(c)),
            paw_conf=float(c[list(PAWS)].min()),
            flip=flip,
            jump=jump,
            edge=min(x0, y0, W - x1, H - y1) < 8,
        )
    flips = [f for f, v in out.items() if v["flip"]]
    for f, v in out.items():
        near = any(abs(f - g) <= 6 for g in flips)
        v["kind"] = (
            "flip"
            if v["flip"]
            else "paw"
            if JUMP < v["jump"] < JUMP_MAX
            else "clean"
            if not near and v["jump"] < 0.08 and v["conf"] > 0.6 and not v["edge"]
            else "other"
        )
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--make", action="store_true")
    args = ap.parse_args()
    vids, by_vid = load()
    feats = {v: features(fr) for v, fr in by_vid.items()}
    cand = collections.defaultdict(list)  # 개 → 후보
    for v, fs in feats.items():
        for f, x in fs.items():
            cand[vids[v]["dog"]].append(
                dict(
                    x,
                    video=v,
                    frame=f,
                    **{k: vids[v][k] for k in ("dog", "split", "cam", "stamp", "site")},
                )
            )
    order = {
        "flip": lambda c: -c["L"],
        "paw": lambda c: -c["jump"],
        "clean": lambda c: -c["conf"],
        "other": lambda c: -c["conf"],
    }
    rng = np.random.default_rng(42)
    picked = []
    for dog in sorted(cand):
        C = cand[dog]
        split = C[0]["split"]
        got = []

        def ok(c):
            same = [g for g in got if g["video"] == c["video"]]
            return len(same) < PER_VIDEO and all(abs(g["frame"] - c["frame"]) >= GAP for g in same)

        for kind, n in QUOTA[split].items():
            pool = [c for c in C if c["kind"] == kind]
            rng.shuffle(pool)  # 같은 점수에서 한 영상만 몰리지 않게
            pool.sort(key=order[kind])
            for c in pool:
                if sum(g["reason"] == kind for g in got) >= n:
                    break
                if ok(c):
                    got.append(dict(c, reason=kind))
        short = sum(QUOTA[split].values()) - len(got)  # 모자라면 깨끗함·기타로 채움
        for c in sorted(C, key=lambda c: -c["conf"]):
            if short <= 0:
                break
            if c["kind"] in ("clean", "other") and ok(c) and all(g is not c for g in got):
                got.append(dict(c, reason=c["kind"] + "(채움)"))
                short -= 1
        picked += got
    pr = {"flip": 0, "paw": 1, "clean": 2}
    picked.sort(key=lambda p: (p["split"], pr.get(p["reason"], 3), p["dog"]))
    cols = [
        "split",
        "dog",
        "video",
        "frame",
        "reason",
        "flip",
        "jump",
        "paw_conf",
        "conf",
        "edge",
        "cam",
        "site",
        "stamp",
    ]
    with open(HERE / "batch1_frames.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["rank"] + cols)
        for n, p in enumerate(picked, 1):
            w.writerow(
                [n]
                + [
                    ",".join(p[c])
                    if c == "flip"
                    else round(p[c], 3)
                    if isinstance(p[c], float)
                    else p[c]
                    for c in cols
                ]
            )
    allk = collections.Counter((c["split"], c["kind"]) for C in cand.values() for c in C)
    print("후보 장수(종류별):", dict(sorted(allk.items())))
    print(
        "고른 장수:",
        len(picked),
        dict(collections.Counter((p["split"], p["reason"]) for p in picked)),
    )
    for dog in sorted({p["dog"] for p in picked}):
        P = [p for p in picked if p["dog"] == dog]
        print(
            f"  {P[0]['split']:5s} {dog:5s} {len(P):2d}장  {dict(collections.Counter(p['reason'] for p in P))}"
        )
    if args.make:
        import cv2

        want = collections.defaultdict(dict)
        for p in picked:
            want[p["video"]][p["frame"]] = p["split"]
        for v, frames in want.items():
            # HEVC 는 건너뛰어 읽으면 프레임이 어긋날 수 있어 처음부터 차례로 읽는다(정답 frame_idx 와 같은 번호)
            cap = cv2.VideoCapture(str(POOL / "videos" / f"{v}.mp4"))
            i = 0
            while frames and i <= max(frames):
                ok, fr = cap.read()
                if not ok:
                    break
                if i in frames:
                    d = FRAMES / f"batch1-{frames[i]}"
                    d.mkdir(parents=True, exist_ok=True)
                    cv2.imencode(".jpg", fr)[1].tofile(str(d / f"{v}_f{i:06d}.jpg"))
                i += 1
        print(
            "프레임 저장:",
            {s: len(list((FRAMES / f"batch1-{s}").glob("*.jpg"))) for s in ("train", "val")},
        )


if __name__ == "__main__":
    main()
