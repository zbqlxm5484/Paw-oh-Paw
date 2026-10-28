"""lr_fix.py 의 영상 좌우 바로잡기를 track 파일 전체에 적용한다(10-22, KPI-24 측정용).

    python lr_fix_track.py --track results/fs-v4.track.json --out results/fs-v4.lrfix0.02.track.json [--penalty 0.02] [--gap 3]

영상마다 앞다리·뒷다리를 따로 비터비로 '그대로 / 좌우 바꿈' 상태를 고르고, '바꿈' 프레임의 다리를 맞바꿔 쓴다.
결과는 video_kpi.py score 에 그대로 넣는다.
"""

import argparse
import json
import sys
from pathlib import Path

from lr_fix import LEG_SETS, viterbi

sys.stdout.reconfigure(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--penalty", type=float, default=0.02)
    ap.add_argument("--gap", type=int, default=3)
    ap.add_argument("--legs", choices=sorted(LEG_SETS), default="all")
    a = ap.parse_args()
    LEGS = LEG_SETS[a.legs]

    doc = json.loads(Path(a.track).read_text(encoding="utf-8"))
    changed = {name: 0 for name in LEGS}
    for v in doc["videos"]:
        ordered = [(f, r["kp"]) for f, r in enumerate(v["frames"]) if r is not None]
        for name, legs in LEGS.items():
            states = viterbi(ordered, legs, a.penalty, a.gap)
            for f, s in states.items():
                if s:
                    kp = v["frames"][f]["kp"]
                    for i, j in zip(*legs):
                        kp[i], kp[j] = kp[j], kp[i]
                    changed[name] += 1
    doc["lr_fix"] = {
        "legs": a.legs,
        "track": a.track,
        "penalty": a.penalty,
        "gap": a.gap,
        "swapped_frames": changed,
    }
    Path(a.out).write_text(json.dumps(doc), encoding="utf-8")
    print(f"-> {a.out}  바꾼 프레임: {changed}")


if __name__ == "__main__":
    main()
