"""회차 하나(같은 날 같은 개의 촬영들)를 팀 서비스처럼 묶어 보고, 수치가 서로 맞는지 본다. S15P31A404-261

실제 영상 검증(docs/engine/sessionCheckJenny1.md)을 다시 돌리는 도구다. 결과 JSON을 만들지 않고 엔진 함수만 부른다.

- 회차 값: 다리(카메라 쪽)별로 유효 통과 값의 중앙값(백엔드 명세 12.5 회차 값과 같음). 통과 사이 변동계수(CV)도 낸다
- 속보 위상 밖 통과: 같은 쪽 앞·뒷발 위상(validity.lateral_phase)이 0.35보다 작은 통과. 보행 유형 판별이 없어
  지금은 회차 값에 섞인다(gait가 null)
- 걸음 길이와 보행 속도의 맞음: 일정한 속도로 걸으면 걸음 길이 = 보행 속도 × 한 주기 시간이다. 그 비율의 중앙값
- 발 높이: 들림이 하나뿐인 통과 수와, 들림 안에서 가장 높은 프레임과 그다음 프레임의 차(튄 점 하나가 값을 정하는지)

    python -m engine.session_check data/tracks/fs-v4.track.json
"""
import statistics
from collections import defaultdict
from typing import Optional

from engine.gait_events import _point, body_length, detect_pass
from engine.gait_metrics import pass_metrics, stance_position
from engine.joint_rom import joint_metrics
from engine.validity import inside_frames, judge_shot, lateral_phase, load_config

TROT_PHASE_MIN = 0.35       # 이보다 작으면 속보 위상 밖(측대보 0, 평보 0.25, 속보 0.5)
KEYS = ("stride_length_front", "stride_length_hind", "stance_ratio_front", "stance_ratio_hind",
        "paw_lift_front", "paw_lift_hind", "walk_speed",
        "rom_shoulder", "rom_elbow", "rom_carpus", "rom_hip", "rom_stifle", "rom_tarsus")


def swing_peaks(frames, events, length) -> list:
    """들림마다 (가장 높은 높이, 그다음 높이) L 대비 %. engine.gait_metrics.paw_lifts와 같은 들림·같은 땅 높이"""
    out = []
    for a, b in zip(events.stances, events.stances[1:]):
        if a.liftoff is None or b.touchdown is None:
            continue
        pa = stance_position(frames, events.slot, a.first_frame, a.last_frame)
        pb = stance_position(frames, events.slot, b.first_frame, b.last_frame)
        if not (pa and pb):
            continue
        span = b.first_frame - a.last_frame
        heights = sorted((pa[1] + (pb[1] - pa[1]) * (i - a.last_frame) / span - p[1]
                          for i in range(a.last_frame + 1, b.first_frame)
                          if (p := _point(frames[i], events.slot))), reverse=True)
        if len(heights) >= 2:
            out.append((heights[0] / length * 100, heights[1] / length * 100))
    return out


def check_pass(video: dict, p: dict, cfg: dict) -> dict:
    """유효 통과 하나의 수치와 검증용 값"""
    _, kps = inside_frames(video, p["start_frame"], p["end_frame"], cfg)
    fps, side = video["fps"], p["camera_side"]
    events = detect_pass(kps, fps, side)
    metrics = {**pass_metrics(kps, fps, side, events), **joint_metrics(kps, fps, side, events)}
    length = body_length(kps)
    ratio = {}
    for paw, e in events.items():
        stride = metrics[f"stride_length_{paw}"].get("value")
        if stride and e.strides and metrics["walk_speed"].get("value"):
            cycle_s = statistics.median((s.end - s.start) / fps for s in e.strides)
            ratio[paw] = stride / (metrics["walk_speed"]["value"] * cycle_s * 100)
    return {
        "side": side, "phase": lateral_phase(events),
        "metrics": metrics, "stride_speed_ratio": ratio,
        "swings": {paw: swing_peaks(kps, e, length) if length else [] for paw, e in events.items()},
    }


def cv(xs) -> Optional[float]:
    return statistics.stdev(xs) / statistics.mean(xs) * 100 if len(xs) >= 2 and statistics.mean(xs) else None


def check_session(data: dict, cfg: Optional[dict] = None) -> dict:
    cfg = cfg or load_config()
    passes, invalid = [], {}
    for video in data["videos"]:
        r = judge_shot(video, cfg)
        if r["validity"] != "valid":
            invalid[video["video"]] = r["validity_reason"]
        passes += [dict(check_pass(video, p, cfg), video=video["video"]) for p in r["passes"] if p["valid"]]

    by_side = defaultdict(list)
    for p in passes:
        by_side[p["side"]].append(p)
    session = {}
    for side, ps in by_side.items():
        for key in KEYS:
            xs = [p["metrics"][key]["value"] for p in ps if p["metrics"][key].get("value") is not None]
            session[(side, key)] = {"n": len(xs), "median": statistics.median(xs) if xs else None, "cv": cv(xs)}
    ratios = [r for p in passes for r in p["stride_speed_ratio"].values()]
    peaks = [(paw, pk) for p in passes for paw, sw in p["swings"].items() for pk in sw]
    return {
        "videos": len(data["videos"]), "invalid": invalid, "passes": len(passes),
        "by_side": {side: len(ps) for side, ps in by_side.items()},
        "off_trot": [(p["video"], round(p["phase"], 2)) for p in passes
                     if p["phase"] is not None and p["phase"] < TROT_PHASE_MIN],
        "session": session,
        "stride_speed_ratio": statistics.median(ratios) if ratios else None,
        "single_swing": {paw: sum(1 for p in passes if len(p["swings"][paw]) == 1) for paw in ("front", "hind")},
        "peak_gap": sorted(a - b for _, (a, b) in peaks),
    }


def main(argv=None) -> None:
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="회차 묶음 검증 (docs/engine/sessionCheckJenny1.md)")
    parser.add_argument("track", help="관절점 파일 (*.track.json)")
    args = parser.parse_args(argv)
    s = check_session(json.loads(Path(args.track).read_text(encoding="utf-8")))
    print(f"영상 {s['videos']}개, 무효 {len(s['invalid'])}개 {s['invalid']}, 유효 통과 {s['passes']}개 {s['by_side']}")
    print(f"속보 위상 밖 통과(위상 < {TROT_PHASE_MIN}): {s['off_trot']}")
    for (side, key), v in sorted(s["session"].items()):
        med = "-" if v["median"] is None else f"{v['median']:7.1f}"
        var = "-" if v["cv"] is None else f"{v['cv']:5.1f}%"
        print(f"  {side:5s} {key:22s} n={v['n']:2d} 회차 값 {med}  통과 사이 CV {var}")
    if s["stride_speed_ratio"]:
        print(f"걸음 길이 ÷ (보행 속도 × 주기 시간) 중앙값 {s['stride_speed_ratio']:.2f}")
    gaps = s["peak_gap"]
    if gaps:
        print(f"들림 하나뿐인 통과: {s['single_swing']}, 가장 높은 프레임 − 그다음(L 대비 %): "
              f"중앙값 {statistics.median(gaps):.1f}, 최대 {max(gaps):.1f}")


if __name__ == "__main__":
    main()
