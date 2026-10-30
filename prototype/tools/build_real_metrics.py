"""실제 영상의 관절점(paw_eval *.track.json) → 회차별 보행 수치(api-spec 10.4 코드). 시제품·앱 가짜 서버의 예시 수치 대신 쓴다.

    python prototype/tools/build_real_metrics.py <출력.json> <track.json>=<이름> [<track.json>=<이름> ...]

- 회차 = 촬영 묶음(파일 이름의 날짜-시각). 카메라마다 통과 하나, 카메라 쪽 다리만 잰다(왼쪽을 향한 통과 → 오른쪽? 아님:
  engine/camera_side 규칙대로 머리가 오른쪽이면 오른쪽 다리가 카메라 쪽). 한쪽 방향만 찍힌 회차는 반대쪽 다리가 비교 불가다.
- 한 걸음 = 같은 발 착지 → 다음 착지(engine/gait_events). 걸음마다 잰 값의 중앙값을 통과 값, 같은 다리 통과들의 중앙값을 회차 값으로 쓴다.
- 수치 정의
  rom_*        : 한 걸음 동안 관절각(engine/angles v1) 최대 − 최소(°). 고관절 장골능·대퇴·무릎, 무릎, 뒷발목, 어깨, 팔꿈치, 앞발목
  stance_ratio : 디딤 프레임 ÷ 한 걸음 프레임 × 100
  stride_length: 한 걸음 동안 몸통 가운데(T13·장골능 중점)가 간 거리 ÷ 몸통 길이 × 100
                 몸통 길이 = T13~장골능(명세 용어 정의, KPI-06 과 같은 기준). 문헌(어깨뼈~고관절 기준)과 비교할 때는 ÷1.92
  paw_lift     : 디딤 때 발끝 높이 − 흔들기 중 가장 높은 발끝 높이, ÷ 몸통 길이 × 100 (화면 기준, 원근 보정 없음)
  walk_speed   : 몸통 가운데 속도 중앙값(몸통 길이/초), gait_cycles: 잰 걸음 수
- 무릎 관절각 한 걸음 평균 곡선(50칸)도 다리별로 남긴다(보고서 그래프).
- 방향(L/R)마다 가장 긴 통과 하나의 프레임별 관절각(어깨·팔꿈치·앞발목·고관절·무릎·뒷발목, 앱 촬영 상세 그래프)도 남긴다.
"""

import json
import math
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if os.environ.get("GAIT_EVENTS_DIR"):
    sys.path.insert(0, os.environ["GAIT_EVENTS_DIR"])
try:
    import engine.gait_events as ge
except ImportError:
    import gait_events as ge  # 161 브랜치 초안(GAIT_EVENTS_DIR)
PAWS, body_length, detect_pass, trunk_speed = ge.PAWS, ge.body_length, ge.detect_pass, ge.trunk_speed
from engine.angles import ANGLE_DEF, FLEX_SIDE, JOINTS, flexion_angle  # noqa: E402

# 10-29 팀 합의(조유진·박규원, PLOS 정답 대조): STANCE_RATIO 0.40, 흔들림 창 0.15초. 엔진(v0)에 반영되기 전이라 여기서만 덮어쓴다.
# 엔진이 바뀌면 이 두 줄과 one_pass 의 SMOOTH_FRAMES 줄을 지운다.
STANCE_RATIO, SMOOTH_SEC = 0.40, 0.15

from engine.camera_side import heading, pass_side  # noqa: E402

CONF, T13, ILIAC, N_PHASE = 0.3, 2, 13, 50
SIDE = {"right": "R", "left": "L"}
# 다리별 관절 행(engine/angles.JOINTS)과 수치 코드
JROWS = {"LF": (0, 1, 2), "RF": (3, 4, 5), "LH": (6, 7, 8), "RH": (9, 10, 11)}
ANGLE_KEY = {"어깨": "shoulder", "팔꿈치": "elbow", "앞발목": "carpus", "고관절": "hip", "무릎": "stifle", "뒷발목": "tarsus"}
ROM_CODE = {"어깨": "rom_shoulder", "팔꿈치": "rom_elbow", "앞발목": "rom_carpus", "고관절": "rom_hip", "무릎": "rom_stifle", "뒷발목": "rom_tarsus"}


def ok(p):
    return p is not None and p[2] >= CONF


def jangle(kp, row):
    v, a, b, name = JOINTS[row]
    if not (kp and ok(kp[v]) and ok(kp[a]) and ok(kp[b]) and ok(kp[T13]) and ok(kp[ILIAC])):
        return None
    return flexion_angle(kp[v], kp[a], kp[b], (kp[T13][0] - kp[ILIAC][0], kp[T13][1] - kp[ILIAC][1]), FLEX_SIDE[name])


def center(kp):
    if not (kp and ok(kp[T13]) and ok(kp[ILIAC])):
        return None
    return ((kp[T13][0] + kp[ILIAC][0]) / 2, (kp[T13][1] + kp[ILIAC][1]) / 2)


def curve(vals):
    idx = [i for i, v in enumerate(vals) if v is not None]
    if len(idx) < 0.8 * len(vals) or len(idx) < 3:
        return None
    out = []
    for k in range(N_PHASE):
        x = k * len(vals) / N_PHASE
        lo = max([i for i in idx if i <= x], default=idx[0])
        hi = min([i for i in idx if i >= x], default=idx[-1])
        out.append(vals[lo] if hi == lo else vals[lo] + (vals[hi] - vals[lo]) * (x - lo) / (hi - lo))
    return out


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def one_pass(v):
    """통과 하나 → (카메라 쪽 L/R, {다리: {코드: 값}}, 무릎 곡선들, 속도, 걸음 수)"""
    frames = [f["kp"] if f else None for f in v["frames"]]
    side = pass_side([f for f in frames if f])
    if side is None:
        return None
    h = 1 if side == "right" else -1
    frames = [f if f and heading(f) == h else None for f in frames]
    L = body_length(frames)
    if not L:
        return None
    ge.STANCE_RATIO, ge.SMOOTH_FRAMES = STANCE_RATIO, max(1, round(SMOOTH_SEC * v["fps"]))
    ev = detect_pass(frames, v["fps"], side)
    s = SIDE[side]
    legs, knees, n = {}, [], 0
    for paw, e in ev.items():
        leg = s + ("F" if paw == "front" else "H")
        slot = PAWS[side][paw]
        per = defaultdict(list)
        for st in e.strides:
            fr = frames[st.start:st.end]
            for r in JROWS[leg]:
                a = [jangle(f, r) for f in fr]
                c = curve(a)
                if c:
                    per[ROM_CODE[JOINTS[r][3]]].append(max(c) - min(c))
                    if JOINTS[r][3] == "무릎":
                        knees.append(c)
            per["stance_ratio"].append(st.stance_ratio * 100)
            c0, c1 = center(frames[st.start]), center(frames[min(st.end, len(frames) - 1)])
            if c0 and c1:
                per["stride_length"].append(math.hypot(c1[0] - c0[0], c1[1] - c0[1]) / L * 100)
            ys = [f[slot][1] for f in fr if f and ok(f[slot])]
            stance = [f[slot][1] for f in frames[st.start:st.start + st.stance_frames] if f and ok(f[slot])]
            if ys and stance:
                per["paw_lift"].append(max(0.0, (statistics.median(stance) - min(ys)) / L * 100))
            n += 1
        legs[leg] = {k: round(med(x), 1) for k, x in per.items() if med(x) is not None}
    series = {}
    for leg in (s + "F", s + "H"):
        for r in JROWS[leg]:
            a = [jangle(f, r) for f in frames]
            series[ANGLE_KEY[JOINTS[r][3]]] = [None if x is None else round(x, 1) for x in a]
    return s, legs, knees, trunk_speed(frames, v["fps"], L), n, series


def main(out, *specs):
    sessions = {}
    for spec in specs:
        path, _, source = spec.partition("=")
        for v in json.load(open(path, encoding="utf-8"))["videos"]:
            name = Path(v["video"]).stem
            key = "-".join(name.split("-")[:2])   # 날짜-시각
            r = one_pass(v)
            S = sessions.setdefault(key, {"id": key, "source": source, "video_names": [], "passes": {"L": 0, "R": 0},
                                          "_legs": defaultdict(lambda: defaultdict(list)), "_knee": defaultdict(list), "_speed": [], "cycles": 0,
                                          "angle_series": {}, "fps": round(v["fps"], 2)})
            S["video_names"].append(v["video"])
            if not r:
                continue
            s, legs, knees, speed, n, series = r
            S["passes"][s] += 1
            sn = sum(x is not None for x in series.get("stifle", []))
            if sn > S["angle_series"].get(s, {}).get("_n", -1):
                S["angle_series"][s] = {"_n": sn, "video": v["video"], **series}
            for leg, vals in legs.items():
                for k, x in vals.items():
                    S["_legs"][leg][k].append(x)
            S["_knee"][s + "H"] += knees
            S["_speed"].append(speed)
            S["cycles"] += n
    res = []
    for S in sessions.values():
        metrics = {leg: {k: round(statistics.median(x), 1) for k, x in d.items()} for leg, d in S.pop("_legs").items()}
        knee = {leg: [round(statistics.fmean(c[i] for c in cs), 1) for i in range(N_PHASE)] for leg, cs in S.pop("_knee").items() if cs}
        sp = med(S.pop("_speed"))
        if not metrics:
            continue
        for a in S["angle_series"].values():
            a.pop("_n", None)
        date = S["id"].split("-")[0]
        res.append({**S, "date": f"20{date[:2]}-{date[2:4]}-{date[4:]}", "metrics": metrics, "knee_curve": knee,
                    "walk_speed": None if sp is None else round(sp, 2)})
    res.sort(key=lambda x: x["id"])
    Path(out).write_text(json.dumps({"angle_def": ANGLE_DEF, "n_phase": N_PHASE, "sessions": res}, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8")
    both = [x for x in res if x["passes"]["L"] and x["passes"]["R"]]
    print(len(res), "회차 (양쪽 다 있는 회차", len(both), ")", {s: sum(1 for x in res if x["source"] == s) for s in {x["source"] for x in res}})
    for x in res[:3] + both[:2]:
        print(x["id"], x["source"], x["passes"], x["cycles"], x["walk_speed"], {k: v.get("rom_stifle") for k, v in x["metrics"].items()})


if __name__ == "__main__":
    main(*sys.argv[1:])
