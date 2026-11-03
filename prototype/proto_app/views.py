"""화면에 넣을 값 계산 (디자인의 renderVals를 Python으로 옮김)."""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Optional

from . import real
from .config import (
    CHANGE_DAYS,
    IMG_KIND,
    LIMB,
    MEMO_CAT,
    NOTE_CAT,
    PAGE_SIZE,
    SEX,
    SITE,
    SIZE,
    SOAP,
    ST,
    STAGE,
    SYM_CHANGE,
    VITAL_REF,
    WEIGHT_CHANGE,
    auto_size,
)
from .store import Account, Dog, Result, Vital


def jround(x: float) -> int:
    """JavaScript Math.round와 같은 반올림 (0.5는 올림)."""
    return math.floor(x + 0.5)


def short(d: str) -> str:
    return d.replace("월 ", ".").replace("일", "")


def fmt_date(iso: str) -> str:
    p = (iso or "").split("-")
    return f"{p[0]}년 {int(p[1])}월 {int(p[2])}일" if len(p) == 3 else iso


def desc(d: Dog) -> str:
    parts = [d.breed or "견종 미입력", f"{d.birth}년생" if d.birth else None, f"{d.kg}kg" if d.kg else None]
    return " · ".join(p for p in parts if p)


def st_chip(st: str) -> dict:
    label, bg, c = ST[st]
    return {"st": label, "bg": bg, "c": c}


def valid(acct: Account, dog_id: str) -> list:
    return [r for r in acct.results if r.dog == dog_id and r.st != "fail"]


def sess_no(acct: Account, r: Result) -> int:
    all_ = [x for x in acct.results if x.dog == r.dog]
    return len(all_) - all_.index(r)


def base_of(acct: Account, d: Dog) -> Optional[str]:
    if d.base and any(r.id == d.base and r.st != "fail" for r in acct.results):
        return d.base
    v = valid(acct, d.id)
    return v[-1].id if v else None


def delta(a, b, unit: str) -> str:
    if b is None:
        return "첫 측정"
    d = a - b
    if d > 0:
        return f"직전 대비 +{d}{unit}"
    if d < 0:
        return f"직전 대비 −{-d}{unit}"
    return "직전과 같음"


def avatar(on: bool) -> dict:
    return {"ring": "0 0 0 3px #FAF9F6,0 0 0 6px #D2601A" if on else "none",
            "av": "#FCEEE3" if on else "#EEEAE4", "avc": "#A8481A" if on else "#7A808A",
            "nc": "#1B2433" if on else "#5B6472", "nw": 700 if on else 500}


def seg(items, cur) -> list:
    out = []
    for key, label in items:
        on = cur == key
        out.append({"key": key, "label": label, "bg": "#fff" if on else "transparent",
                    "c": "#1B2433" if on else "#5B6472", "sh": "0 1px 3px rgba(27,36,51,.12)" if on else "none"})
    return out


# ── 회차 수치 ──
def mrows(r: Result, gait: str) -> list:
    if r.m:   # 실측 수치(real.py). 평보·속보 구분은 영상에 없어 같은 값
        return real.rows(r)
    f = 0.86 if gait == "walk" else 1

    def v(x):
        return jround(x * f)

    return [
        {"sec": "뒷다리", "n": "무릎 가동 범위", "l": v(r.j[0][1]), "r": v(r.j[0][2]), "u": "°", "leg": "뒷다리"},
        {"n": "고관절 가동 범위", "l": v(r.j[1][1]), "r": v(r.j[1][2]), "u": "°", "leg": "뒷다리"},
        {"n": "걸음 길이", "l": v(r.sL * 1.5), "r": v(r.sR * 1.5), "u": "%", "leg": "뒷다리"},
        {"n": "입각기 비율", "l": 61, "r": 61 - jround((r.sL - r.sR) / 2), "u": "%", "leg": "뒷다리"},
        {"sec": "앞다리", "n": "팔꿈치 가동 범위", "l": v(r.j[2][1]), "r": v(r.j[2][2]), "u": "°", "leg": "앞다리"},
        {"n": "발 높이", "na": True, "reason": "반대쪽 다리가 가려졌어요", "leg": "앞다리"},
    ]


def _rank(rows) -> list:
    out = []
    for x in rows:
        if x.get("na"):
            continue
        df = abs(x["l"] - x["r"])
        out.append({**x, "df": df, "si": df / ((x["l"] + x["r"]) / 2) * 100})
    return sorted(out, key=lambda x: -x["si"])


GAIT_FILE = Path(__file__).parent / "static" / "assets" / "dog3d" / "gait_demo.json"   # tools/build_demo_clip.py
REF_FILE = GAIT_FILE.with_name("gait_ref_plos.json")


def _median(vals, default):
    v = sorted(x for x in vals if x)
    return v[len(v) // 2] if v else default


# 3D 움직임 기준: 시연 회차들의 관절별 가동 범위 중앙값(°). 두 다리 모두 이보다 작으면 둘 다 덜 움직인다
_JOINT_CODES = {"어깨": "rom_shoulder", "팔꿈치": "rom_elbow", "앞발목": "rom_carpus", "고관절": "rom_hip", "무릎": "rom_stifle", "뒷발목": "rom_tarsus"}
ROM_REF = {j: round(_median([real.met(s["metrics"], c, leg) for s in real.sessions() for leg in ("LF", "RF", "LH", "RH")],
                            real._HEALTHY["F" if c in ("rom_shoulder", "rom_elbow", "rom_carpus") else "H"][c]), 1)
           for j, c in _JOINT_CODES.items()}
MEDIAN_SPEED = _median([s.get("walk_speed") for s in real.sessions()], 1)


TEMPLATE_STANCE = 60.0   # 모양 틀(공개 논문 속보 평균 곡선)의 입각기 비율 가정(%)


def fit_curve(base: list, rom, stance) -> list:
    """모양 틀 곡선을 이 회차 수치에 맞춘다: 굽힘 폭 = 가동 범위(°), 디딤 구간 길이 = 입각기 비율(%).
    입각기 비율이 틀보다 길면 디딤 구간(곡선 앞쪽)을 늘리고 나머지를 줄인다. 값이 없으면 그 항목은 틀 그대로."""
    n, mean, amp = len(base), sum(base) / len(base), (max(base) - min(base)) or 1
    k = (rom / amp) if rom else 1
    c = [mean + (v - mean) * k for v in base]
    if not stance:
        return [round(v, 1) for v in c]
    a, b = TEMPLATE_STANCE / 100, min(0.8, max(0.35, stance / 100))
    out = []
    for i in range(n):
        p = i / n
        q = p / b * a if p < b else a + (p - b) / (1 - b) * (1 - a)   # 이 회차의 걸음 위치 → 틀의 걸음 위치
        x = q * n
        j, f = int(x) % n, x - int(x)
        out.append(round(c[j] * (1 - f) + c[(j + 1) % n] * f, 1))
    return out


def knee_chart(r) -> dict:
    """보고서 "뒷무릎 각도 · 보행 주기" 그래프. x = 한 걸음(같은 뒷발 착지 → 다음 착지) 0~100%, y = 무릎 각도(°, engine/angles.py v1).
    회차에 실측 곡선(AI-Hub 라벨 관절점)이 붙어 있으면 그 곡선, 없으면 공개 논문 속보 평균 모양을 이 회차의
    다리별 무릎 가동 범위·입각기 비율에 맞춰 만든다(반려견마다·회차마다 다르다)."""
    s = real.session(r.src)
    if s and {"LH", "RH"} <= set(s["knee_curve"]):
        L, R = s["knee_curve"]["LH"], s["knee_curve"]["RH"]
        label = (f"AI-Hub 라벨 관절점({real.source_name(s)}) 근사 곡선" if s["source"] == "aihub"
                 else f"실측 영상 {len(s['video_names'])}개({real.source_name(s)}) 걸음 평균")
    else:
        g = json.loads(GAIT_FILE.read_text(encoding="utf-8"))
        base = g["legs"]["LH"]["joint"]["무릎"]      # 틀은 덜 쓰지 않는 쪽 곡선
        L, R = (fit_curve(base, real.met(r.m, "rom_stifle", leg), real.met(r.m, "stance_ratio", leg)) for leg in ("LH", "RH"))
        label = "이 회차 무릎 가동 범위·입각기 비율로 만든 합성 곡선(모양은 공개 논문 속보 평균)"
    # 정상 참고 범위: 공개 데이터 건강한 대형견 6마리 속보 무릎(tools/build_plos_reference.py)
    ref = json.loads(REF_FILE.read_text(encoding="utf-8"))["gaits"]["trot"]["무릎"]
    allv = L + R + ref["min"] + ref["max"]
    lo, hi = math.floor(min(allv) / 10) * 10, math.ceil(max(allv) / 10) * 10
    x0, x1, y0, y1 = 44, 300, 12, 120

    def y(v):
        return y1 - (v - lo) / (hi - lo) * (y1 - y0)

    def line(c):   # 칸 i = 한 걸음의 i/n. 마지막 칸은 100% 바로 앞(다음 착지는 다음 걸음의 0%)
        return " ".join(f"{x0 + (x1 - x0) * i / len(c):.1f},{y(v):.1f}" for i, v in enumerate(c))

    def pt(c):
        return [f"{x0 + (x1 - x0) * i / len(c):.1f},{y(v):.1f}" for i, v in enumerate(c)]

    mid = (lo + hi) // 2
    return {"L": line(L), "R": line(R), "ref_band": " ".join(pt(ref["max"]) + pt(ref["min"])[::-1]), "ref_mean": line(ref["mean"]),
            "ref_src": f"건강한 대형견 {ref['dogs']}마리 속보 범위(Catavitello 외 2015, PLOS ONE, CC BY 4.0)", "y": [{"y": round(y(v), 1), "t": f"{v}°"} for v in (hi, mid, lo)],
            "x": [{"x": x0 + (x1 - x0) * p / 100, "t": f"{p}"} for p in (0, 50, 100)],  # 단위는 축 이름에(보고서 검사가 "100%" 를 단정 표현으로 본다)
            "x0": x0, "x1": x1, "src": label}


def result_view(acct: Account, r: Result, gait: str = "trot", home: bool = False) -> dict:
    """회차 결과 화면(rd)과 보고서(rp)에 쓰는 값."""
    d = acct.dog(r.dog)
    rd = {"name": d.name if d else "-", "desc": desc(d) if d else "", "when": f"{r.date} · {sess_no(acct, r)}회차 · 체중 {r.w}kg",
          **st_chip(r.st), "fail": r.st == "fail", "ok": r.st != "fail", "part": r.st == "part", "id": r.id, "dog": r.dog}
    rp = {}
    if r.st == "fail":
        return {"rd": rd, "rp": rp}
    vv = valid(acct, r.dog)
    idx = vv.index(r)
    prev = vv[idx + 1] if idx + 1 < len(vv) else None
    rows = mrows(r, "trot" if home else gait)
    rows_t = mrows(r, "trot")
    meas = _rank(rows)
    top, top_t = meas[0], _rank(rows_t)[0]
    sL, sR = (r.sL, r.sR) if r.m else (jround(r.sL * 1.5), jround(r.sR * 1.5))
    rd.update({
        "sym": r.sym, "symD": delta(r.sym, prev.sym if prev else None, "%p"),
        "rom": r.rom, "romD": delta(r.rom, prev.rom if prev else None, "°"),
        "sL": sL, "sR": sR, "stD": "좌우 같음" if sL == sR else f"{'오른쪽' if sL > sR else '왼쪽'}이 {abs(sL - sR)}%p 짧음",
        "topTitle": f"{top['leg']} {top['n']}에서 좌우 차이가 가장 커요",
        "topSub": f"왼 {top['l']}{top['u']} · 오 {top['r']}{top['u']} · 차이 {top['df']}{top['u']} · 대칭 지수 차이 {top['si']:.1f}%",
        "rank": [{"n": f"{x['leg']} · {x['n']}", "v": f"차이 {x['df']}{x['u']}", "c": "#fff"} for x in meas[1:4]]
        + [{"n": f"{x['leg']} · {x['n']}", "v": "비교 불가", "c": "rgba(255,255,255,.5)"} for x in rows if x.get("na")],
        "rows": [{"sec": x.get("sec"), "na": bool(x.get("na")), "n": x["n"], "reason": x.get("reason", ""),
                  "lv": "" if x.get("na") else f"{x['l']}{x['u']}", "rv": "" if x.get("na") else f"{x['r']}{x['u']}",
                  "dv": "" if x.get("na") else f"{abs(x['l'] - x['r'])}{x['u']}"} for x in rows],
        "pm": r.ps[0], "pu": r.ps[1], "px": r.ps[0] - r.ps[1], "ex": r.ex, "model": f"pga-pose {r.model}",
        "kc": knee_chart(r), "n_videos": len(r.videos) or 16,
    })
    k0 = rows_t[0]
    rp = {
        "title": f"{rd['name']}의 걸음 보고서",
        "when": f"{r.date} 측정 · {sess_no(acct, r)}회차 · {rd['desc']}",
        "summary": f"{top_t['leg']} {top_t['n']}에서 왼쪽과 오른쪽 차이가 가장 컸어요({top_t['df']}{top_t['u']}). 수의사 선생님과 함께 확인해 보세요.",
        "items": [
            {"k": "좌우 대칭 지수", "v": f"{r.sym}%", "d": f"직전 {prev.sym}%" if prev else "첫 측정"},
            {"k": "뒷무릎 움직임 범위", "v": f"왼 {k0['l']}° · 오 {k0['r']}°", "d": f"차이 {abs(k0['l'] - k0['r'])}°"},
            {"k": "걸음 길이(몸통 대비)", "v": f"왼 {sL}% · 오 {sR}%", "d": f"차이 {abs(sL - sR)}%p"},
        ],
        "rows": [{"n": x["n"], "l": "측정 불가" if x.get("na") else f"{x['l']}{x['u']}",
                  "r": "—" if x.get("na") else f"{x['r']}{x['u']}",
                  "d": "—" if x.get("na") else f"{abs(x['l'] - x['r'])}{x['u']}"} for x in rows_t]
        + [{"n": "대칭 지수", "l": "—", "r": "—", "d": f"{r.sym}%"}],
        "cond": f"측면 가로 촬영 · 영상 {len(r.videos) or 16}개 · 통과 {r.ps[0]}개 중 {r.ps[1]}개 사용 · 분석 모델 pga-pose {r.model}. 측정 불가 항목은 사유와 함께 표시했습니다." + (" 걸음 길이·발 높이는 몸통 길이(T13~장골능) 대비이며, 문헌 값(어깨뼈~고관절 기준)과 비교할 때는 1.92로 나눕니다." if r.m else ""),
    }
    for i, row in enumerate(rp["rows"]):
        row["bg"] = "#fff" if i % 2 else "#FAF8F5"
    return {"rd": rd, "rp": rp}


# ── 홈: 선택한 반려견 ──
def dog_detail(acct: Account, d: Dog) -> dict:
    all_ = [r for r in acct.results if r.dog == d.id]
    b_id = base_of(acct, d)
    b_r = acct.result(b_id) if b_id else None
    hist = []
    for i, r in enumerate(all_):
        hist.append({"id": r.id, "no": f"{sess_no(acct, r)}회차", "date": r.date, "w": f"{r.w}kg", "by": r.by or "—",
                     "pass": "—" if r.st == "fail" else f"{r.ps[1]} / {r.ps[0]}", "model": r.model,
                     "rep": "있음" if r.rep else "—", "base": r.id == b_id, "canBase": r.st != "fail" and r.id != b_id,
                     **st_chip(r.st), "bt": "1px solid #F2EFEA" if i else "none"})
    return {
        "name": d.name, "desc": f"{desc(d)} · {SEX.get(d.sex or 'm')}",
        "cells": [
            {"k": "체급", "v": SIZE[d.size or auto_size(d.breed, d.kg)], "sub": "직접 지정" if d.size_manual else "자동 분류"},
            {"k": "재활 시작일", "v": fmt_date(d.rehab) if d.rehab else "미입력", "sub": ""},
            {"k": "관심 다리", "v": LIMB[d.focus] if d.focus else "미선택", "sub": ""},
            {"k": "기준 회차", "v": f"{b_r.date} · {sess_no(acct, b_r)}회차" if b_r else "없음",
             "sub": "직접 지정" if d.base else ("가장 이른 회차" if b_r else "")},
        ],
        "memo": d.memo or "없음", "hist": hist, "count": f"{len(all_)}회차",
    }


# ── 보고서: 몸 그림 위에 다리별 수치 (10-28) ──
_DOG_SVG = {}
_LEGS = [("front_left", "LF", "왼앞"), ("front_right", "RF", "오른앞"), ("hind_left", "LH", "왼뒤"), ("hind_right", "RH", "오른뒤")]
_LEVEL = [  # (대칭 지수 차이 % 미만, 이름, 다리 색, 글자 색)
    (5, "비슷해요", "#DCEFE2", "#2E8B57"),
    (10, "조금 차이 나요", "#F7D6AE", "#9A6A12"),
    (999, "차이가 커요", "#F2A898", "#C2412D"),
]


def _svg(size: str) -> str:
    name = {"S": "small", "L": "large"}.get(size, "medium")
    if name not in _DOG_SVG:
        from .config import BASE_DIR
        s = (BASE_DIR / "static/assets/dog" / f"dog_{name}.svg").read_text(encoding="utf-8")
        s = s[s.index("<svg"):].replace('width="1024" height="1024"', 'width="100%" height="100%"', 1)
        s = s.replace('viewBox="0 0 1024 1024"', 'viewBox="362 144 300 736"', 1)   # 빈 둘레를 잘라 크게(세 체급 공통 범위)
        _DOG_SVG[name] = s
    return _DOG_SVG[name]


def _level(si: float) -> tuple:
    return next(x for x in _LEVEL if si < x[0])


def body_map(acct: Account, r: Result) -> dict:
    """다리 한 쌍(앞·뒤)마다 좌우 차이를 재서, 덜 쓰는 쪽 다리를 색으로 칠한 그림과 다리별 수치."""
    d = acct.dog(r.dog)
    # 앞·뒷다리에 같은 이름(입각기 비율 등)이 있어 부위까지 붙여 모은다. 이름만 쓰면 뒷다리 카드에 앞다리 값이 들어갔다(11-03 KPI-30)
    rows = {(x["leg"], x["n"]): x for x in mrows(r, "trot") if not x.get("na")}
    pairs = {"front": ["팔꿈치 가동 범위"], "hind": ["무릎 가동 범위", "고관절 가동 범위", "걸음 길이", "입각기 비율"]}
    word = {"팔꿈치 가동 범위": "팔꿈치를 굽히는 정도", "무릎 가동 범위": "무릎을 굽히는 정도",
            "고관절 가동 범위": "엉덩이 관절 움직임", "걸음 길이": "한 걸음 길이", "입각기 비율": "땅을 딛고 있는 시간"}
    legs, fills = {}, {}
    for part, names in pairs.items():
        sec = "앞다리" if part == "front" else "뒷다리"
        mets = [rows[(sec, n)] for n in names if (sec, n) in rows]
        sis = [abs(m["l"] - m["r"]) / ((m["l"] + m["r"]) / 2) * 100 for m in mets]
        k = max(range(len(mets)), key=lambda i: sis[i])
        worst, si = mets[k], sis[k]
        weak = "l" if worst["l"] < worst["r"] else "r"     # 값이 작은 쪽 = 덜 쓰는 쪽
        lv = _level(si)
        side_kr = {"l": "왼쪽", "r": "오른쪽"}
        leg_kr = "앞다리" if part == "front" else "뒷다리"
        if si < 5:
            say = f"{leg_kr} 양쪽을 비슷하게 써요"
        else:
            w = word[worst["n"]]
            say = f"{side_kr[weak]} {leg_kr}의 {w}{'이' if (ord(w[-1]) - 0xAC00) % 28 else '가'} 반대쪽보다 작아요"
        for side in ("l", "r"):
            code = ("L" if side == "l" else "R") + ("F" if part == "front" else "H")
            on = si >= 5 and side == weak
            fills[code] = lv[2] if on else ("#DCEFE2" if si < 5 else "#E9E4DC")
            legs[code] = {
                "label": dict((c, k_) for _, c, k_ in _LEGS)[code], "weak": on, "c": lv[3] if on else "#5B6472",
                "dot": fills[code],
                "mets": [{"n": m["n"], "v": f"{m[side]}{m['u']}", "other": f"{m['r' if side == 'l' else 'l']}{m['u']}",
                          "lower": m[side] < m["r" if side == "l" else "l"]} for m in mets],
            }
        legs[part] = {"si": round(si, 1), "level": lv[1], "c": lv[3], "say": say, "metric": worst["n"],
                      "diff": f"{abs(worst['l'] - worst['r'])}{worst['u']}"}
    svg = _svg(d.size if d else "M")
    for pid, code, _ in _LEGS:
        stroke = 'stroke="#D2601A" stroke-width="6" stroke-dasharray="14 8"' if d and d.focus == code else 'stroke="#B8B0A4" stroke-width="2"'
        svg = svg.replace(f'<path id="{pid}" fill="#E9E4DC" stroke="#B8B0A4" stroke-width="2"',
                          f'<path id="{pid}" fill="{fills[code]}" {stroke}', 1)
    vs = list(reversed(valid(acct, r.dog)))
    idx = next((i for i, x in enumerate(vs) if x.id == r.id), len(vs) - 1)
    hist = vs[: idx + 1][-8:]
    lo, hi = (min(x.sym for x in hist) - 3, max(x.sym for x in hist) + 3) if hist else (0, 100)
    trend = [{"x": round(30 + i * (300 / max(1, len(hist) - 1)), 1), "y": round(80 - (x.sym - lo) / (hi - lo) * 64, 1),
              "v": x.sym, "t": short(x.date), "cur": x.id == r.id} for i, x in enumerate(hist)]
    base_id = base_of(acct, d) if d else None
    base = next((x for x in vs if x.id == base_id), None)
    return {"svg": svg, "legs": legs, "sym": r.sym, "sym_level": _level(100 - r.sym),
            "vs_base": (r.sym - base.sym) if base and base.id != r.id else None,
            "base_date": short(base.date) if base else "", "focus": LIMB.get(d.focus, "") if d and d.focus else "",
            "trend": trend, "trend_line": " ".join(f"{p['x']},{p['y']}" for p in trend)}


# ── 홈 표 한 줄 값 (10-28) ──
def age(d: Dog) -> str:
    try:
        return f"{date.today().year - int(d.birth)}살"
    except ValueError:
        return "나이 미입력"


def days_ago(day: str) -> int:
    return (date.today() - date.fromisoformat(day)).days


def latest_vital(d: Dog) -> Optional[Vital]:
    return d.vitals[0] if d.vitals else None


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def vital_flags(v: Vital, size: str = "M", prev: Optional[Vital] = None) -> dict:
    """바이탈 이상값 표시(EMR 의 H/L). 참고 범위는 config.VITAL_REF(일반 성견). 체중은 직전 방문 대비 변화율."""
    red, amber, ok = "#C2412D", "#9A6A12", ""
    out = {k: {"m": "", "c": ok, "ref": ""} for k in ("kg", "temp", "hr", "bp")}
    lo, hi = VITAL_REF["temp"]
    t = _num(v.temp)
    out["temp"]["ref"] = f"참고 {lo}~{hi}℃"
    if t is not None and not lo <= t <= hi:
        out["temp"].update(m="H" if t > hi else "L", c=red)
    lo, hi = VITAL_REF["hr"].get(size or "M", VITAL_REF["hr"]["M"])
    h = _num(v.hr)
    out["hr"]["ref"] = f"참고 {lo}~{hi}회/분({SIZE.get(size or 'M', '')})"
    if h is not None and not lo <= h <= hi:
        out["hr"].update(m="H" if h > hi else "L", c=red)
    low, border, high = VITAL_REF["sbp"]
    s = _num(v.sbp)
    out["bp"]["ref"] = f"수축기 참고 {low}~{border - 1}, {border}~{high - 1} 경계, {high} 이상 높음"
    if s is not None:
        if s >= high or s < low:
            out["bp"].update(m="H" if s >= high else "L", c=red)
        elif s >= border:
            out["bp"].update(m="경계", c=amber)
    k, pk = _num(v.kg), _num(prev.kg) if prev else None
    if k is not None and pk:
        ch = (k - pk) / pk * 100
        out["kg"]["ref"] = f"직전 방문 {prev.kg}kg 대비 {ch:+.1f}%"
        if abs(ch) > WEIGHT_CHANGE:
            out["kg"].update(m=f"{'▲' if ch > 0 else '▼'}{abs(ch):.0f}%", c=red)
    return out


def vital_line(v: Optional[Vital], size: str = "M", prev: Optional[Vital] = None) -> dict:
    """체중 · 체온 · 심박 · 혈압. 재지 않은 값은 '—'. f = 이상값 표시"""
    if not v:
        return {"kg": "—", "temp": "—", "hr": "—", "bp": "—", "when": "기록 없음", "f": {}}
    return {"kg": f"{v.kg}kg" if v.kg else "—", "temp": f"{v.temp}℃" if v.temp else "—",
            "hr": v.hr or "—", "bp": f"{v.sbp}/{v.dbp}" if v.sbp else "—", "when": short_day(v.day),
            "f": vital_flags(v, size, prev)}


def prev_vital(d: Dog, v: Vital) -> Optional[Vital]:
    """v 바로 전 방문의 바이탈(체중 변화 비교용)."""
    return next((x for x in d.vitals if x.day < v.day and x.kg), None)


def short_day(day: str) -> str:
    p = day.split("-")
    return f"{int(p[1])}/{int(p[2])}" if len(p) == 3 else day


def badges(d: Dog) -> list:
    """홈에 바로 보이는 특이사항: 최근 수술(없으면 진단) 하나만. 메모는 쌓이므로 목록에 내용을 띄우지 않는다(차트·오른쪽 패널에서 본다)."""
    out = []
    surg = next((h for h in reversed(d.history) if h.kind == "수술"), None)
    if surg:
        out.append({"t": f"{surg.title.split(' (')[0]} · {SITE.get(surg.site, '')} · D+{days_ago(surg.day)}",
                    "kind": "surg"})
    else:
        diag = next((h for h in reversed(d.history) if h.kind == "진단"), None)
        if diag:
            out.append({"t": f"{diag.title.split(' (')[0]} · {SITE.get(diag.site, '')}", "kind": "diag"})
    return out


def trend(acct: Account, d: Dog) -> dict:
    """대칭 지수 작은 그래프(최근 유효 회차 6개)와 직전 대비 판정."""
    vs = list(reversed(valid(acct, d.id)))[-6:]
    if not vs:
        return {"has": False}
    syms = [r.sym for r in vs]
    lo, hi = min(syms) - 1, max(syms) + 1
    pts = " ".join(f"{4 + i * (64 / max(1, len(syms) - 1)):.0f},{22 - (s - lo) / (hi - lo) * 18:.0f}"
                   for i, s in enumerate(syms))
    diff = syms[-1] - syms[-2] if len(syms) > 1 else 0
    label, c = (("첫 측정", "#7A808A") if len(syms) == 1 else
                ("좋아짐", "#2E8B57") if diff >= SYM_CHANGE else
                ("나빠짐", "#C2412D") if diff <= -SYM_CHANGE else ("비슷함", "#7A808A"))
    return {"has": True, "pts": pts, "sym": syms[-1], "label": label, "c": c, "single": len(syms) == 1}


def changes(acct: Account, d: Dog) -> tuple[list, str]:
    """최근 CHANGE_DAYS 일 안의 변동 사유와 가장 최근 변동일.
    EMR 처럼 조치가 필요하거나 이상한 것만 띄운다(11-02): 재촬영, 보행 나빠짐·좋아짐, 수술 등록, 중요 메모.
    새 측정·새 진단·재활 단계 변경은 기록이 생긴 사실일 뿐이라 차트 이력에서 본다."""
    out, last = [], ""

    def add(day, label, tone):
        nonlocal last
        out.append({"t": label, "tone": tone})
        last = max(last, day)

    for h in d.history:
        if h.kind == "수술" and days_ago(h.day) <= CHANGE_DAYS:
            add(h.day, "수술 등록", "surg")
    rs = [r for r in acct.results if r.dog == d.id and r.day]
    for r in rs:
        if days_ago(r.day) > CHANGE_DAYS:
            continue
        if r.st == "fail":
            add(r.day, "재촬영 필요", "bad")
            continue
        prev = next((x for x in rs if x.st != "fail" and x.day < r.day), None)
        if r.st == "part":
            add(r.day, "일부 유효 · 재촬영 권장", "warn")
        if prev and r.sym - prev.sym >= SYM_CHANGE:
            add(r.day, f"보행 좋아짐 +{r.sym - prev.sym}%p", "good")
        elif prev and prev.sym - r.sym >= SYM_CHANGE:
            add(r.day, f"보행 나빠짐 −{prev.sym - r.sym}%p", "bad")
    for n in d.notes:
        if n.important and days_ago(n.at[:10]) <= CHANGE_DAYS:
            add(n.at[:10], "중요 메모", "warn")
    seen, uniq = set(), []
    for x in out:   # 같은 사유는 한 번만
        if x["t"] not in seen:
            seen.add(x["t"])
            uniq.append(x)
    return uniq, last


def patient_row(acct: Account, d: Dog, live: set) -> dict:
    st_label, st_bg, st_c = STAGE[d.stage]
    last = next((r for r in acct.results if r.dog == d.id), None)
    ch, ch_day = changes(acct, d)
    return {
        "id": d.id, "no": d.no or "—", "name": d.name, "init": d.name[0],
        "breed": d.breed or "견종 미입력", "size": SIZE.get(d.size, ""), "age": age(d), "sex": SEX.get(d.sex, ""),
        "v": vital_line(latest_vital(d), d.size, prev_vital(d, latest_vital(d)) if d.vitals else None), "badges": badges(d),
        "owner": d.owner or "—", "phone4": d.phone[-4:] if d.phone else "",
        "last": f"{short(last.date)} · {last.by.split(' ')[0]}" if last else "측정 전", "tr": trend(acct, d),
        "stage": st_label, "st_bg": st_bg, "st_c": st_c, "live": d.id in live,
        "changes": ch, "ch_day": ch_day, "site": next((h.site for h in reversed(d.history) if h.site), ""),
    }


# ── 홈: 분석 · 반려견 · 촬영 담당자 목록 (10-28 2판) ──
def dog_text(d: Dog) -> str:
    """검색 대상: 이름·동물번호·견종·보호자·진단/수술·메모."""
    return " ".join([d.name, d.no, d.breed, d.owner, d.phone[-4:] if d.phone else "", d.memo]
                    + [h.title for h in d.history] + [n.text for n in d.notes])


def analysis_rows(acct: Account, rs: list) -> list:
    out = []
    for r in rs:
        d = acct.dog(r.dog)
        out.append({"id": r.id, "dog": d.id, "name": d.name, "no": d.no or "—", "breed": d.breed or "견종 미입력",
                    "when": f"{short(r.date)} {r.time}", "no_s": f"{sess_no(acct, r)}회차", **st_chip(r.st),
                    "sym": "—" if r.st == "fail" else f"{r.sym}%", "pass": "—" if r.st == "fail" else f"{r.ps[1]} / {r.ps[0]}",
                    "by": r.by or "—", "badges": badges(d), "dx": diagnosis(d), **sym_view(acct, r)})
    return out


def sym_view(acct: Account, r) -> dict:
    """분석 표의 대칭 지수 배지: 수준별 색, 직전 유효 회차 대비 오르내림"""
    if r.st == "fail":
        return {"sym_bg": "#F2EFEA", "sym_c": "#8E949C", "sym_d": ""}
    lv = ((90, "", "#DCEFE2", "#2E7A4F") if r.sym >= 90 else (80, "", "#FBEBC8", "#8A6100") if r.sym >= 80
          else (0, "", "#FBE0D9", "#C2412D"))   # 회차 균형 점수 기준(다리 하나 차이 기준 _LEVEL 과 다름)
    prev = next((x for x in acct.results if x.dog == r.dog and x.st != "fail" and (x.day, x.time) < (r.day, r.time)), None)
    dv = r.sym - prev.sym if prev else 0
    return {"sym_bg": lv[2], "sym_c": lv[3],
            "sym_d": (f"▲{dv}" if dv > 0 else f"▼{-dv}") if prev and dv else "", "sym_dc": "#2E8B57" if dv > 0 else "#C2412D"}


def diagnosis(d: Dog) -> str:
    """병명: 히스토리의 가장 최근 진단(분석 표 칸). 괄호 설명은 뺀다"""
    h = next((h for h in reversed(d.history) if h.kind == "진단"), None)
    return h.title.split(" (")[0] if h else "—"


def today_rows(acct: Account, dogs: list) -> list:
    """홈 '오늘' 탭(EMR 의 오늘 접수 목록): 오늘 바이탈·진료 기록·메모·보행 측정이 있거나 지금 분석 중인 반려견.
    시각 = 오늘 처음 남긴 기록 시각. 진료 기록(SOAP)이 아직 없으면 '기록 전'."""
    today = date.today().isoformat()
    live = {j.dog: j for j in acct.active_jobs()}
    out = []
    for d in dogs:
        notes = [n for n in d.notes if n.at.startswith(today)]
        res = [r for r in acct.results if r.dog == d.id and r.day == today]
        vit = next((v for v in d.vitals if v.day == today), None)
        if not (notes or res or vit or d.id in live):
            continue
        times = [n.at[11:16] for n in notes] + [r.time for r in res]
        steps = []
        if vit:
            steps.append(("바이탈", "#E7EEFB", "#3B5BA9"))
        if any(n.cat in SOAP for n in notes):
            steps.append(("진료 기록", "#E3F1E7", "#2E7A4F"))
        if d.id in live:
            steps.append(("분석 중", "#FCEEE3", "#A8481A"))
        for r in res:
            steps.append((("재촬영 필요" if r.st == "fail" else "보행 측정"), "#FBE0D9" if r.st == "fail" else "#F1ECE5", "#C2412D" if r.st == "fail" else "#5B6472"))
        done = any(n.cat in SOAP for n in notes)
        out.append({**patient_row(acct, d, set(live)), "time": min(times) if times else "—",
                    "steps": [{"t": t, "bg": bg, "c": c} for t, bg, c in steps], "dx": diagnosis(d),
                    "who": next((n.author for n in sorted(notes, key=lambda n: n.at)), "") or (live[d.id].by if d.id in live else "") or (vit.author if vit else ""),
                    "todo": "" if done else "진료 기록 전"})
    return sorted(out, key=lambda r: r["time"])


def staff_rows(acct: Account, rs: list) -> list:
    by = {}
    for r in rs:
        if not r.by:
            continue
        x = by.setdefault(r.by, {"name": r.by, "n": 0, "dogs": set(), "last": "", "fail": 0})
        x["n"] += 1
        x["dogs"].add(r.dog)
        x["last"] = max(x["last"], r.day)
        x["fail"] += r.st == "fail"
    return [{**x, "dogs": len(x["dogs"]), "last": short_day(x["last"]) if x["last"] else "—"}
            for x in sorted(by.values(), key=lambda x: -x["n"])]


def home_view(acct: Account, view: str, q: str, dog: str, by: str, changed: bool, stage: str, page: int) -> dict:
    q = q.strip()
    ch = {d.id: changes(acct, d) for d in acct.dogs}
    dogs = [d for d in acct.dogs if (not q or q in dog_text(d)) and (not changed or ch[d.id][0])
            and (stage not in STAGE or d.stage == stage)]
    keep = {d.id for d in dogs}
    rs = [r for r in acct.results if acct.dog(r.dog)]
    counts = {"dogs": len(acct.dogs), "changed": sum(1 for v in ch.values() if v[0]),
              "retake": sum(1 for v in ch.values() if any("재촬영" in c["t"] and c["tone"] == "bad" for c in v[0]))}
    counts["today"] = len(today_rows(acct, acct.dogs))
    if view == "today":
        rows = today_rows(acct, dogs)
    elif view == "dogs":
        rows = [{**patient_row(acct, d, set()), "n": sum(1 for r in rs if r.dog == d.id)} for d in dogs]
        if changed:
            rows.sort(key=lambda r: r["ch_day"], reverse=True)
    elif view == "staff":
        rows = staff_rows(acct, [r for r in rs if r.dog in keep or (q and q in r.by)])
    else:
        sel = [r for r in rs if (r.dog in keep or (q and q in r.by)) and (not dog or r.dog == dog) and (not by or r.by == by)]
        rows = analysis_rows(acct, sel) if view == "analyses" else []
    total = len(rows)
    pages = max(1, -(-total // PAGE_SIZE))
    page = min(max(1, page), pages)
    return {"rows": rows[(page - 1) * PAGE_SIZE: page * PAGE_SIZE], "total": total, "page": page, "pages": pages, **counts}


def memos(d: Dog) -> list:
    """차트 위 고정 줄의 메모 카드: 주의·보호자·예약·기타. 중요 먼저, 그 안에서 최신순. 등록할 때 적은 메모(Dog.memo)는 맨 끝."""
    rows = [{"id": n.id, "cat": n.cat, "bg": MEMO_CAT[n.cat][0], "c": MEMO_CAT[n.cat][1], "text": n.text, "imp": n.important,
             "at": n.at.replace("-", ".", 2)[2:], "author": n.author,
             "revs": [{"at": a.replace("-", ".", 2)[2:], "author": w, "text": t} for a, w, t in n.revs]}
            for n in sorted(d.notes, key=lambda n: (n.important, n.at), reverse=True) if n.cat in MEMO_CAT]
    if d.memo:
        rows.append({"id": "", "cat": "등록", "bg": "#F1ECE5", "c": "#5B6472", "text": d.memo, "imp": False, "at": "", "author": "", "revs": []})
    return rows


def memo_panel(acct: Account, d: Dog, rid: str = "") -> dict:
    """분석 결과 화면 오른쪽 칸: 메모를 바로 쓰고 보며, 이 회차 진료 기록을 본다."""
    groups = soap_entries(d, acct)
    return {**patient_row(acct, d, set()), "rid": rid, "memo_cat": MEMO_CAT, "memos": memos(d),
            "run_soap": [g for g in groups if rid and g["rid"] == rid],
            "n_res": sum(1 for r in acct.results if r.dog == d.id)}


def visits(acct: Account, d: Dog) -> list:
    """방문 목록(EMR 왼쪽 칸): 같은 날짜의 보행 측정·바이탈·진료 기록·진단/수술/재활·영상을 한 방문으로 묶는다. 최신순.
    방문은 따로 저장하지 않고 날짜로 묶어 만든다(백엔드에 방문 엔티티 없음)."""
    by = {}

    def v(day):
        return by.setdefault(day, {"day": day, "res": [], "vital": None, "soap": [], "hist": [], "imgs": []})

    for r in acct.results:
        if r.dog == d.id and r.day:
            v(r.day)["res"].append(r)
    for x in d.vitals:
        v(x.day)["vital"] = x
    for g in soap_entries(d, acct):
        v("20" + g["at"][:8].replace(".", "-"))["soap"].append(g)
    for h in d.history:
        v(h.day)["hist"].append(h)
    for im in d.images:
        v(im.day)["imgs"].append(im)
    out = []
    for day in sorted(by, reverse=True):
        x = by[day]
        res = sorted(x["res"], key=lambda r: r.time)
        tags = [{"t": h.kind, "bg": "#FCEEE3" if h.kind == "수술" else "#EEF1F6", "c": "#A8481A" if h.kind == "수술" else "#4A5A78"}
                for h in x["hist"]]
        if res:
            tags.append({"t": "보행 측정", "bg": "#F1ECE5", "c": "#5B6472"})
        if x["imgs"]:
            tags.append({"t": f"영상 {len(x['imgs'])}", "bg": "#F1ECE5", "c": "#5B6472"})
        a = next((p["text"] for g in x["soap"] for p in g["parts"] if p["cat"] in ("A", "S")), "")
        title = (x["hist"][0].title.split(" (")[0] if x["hist"] else a or
                 (f"보행 측정 · 대칭 지수 {res[-1].sym}%" if res and res[-1].st != "fail" else "보행 측정 · 재촬영 필요" if res else
                  "바이탈 측정" if x["vital"] else ""))
        who = next((g["author"] for g in x["soap"]), "") or next((h.by or h.author for h in x["hist"]), "") or             (res[-1].by if res else "") or (x["vital"].author if x["vital"] else "")
        st = st_chip(res[-1].st) if res else None
        out.append({"day": day, "date": day[2:].replace("-", "."), "tags": tags, "title": title, "who": who, "st": st,
                    "n_soap": len(x["soap"]), "today": day == date.today().isoformat(),
                    "res": [{"id": r.id, "no": f"{sess_no(acct, r)}회차", "time": r.time, "by": r.by, "fail": r.st == "fail",
                             "sym": r.sym, "rom": r.rom, "sL": r.sL, "sR": r.sR, **st_chip(r.st), **sym_view(acct, r)} for r in res],
                    "vital": vital_line(x["vital"], d.size, prev_vital(d, x["vital"])) if x["vital"] else None, "vital_by": x["vital"].author if x["vital"] else "",
                    "soap": x["soap"], "hist": x["hist"],
                    "imgs": [{"id": im.id, "path": im.path, "caption": im.caption, "kind": IMG_KIND.get(im.kind, im.kind), "by": im.author}
                             for im in x["imgs"]]})
    return out


# 보호자용 "알아 두면 좋은 점"(11-02): 덜 쓰는 다리가 있을 때 걸음에 생기는 일, 집에서 보일 수 있는 모습, 도와줄 일.
# 병명·질환 가능성·정상 범위는 말하지 않는다(PR-F08-11). 문구는 수의사 검토 전 초안이다.
_PLAIN = {"팔꿈치 가동 범위": "팔꿈치를 굽히는 폭", "무릎 가동 범위": "무릎을 굽히는 폭", "고관절 가동 범위": "엉덩이 관절이 움직이는 폭",
          "걸음 길이": "한 걸음 길이", "입각기 비율": "발을 딛고 있는 시간"}
_URGENT = ["다리를 전혀 딛지 않을 때", "만졌을 때 싫어하거나, 붓거나, 열감이 있을 때", "며칠 사이 갑자기 더 절 때"]


def owner_guide(bm: dict) -> dict:
    """첫 쪽 주요 소견 한 문장과 둘째 쪽 보호자 안내. 덜 쓰는 쪽은 대칭 지수 차이가 더 큰 쌍(앞·뒤)에서 고른다."""
    fr, hd = bm["legs"]["front"], bm["legs"]["hind"]
    part = "hind" if hd["si"] >= fr["si"] else "front"
    p = bm["legs"][part]
    fh = "H" if part == "hind" else "F"
    weak = next((s + fh for s in "LR" if bm["legs"][s + fh]["weak"]), None)
    if p["si"] < 5 or not weak:
        return {"weak": False, "summary": "앞다리·뒷다리 모두 양쪽을 비슷하게 써요.",
                "what": "왼쪽·오른쪽 다리에 몸무게를 비슷하게 싣고 걸어요.",
                "look": [], "help": ["지금처럼 꾸준히 산책해 주세요", "미끄러운 바닥에는 매트를 깔아 주세요"], "urgent": _URGENT}
    side = "왼쪽" if weak[0] == "L" else "오른쪽"
    other = "오른쪽" if side == "왼쪽" else "왼쪽"
    leg = "뒷다리" if part == "hind" else "앞다리"
    m = next((x for x in bm["legs"][weak]["mets"] if x["n"] == p["metric"]), bm["legs"][weak]["mets"][0])
    plain = _PLAIN.get(m["n"], m["n"])
    josa = "이" if (ord(plain[-1]) - 0xAC00) % 28 else "가"   # 받침 있으면 이, 없으면 가
    summary = f"{side} {leg}를 덜 써요. {plain}{josa} {side} {m['v']}, {other} {m['other']}예요."
    what = f"{side} {leg}에 몸무게를 덜 싣고 걸어요. 그만큼 {other} {leg}" + ("와 앞다리가" if part == "hind" else "와 뒷다리가") + " 몸무게를 더 받아요."
    if part == "hind":
        look = [f"{side} 뒷다리를 디딜 때 엉덩이가 들썩이거나, 몸이 {other}으로 기울어 보일 수 있어요",
                f"앉을 때 {side} 뒷다리를 옆으로 빼고 앉을 수 있어요",
                "계단을 오르거나 소파·차에 뛰어오를 때 머뭇거릴 수 있어요"]
        help_ = ["미끄러운 바닥에는 매트를 깔아 주세요",
                 "계단·점프는 담당 수의사가 괜찮다고 할 때까지 줄여 주세요",
                 "산책은 평지에서 짧게, 자주 하는 것이 좋아요",
                 f"양쪽 허벅지 굵기를 가끔 손으로 만져 비교해 보세요. {side}이 가늘어지면 다음 진료 때 알려 주세요"]
    else:
        look = [f"{side} 앞다리를 디딜 때 고개가 위로 들리며 끄덕이듯 걸을 수 있어요",
                f"서 있을 때 {side} 앞발을 살짝 들거나 짧게 디딜 수 있어요",
                "계단을 내려가거나 높은 곳에서 뛰어내릴 때 머뭇거릴 수 있어요"]
        help_ = ["미끄러운 바닥에는 매트를 깔아 주세요",
                 "계단 내려가기·높은 곳에서 뛰어내리기는 담당 수의사가 괜찮다고 할 때까지 줄여 주세요",
                 "산책은 평지에서 짧게, 자주 하는 것이 좋아요"]
    return {"weak": True, "summary": summary, "what": what, "look": look, "help": help_, "urgent": _URGENT}


def best_view(bm: dict) -> dict:
    """3D 에서 좌우 차이가 가장 잘 보이는 각도. 이 3D 는 다리마다 관절을 굽히는 폭·딛는 시간을 바꾸므로
    (엉덩이 높이·머리 끄덕임은 흉내 내지 않는다) 기본은 덜 쓰는 다리 쪽 옆모습이고, 두 다리를 한 화면에서 견줄 때는
    뒷다리면 뒤에서, 앞다리면 앞에서 본다."""
    pairs = [(p, bm["legs"][p]) for p in ("hind", "front")]
    part, x = max(pairs, key=lambda t: t[1]["si"])
    leg_kr = "뒷다리" if part == "hind" else "앞다리"
    if x["si"] < 5:
        return {"main": "right", "label": "옆", "sub": "back", "sub_label": "뒤",
                "why": "좌우 차이가 거의 없어요. 옆에서 걷는 모양을, 뒤에서 두 뒷다리가 같이 움직이는지 보세요."}
    fh = "F" if part == "front" else "H"
    weak = next(s + fh for s in "LR" if bm["legs"][s + fh]["weak"])
    side = "left" if weak[0] == "L" else "right"
    side_kr = "왼쪽" if side == "left" else "오른쪽"
    sub, sub_kr = ("back", "뒤") if part == "hind" else ("front", "앞")
    return {"main": side, "label": f"{side_kr} 옆", "sub": sub, "sub_label": sub_kr,
            "why": f"{side_kr} {leg_kr}가 덜 움직여요. {side_kr} 옆에서 보면 그 다리가 관절을 덜 굽히고 짧게 딛는 게 가려지지 않고 보여요. "
                   f"{sub_kr}에서 보면 두 {leg_kr}의 발 드는 높이를 한 화면에서 견줄 수 있어요."}


def image_list(d: Dog) -> list:
    """환자 단위 영상·사진 모아 보기(경과 탭): 촬영일 순(오래된 것 먼저)이라 수술 전 → 후가 왼쪽에서 오른쪽으로 놓인다."""
    return [{"id": im.id, "day": im.day, "date": im.day[2:].replace("-", "."), "path": im.path, "caption": im.caption,
             "kind": IMG_KIND.get(im.kind, im.kind), "pre": im.kind == "pre", "post": im.kind == "post", "by": im.author}
            for im in sorted(d.images, key=lambda x: x.day)]


def dx_history(acct: Account, d: Dog) -> list:
    """진단 이력(EMR 오른쪽 칸): 진단 하나에 뒤따른 수술·재활을 묶는다. 종결 기록이 있으면 종결, 아니면 진행중.
    회차 = 진단일 이후 보행 측정 수."""
    eps = []
    for h in d.history:
        if h.kind == "진단" or not eps:
            eps.append({"start": h.day, "title": h.title.split(" (")[0], "site": SITE.get(h.site, ""), "by": h.by or h.author, "events": []})
        if h.kind != "진단":
            eps[-1]["events"].append({"day": h.day[2:].replace("-", "."), "kind": h.kind, "title": h.title})
    for i, e in enumerate(eps):
        end = eps[i + 1]["start"] if i + 1 < len(eps) else None
        done = any("종결" in x["title"] for x in e["events"])
        e["done"] = done
        e["n"] = sum(1 for r in acct.results if r.dog == d.id and r.day >= e["start"] and (not end or r.day < end))
        e["range"] = e["start"][2:].replace("-", ".") + " ~" + (" " + next(x["day"] for x in reversed(e["events"]) if "종결" in x["title"]) if done else "")
    return list(reversed(eps))


def care_team(acct: Account, d: Dog) -> dict:
    """담당: 주치의 = 최근 진단·수술한 수의사, 최근 측정 = 마지막 회차 측정자."""
    h = next((h for h in reversed(d.history) if h.kind in ("수술", "진단") and h.by), None)
    last = next((r for r in acct.results if r.dog == d.id), None)
    return {"doctor": h.by if h else "—", "measurer": last.by if last and last.by else "—"}


# ── 반려견 차트 (10-28) ──
def chart_summary(acct: Account, d: Dog) -> dict:
    """차트 요약 탭: 시간 축 하나에 대칭 지수 선, 수술·재활 단계 세로선, 메모·바이탈 점."""
    vs = [r for r in reversed(valid(acct, d.id)) if r.day]
    days = [h.day for h in d.history] + [r.day for r in vs] + [v.day for v in d.vitals] + [n.at[:10] for n in d.notes]
    if not days:
        return {"has": False}
    t0 = date.fromisoformat(min(days))
    t1 = date.today()
    span = max(1, (t1 - t0).days)
    W, H, L, R, T, B = 760, 220, 44, 16, 18, 52   # 그림 크기와 여백

    def X(day):
        return round(L + (date.fromisoformat(day) - t0).days / span * (W - L - R), 1)

    syms = [r.sym for r in vs]
    lo, hi = (min(syms) - 3, max(syms) + 3) if syms else (70, 100)

    def Y(v):
        return round(T + (hi - v) / (hi - lo) * (H - T - B), 1)

    marks = [{"x": X(h.day), "kind": h.kind, "label": h.title.split(" (")[0], "day": short_day(h.day)}
             for h in d.history if h.kind in ("수술", "재활")]
    pts = [{"x": X(r.day), "y": Y(r.sym), "sym": r.sym, "day": short_day(r.day), "by": r.by, "id": r.id} for r in vs]
    notes = [{"x": X(n.at[:10]), "imp": n.important, "t": n.text[:40], "day": short_day(n.at[:10])} for n in d.notes]
    vit = [{"x": X(v.day)} for v in d.vitals]
    ticks = []
    for k in range(6):
        day = t0.toordinal() + round(span * k / 5)
        ticks.append({"x": round(L + k / 5 * (W - L - R), 1), "t": short_day(date.fromordinal(day).isoformat())})
    first, last = (vs[0], vs[-1]) if vs else (None, None)
    surg = next((h for h in reversed(d.history) if h.kind == "수술"), None)
    return {
        "has": True, "W": W, "H": H, "L": L, "R": R, "T": T, "B": B, "line": " ".join(f"{p['x']},{p['y']}" for p in pts),
        "pts": pts, "marks": marks, "notes": notes, "vit": vit, "ticks": ticks,
        "yt": [{"y": Y(v), "v": v} for v in (round(lo + 3), round((lo + hi) / 2), round(hi - 3))],
        "facts": [
            {"k": "수술 후", "v": f"D+{days_ago(surg.day)}" if surg else "수술 없음", "sub": surg.title.split(" (")[0] if surg else ""},
            {"k": "대칭 지수", "v": f"{last.sym}%" if last else "—",
             "sub": f"첫 측정 {first.sym}% → {last.sym - first.sym:+d}%p" if last and first is not last else ("첫 측정" if last else "유효 측정 없음")},
            {"k": "보행 측정", "v": f"{len(vs)}회 유효", "sub": f"마지막 {short_day(last.day)} · {last.by}" if last else ""},
            {"k": "마지막 바이탈", "v": vital_line(latest_vital(d))["when"], "sub": d.vitals[0].author if d.vitals else ""},
        ],
    }


def note_rows(d: Dog, acct: Optional[Account] = None) -> list:
    def run_label(rid):   # 회차 메모면 "10.25 · 5회차"
        r = acct.result(rid) if acct and rid else None
        return f"{short(r.date)} · {sess_no(acct, r)}회차" if r else ""

    return [{"id": n.id, "at": n.at.replace("-", ".", 2)[2:], "author": n.author, "cat": n.cat, "text": n.text,
             "imp": n.important, "rid": n.rid, "run": run_label(n.rid),
             "soap": SOAP.get(n.cat, ("", ""))[0],
             "revs": [{"at": a.replace("-", ".", 2)[2:], "author": w, "text": t} for a, w, t in n.revs]}
            for n in sorted(d.notes, key=lambda n: (n.important, n.at), reverse=True)]   # 중요 메모 먼저, 그 안에서 최신순


def soap_entries(d: Dog, acct: Optional[Account] = None) -> list:
    """차트 '진료 기록' 탭: 같은 시각·같은 사람·같은 회차로 쓴 메모를 한 기록으로 묶고 S·O·A·P 순서로 보인다(EMR 방식).
    중요 표시가 있는 기록이 먼저, 그 안에서 최신순."""
    groups = {}
    for n in note_rows(d, acct):
        if n["cat"] not in SOAP:     # 메모(주의·보호자·예약·기타)는 진료 기록이 아니다
            continue
        g = groups.setdefault((n["at"], n["author"], n["rid"]), {"at": n["at"], "author": n["author"], "rid": n["rid"],
                                                                  "run": n["run"], "imp": False, "parts": []})
        g["imp"] = g["imp"] or n["imp"]
        g["parts"].append(n)
    order = {k: i for i, k in enumerate(NOTE_CAT)}
    for g in groups.values():
        g["parts"].sort(key=lambda x: order.get(x["cat"], 9))
    return sorted(groups.values(), key=lambda g: (g["imp"], g["at"]), reverse=True)


def kg_trend(d: Dog, n: int = 8) -> dict:
    """차트 위 고정 줄의 체중 추이(최근 n번 방문). 세로 폭은 최소 ±0.5kg 로 잡아 작은 흔들림이 크게 보이지 않게 한다."""
    kg = [(v.day, _num(v.kg)) for v in reversed(d.vitals) if _num(v.kg)][-n:]
    if len(kg) < 2:
        return {"has": False}
    vals = [k for _, k in kg]
    mid, half = (max(vals) + min(vals)) / 2, max(0.5, (max(vals) - min(vals)) / 2 * 1.15)
    W, H = 72, 22
    pts = [(2 + i * (W - 4) / (len(kg) - 1), H - 3 - (k - (mid - half)) / (2 * half) * (H - 6)) for i, (_, k) in enumerate(kg)]
    ch = (vals[-1] - vals[0]) / vals[0] * 100
    return {"has": True, "W": W, "H": H, "line": " ".join(f"{x:.1f},{y:.1f}" for x, y in pts), "last": pts[-1],
            "text": f"{vals[0]:g}→{vals[-1]:g}kg", "ch": f"{ch:+.1f}%", "n": len(kg), "since": short_day(kg[0][0]),
            "c": "#C2412D" if abs(ch) > WEIGHT_CHANGE else "#5B6472"}


def vital_rows(d: Dog) -> dict:
    rows = [{"day": v.day, **vital_line(v, d.size, prev_vital(d, v)), "author": v.author} for v in d.vitals]
    kg = [(v.day, float(v.kg)) for v in reversed(d.vitals) if v.kg]
    spark = ""
    if len(kg) > 1:
        lo, hi = min(k for _, k in kg) - 0.2, max(k for _, k in kg) + 0.2
        spark = " ".join(f"{6 + i * (188 / (len(kg) - 1)):.0f},{34 - (k - lo) / (hi - lo) * 28:.0f}" for i, (_, k) in enumerate(kg))
    return {"rows": rows, "kg_spark": spark, "kg_range": f"{kg[0][1]} → {kg[-1][1]}kg" if kg else ""}


# ── 경과 비교 ──
_CMP = [
    ("무릎 가동 범위", "LH", lambda r: r.j[0][1], "°"), ("무릎 가동 범위", "RH", lambda r: r.j[0][2], "°"),
    ("고관절 가동 범위", "LH", lambda r: r.j[1][1], "°"), ("고관절 가동 범위", "RH", lambda r: r.j[1][2], "°"),
    ("걸음 길이", "LH", lambda r: r.sL if r.m else jround(r.sL * 1.5), "%"), ("걸음 길이", "RH", lambda r: r.sR if r.m else jround(r.sR * 1.5), "%"),
    ("팔꿈치 가동 범위", "LF", lambda r: r.j[2][1], "°"), ("팔꿈치 가동 범위", "RF", lambda r: r.j[2][2], "°"),
    ("대칭 지수", None, lambda r: r.sym, "%"), ("발 높이", "LF", None, "%"),
]
_TREND = {
    "rom": (lambda r: r.j[0][1], lambda r: r.j[0][2]),
    "stride": (lambda r: r.sL if r.m else jround(r.sL * 1.5), lambda r: r.sR if r.m else jround(r.sR * 1.5)),
    "stance": (lambda r: round(real.met(r.m, "stance_ratio", "LH") or 0) if r.m else 61,
               lambda r: round(real.met(r.m, "stance_ratio", "RH") or 0) if r.m else 61 - jround((r.sL - r.sR) / 2)),
    "sym": (lambda r: r.sym, None),
}
TREND_KEYS = [("rom", "무릎 가동 범위"), ("stride", "걸음 길이"), ("stance", "입각기 비율"), ("sym", "대칭 지수")]


def compare_view(acct: Account, d: Dog, mode: str, tk: str) -> dict:
    vs = list(reversed(valid(acct, d.id)))   # 오래된 회차부터
    if len(vs) < 2:
        return {"has": False, "name": d.name}
    t = vs[-1]
    b_id = base_of(acct, d)
    b = next((r for r in vs if r.id == b_id), None) if mode == "base" else vs[-2]
    if not b or b.id == t.id:
        b = vs[-2]
    order = sorted(enumerate(_CMP), key=lambda p: (0 if d.focus and p[1][1] == d.focus else (1 if p[1][2] else 2), p[0]))
    rows = []
    for i, (_, (n, limb, fn, u)) in enumerate(order):
        focus = bool(d.focus) and limb == d.focus
        bt = "1px solid #F2EFEA" if i else "none"
        if not fn:
            rows.append({"n": n, "limb": LIMB[limb], "lc": "#8E949C", "vals": "한쪽 회차에서 측정 불가", "j": "비교 불가",
                         "bg": "#F4F2EE", "c": "#8E949C", "bt": bt})
            continue
        bv, tv = fn(b), fn(t)
        df = tv - bv
        in_range = abs(df) <= 1
        rows.append({"n": n, "limb": (LIMB[limb] + (" · 관심 다리" if focus else "")) if limb else "전체",
                     "lc": "#B4501A" if focus else "#8E949C", "vals": f"{bv}{u} → {tv}{u}",
                     "j": "범위 안" if in_range else (f"▲ 증가 {df}{u}" if df > 0 else f"▼ 감소 {-df}{u}"),
                     "bg": "#F4F2EE" if in_range else "#EEE8DF", "c": "#5B6472" if in_range else "#1B2433", "bt": bt})
    left_fn, right_fn = _TREND.get(tk, _TREND["rom"])
    a_vals = [left_fn(r) for r in vs]
    b_vals = [right_fn(r) for r in vs] if right_fn else []
    all_v = a_vals + b_vals
    mn, mx = min(all_v) - 2, max(all_v) + 2

    def X(i):
        return jround(20 + i * (280 / (len(vs) - 1)))

    def Y(v):
        return jround(130 - (v - mn) / (mx - mn) * 110)

    return {
        "has": True, "name": d.name, "baseLabel": "기준 회차" if mode == "base" else "직전 회차",
        "baseDate": f"{b.date} · {sess_no(acct, b)}회차", "tDate": f"{t.date} · {sess_no(acct, t)}회차",
        "modelChanged": b.model != t.model,
        "modelMsg": f"두 회차의 분석 모델이 달라요({b.model} → {t.model}). 분석 방식이 바뀌어 수치를 그대로 비교하기 어려워요.",
        "rows": rows, "tl": " ".join(f"{X(i)},{Y(v)}" for i, v in enumerate(a_vals)),
        "tr": " ".join(f"{X(i)},{Y(v)}" for i, v in enumerate(b_vals)),
        "dl": [{"x": X(i), "y": Y(v), "c": "#3B6FE0"} for i, v in enumerate(a_vals)]
        + [{"x": X(i), "y": Y(v), "c": "#E5604D"} for i, v in enumerate(b_vals)],
        "xl": [short(r.date) for r in vs], "two": right_fn is not None,
        "focusNote": f"관심 다리({LIMB[d.focus]})를 맨 앞에 보여 드려요." if d.focus else "관심 다리를 정하면 그 다리를 맨 앞에 보여 드려요.",
    }
