"""예시 회차의 보행 수치를 시연 회차 값으로 채운다.

static/assets/demo_sessions.json(tools/build_demo_sessions.py): AI-Hub 71878 라벨 관절점으로 잰 관절각·가동 범위 + 합성 값.
static/assets/company_sample.json: 회사 데이터(제니) 1회차. 시연에 써도 되는지 멘토링에서 확인 전까지만 두고, 파일을 지우면 자동으로 빠진다.
예시 반려견의 이름·보호자·날짜·측정자는 지어낸 값이고, 회차 수치만 시연 회차를 돌려 가며 붙인다(양쪽 다리가 다 찍히고 걸음 4개 이상인 회차만).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ASSETS = Path(__file__).parent / "static" / "assets"
REAL_FILES = [ASSETS / "demo_sessions.json", ASSETS / "company_sample.json"]   # 없는 파일은 건너뜀
MIN_CYCLES = 4
# (화면 이름, 수치 코드, 앞/뒤, 단위). 디딤 비율·걸음 길이·발 높이는 엔진 v0 정의(몸통 = T13~장골능 길이 기준)
ROWS = [
    ("뒷다리", "무릎 가동 범위", "rom_stifle", "H", "°"), ("뒷다리", "고관절 가동 범위", "rom_hip", "H", "°"),
    ("뒷다리", "뒷발목 가동 범위", "rom_tarsus", "H", "°"), ("뒷다리", "걸음 길이(몸통 대비)", "stride_length", "H", "%"),
    ("뒷다리", "입각기 비율", "stance_ratio", "H", "%"), ("뒷다리", "발 높이(몸통 대비)", "paw_lift", "H", "%"),
    ("앞다리", "어깨 가동 범위", "rom_shoulder", "F", "°"), ("앞다리", "팔꿈치 가동 범위", "rom_elbow", "F", "°"),
    ("앞다리", "앞발목 가동 범위", "rom_carpus", "F", "°"), ("앞다리", "걸음 길이(몸통 대비)", "stride_length", "F", "%"),
    ("앞다리", "입각기 비율", "stance_ratio", "F", "%"), ("앞다리", "발 높이(몸통 대비)", "paw_lift", "F", "%"),
]
SYM_CODES = [("rom_stifle", "H"), ("rom_hip", "H"), ("rom_elbow", "F"), ("stride_length", "H"), ("stance_ratio", "H")]


@lru_cache(maxsize=1)
def sessions() -> list:
    d = [s for f in REAL_FILES if f.exists() for s in json.loads(f.read_text(encoding="utf-8"))["sessions"]]
    return [s for s in d if s["passes"]["L"] and s["passes"]["R"] and s["cycles"] >= MIN_CYCLES]


def session(src: str):
    """'출처:촬영 묶음' → 실측 회차"""
    sid = src.split(":", 1)[-1] if src else ""
    return next((s for s in sessions() if s["id"] == sid), None)


def source_name(s: dict) -> str:
    return {"jenny": "제니", "wowwow": "와우와우", "aihub": "AI-Hub"}.get(s["source"], s["source"]) + f" {s['id']}"


def met(m: dict, code: str, leg: str):
    return (m.get(leg) or {}).get(code)


def si(left, right):
    """좌우 차이 비율(%) = |왼 − 오| ÷ 평균"""
    if left is None or right is None or left + right == 0:
        return None
    return abs(left - right) / ((left + right) / 2) * 100


def apply(r, s: dict) -> None:
    """실측 회차 s 의 수치로 결과 r 의 수치 칸을 채운다(상태·날짜·측정자는 그대로)."""
    m = s["metrics"]
    r.m, r.src = m, f"{s['source']}:{s['id']}"

    def pair(code, fh):
        return [round(met(m, code, "L" + fh) or 0), round(met(m, code, "R" + fh) or 0)]

    r.j = [["무릎", *pair("rom_stifle", "H")], ["고관절", *pair("rom_hip", "H")], ["팔꿈치", *pair("rom_elbow", "F")]]
    r.sL, r.sR = pair("stride_length", "H")
    sis = [x for x in (si(met(m, c, "L" + fh), met(m, c, "R" + fh)) for c, fh in SYM_CODES) if x is not None]
    r.sym = max(0, round(100 - sum(sis) / len(sis))) if sis else 0
    r.rom = round(sum(r.j[0][1:]) / 2)
    used = s["passes"]["L"] + s["passes"]["R"]
    r.ps = (len(s["video_names"]), used)
    r.ex = [("방향·관절점 부족", len(s["video_names"]) - used)] if len(s["video_names"]) > used else []


def fill(results: list) -> None:
    """실패가 아닌 예시 회차에 실측 회차를 차례로 붙인다(오래된 회차부터)."""
    ss = sessions()
    if not ss:
        return
    i = 0
    for r in sorted(results, key=lambda r: (r.day, r.time, r.id)):
        if r.st != "fail":
            apply(r, ss[i % len(ss)])
            i += 1


def rows(r) -> list:
    """회차 수치 표. 한쪽이 없으면 비교 불가"""
    out, last = [], None
    for sec, name, code, fh, unit in ROWS:
        left, right = met(r.m, code, "L" + fh), met(r.m, code, "R" + fh)
        row = {"n": name, "leg": sec}
        if sec != last:
            row["sec"] = sec
            last = sec
        if left is None or right is None:
            row.update(na=True, reason="이 방향 영상에서 해당 관절을 잴 수 없었어요")
        else:
            row.update(l=round(left), r=round(right), u=unit)
        out.append(row)
    return out
