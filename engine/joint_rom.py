"""관절 가동 범위·각도 중앙값·무릎 주기별 가동 범위 (F-02, PR-F02-05). S15P31A404-184

카메라 쪽 다리 6관절(어깨·팔꿈치·앞발목, 고관절·무릎·뒷발목)의 굽힘 각도(engine/angles.py, angle_def v1, 0에서 360°)를
프레임마다 재고, 결과 JSON v1 3절의 키로 낸다.

- 가동 범위(rom_<관절>): 각도의 5백분위와 95백분위 사이 폭. 최솟값·최댓값 대신 백분위를 쓰는 건 관절점이 한두 프레임
  튀어도 값이 흔들리지 않게 하려는 것이다
- 각도 중앙값(angle_median_<관절>)
- 무릎 주기별 가동 범위(stifle_cycle_rom): 뒷발 주기마다 무릎 가동 범위. 팀 서비스가 회차의 주기들을 모아
  무릎 움직임 일관성(stifle_cv = 표본 표준편차 ÷ 평균 × 100)을 낸다

어느 프레임에서 재나: 그 다리 발의 **완전한 보행 주기**(착지에서 다음 착지까지, engine/gait_events.py) 안의 프레임만 쓴다.
앞다리 관절은 앞발 주기, 뒷다리 관절은 뒷발 주기다. 주기의 일부만 보면 관절이 덜 움직인 구간만 잡혀 가동 범위가 작게
나오기 때문이다. 그래서 주기를 못 잡은 통과는 NOT_ENOUGH_CYCLES다(docs/engine/gaitMetrics.md 4절: 통과당 주기는 많아야 1개).

측정 불가는 0이 아니라 {"value": null, "reason"}로 낸다(PR-F02-05).
- NOT_ENOUGH_CYCLES: 그 발의 주기가 없음
- LOW_CONFIDENCE: 주기 안 프레임 중 세 점(꼭짓점·근위·원위)을 모두 믿을 만한 프레임이 절반이 안 됨
"""
import statistics
from typing import Optional, Sequence

from engine.angles import FLEX_SIDE, JOINTS, flexion_angle
from engine.gait_events import CONF, Frame, detect_pass

ROM_VERSION = "v1"
LOW_PCT, HIGH_PCT = 5, 95       # 가동 범위 백분위 (결과 형식 3절)
MIN_ANGLE_SEEN = 0.5            # 주기 안 프레임 중 각도를 잰 프레임 비율이 이보다 작으면 LOW_CONFIDENCE

JOINT_NAMES = {"어깨": "shoulder", "팔꿈치": "elbow", "앞발목": "carpus",
               "고관절": "hip", "무릎": "stifle", "뒷발목": "tarsus"}
FORE = ("shoulder", "elbow", "carpus")
HIND = ("hip", "stifle", "tarsus")
RIGHT_SLOTS = {1, 8, 9, 10, 11, 12, 18, 19, 20, 21}   # 오른쪽 관절점 (세부명세서 6.5.3)


def _ok(p, conf: float = CONF) -> bool:
    return p is not None and len(p) >= 2 and (len(p) < 3 or p[2] >= conf)


def frame_angles(kp: Frame, camera_side: str, conf: float = CONF) -> dict:
    """카메라 쪽 다리 6관절의 굽힘 각도 {관절 영문 이름: 각도}. 세 점 중 하나라도 확신도가 낮으면 그 관절은 뺀다.
    머리 방향은 카메라 쪽과 같다(오른쪽을 보고 지나가면 오른쪽 다리가 카메라 쪽)"""
    if kp is None:
        return {}
    cranial = (1.0 if camera_side == "right" else -1.0, 0.0)
    out = {}
    for vertex, proximal, distal, name in JOINTS:
        if (vertex in RIGHT_SLOTS) != (camera_side == "right"):
            continue
        pts = (kp[vertex], kp[proximal], kp[distal])
        if not all(_ok(p, conf) for p in pts):
            continue
        angle = flexion_angle(pts[0][:2], pts[1][:2], pts[2][:2], cranial, FLEX_SIDE[name])
        if angle is not None:
            out[JOINT_NAMES[name]] = angle
    return out


def percentile_width(values: Sequence[float], low: float = LOW_PCT, high: float = HIGH_PCT) -> Optional[float]:
    """low 백분위와 high 백분위 사이 폭. 값이 2개 미만이면 None"""
    if len(values) < 2:
        return None
    q = statistics.quantiles(values, n=100, method="inclusive")   # q[k-1] = k백분위
    return q[high - 1] - q[low - 1]


def _missing(reason: str) -> dict:
    return {"value": None, "reason": reason}


def _cycle_frames(strides) -> list:
    """주기들에 든 프레임 번호 (착지부터 다음 착지 바로 전까지)"""
    return [i for s in strides for i in range(s.start, s.end)]


def joint_metrics(frames: Sequence[Frame], fps: float, camera_side: str,
                  events: Optional[dict] = None) -> dict:
    """통과 하나의 가동 범위·각도 중앙값·무릎 주기별 가동 범위. 결과 JSON v1 passes[].metrics에 그대로 넣는 모양

    frames: 통과 구간의 프레임별 22점(몸 전체가 안 보인 프레임은 None, engine/validity.py inside_frames).
    events를 주면 착지 검출을 다시 하지 않는다(engine/gait_metrics.py와 같은 결과를 쓰기 위해)
    """
    events = events if events is not None else detect_pass(frames, fps, camera_side)
    angles = [frame_angles(f, camera_side) for f in frames]
    out = {}
    for paw, joints in (("front", FORE), ("hind", HIND)):
        paw_events = events.get(paw)
        strides = paw_events.strides if paw_events else []
        idx = _cycle_frames(strides)
        for joint in joints:
            if not idx:
                out[f"rom_{joint}"] = out[f"angle_median_{joint}"] = _missing("NOT_ENOUGH_CYCLES")
                continue
            series = [angles[i][joint] for i in idx if joint in angles[i]]
            width = percentile_width(series)
            if len(series) < MIN_ANGLE_SEEN * len(idx) or width is None:
                out[f"rom_{joint}"] = out[f"angle_median_{joint}"] = _missing("LOW_CONFIDENCE")
                continue
            out[f"rom_{joint}"] = {"value": round(width, 1), "unit": "deg"}
            out[f"angle_median_{joint}"] = {"value": round(statistics.median(series), 1), "unit": "deg"}

    hind = events.get("hind")
    cycles = []
    for s in (hind.strides if hind else []):
        series = [angles[i]["stifle"] for i in range(s.start, s.end) if "stifle" in angles[i]]
        width = percentile_width(series)
        if width is not None and len(series) >= MIN_ANGLE_SEEN * (s.end - s.start):
            cycles.append(round(width, 1))
    if cycles:
        out["stifle_cycle_rom"] = {"values": cycles, "unit": "deg"}
    else:
        out["stifle_cycle_rom"] = _missing("NOT_ENOUGH_CYCLES" if not (hind and hind.strides) else "LOW_CONFIDENCE")
    return out

