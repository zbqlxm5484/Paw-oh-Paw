"""화면에 넣을 값 계산 (디자인의 renderVals를 Python으로 옮김)."""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Optional

from .config import CHANGE_DAYS, LIMB, PAGE_SIZE, SEX, SITE, SIZE, ST, STAGE, SYM_CHANGE, auto_size
from . import real
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


def knee_chart(src: str = "") -> dict:
    """보고서 "뒷무릎 각도 · 보행 주기" 그래프. x = 한 걸음(같은 뒷발 착지 → 다음 착지) 0~100%, y = 무릎 각도(°, engine/angles.py v1).
    회차에 시연 회차가 붙어 있으면 그 회차의 다리별 무릎 곡선, 없으면 시연 걸음(공개 논문 속보 평균, tools/build_demo_clip.py)."""
    s = real.session(src)
    if s and {"LH", "RH"} <= set(s["knee_curve"]):
        L, R = s["knee_curve"]["LH"], s["knee_curve"]["RH"]
        label = (f"AI-Hub 라벨 관절점({real.source_name(s)}) 근사 곡선" if s["source"] == "aihub"
                 else f"실측 영상 {len(s['video_names'])}개({real.source_name(s)}) 걸음 평균")
    else:
        g = json.loads(GAIT_FILE.read_text(encoding="utf-8"))
        L, R = (g["legs"][k]["joint"]["무릎"] for k in ("LH", "RH"))
        label = g["label"]
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
            "x": [{"x": x0 + (x1 - x0) * p / 100, "t": f"{p}%"} for p in (0, 50, 100)],
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
        "kc": knee_chart(r.src), "n_videos": len(r.videos) or 16,
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
    rows = {x["n"]: x for x in mrows(r, "trot") if not x.get("na")}
    pairs = {"front": ["팔꿈치 가동 범위"], "hind": ["무릎 가동 범위", "고관절 가동 범위", "걸음 길이", "입각기 비율"]}
    word = {"팔꿈치 가동 범위": "팔꿈치를 굽히는 정도", "무릎 가동 범위": "무릎을 굽히는 정도",
            "고관절 가동 범위": "엉덩이 관절 움직임", "걸음 길이": "한 걸음 길이", "입각기 비율": "땅을 딛고 있는 시간"}
    legs, fills = {}, {}
    for part, names in pairs.items():
        mets = [rows[n] for n in names if n in rows]
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


def vital_line(v: Optional[Vital]) -> dict:
    """체중 · 체온 · 심박 · 혈압. 재지 않은 값은 '—'."""
    if not v:
        return {"kg": "—", "temp": "—", "hr": "—", "bp": "—", "when": "기록 없음"}
    return {"kg": f"{v.kg}kg" if v.kg else "—", "temp": f"{v.temp}℃" if v.temp else "—",
            "hr": v.hr or "—", "bp": f"{v.sbp}/{v.dbp}" if v.sbp else "—", "when": short_day(v.day)}


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
    """최근 CHANGE_DAYS 일 안의 변동 사유와 가장 최근 변동일."""
    out, last = [], ""

    def add(day, label, tone):
        nonlocal last
        out.append({"t": label, "tone": tone})
        last = max(last, day)

    for h in d.history:
        if days_ago(h.day) <= CHANGE_DAYS:
            add(h.day, {"수술": "수술 등록", "진단": "새 진단"}.get(h.kind, "재활 종결" if "종결" in h.title else "재활 단계 변경"),
                "surg")
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
        elif r.st == "ok":
            add(r.day, "새 측정", "plain")
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
        "v": vital_line(latest_vital(d)), "badges": badges(d),
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
                    "by": r.by or "—", "badges": badges(d)})
    return out


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
    if view == "dogs":
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


def memo_panel(acct: Account, d: Dog, rid: str = "") -> dict:
    """오른쪽 반려견 칸(분석 결과·반려견 차트 공통): 신원·바이탈·특이사항, 이번 회차 메모, 반려견 메모."""
    rows = note_rows(d, acct)
    return {**patient_row(acct, d, set()), "rid": rid,
            "run_notes": [n for n in rows if rid and n["rid"] == rid],
            "dog_notes": [n for n in rows if not rid or n["rid"] != rid][:10],
            "n_notes": len(d.notes), "n_res": sum(1 for r in acct.results if r.dog == d.id)}


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
             "revs": [{"at": a.replace("-", ".", 2)[2:], "author": w, "text": t} for a, w, t in n.revs]}
            for n in sorted(d.notes, key=lambda n: (n.important, n.at), reverse=True)]   # 중요 메모 먼저, 그 안에서 최신순


def vital_rows(d: Dog) -> dict:
    rows = [{"day": v.day, **vital_line(v), "author": v.author} for v in d.vitals]
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
