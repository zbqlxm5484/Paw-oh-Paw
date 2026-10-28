"""화면 끝에 걸친 가는 헛상자를 거르는 후처리 시험(10-22). 기업 도구는 안 건드린다.

    python edge_filter.py --track in.track.json --out out.track.json [--ratio 0.25] [--conf 0.30]

상자가 화면 왼쪽·오른쪽 끝에 닿고, 폭/높이가 ratio 미만이고, 관절점 확신도 평균이 conf 미만이면 그 프레임을
'개 없음'(None)으로 바꾼다. 가벼운 탐지기를 낮은 점수 문턱(0.08)으로 쓸 때 사람 다리 같은 헛것을 빼려는 것이다.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
EDGE_PX = 2  # video_kpi 와 같은 기준


def is_sliver(f, width, ratio, conf):
    x1, y1, x2, y2 = f["box"][:4]
    edge = x1 <= EDGE_PX or x2 >= width - EDGE_PX
    thin = (x2 - x1) / max(1.0, y2 - y1) < ratio
    weak = statistics.mean(k[2] for k in f["kp"]) < conf
    return edge and thin and weak


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ratio", type=float, default=0.25)
    ap.add_argument("--conf", type=float, default=0.30)
    a = ap.parse_args()
    doc = json.loads(Path(a.track).read_text(encoding="utf-8"))
    n = 0
    for v in doc["videos"]:
        for i, f in enumerate(v["frames"]):
            if f is not None and is_sliver(f, v["width"], a.ratio, a.conf):
                v["frames"][i] = None
                n += 1
    doc["edge_filter"] = {"ratio": a.ratio, "conf": a.conf, "removed": n}
    Path(a.out).write_text(json.dumps(doc), encoding="utf-8")
    print(f"-> {a.out}  지운 프레임 {n}")


if __name__ == "__main__":
    main()
