import argparse
import json
import statistics
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def center(b):
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def size(b):
    return max(b[2] - b[0], b[3] - b[1])


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def step_motion(videos):
    out = []
    for v in videos:
        fr = v["frames"]
        for i in range(1, len(fr)):
            a, b = fr[i - 1], fr[i]
            if a is None or b is None:
                continue
            ca, cb = center(a["box"]), center(b["box"])
            d = ((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2) ** 0.5
            out.append(d / size(b["box"]))
    return out


def interp_error(videos, k):
    ious, shifts, per_video = [], [], []
    for v in videos:
        fr = v["frames"]
        n = len(fr)
        keys = sorted(set(range(0, n, k)) | {n - 1})
        v_ious = []
        for a, b in zip(keys, keys[1:]):
            if b - a <= 1 or fr[a] is None or fr[b] is None:
                continue
            for j in range(a + 1, b):
                if fr[j] is None:
                    continue
                t = (j - a) / (b - a)
                box = [(1 - t) * fr[a]["box"][m] + t * fr[b]["box"][m] for m in range(4)]
                actual = fr[j]["box"]
                v_ious.append(iou(box, actual))
                cp, ca = center(box), center(actual)
                shifts.append((((cp[0] - ca[0]) ** 2 + (cp[1] - ca[1]) ** 2) ** 0.5) / size(actual))
        ious += v_ious
        if v_ious:
            per_video.append((statistics.mean(v_ious), v["video"]))
    return ious, shifts, per_video


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--ks", default="2,3,4,5,6,8")
    a = ap.parse_args()
    videos = json.loads(Path(a.track).read_text(encoding="utf-8"))["videos"]
    det = sum(1 for v in videos for f in v["frames"] if f is not None)
    tot = sum(len(v["frames"]) for v in videos)
    print(f"영상 {len(videos)}개, 프레임 {tot}개 중 개가 잡힌 프레임 {det}개 ({100 * det / tot:.1f}%)")
    steps = step_motion(videos)
    print(f"\n연속한 두 프레임 사이 상자 중심 이동(상자 큰 변 대비) n={len(steps)}")
    print(f"  중앙값 {statistics.median(steps):.3f}  p90 {pct(steps, .9):.3f}  p99 {pct(steps, .99):.3f}  최대 {max(steps):.3f}")
    print("\nK별 보간 상자 오차 (실제 탐지 상자와 비교)")
    print("K | 평가 프레임 | IoU 평균 | IoU 중앙값 | IoU 하위10% | IoU<0.8 비율 | 중심 오차 중앙값 | 중심 오차 p90")
    worst = {}
    for k in [int(x) for x in a.ks.split(",")]:
        ious, shifts, per = interp_error(videos, k)
        if not ious:
            continue
        low = sum(1 for x in ious if x < 0.8) / len(ious)
        print(f"{k} | {len(ious)} | {statistics.mean(ious):.3f} | {statistics.median(ious):.3f} | {pct(ious, .1):.3f} | {100 * low:.1f}% | {statistics.median(shifts):.3f} | {pct(shifts, .9):.3f}")
        worst[k] = sorted(per)[:3]
    print("\nK별 보간이 가장 나빴던 영상 3개 (영상 평균 IoU)")
    for k, w in worst.items():
        print(f"K={k}: " + ", ".join(f"{s:.3f} {name[:24]}" for s, name in w))


if __name__ == "__main__":
    main()
