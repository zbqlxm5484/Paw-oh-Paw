"""보행 유형 판별 규칙(docs/engine/gaitTypeRules.md 3절)을 맞춰 볼 대상 158건(docs/engine/gaitTypeTargets.csv)의 트랙에 돌려
촬영 라벨(trot·pace·not_trot)과 맞춰 본다 (S15P31A404-284, 11-10).

    python ai/experiments/gait_type/verify_rules.py <트랙 파일> [--pace-tol 0.20] [--tol 0.12] [--r-min 0.7] [--walk-duty 0.50] [--out 판정.json]

- 트랙: 기업 video_kpi.py track 형식(fs-v4+flip 으로 뽑은 158건). 기업 데이터라 저장소에 두지 않는다.
- 통과 자르기·유효 판별은 engine.validity.judge_shot, 착지·이지는 engine.gait_events.detect_pass 를 그대로 쓴다.
- 판정은 유효 통과만 쓴다(지금 엔진은 GAIT_PACE 사유를 내지 않아 측대보 통과도 유효로 들어온다).
- 촬영 단위 결과는 판정된 통과의 다수결, 같은 수면 OTHER, 판정된 통과가 없으면 null.
"""
import argparse
import collections
import csv
import json
import math
import os
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8")
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)
from engine.gait_events import detect_pass  # noqa: E402
from engine.validity import inside_frames, judge_shot, load_config  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("track")
ap.add_argument("--tol", type=float, default=0.12, help="속보 위상 허용 폭(0.5 ± tol)")
ap.add_argument("--pace-tol", type=float, default=0.12, help="측대보 위상 허용 폭(0 ± pace-tol)")
ap.add_argument("--r-min", type=float, default=0.7, help="위상 일관성 R 최소")
ap.add_argument("--walk-duty", type=float, default=0.50, help="평보 디딤 비율 최소")
ap.add_argument("--out", help="촬영별 판정 JSON")
a = ap.parse_args()


def classify(ev: dict, fps: float):
    """통과 하나 → (유형 또는 None, 근거). 규칙 문서 3절 표 그대로"""
    if fps < 20 or not ev:
        return None, {}
    front, hind = ev.get("front"), ev.get("hind")
    if not front or not hind:
        return None, {}
    ftd = sorted(front.touchdowns())
    phases = []
    for s in hind.strides:
        nxt = [x for x in ftd if s.start <= x < s.end]
        if nxt:
            phases.append((nxt[0] - s.start) / (s.end - s.start))
    if len(phases) < 2:
        return None, {"n": len(phases)}
    c = sum(math.cos(2 * math.pi * p) for p in phases) / len(phases)
    sn = sum(math.sin(2 * math.pi * p) for p in phases) / len(phases)
    r = math.hypot(c, sn)
    mean = (math.atan2(sn, c) / (2 * math.pi)) % 1
    duty = [s.stance_ratio for s in list(front.strides) + list(hind.strides)]
    d = statistics.median(duty) if duty else 0.0
    info = {"phi": round(mean, 3), "R": round(r, 2), "D": round(d, 2), "n": len(phases)}
    if r < a.r_min:
        return "OTHER", info
    if min(mean, 1 - mean) <= a.pace_tol:
        return "PACE", info
    if abs(mean - 0.5) <= a.tol:
        return "TROT", info
    if (0.15 <= mean <= 0.40 or 0.60 <= mean <= 0.85) and d >= a.walk_duty:
        return "WALK", info
    return "OTHER", info


rows = list(csv.DictReader(open(os.path.join(REPO, "docs", "engine", "gaitTypeTargets.csv"), encoding="utf-8-sig")))
data = json.load(open(a.track, encoding="utf-8"))
cfg = load_config()
by_label = collections.defaultdict(collections.Counter)
per_pass = collections.defaultdict(list)
detail = []
for row in rows:
    votes = collections.Counter()
    for v in (v for v in data["videos"] if row["stamp"] in os.path.basename(v["video"])):
        for p in judge_shot(v, cfg)["passes"]:
            if not p["valid"]:
                continue
            _, kps = inside_frames(v, p["start_frame"], p["end_frame"], cfg)
            g, info = classify(detect_pass(kps, v["fps"], p["camera_side"]), v["fps"])
            per_pass[row["label"]].append((g, info))
            if g:
                votes[g] += 1
    top = votes.most_common()
    shot = "null" if not top else top[0][0] if len(top) == 1 or top[0][1] > top[1][1] else "OTHER"
    group = "trot(dogA)" if row["label"] == "trot" and row["dog"] == "dogA" else row["label"]
    by_label[group][shot] += 1
    detail.append({"stamp": row["stamp"], "dog": row["dog"], "label": row["label"], "shot": shot, "passes": dict(votes)})

print(f"기준: 속보 ±{a.tol} · 측대보 ±{a.pace_tol} · R≥{a.r_min} · 평보 디딤≥{a.walk_duty}")
print("촬영 단위 (라벨 → 판정):")
for k in sorted(by_label):
    print(f"  {k}: {dict(by_label[k])}")
print("통과 단위:")
for lab, items in per_pass.items():
    ok = [i for _, i in items if "phi" in i]
    if ok:
        print(f"  {lab}: 통과 {len(items)} · 판정 가능 {len(ok)} · φ 중앙 {statistics.median(i['phi'] for i in ok):.2f}"
              f" · R 중앙 {statistics.median(i['R'] for i in ok):.2f} · D 중앙 {statistics.median(i['D'] for i in ok):.2f}"
              f" · {dict(collections.Counter(g for g, _ in items))}")
if a.out:
    json.dump(detail, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
