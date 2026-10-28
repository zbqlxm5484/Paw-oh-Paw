"""lr_fix 후처리 시간(KPI-14 에 더할 몫): track 파일의 영상마다 앞·뒷다리 비터비를 돌린 시간.

python lr_fix_time.py --track results/gt_videos.fs-v4.track.json
"""

import argparse
import json
import statistics
import time
from pathlib import Path

from lr_fix import LEG_SETS, viterbi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--penalty", type=float, default=0.02)
    ap.add_argument("--gap", type=int, default=3)
    ap.add_argument("--legs", choices=sorted(LEG_SETS), default="all")
    a = ap.parse_args()
    LEGS = LEG_SETS[a.legs]
    times, frames = [], []
    for v in json.loads(Path(a.track).read_text(encoding="utf-8"))["videos"]:
        seq = [(f, r["kp"]) for f, r in enumerate(v["frames"]) if r is not None]
        t0 = time.perf_counter()
        for legs in LEGS.values():
            viterbi(seq, legs, a.penalty, a.gap)
        times.append(time.perf_counter() - t0)
        frames.append(len(v["frames"]))
    print(
        f"영상 {len(times)}개 · 프레임 중앙 {statistics.median(frames)} · 후처리 중앙 {statistics.median(times) * 1000:.1f}ms"
        f" · 최대 {max(times) * 1000:.1f}ms"
    )


if __name__ == "__main__":
    main()
