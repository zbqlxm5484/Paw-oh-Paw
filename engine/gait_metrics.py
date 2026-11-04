"""보행 수치: 걸음 길이·입각기 비율·보행 속도·보행 주기 수 (F-02, PR-F02-05). S15P31A404-183

통과 하나의 카메라 쪽 앞발·뒷발 착지·이지(engine/gait_events.py)에서 계산한다. 결과 JSON v1 3절의 키와 단위로 낸다.

- 걸음 길이(stride_length): 같은 발이 연달아 디딘 두 자리 사이 거리. 한 주기 동안 그 발이 나아간 거리다.
  디딤 동안 발끝은 거의 움직이지 않으므로, 디딤 구간 발끝 위치의 중앙값을 그 디딤의 자리로 쓴다(한 프레임보다 흔들림이 적다)
- 입각기 비율(stance_ratio): 한 주기(착지에서 다음 착지까지) 중 발이 땅에 닿아 있는 시간의 비율
- 보행 속도(walk_speed): 측정 구간(첫 착지부터 마지막 이지) 안에서 몸통 가운데(T13과 장골능의 가운데) 속도의 중앙값.
  착지를 못 찾으면 몸이 보인 프레임 전체로 잰다
- 보행 주기 수(gait_cycles): 앞발·뒷발 중 주기를 더 많이 잰 쪽의 주기 수

거리는 몸통 길이 L(T13과 장골능 사이 거리, 명세서 용어 정의)로 나눈다. pct_body는 L 대비 %, body_per_sec는 L/초다.
통과 하나의 값은 주기들의 중앙값이다. 회차 값(통과들의 중앙값)은 팀 서비스가 낸다.

측정 불가는 0이 아니라 {"value": null, "reason"}로 낸다(PR-F02-05).
- LOW_CONFIDENCE: 몸이 보인 프레임 중 그 발끝 관절점을 믿을 만한 프레임이 절반이 안 됨
- NOT_ENOUGH_CYCLES: 발끝은 보였지만 착지를 두 번 이어서 보지 못해 주기가 없음

입력은 유효 판별과 같은 프레임(engine/validity.py inside_frames: 몸 전체가 화면 안에 보인 프레임만)이다.
걸음 길이·입각기 비율은 착지와 다음 착지 사이 주기로 재므로 저절로 측정 구간 안이다(결과 형식 2절 measure_start·measure_end).

실제 관절점으로 한 번에 재 보기(저장소 루트, 관절점 파일은 data/ 아래, git에 올리지 않음):
    python -m engine.gait_metrics data/tracks/fs-v4.track.json
"""
import statistics
from typing import Optional, Sequence

from engine.gait_events import (
    CONF,
    PAWS,
    Frame,
    PawEvents,
    _point,
    body_length,
    detect_pass,
    trunk_speed,
)

METRICS_VERSION = "v1"
MIN_PAW_SEEN = 0.5          # 몸이 보인 프레임 중 발끝을 믿을 만한 프레임 비율이 이보다 작으면 LOW_CONFIDENCE


def _value(value: float, unit: str, places: int = 1) -> dict:
    return {"value": round(value, places), "unit": unit}


def _missing(reason: str) -> dict:
    return {"value": None, "reason": reason}


def stance_position(frames: Sequence[Frame], slot: int, first: int, last: int) -> Optional[tuple]:
    """디딤 구간의 발끝 자리: 믿을 만한 발끝 좌표의 중앙값"""
    points = [p for p in (_point(frames[i], slot) for i in range(first, last + 1)) if p]
    if not points:
        return None
    return statistics.median(p[0] for p in points), statistics.median(p[1] for p in points)


def stride_lengths(frames: Sequence[Frame], events: PawEvents, length: float) -> list:
    """주기마다 걸음 길이(L 대비 %). 착지를 두 번 이어서 본 주기만 (gait_events의 Stride와 같은 짝)"""
    out = []
    for a, b in zip(events.stances, events.stances[1:]):
        if a.touchdown is None or b.touchdown is None:
            continue
        pa = stance_position(frames, events.slot, a.first_frame, a.last_frame)
        pb = stance_position(frames, events.slot, b.first_frame, b.last_frame)
        if pa and pb:
            out.append(((pb[0] - pa[0]) ** 2 + (pb[1] - pa[1]) ** 2) ** 0.5 / length * 100)
    return out


def stance_ratios(events: PawEvents) -> list:
    """주기마다 입각기 비율(%)"""
    return [s.stance_ratio * 100 for s in events.strides]


def paw_seen_ratio(frames: Sequence[Frame], slot: int, conf: float = CONF) -> float:
    """몸이 보인 프레임 중 발끝 관절점을 믿을 만한 프레임의 비율"""
    body = [f for f in frames if f is not None]
    if not body:
        return 0.0
    return sum(_point(f, slot, conf) is not None for f in body) / len(body)


def pass_metrics(frames: Sequence[Frame], fps: float, camera_side: str,
                 events: Optional[dict] = None) -> dict:
    """통과 하나의 보행 수치. 결과 JSON v1 passes[].metrics에 그대로 넣는 모양

    frames: 통과 구간의 프레임별 22점(몸 전체가 안 보인 프레임은 None). events를 주면 착지 검출을 다시 하지 않는다
    """
    length = body_length(frames)
    if not length or fps <= 0:
        out = {f"{name}_{paw}": _missing("LOW_CONFIDENCE")
               for name in ("stride_length", "stance_ratio") for paw in ("front", "hind")}
        out["walk_speed"] = _missing("LOW_CONFIDENCE")
        out["gait_cycles"] = {"value": 0, "unit": "count"}
        return out

    events = events if events is not None else detect_pass(frames, fps, camera_side)
    out, cycles = {}, 0
    for paw, slot in PAWS[camera_side].items():
        paw_events = events.get(paw) or PawEvents(paw=paw, slot=slot)
        lengths = stride_lengths(frames, paw_events, length)
        ratios = stance_ratios(paw_events)
        cycles = max(cycles, len(ratios))
        if paw_seen_ratio(frames, slot) < MIN_PAW_SEEN:
            reason = "LOW_CONFIDENCE"
        else:
            reason = "NOT_ENOUGH_CYCLES"
        out[f"stride_length_{paw}"] = (_value(statistics.median(lengths), "pct_body") if lengths
                                       else _missing(reason))
        out[f"stance_ratio_{paw}"] = (_value(statistics.median(ratios), "pct") if ratios
                                      else _missing(reason))

    tds = [t for e in events.values() for t in e.touchdowns()]
    los = [t for e in events.values() for t in e.liftoffs()]
    measured = frames[min(tds):max(los) + 1] if tds and los and max(los) > min(tds) else frames
    speed = trunk_speed(measured, fps, length)
    out["walk_speed"] = _value(speed, "body_per_sec", 2) if speed is not None else _missing("LOW_CONFIDENCE")
    out["gait_cycles"] = {"value": cycles, "unit": "count"}
    return out


def summarize_track(path: str, metrics_fn=None) -> dict:
    """관절점 파일(기업 video_kpi.py track 형식)의 유효 통과마다 수치를 내고, 키마다 값 목록과 측정 불가 사유 수를 모은다.
    metrics_fn(frames, fps, camera_side)를 주면 그 함수로 잰다(가동 범위: engine.joint_rom.joint_metrics)"""
    import json
    from collections import Counter, defaultdict
    from pathlib import Path

    from engine.validity import inside_frames, judge_shot, load_config

    metrics_fn = metrics_fn or pass_metrics
    cfg = load_config()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    values, missing, passes = defaultdict(list), Counter(), 0
    for video in data["videos"]:
        for p in judge_shot(video, cfg)["passes"]:
            if not p["valid"]:
                continue
            passes += 1
            _, kps = inside_frames(video, p["start_frame"], p["end_frame"], cfg)
            for key, item in metrics_fn(kps, video["fps"], p["camera_side"]).items():
                if item.get("values"):          # 주기별 값 목록 (stifle_cycle_rom)
                    values[key].extend(item["values"])
                elif item.get("value") is None:
                    missing[(key, item["reason"])] += 1
                else:
                    values[key].append(item["value"])
    return {"videos": len(data["videos"]), "valid_passes": passes, "values": dict(values), "missing": dict(missing)}


def main(argv=None, metrics_fn=None, doc="docs/engine/gaitMetrics.md 4절") -> None:
    import argparse

    parser = argparse.ArgumentParser(description=f"관절점 파일의 유효 통과 수치 요약 ({doc})")
    parser.add_argument("track", help="관절점 파일 (*.track.json)")
    args = parser.parse_args(argv)
    s = summarize_track(args.track, metrics_fn)
    print(f"영상 {s['videos']}개, 유효 통과 {s['valid_passes']}개")
    for key, xs in sorted(s["values"].items()):
        print(f"  {key:22s} n={len(xs):3d} 중앙값 {statistics.median(xs):7.2f}  최소 {min(xs):7.2f}  최대 {max(xs):7.2f}")
    for (key, reason), count in sorted(s["missing"].items()):
        print(f"  {key:22s} 측정 불가 {reason} {count}")


if __name__ == "__main__":
    main()
