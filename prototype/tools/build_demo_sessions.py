"""시연용 회차 수치를 AI-Hub 71878(반려견 보행영상 기반 건강관리 데이터) 라벨로 만든다. 회사 데이터는 쓰지 않는다.

    python prototype/tools/build_demo_sessions.py <71878 폴더> [--n-normal 8] [--n-per-grade 2]

- 출력: prototype/proto_app/static/assets/demo_sessions.json, frontend/src/mocks/demoSessions.json (형식은 build_real_metrics.py 와 같음)
- 회차 = 71878 의 세션 폴더(촬영 하나). Left·Right 옆모습 폴더가 둘 다 있고 쪽마다 라벨 프레임이 MIN_FRAMES 이상인 것만.
  Left 폴더 = 개의 왼쪽(머리 방향으로 98.6~100% 확인, ai/data_prep/check_sides.py) → left_* 칸, Right → right_* 칸.
- 사람이 찍은 관절점(라벨)으로 잰 값: 관절각(engine/angles v1), 쪽마다 프레임별 관절각, rom_*.
  라벨이 프레임마다 따로 찍혀 흔들리므로 관절각을 앞뒤 2프레임 중앙값으로 다듬고, rom_* 는 최대 − 최소 대신 p90 − p10 으로 잰다
  (최대 − 최소는 어깨 106° 처럼 부풀었고, 이렇게 하면 어깨 31°·무릎 41° 로 문헌 범위에 든다, 10-30).
- **합성 값**(71878 은 라벨 프레임만 있고 fps 가 없어 잴 수 없음): stance_ratio·stride_length·paw_lift·walk_speed·gait_cycles,
  무릎 한 걸음 곡선. 세션 id 로 정한 난수라 매번 같고, 기록부(pet_medical_record_info)에 표시된 다리는 등급만큼 조금 나쁘게 만든다.
  어떤 값이 합성인지 각 회차의 `synthetic` 에 적는다.
- 사진은 쓰지 않고 좌표에서 계산한 수치만 남긴다.
"""

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine.angles import ANGLE_DEF, FLEX_SIDE, JOINTS, flexion_angle  # noqa: E402

W, H, FPS = 1920, 1080, 30.0        # 71878 은 1920x1080. fps 정보가 없어 30 으로 둔다(합성 값 계산에만 씀)
MIN_FRAMES, N_PHASE = 24, 50
T13, ILIAC = 2, 13
GRADES = ["정상", "1기", "2기", "3기", "4기"]
PART = {  # 71878 라벨 이름 → 22점 칸 (side = left/right). ai/data_prep/aihub_to_coco.py 의 NAME_71878 과 같은 대응
    "Ear": {"left": 0, "right": 1}, "T13 Spinous precess": 2, "Iliac crest": 13,
    "Dorsal scapular spine": {"left": 3, "right": 8}, "Acromion/Greater tubercle": {"left": 4, "right": 9},
    "Lateral humeral epicondyle": {"left": 5, "right": 10}, "Ulnar styloid process": {"left": 6, "right": 11},
    "Distal lateral aspect of fifth metacarpal bone": {"left": 7, "right": 12},
    "Femoral greater trochanter": {"left": 14, "right": 18}, "Femorotibial joint": {"left": 15, "right": 19},
    "Lateral malleolus of the distal tibia": {"left": 16, "right": 20},
    "Distal lateral aspect of the fifth metatarsus": {"left": 17, "right": 21},
}
JROWS = {"LF": (0, 1, 2), "RF": (3, 4, 5), "LH": (6, 7, 8), "RH": (9, 10, 11)}   # engine/angles.JOINTS 행
ANGLE_KEY = {"어깨": "shoulder", "팔꿈치": "elbow", "앞발목": "carpus", "고관절": "hip", "무릎": "stifle", "뒷발목": "tarsus"}
ROM_CODE = {"어깨": "rom_shoulder", "팔꿈치": "rom_elbow", "앞발목": "rom_carpus", "고관절": "rom_hip", "무릎": "rom_stifle", "뒷발목": "rom_tarsus"}
OUT_PROTO = ROOT / "prototype" / "proto_app" / "static" / "assets" / "demo_sessions.json"
OUT_FRONT = ROOT / "frontend" / "src" / "mocks" / "demoSessions.json"


def frame_kp(d, side):
    kp = [None] * 22
    for a in d.get("annotation_info", []):
        slot = PART.get(a["label"])
        if slot is None:
            continue
        i = slot[side] if isinstance(slot, dict) else slot
        kp[i] = [float(a["x"]) * W, float(a["y"]) * H, 1.0]
    return kp


def jangle(kp, row):
    v, a, b, name = JOINTS[row]
    if not (kp and kp[v] and kp[a] and kp[b] and kp[T13] and kp[ILIAC]):
        return None
    return flexion_angle(kp[v], kp[a], kp[b], (kp[T13][0] - kp[ILIAC][0], kp[T13][1] - kp[ILIAC][1]), FLEX_SIDE[name])


def load_session(folder):
    """세션 폴더 → {'L': {프레임: kp}, 'R': ...}, 기록부, 반"""
    views, rec = {}, None
    for view, key, side in (("Left", "L", "left"), ("Right", "R", "right")):
        frames = {}
        for p in sorted((folder / view).glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            frames[int(p.stem.rsplit("_", 1)[1])] = frame_kp(d, side)
            rec = rec or d.get("pet_medical_record_info")
        views[key] = frames
    return views, rec


def smooth(vals, w=2):
    """앞뒤 w 프레임 중앙값. 값이 없는 프레임은 그대로 비우고, 창 안 값이 3개 미만이면 비운다."""
    out = []
    for i, v in enumerate(vals):
        win = sorted(x for x in vals[max(0, i - w):i + w + 1] if x is not None)
        out.append(None if v is None or len(win) < 3 else win[len(win) // 2])
    return out


def pct(vals, q):
    s = sorted(vals)
    k = (len(s) - 1) * q
    i = int(k)
    return s[i] + (s[min(i + 1, len(s) - 1)] - s[i]) * (k - i)


def resample(vals, n):
    xs = [i for i, v in enumerate(vals) if v is not None]
    if len(xs) < 4:
        return None
    out = []
    for k in range(n):
        t = xs[0] + (xs[-1] - xs[0]) * k / (n - 1)
        j = max(i for i in xs if i <= t)
        nxt = min((i for i in xs if i >= t), default=j)
        w = 0 if nxt == j else (t - j) / (nxt - j)
        out.append(round(vals[j] * (1 - w) + vals[nxt] * w, 1))
    return out


def build(folder, grade):
    views, rec = load_session(folder)
    sid = folder.name
    rng = random.Random(sid)
    bad = {r["foot_position"] for r in (rec or []) if r.get("value")}   # 기록부에 표시된 쪽(left/right)
    sev = GRADES.index(grade)
    metrics, series, knee = {}, {}, {}
    for key in ("L", "R"):
        fr = views[key]
        lo, hi = min(fr), max(fr)
        seq = [fr.get(i) for i in range(lo, hi + 1)]
        ser = {"video": f"aihub71878/{grade}/{sid}/{'Left' if key == 'L' else 'Right'}"}
        for limb, rows in JROWS.items():
            if limb[0] != key:
                continue
            m = metrics.setdefault(limb, {})
            for r in rows:
                name = JOINTS[r][3]
                a = smooth([jangle(k, r) if k else None for k in seq])
                ser[ANGLE_KEY[name]] = [None if x is None else round(x, 1) for x in a]
                vals = [x for x in a if x is not None]
                if len(vals) >= MIN_FRAMES // 2:
                    m[ROM_CODE[name]] = round(pct(vals, 0.9) - pct(vals, 0.1), 1)
                if name == "무릎":
                    knee[limb] = resample(a, N_PHASE)
            # 합성: 기록부에 표시된 쪽은 등급만큼 디딤 짧게·걸음 짧게·발 낮게
            hurt = ("left" if key == "L" else "right") in bad and sev > 0
            m["stance_ratio"] = round(rng.uniform(56, 64) - (2.5 * sev if hurt else 0), 1)
            m["stride_length"] = round(rng.uniform(210, 260) * (1 - (0.05 * sev if hurt else 0)), 1)
            m["paw_lift"] = round(rng.uniform(18, 28) * (1 - (0.08 * sev if hurt else 0)), 1)
        series[key] = ser
    return {
        "id": sid, "source": "aihub", "grade": grade,
        "video_names": [series["L"]["video"], series["R"]["video"]],
        "passes": {"L": 1, "R": 1}, "cycles": rng.randint(6, 12), "walk_speed": round(rng.uniform(2.6, 3.8), 2),
        "fps": FPS, "date": f"{sid[:4]}-{sid[5:7]}-{sid[8:10]}",
        "metrics": metrics, "knee_curve": {k: v for k, v in knee.items() if v},
        "angle_series": series,
        "synthetic": ["stance_ratio", "stride_length", "paw_lift", "walk_speed", "gait_cycles", "knee_curve"],
    }


def candidates(root):
    out = defaultdict(list)
    for split, lab in (("Training", "TL"), ("Validation", "VL")):
        base = root / split / "02.라벨링데이터" / lab
        for g in GRADES:
            for s in sorted((base / g).glob("*")) if (base / g).exists() else []:
                nl, nr = len(list((s / "Left").glob("*.json"))), len(list((s / "Right").glob("*.json")))
                if nl >= MIN_FRAMES and nr >= MIN_FRAMES:
                    out[g].append((min(nl, nr), s))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--n-normal", type=int, default=8)
    ap.add_argument("--n-per-grade", type=int, default=2)
    a = ap.parse_args()
    cand = candidates(a.root)
    rng = random.Random(71878)
    picks = []
    for g in GRADES:
        pool = sorted(cand[g], key=lambda x: (-x[0], x[1].name))[:40]   # 라벨 프레임이 많은 세션 중에서
        n = a.n_normal if g == "정상" else a.n_per_grade
        picks += [(g, s) for _, s in sorted(rng.sample(pool, min(n, len(pool))), key=lambda x: x[1].name)]
    sessions = [build(s, g) for g, s in picks]
    doc = {"note": "AI-Hub 71878 라벨 관절점으로 잰 관절각·가동 범위 + 합성 값(각 회차 synthetic). 회사 데이터 없음. "
                   "prototype/tools/build_demo_sessions.py",
           "angle_def": ANGLE_DEF, "n_phase": N_PHASE, "sessions": sessions}
    for out in (OUT_PROTO, OUT_FRONT):
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(sessions), "회차:", ", ".join(f"{g} {sum(1 for x, _ in picks if x == g)}" for g in GRADES))


if __name__ == "__main__":
    main()
