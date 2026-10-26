"""화면에 넣을 값 계산 (디자인의 renderVals를 Python으로 옮김)."""

from __future__ import annotations

import math
from typing import Optional

from .config import LIMB, SEX, SIZE, ST, auto_size
from .store import Account, Dog, Result


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


def knee(depth: float) -> str:
    """뒷무릎 각도 곡선 (보행 주기 0~100%)."""
    def gs(p, c, w):
        return math.exp(-(((p - c) / w) ** 2))

    pts = []
    for i in range(41):
        p = i / 40
        a = 150 - 16 * gs(p, 0.12, 0.07) - depth * gs(p, 0.7, 0.11)
        pts.append(f"{24 + p * 286:.1f},{130 - (a - 90) / 60 * 110:.1f}")
    return " ".join(pts)


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
    sL, sR = jround(r.sL * 1.5), jround(r.sR * 1.5)
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
        "kL": knee(r.j[0][1] * 0.8), "kR": knee(r.j[0][2] * 0.8), "n_videos": len(r.videos) or 16,
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
        "cond": f"측면 가로 촬영 · 영상 {len(r.videos) or 16}개 · 통과 {r.ps[0]}개 중 {r.ps[1]}개 사용 · 분석 모델 pga-pose {r.model}. 측정 불가 항목은 사유와 함께 표시했습니다.",
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
        hist.append({"id": r.id, "no": f"{sess_no(acct, r)}회차", "date": r.date, "w": f"{r.w}kg",
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


# ── 경과 비교 ──
_CMP = [
    ("무릎 가동 범위", "LH", lambda r: r.j[0][1], "°"), ("무릎 가동 범위", "RH", lambda r: r.j[0][2], "°"),
    ("고관절 가동 범위", "LH", lambda r: r.j[1][1], "°"), ("고관절 가동 범위", "RH", lambda r: r.j[1][2], "°"),
    ("걸음 길이", "LH", lambda r: jround(r.sL * 1.5), "%"), ("걸음 길이", "RH", lambda r: jround(r.sR * 1.5), "%"),
    ("팔꿈치 가동 범위", "LF", lambda r: r.j[2][1], "°"), ("팔꿈치 가동 범위", "RF", lambda r: r.j[2][2], "°"),
    ("대칭 지수", None, lambda r: r.sym, "%"), ("발 높이", "LF", None, "%"),
]
_TREND = {
    "rom": (lambda r: r.j[0][1], lambda r: r.j[0][2]),
    "stride": (lambda r: jround(r.sL * 1.5), lambda r: jround(r.sR * 1.5)),
    "stance": (lambda r: 61, lambda r: 61 - jround((r.sL - r.sR) / 2)),
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
