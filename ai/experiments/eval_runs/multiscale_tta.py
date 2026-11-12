"""상자 크기를 바꿔 여러 번 추론하고 평균 내기(추론할 때 증강) 시험(10-22). 기업 도구는 안 건드린다.

    python multiscale_tta.py prep --gt <정답> --scales 0.9 1.1 --out-dir results/mstta    # 상자만 바꾼 정답 사본
    (predict.py 를 사본마다 돌린다)
    python multiscale_tta.py merge --preds a.preds.json b.preds.json ... --out merged.preds.json [--how mean|median]

상자는 가운데를 고정하고 너비·높이를 배율만큼 바꾼다. predict.py 는 정답의 상자만 쓰고 관절점 정답은 보지 않는다.
"""

import argparse
import copy
import json
import statistics
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def prep(a):
    gt = json.loads(Path(a.gt).read_text(encoding="utf-8"))
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for s in a.scales:
        d = copy.deepcopy(gt)
        for an in d["annotations"]:
            x, y, w, h = an["bbox"]
            cx, cy = x + w / 2, y + h / 2
            an["bbox"] = [cx - w * s / 2, cy - h * s / 2, w * s, h * s]
        p = out / f"gt_s{s}.json"
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        print("->", p)


def merge(a):
    docs = [json.loads(Path(p).read_text(encoding="utf-8")) for p in a.preds]
    by = [{r["ann_id"]: r for r in d["predictions"]} for d in docs]
    out = copy.deepcopy(docs[0])
    agg = statistics.mean if a.how == "mean" else statistics.median
    for r in out["predictions"]:
        ks = [b[r["ann_id"]]["keypoints"] for b in by]
        n = len(ks[0]) // 3
        kp = []
        for i in range(n):
            kp += [
                agg(k[3 * i] for k in ks),
                agg(k[3 * i + 1] for k in ks),
                statistics.mean(k[3 * i + 2] for k in ks),
            ]
        r["keypoints"] = kp
    out["meta"] = dict(out.get("meta", {}), multiscale_tta={"preds": a.preds, "how": a.how})
    Path(a.out).write_text(json.dumps(out), encoding="utf-8")
    print(f"-> {a.out} ({len(out['predictions'])} 예측, {len(docs)}개 {a.how})")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prep")
    p.add_argument("--gt", required=True)
    p.add_argument("--scales", type=float, nargs="+", required=True)
    p.add_argument("--out-dir", required=True)
    m = sub.add_parser("merge")
    m.add_argument("--preds", nargs="+", required=True)
    m.add_argument("--out", required=True)
    m.add_argument("--how", choices=["mean", "median"], default="mean")
    a = ap.parse_args()
    prep(a) if a.cmd == "prep" else merge(a)


if __name__ == "__main__":
    main()
