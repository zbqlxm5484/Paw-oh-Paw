"""보행 수치: 걸음 길이·입각기 비율·보행 속도·보행 주기 수 (F-02, PR-F02-05). S15P31A404-183

통과 하나의 카메라 쪽 앞발·뒷발 착지·이지(engine/gait_events.py)에서 계산한다. 결과 JSON v1 3절의 키와 단위로 낸다.

- 걸음 길이(stride_length): 같은 발이 연달아 디딘 두 자리 사이 거리. 한 주기 동안 그 발이 나아간 거리다.
  디딤 동안 발끝은 거의 움직이지 않으므로, 디딤 구간 발끝 위치의 중앙값을 그 디딤의 자리로 쓴다(한 프레임보다 흔들림이 적다)
- 입각기 비율(stance_ratio): 한 주기(착지에서 다음 착지까지) 중 발이 땅에 닿아 있는 시간의 비율
- 보행 속도(walk_speed): 몸통 가운데(T13과 장골능의 가운데) 속도의 중앙값
- 보행 주기 수(gait_cycles): 앞발·뒷발 중 주기를 더 많이 잰 쪽의 주기 수

거리는 몸통 길이 L(T13과 장골능 사이 거리, 명세서 용어 정의)로 나눈다. pct_body는 L 대비 %, body_per_sec는 L/초다.
통과 하나의 값은 주기들의 중앙값이다. 회차 값(통과들의 중앙값)은 팀 서비스가 낸다.

측정 불가는 0이 아니라 {"value": null, "reason"}로 낸다(PR-F02-05).
- LOW_CONFIDENCE: 몸이 보인 프레임 중 그 발끝 관절점을 믿을 만한 프레임이 절반이 안 됨
- NOT_ENOUGH_CYCLES: 발끝은 보였지만 착지를 두 번 이어서 보지 못해 주기가 없음

입력은 유효 판별과 같은 프레임(engine/validity.py inside_frames: 몸 전체가 화면 안에 보인 프레임만)이다.
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

    speed = trunk_speed(frames, fps, length)
    out["walk_speed"] = _value(speed, "body_per_sec", 2) if speed is not None else _missing("LOW_CONFIDENCE")
    out["gait_cycles"] = {"value": cycles, "unit": "count"}
    return out
