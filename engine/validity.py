"""유효·무효 판별 v1 (F-03, S15P31A404-162). 규칙: docs/engine/validityRules.md, 기준값: engine/validity.yaml

관절점 시계열(기업 video_kpi.py track 형식: fps·width·height·프레임별 {box, kp} 또는 None)로 촬영 한 건을 판별한다.

1. 통과 자르기: 기업 video_kpi.find_passes와 같은 규칙
2. 통과마다 무효 사유를 우선순위대로 검사해 첫 사유 하나를 낸다
3. 촬영 판정: 기업 판별 기준 문서(10-22)의 무효 사유가 붙은 통과가 하나라도 있으면 invalid,
   촬영 조건 문제(옆모습 아님·가림 등)로만 뺀 통과가 있으면 partial, 모두 쓰면 valid

측정 구간은 통과 안의 첫 착지부터 마지막 이지다(기업 문서 1절). 매트를 아직 못 찾아서 "매트 안"은 보지 않는다.
측대보(같은 쪽 앞·뒷발 착지 위상 차이)는 계산만 하고 판정은 꺼 두었다(pace_phase_max: null). 제니 유효 영상에서도
위상이 0.1에서 0.47로 퍼져 측대보와 가를 수 없었다. 측대보 영상의 관절점을 받은 뒤, 또는 보행 유형 판별(박규원)로 켠다.
"""
import math
import statistics
from pathlib import Path
from typing import Optional

from engine.camera_side import heading
from engine.gait_events import PAWS, detect_pass
from engine.reasons import REASON_TEXT, pass_reason_detail, shot_reason_detail

VALIDITY_VERSION = "v1"
CONFIG_PATH = Path(__file__).resolve().parent / "validity.yaml"
T13, ILIAC = 2, 13
NEAR_LEGS = {"right": (8, 9, 10, 11, 12, 18, 19, 20, 21), "left": (3, 4, 5, 6, 7, 14, 15, 16, 17)}

# 기업 판별 기준 문서 2절의 무효 사유. 이 사유가 붙은 통과가 있으면 촬영 전체가 무효다
SHOT_INVALID_REASONS = {"GAIT_PACE", "RUNNING", "TURNED", "STOPPED", "SITTING", "PARTIAL_PASS", "OVERLAP"}



def load_config(path: Path = CONFIG_PATH) -> dict:
    import yaml  # 설정을 읽을 때만 필요하다

    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


# ---- 공통 값 ----


def _ok(p, conf) -> bool:
    return p is not None and len(p) > 2 and p[2] >= conf


def _trunk(kp, conf) -> Optional[tuple]:
    """(가로 차이, 몸통 길이, 몸통 가운데 x, 가운데 y). 못 재면 None"""
    if kp is None or not (_ok(kp[T13], conf) and _ok(kp[ILIAC], conf)):
        return None
    (ax, ay), (bx, by) = kp[T13][:2], kp[ILIAC][:2]
    length = math.hypot(ax - bx, ay - by)
    return (ax - bx, length, (ax + bx) / 2, (ay + by) / 2) if length > 1e-6 else None


def _longest_run(flags: list) -> int:
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def find_passes(video: dict, cfg: dict) -> list:
    """[(시작, 끝, heading)]. 기업 video_kpi.find_passes와 같은 규칙(끊김 GAP_S, 10프레임, 화면 폭 1/3 이동)"""
    conf, side_min = cfg["common"]["conf_min"], cfg["common"]["side_min"]
    split = cfg["pass_split"]
    frames, fps, width = video["frames"], video["fps"], video["width"]
    gap = max(1, round(split["gap_s"] * fps))
    runs, cur, last = [], [], None
    for i, f in enumerate(frames):
        if f is None:
            continue
        if last is not None and i - last > gap:
            runs.append(cur)
            cur = []
        cur.append(i)
        last = i
    if cur:
        runs.append(cur)
    out = []
    for run in runs:
        tr = [_trunk(frames[i]["kp"], conf) for i in run]
        xs = [t[2] for t in tr if t]
        signs = [1 if t[0] > 0 else -1 for t in tr if t and abs(t[0]) / t[1] >= side_min]
        if len(xs) < split["min_frames"] or not signs:
            continue
        if abs(statistics.median(xs[-5:]) - statistics.median(xs[:5])) / width >= split["min_travel"]:
            out.append((run[0], run[-1], 1 if sum(signs) > 0 else -1))
    return out


# ---- 통과 하나 검사 ----


def inside_frames(video: dict, start: int, end: int, cfg: dict) -> tuple:
    """통과 구간의 (몸 전체가 화면 안에 보였는지, 그 프레임의 관절점). 화면에 들어오고 나가는 동안은 몸이 잘려
    관절점이 틀리므로, 상자가 화면 끝에 닿지 않은 프레임만 쓴다. 보행 수치(gait_metrics)도 같은 프레임을 쓴다"""
    edge, width = cfg["pass_rules"]["edge_px"], video["width"]
    frames = video["frames"][start:end + 1]
    inside = [f is not None and f["box"][0] > edge and f["box"][2] < width - edge for f in frames]
    return inside, [f["kp"] if ok else None for f, ok in zip(frames, inside)]


def check_pass(video: dict, start: int, end: int, head: int, cfg: dict) -> dict:
    """통과 하나 → {"reason_code", "camera_side", "measure_start", "measure_end", "checks"}"""
    conf = cfg["common"]["conf_min"]
    rules = cfg["pass_rules"]
    fps, width = video["fps"], video["width"]
    frames = video["frames"][start:end + 1]
    side = "right" if head > 0 else "left"
    found = {}

    inside, kps = inside_frames(video, start, end, cfg)
    n = max(1, sum(f is not None for f in frames))
    present = [k is not None for k in kps]
    n_in = max(1, sum(present))

    # 개 없음, 가림
    ev = {}   # 사유 문장(engine/reasons.py)에 쓰는 측정값. checks에 함께 남긴다
    ev["no_dog_ratio"] = 1 - n / len(frames)
    found["NO_DOG"] = ev["no_dog_ratio"] > rules["no_dog_frame_ratio"]
    hidden = [k is not None and sum(not _ok(k[i], conf) for i in NEAR_LEGS[side]) / len(NEAR_LEGS[side])
              >= rules["occluded_point_ratio"] for k in kps]
    ev["occluded_ratio"] = sum(hidden) / n_in
    found["OCCLUDED"] = ev["occluded_ratio"] > rules["occluded_frame_ratio"]

    # 옆모습
    heads = [heading(k, conf) if k else None for k in kps]
    side_frames = [h for h in heads if h is not None]
    found["NOT_SIDE_VIEW"] = len(side_frames) / n_in < rules["side_view_min_ratio"]

    # 다 지나가지 않음: 몸 전체가 보인 시간이 너무 짧거나, 나가는 쪽 끝에 닿기 전에 영상이 끝남
    last_box = next((f["box"] for f in reversed(frames) if f), None)
    ends_with_video = end >= len(video["frames"]) - max(1, round(cfg["pass_split"]["gap_s"] * fps))
    exit_edge = width * rules["exit_margin"]
    not_out = last_box is not None and ((head > 0 and last_box[2] < width - exit_edge) or
                                        (head < 0 and last_box[0] > exit_edge))
    ev["ends_before_exit"] = bool(ends_with_video and not_out)
    found["PARTIAL_PASS"] = sum(present) / fps < rules["min_inside_s"] or ev["ends_before_exit"]

    # 카메라 쪽으로 걸음: 상자 높이가 처음과 끝에서 크게 다름
    heights = [f["box"][3] - f["box"][1] for f, ok in zip(frames, inside) if ok]
    if heights:
        k = max(1, len(heights) // 5)
        h0, h1 = statistics.median(heights[:k]), statistics.median(heights[-k:])
        ev["height_scale"] = max(h0, h1) / max(1e-6, min(h0, h1))
        found["TOWARD_CAMERA"] = ev["height_scale"] > rules["toward_camera_scale"]

    # 돌아섬: 반대 방향 프레임, 몸통이 거꾸로 움직인 시간
    opposite = sum(h == -head for h in side_frames) / max(1, len(side_frames))
    trunks = [_trunk(k, conf) if k else None for k in kps]
    lengths = [t[1] for t in trunks if t]
    body = statistics.median(lengths) if lengths else 1.0
    speeds = []   # 진행 방향 속도(몸통 길이/초). 프레임 사이가 비면 None
    for a, b in zip(trunks, trunks[1:]):
        speeds.append(None if not (a and b) else (b[2] - a[2]) * head * fps / body)
    smooth = _median_filter(speeds, max(3, round(0.1 * fps) | 1))
    backwards = [s is not None and s < 0 for s in smooth]
    ev["opposite_ratio"], ev["reverse_s"] = opposite, _longest_run(backwards) / fps
    found["TURNED"] = opposite > rules["turned_frame_ratio"] or ev["reverse_s"] > rules["turned_reverse_s"]

    # 앉음: 골반 높이(카메라 쪽 뒷발끝과 장골능의 세로 거리)가 크게 낮아짐
    toe = PAWS[side]["hind"]
    pelvis = [(k[toe][1] - k[ILIAC][1]) / body if k and _ok(k[toe], conf) and _ok(k[ILIAC], conf) else None
              for k in kps]
    valid_pelvis = [p for p in pelvis if p is not None]
    if valid_pelvis:
        low = rules["sitting_height_ratio"] * statistics.median(valid_pelvis)
        ev["sitting_s"] = _longest_run([p is not None and p < low for p in pelvis]) / fps
        found["SITTING"] = ev["sitting_s"] > rules["sitting_min_s"]
    else:
        found["SITTING"] = False

    # 멈춤, 뛰기
    slow = [s is not None and abs(s) < rules["stopped_speed"] for s in smooth]
    ev["stopped_s"] = _longest_run(slow) / fps
    found["STOPPED"] = ev["stopped_s"] > rules["stopped_min_s"]
    moving = [abs(s) for s in smooth if s is not None]
    pace_speed = statistics.median(moving) if moving else 0.0
    found["RUNNING"] = pace_speed > rules["running_speed"]

    # 측대보: 같은 쪽 앞·뒷발 착지가 거의 동시에 일어남 (보행 주기 대비 위상 차이가 작음)
    events = detect_pass(kps, fps, side)
    lag = lateral_phase(events)
    pace_max = rules.get("pace_phase_max")   # None이면 측대보 검사를 끈다(hold)
    found["GAIT_PACE"] = pace_max is not None and lag is not None and lag < pace_max

    reason = next((r for r in cfg["reason_priority"] if found.get(r)), None)
    tds = [t for e in events.values() for t in e.touchdowns()]
    los = [t for e in events.values() for t in e.liftoffs()]
    return {
        "reason_code": reason,
        "camera_side": side,
        "measure_start": start + min(tds) if tds else None,
        "measure_end": start + max(los) if los else None,
        "checks": {
            "speed_body_per_s": round(pace_speed, 2),
            "lateral_phase": None if lag is None else round(lag, 2),
            "side_view_ratio": round(len(side_frames) / n_in, 2),
            "inside_s": round(sum(present) / fps, 2),
            "found": sorted(r for r, v in found.items() if v),
            **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in ev.items()},
        },
    }


def _median_filter(values: list, window: int) -> list:
    half = window // 2
    out = []
    for i, v in enumerate(values):
        near = [x for x in values[max(0, i - half): i + half + 1] if x is not None]
        out.append(statistics.median(near) if v is not None and near else None)
    return out


def lateral_phase(events: dict) -> Optional[float]:
    """같은 쪽 뒷발 착지 → 가장 가까운 앞발 착지까지의 시간 / 보행 주기, 중앙값(0에서 0.5).
    측대보는 0 근처, 평보는 0.25 근처, 속보는 0.5 근처다. 착지가 모자라면 None"""
    if not events:
        return None
    front, hind = events["front"].touchdowns(), events["hind"].touchdowns()
    strides = [s.end - s.start for s in events["hind"].strides]
    if len(front) < 2 or len(hind) < 2 or not strides:
        return None
    cycle = statistics.median(strides)
    lags = []
    for h in hind:
        d = min(abs(f - h) for f in front)
        lags.append(min(d, cycle - d) / cycle if cycle > 0 else 0.0)
    return statistics.median(lags)


# ---- 촬영 판정 ----


def judge_shot(video: dict, cfg: Optional[dict] = None) -> dict:
    """촬영 한 건 → 결과 JSON의 validity·validity_reason·summary·passes 부분"""
    cfg = cfg or load_config()
    frames = video["frames"]
    found_ratio = sum(f is not None for f in frames) / max(1, len(frames))
    passes = []
    if found_ratio >= cfg["shot_rules"]["no_dog_frame_ratio"]:
        for i, (a, b, head) in enumerate(find_passes(video, cfg), start=1):
            r = check_pass(video, a, b, head, cfg)
            code = r["reason_code"]
            passes.append({
                "index": i, "start_frame": a, "end_frame": b,
                "heading": "right" if head > 0 else "left", "camera_side": r["camera_side"],
                "gait": None, "valid": code is None,
                "reason_code": code, "reason": REASON_TEXT.get(code) if code else None,
                "reason_detail": pass_reason_detail(code, r["checks"], cfg) if code else None,
                "measure_start": r["measure_start"], "measure_end": r["measure_end"],
                "checks": r["checks"],
            })
    used = [p for p in passes if p["valid"]]
    if found_ratio < cfg["shot_rules"]["no_dog_frame_ratio"]:
        validity, reason = "invalid", "NO_DOG"
    elif any(p["reason_code"] in SHOT_INVALID_REASONS for p in passes):
        validity = "invalid"
        reason = next(p["reason_code"] for p in passes if p["reason_code"] in SHOT_INVALID_REASONS)
    elif not used:
        validity, reason = "invalid", "NO_VALID_PASS"
    elif len(used) < len(passes):
        validity = "partial"
        reason = "FEW_VALID_PASSES" if len(used) < cfg["shot_rules"]["min_valid_passes"] else None
    else:
        validity, reason = "valid", None
    return {
        "validity_version": VALIDITY_VERSION,
        "validity": validity,
        "validity_reason": reason,
        "validity_reason_text": shot_reason_detail(reason, passes, cfg, found_ratio) if reason else None,
        "summary": {"passes": len(passes), "used": len(used), "excluded": len(passes) - len(used)},
        "passes": passes,
    }
