"""착지·이지 검출 정답 대조 (S15P31A404-160, KPI-05).

사람이 영상에서 표시한 착지·이지 프레임(정답 CSV)과 engine.gait_events의 검출 결과를 비교한다.

    python -m engine.gait_eval --track fs-v4-flip.track.json --gt gait_gt.csv [--out result.json]

- 관절점은 기업 video_kpi.py track 결과 형식(영상마다 fps와 프레임별 {box, kp} 또는 null)을 읽는다
- 정답 CSV 열: video, paw(front|hind), event(touchdown|liftoff), frame, marker
  영상 이름은 track의 video 값과 같게 쓴다. 표시 방법은 docs/engine/gaitEventsGT.md
- 영상 하나를 통과 하나로 보고, 카메라 쪽은 프레임 판정의 다수결로 정한다 (제니 main 영상은 통과가 하나)
- 정답을 표시한 범위(첫 표시 - 여유 ~ 마지막 표시 + 여유) 밖의 검출은 세지 않는다. 사람이 표시하지 않은
  구간의 검출을 "잘못 찾음"으로 세지 않기 위해서다

내는 값 (앞발·뒷발, 착지·이지별)
- 맞힘 비율: 정답 중 MATCH_S 안에 검출이 있는 비율
- 오차 중앙값: 맞힌 것의 |검출 - 정답| 프레임과 밀리초. KPI-05 목표는 60fps 기준 2프레임(33ms) 이하
- 더 찾음: 정답 범위 안에서 짝이 없는 검출 수
- 표시자가 둘 이상이면 표시자끼리 차이(사람 사이 오차)도 낸다

정답 CSV는 기업 영상에서 나온 자료라 저장소에 올리지 않는다.
"""
import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from engine.camera_side import pass_side
from engine.gait_events import EVENTS_VERSION, detect_pass

MATCH_S = 0.1          # 정답과 이 시간 안의 검출만 짝으로 본다
MARGIN_S = 0.2         # 정답 표시 범위 앞뒤 여유
KPI05_MS = 1000 / 60 * 2   # 60fps 기준 2프레임
FPS_SLACK_MS = 0.5         # 30fps(29.99)의 1프레임 33.34ms가 반올림 때문에 미달로 나오지 않게

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def load_track(path: Path) -> dict:
    """영상 이름 → (fps, 프레임별 22점 또는 None)"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for v in data["videos"]:
        name = Path(v["video"]).name
        out[name] = (float(v["fps"]), [f["kp"] if f else None for f in v["frames"]])
    return out


def load_gt(path: Path) -> dict:
    """(영상, 발, 사건) → 표시자 → 정렬된 프레임 목록"""
    gt = defaultdict(lambda: defaultdict(list))
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if not row.get("video") or row["video"].startswith("#"):
                continue
            key = (Path(row["video"].strip()).name, row["paw"].strip(), row["event"].strip())
            gt[key][(row.get("marker") or "").strip()].append(int(row["frame"]))
    for markers in gt.values():
        for frames in markers.values():
            frames.sort()
    return gt


def match(truth: list, found: list, tol: int) -> tuple:
    """가까운 쌍부터 하나씩 짝짓는다 → (오차 목록(검출 - 정답), 짝 없는 정답 수, 짝 없는 검출 수)"""
    pairs = sorted((abs(f - t), i, j) for i, t in enumerate(truth) for j, f in enumerate(found)
                   if abs(f - t) <= tol)
    used_t, used_f, errors = set(), set(), []
    for _, i, j in pairs:
        if i in used_t or j in used_f:
            continue
        used_t.add(i)
        used_f.add(j)
        errors.append(found[j] - truth[i])
    return errors, len(truth) - len(used_t), len(found) - len(used_f)


def detect_video(fps: float, frames: list) -> dict:
    side = pass_side([f for f in frames if f])
    if side is None:
        return {}
    events = detect_pass(frames, fps, side)
    return {(paw, "touchdown"): e.touchdowns() for paw, e in events.items()} | \
           {(paw, "liftoff"): e.liftoffs() for paw, e in events.items()}


def evaluate(track: dict, gt: dict) -> dict:
    rows = defaultdict(lambda: {"n": 0, "hit": 0, "extra": 0, "errors_ms": [], "errors_frames": []})
    human = defaultdict(list)
    missing = sorted({v for v, _, _ in gt if v not in track})
    detected = {}
    for (video, paw, event), markers in sorted(gt.items()):
        if video not in track:
            continue
        fps, frames = track[video]
        if video not in detected:
            detected[video] = detect_video(fps, frames)
        found_all = detected[video].get((paw, event), [])
        tol = max(1, round(MATCH_S * fps))
        margin = round(MARGIN_S * fps)
        names = sorted(markers)
        truth = markers[names[0]]                      # 첫 표시자를 정답으로
        lo, hi = truth[0] - margin, truth[-1] + margin
        found = [f for f in found_all if lo <= f <= hi]
        errors, missed, extra = match(truth, found, tol)
        r = rows[(paw, event)]
        r["n"] += len(truth)
        r["hit"] += len(truth) - missed
        r["extra"] += extra
        r["errors_frames"] += [abs(e) for e in errors]
        r["errors_ms"] += [abs(e) * 1000 / fps for e in errors]
        for other in names[1:]:                         # 사람끼리 차이
            errs, _, _ = match(truth, markers[other], tol)
            human[(paw, event)] += [abs(e) * 1000 / fps for e in errs]

    def summary(r):
        med = statistics.median(r["errors_ms"]) if r["errors_ms"] else None
        return {
            "n": r["n"],
            "hit_rate": round(r["hit"] / r["n"], 3) if r["n"] else None,
            "median_error_frames": statistics.median(r["errors_frames"]) if r["errors_frames"] else None,
            "median_error_ms": round(med, 1) if med is not None else None,
            "kpi05_ok": med is not None and med <= KPI05_MS + FPS_SLACK_MS,
            "extra": r["extra"],
        }

    return {
        "events_version": EVENTS_VERSION,
        "match_s": MATCH_S,
        "rows": {f"{paw}/{event}": summary(r) for (paw, event), r in sorted(rows.items())},
        "human_median_ms": {f"{paw}/{event}": round(statistics.median(v), 1)
                            for (paw, event), v in sorted(human.items()) if v},
        "videos_without_track": missing,
    }


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="착지·이지 검출 정답 대조 (KPI-05)")
    ap.add_argument("--track", required=True, type=Path)
    ap.add_argument("--gt", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    res = evaluate(load_track(a.track), load_gt(a.gt))
    print(f"gait_events {res['events_version']} · 짝 기준 ±{res['match_s']}초 · KPI-05 목표 {KPI05_MS:.0f}ms 이하")
    print(f"{'구분':<18}{'정답':>6}{'맞힘':>8}{'오차(프레임)':>14}{'오차(ms)':>10}{'더 찾음':>8}  KPI-05")
    for name, r in res["rows"].items():
        ok = "통과" if r["kpi05_ok"] else "미달"
        print(f"{name:<18}{r['n']:>6}{r['hit_rate']:>8}{str(r['median_error_frames']):>14}"
              f"{str(r['median_error_ms']):>10}{r['extra']:>8}  {ok}")
    if res["human_median_ms"]:
        print("사람 사이 차이(ms):", res["human_median_ms"])
    if res["videos_without_track"]:
        print("track에 없는 영상:", ", ".join(res["videos_without_track"]))
    if a.out:
        a.out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print("->", a.out)


if __name__ == "__main__":
    main()
