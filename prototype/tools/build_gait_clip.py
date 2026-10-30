"""실제 영상의 프레임별 관절점 → 3D 화면용 한 걸음 곡선(JSON).

    python prototype/tools/build_gait_clip.py <track.json> <영상 이름 접두사> <출력.json>
    예) ... gt_videos.fs-v4-flip.track.json 260820-1 prototype/proto_app/static/assets/dog3d/gait_jenny.json

- 입력: paw_eval 의 *.track.json (영상마다 fps, 프레임별 22점 [x, y, 확신도] 또는 null).
- 카메라 쪽 다리만 잰다. 왼쪽 다리는 왼쪽이 카메라를 향한 통과에서, 오른쪽 다리는 반대 통과에서 따로 모은다.
- 한 걸음 = 같은 발의 착지 → 다음 착지(engine/gait_events.py, S15P31A404-161). 0~100% 를 N_PHASE 칸으로 다시 뽑아 평균.
- 마디 기울기: 다리 마디(위팔·아래팔·앞발 / 넙다리·정강이·뒷발허리)가 몸통 앞 방향과 이루는 각(위로 들리면 +).
  3D 는 이 값의 "한 걸음 평균에서 벗어난 정도"만 쓴다. 모델 체형이 실제 개와 달라서 평균 자세는 모델 것을 둔다.
- 관절각(engine/angles.py v1)도 같은 칸으로 평균해 둔다. 보고서 보행 주기 그래프용.

gait_events 가 아직 develop 에 없으면 161 브랜치의 파일을 GAIT_EVENTS_DIR 로 가리킨다.
"""

import json
import math
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if os.environ.get("GAIT_EVENTS_DIR"):
    sys.path.insert(0, os.environ["GAIT_EVENTS_DIR"])
try:
    from engine.gait_events import detect_pass
except ImportError:
    from gait_events import detect_pass  # 161 브랜치 초안
from engine.angles import ANGLE_DEF, FLEX_SIDE, JOINTS, flexion_angle  # noqa: E402
from engine.camera_side import heading, pass_side  # noqa: E402

N_PHASE = 50
CONF = 0.3
MIN_VALID = 0.8  # 한 걸음 안에서 마디 각을 잰 프레임 비율이 이보다 낮으면 버림
T13, ILIAC = 2, 13
# 다리별 마디 (근위, 원위) — 3D 뼈 순서와 같다
SEGS = {
    "LF": [(4, 5), (5, 6), (6, 7)], "RF": [(9, 10), (10, 11), (11, 12)],
    "LH": [(14, 15), (15, 16), (16, 17)], "RH": [(18, 19), (19, 20), (20, 21)],
}
# 다리별 관절각 (engine/angles.JOINTS 의 행 번호)
JROWS = {"LF": (0, 1, 2), "RF": (3, 4, 5), "LH": (6, 7, 8), "RH": (9, 10, 11)}
PAW = {"LF": "front", "RF": "front", "LH": "hind", "RH": "hind"}


def ok(p):
    return p is not None and p[2] >= CONF


def seg_angle(kp, a, b, h):
    """마디 a→b 가 몸통 앞 방향(장골능→T13)과 이루는 각(도). 머리 쪽 = 앞, 화면 위 = +"""
    if not (ok(kp[a]) and ok(kp[b]) and ok(kp[T13]) and ok(kp[ILIAC])):
        return None
    tx, ty = (kp[T13][0] - kp[ILIAC][0]) * h, -(kp[T13][1] - kp[ILIAC][1])
    sx, sy = (kp[b][0] - kp[a][0]) * h, -(kp[b][1] - kp[a][1])
    d = math.degrees(math.atan2(sy, sx) - math.atan2(ty, tx))
    return (d + 180) % 360 - 180


def joint_angle(kp, row):
    v, a, b, name = JOINTS[row]
    if not (ok(kp[v]) and ok(kp[a]) and ok(kp[b]) and ok(kp[T13]) and ok(kp[ILIAC])):
        return None
    cranial = (kp[T13][0] - kp[ILIAC][0], kp[T13][1] - kp[ILIAC][1])
    return flexion_angle(kp[v], kp[a], kp[b], cranial, FLEX_SIDE[name])


def resample(vals):
    """프레임별 값(None 허용) → N_PHASE 칸. 빈 칸은 앞뒤 값으로 선형 보간, 잰 비율이 낮으면 None"""
    idx = [i for i, v in enumerate(vals) if v is not None]
    if len(idx) < MIN_VALID * len(vals) or len(idx) < 3:
        return None
    # 각이 ±180 을 넘나드는 일을 막으려고 이어 붙인다
    un, prev = {}, None
    for i in idx:
        v = vals[i]
        if prev is not None:
            v += 360 * round((prev - v) / 360)
        un[i], prev = v, v
    out = []
    n = len(vals)
    for k in range(N_PHASE):
        x = k * n / N_PHASE
        lo = max([i for i in idx if i <= x], default=idx[0])
        hi = min([i for i in idx if i >= x], default=idx[-1])
        out.append(un[lo] if hi == lo else un[lo] + (un[hi] - un[lo]) * (x - lo) / (hi - lo))
    return out


def mean_curve(curves):
    return [round(statistics.fmean(c[k] for c in curves), 2) for k in range(N_PHASE)]


def main(track, prefix, out):
    d = json.load(open(track, encoding="utf-8"))
    acc = {leg: {"seg": [], "joint": [], "td": []} for leg in SEGS}
    offsets, used = {"L": [], "R": []}, []
    for v in d["videos"]:
        if not v["video"].startswith(prefix):
            continue
        frames = [f["kp"] if f else None for f in v["frames"]]
        side = pass_side([f for f in frames if f])
        if side is None:
            continue
        h = 1 if side == "right" else -1
        # 옆모습이 아닌 프레임은 빈 프레임으로
        frames = [f if f and heading(f) == h else None for f in frames]
        ev = detect_pass(frames, v["fps"], side)
        s = "R" if side == "right" else "L"
        n_before = sum(len(acc[s + p]["seg"]) for p in "FH")
        for paw in ("F", "H"):
            leg = s + paw
            e = ev.get(PAW[leg])
            if not e:
                continue
            for st in e.strides:
                fr = frames[st.start:st.end]
                segs = [resample([seg_angle(f, a, b, h) if f else None for f in fr]) for a, b in SEGS[leg]]
                joints = [resample([joint_angle(f, r) if f else None for f in fr]) for r in JROWS[leg]]
                if all(segs) and all(joints):
                    acc[leg]["seg"].append(segs)
                    acc[leg]["joint"].append(joints)
                    acc[leg]["td"].append((st.start, st.end - st.start))
        # 같은 통과의 앞발 착지 → 뒷발 착지 시차(한 걸음 대비)
        fe, he = ev.get("front"), ev.get("hind")
        if fe and he:
            for st in fe.strides:
                tds = [t for t in he.touchdowns() if st.start <= t < st.end]
                if tds:
                    offsets[s].append((tds[0] - st.start) / (st.end - st.start))
        if sum(len(acc[s + p]["seg"]) for p in "FH") > n_before:
            used.append(v["video"])

    legs = {}
    for leg, a in acc.items():
        if not a["seg"]:
            raise SystemExit(f"{leg}: 쓸 수 있는 걸음이 없음")
        legs[leg] = {
            "strides": len(a["seg"]),
            "frames_per_stride": round(statistics.fmean(n for _, n in a["td"]), 1),
            "seg": [mean_curve([c[i] for c in a["seg"]]) for i in range(3)],
            "joint": {JOINTS[r][3]: mean_curve([c[i] for c in a["joint"]]) for i, r in enumerate(JROWS[leg])},
        }
    hind_after_front = {k: round(statistics.median(v), 3) for k, v in offsets.items() if v}
    res = {
        "source": Path(track).name,
        "videos": len(used),
        "fps": round(statistics.fmean(v["fps"] for v in d["videos"] if v["video"] in used), 2),
        "angle_def": ANGLE_DEF,
        "n_phase": N_PHASE,
        "seg_names": {"F": ["위팔", "아래팔", "앞발"], "H": ["넙다리", "정강이", "뒷발허리"]},
        # 0 = 왼쪽 앞발 착지. 같은 쪽 뒷발은 앞발 착지 뒤 hind_after_front 만큼, 반대쪽은 반 걸음 늦게 둔다(평보·속보 가정)
        "hind_after_front": hind_after_front,
        "legs": legs,
        "note": "옆에서 찍은 2D 관절점의 앞뒤 굽힘만 재현. 좌우 다리 사이 시차는 실측이 아니라 반 걸음 가정.",
    }
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("videos", len(used), "| strides", {k: v["strides"] for k, v in legs.items()}, "| hind_after_front", hind_after_front)
    for leg, v in legs.items():
        print(leg, "마디 폭", [round(max(c) - min(c), 1) for c in v["seg"]],
              "관절 폭", {k: round(max(c) - min(c), 1) for k, c in v["joint"].items()})


if __name__ == "__main__":
    main(*sys.argv[1:4])
