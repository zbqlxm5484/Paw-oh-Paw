"""10-26 실험(이어 학습: 와우와우 보정·시험 라벨·학습 방식 점검)을 팀 시트 형식으로 내보낸다. 실험 번호 줄부터, 항목 이름 열 없음.
번호는 E-075 부터(10-23 마지막 E-074). 그 사이 누가 붙였으면 밀어서 쓴다. 각 실험은 시드 0 값, 판정 칸에 시드 3개 범위.
모두 기업 정답 채점(정답 상자 + 15%) + flip test."""

import hashlib
import json
import os
import sys
from pathlib import Path

_CVAT = os.environ.get("CVAT_LABELING_DIR", "C:/cvat-labeling")
_OUT = os.environ.get("CREAMOFF_OUT", "C:/Users/SSAFY/Downloads")

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(f"{_OUT}/구글시트_붙여넣기_1026/")
OUT.mkdir(exist_ok=True)
GT1, FP1 = "keypoints_260820 (205장, 221건)", "a08e9d47b680"
DATE = "2026-10-26"
TW = f"{_CVAT}/train_ww/"
BASE = "BN 고정(norm_eval), AdamW lr 5e-5, 100에폭, 배치 32, 좌우 뒤집기·크기 0.8~1.2·회전 15° 증강"
HEAD = BASE + ", 뼈대 고정(backbone lr_mult 0, 머리만 학습)"
mae = lambda f: json.load(open(f, encoding="utf-8"))["kpi"]["KPI-04"]["mae"]


def rng(fs):
    v = [mae(f) for f in fs if Path(f).exists()]
    return f"시드 {len(v)}개 {min(v):.2f}~{max(v):.2f}°" if len(v) > 1 else f"{v[0]:.2f}°"


C = "results/curve/"
E = []


def add(what, name, w, data, recipe, res, judge, nxt="-", seeds=None):
    seeds = seeds or [res]
    E.append(
        dict(
            what=what,
            name=name,
            w=w,
            data=data,
            recipe=recipe,
            f=C + res,
            judge=f"{judge} ({rng([C + s for s in seeds])})",
            nxt=nxt,
        )
    )


S3 = lambda p: [p.replace("_s0", f"_s{s}") for s in range(3)]
add(
    "와우와우 학습셋 관절별 보정(어깨뼈 위끝·팔꿈치·뒷발끝·T13) 후 이어 학습",
    "c_offset_s0",
    TW + "offset/s0/pose.pth",
    "와우와우 학습 1,144장, 사람이 찍은 50장으로 구한 관절별 평균 차이를 4부위에 더함(S15P31A404-96)",
    BASE,
    "c_offset_s0.gt.json",
    "보정 전 학습(14.74~15.07°)보다 더 나쁨. 옮긴 부위가 기업 정답에서 멀어짐",
    "보정 라벨 안 씀",
    S3("c_offset_s0.gt.json"),
)
add(
    "팀 시험 라벨 76장(묶음 1~4)으로 이어 학습",
    "c_pilot_s0",
    TW + "pilot/s0/pose.pth",
    "시험 라벨 76장, 개 14마리(S15P31A404-100)",
    BASE,
    "c_pilot_s0.gt.json",
    "flip(7.89°) 못 이김, 판정 기준 불합격",
    "-",
    S3("c_pilot_s0.gt.json"),
)
for v, d, j in (
    ("base", "시험 라벨 96장(묶음 1~5) 그대로", "flip 못 이김"),
    (
        "scap_reset",
        "96장, 어깨뼈 위끝(3·8)만 오토라벨 자리로 되돌림",
        "어깨뼈 위끝 오차는 해결, 전체는 여전히 나쁨",
    ),
    ("scap_drop", "96장, 어깨뼈 위끝을 학습에서 뺌(가시성 0)", "되돌림과 비슷"),
):
    add(
        f"시험 라벨: {d}",
        f"c_p96_{v}_s0",
        TW + f"pilot96/{v}_s0/pose.pth",
        d,
        BASE,
        f"c_p96_{v}_s0.gt.json",
        j,
        "-",
        S3(f"c_p96_{v}_s0.gt.json"),
    )
add(
    "시험 라벨 96장, 어깨뼈 위끝 + 어깨(3·4·8·9) 되돌림",
    "c_r_p96_scapsh_s0",
    TW + "runs/p96_scapsh_s0/pose.pth",
    "96장, 4점 오토라벨 자리로",
    BASE,
    "c_r_p96_scapsh_s0.gt.json",
    "되돌림만과 비슷",
    "-",
    S3("c_r_p96_scapsh_s0.gt.json"),
)
for t in ("05", "10"):
    add(
        f"시험 라벨 최소 수정판(몸통 점 + 몸 길이 {int(t)}% 미만 이동은 오토라벨로)",
        f"c_pmin_min{t}_s0",
        TW + f"pilotmin/min{t}_s0/pose.pth",
        "96장, 기업처럼 크게 틀린 점만 고친 것으로 흉내",
        BASE,
        f"c_pmin_min{t}_s0.gt.json",
        "라벨이 오토라벨에 가까워도 각도는 10°대 → 학습 방식 의심",
        "-",
        S3(f"c_pmin_min{t}_s0.gt.json"),
    )
add(
    "[대조군] 오토라벨 점을 그대로 정답으로 96장 학습",
    "c_r_p96_auto_s0",
    TW + "runs/p96_auto_s0/pose.pth",
    "96장, 점 = fs-v4 오토라벨",
    BASE,
    "c_r_p96_auto_s0.gt.json",
    "★ 라벨이 모델 자기 출력인데도 나빠짐 → 학습 방식이 망가뜨림",
    "학습 설정 점검",
    S3("c_r_p96_auto_s0.gt.json"),
)
for v, r, j in (
    ("auto_lr0", BASE.replace("lr 5e-5", "lr 1e-12(점검)"), "7.89° 그대로 → 저장·불러오기 정상"),
    ("auto_ep10", BASE.replace("100에폭", "10에폭"), "덜 나빠짐"),
    ("auto_lr1e5", BASE.replace("lr 5e-5", "lr 1e-5"), "덜 나빠짐"),
    ("auto_headonly", HEAD, "★ 안 나빠짐(7.79°)"),
):
    add(
        f"[대조군] 오토라벨 96장, 설정: {v.split('_', 1)[1]}",
        f"c_r_{v}_s0",
        TW + f"runs/{v}_s0/pose.pth",
        "96장, 점 = fs-v4 오토라벨",
        r,
        f"c_r_{v}_s0.gt.json",
        j,
    )
for v, d, j in (
    ("h_auto", "[대조군] 오토라벨 96장", "flip 과 같거나 조금 좋음"),
    ("h_base", "시험 라벨 96장 그대로", "★ 대조군보다 약 1° 나쁨 → 라벨 기준 차이"),
    ("h_scap", "96장, 어깨뼈 위끝 되돌림", "그대로와 비슷"),
    ("h_min05", "96장, 최소 수정판 5%", "그대로와 비슷, 고친 점만 조금 나음"),
):
    add(
        f"머리만 학습: {d}",
        f"c_r_{v}_s0",
        TW + f"runs/{v}_s0/pose.pth",
        d,
        HEAD,
        f"c_r_{v}_s0.gt.json",
        j,
        "기업 정답 직접 비교로 라벨 기준 재정리(10-28)" if v == "h_base" else "-",
        S3(f"c_r_{v}_s0.gt.json"),
    )
for v, d in (
    ("ww50_base", "규원이 기업 기준으로 찍은 와우와우 50장(카메라 쪽만)"),
    ("ww50_scap", "50장, 어깨뼈 위끝 되돌림"),
    ("ww50_scapsh", "50장, 어깨뼈 위끝 + 어깨 되돌림"),
):
    add(
        f"와우와우 50장: {d.split(', ')[-1] if ',' in d else '그대로'}",
        f"c_r_{v}_s0",
        TW + f"runs/{v}_s0/pose.pth",
        d,
        BASE,
        f"c_r_{v}_s0.gt.json",
        "크게 나쁨. 와우와우 사진은 기업 정답과 너무 다름",
        "-",
        S3(f"c_r_{v}_s0.gt.json"),
    )
EXTRA = Path("sheet_1026_extra.json")  # 나중 실험(기업 정답 교차 학습 등)은 여기서 덧붙임
if EXTRA.exists():
    for e in json.load(open(EXTRA, encoding="utf-8")):
        e["f"] = C + e.pop("res")
        E.append(e)
for i, e in enumerate(E):
    e["id"] = f"E-{75 + i:03d}"
R = {e["id"]: json.load(open(e["f"], encoding="utf-8"))["kpi"] for e in E}
pct = lambda x: "-" if x is None else f"{100 * x:.1f}%"
f4 = lambda x: "-" if x is None else f"{x:.4f}"


def worst(d, touched=False):
    j = d["KPI-22"]
    if touched:
        c = [
            (v["touched_only"], n)
            for n, v in j.items()
            if v.get("touched_only") is not None and v.get("n_touched")
        ]
        return min(c) if c else (None, "-")
    return min((v["value"], n) for n, v in j.items())


sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()[:12] if Path(p).exists() else "-"
rows = [[e["id"] for e in E]]


def row(fn):
    rows.append([str(fn(e, R[e["id"]])) for e in E])


row(lambda e, d: DATE)
row(lambda e, d: "박규원")
row(lambda e, d: e["what"])
row(lambda e, d: e["name"])
row(lambda e, d: "models/curve_" + e["name"] + ".toml")
row(lambda e, d: sha(e["w"]))
row(lambda e, d: "이어 학습(fs-v4 에서 시작, 로컬)")
row(lambda e, d: e["recipe"])
row(lambda e, d: "-")
row(lambda e, d: "cuda:0")
row(lambda e, d: "2.1.2+cu121")
row(lambda e, d: "1.3.2")
row(lambda e, d: "0.1.0")
row(lambda e, d: "v1")
row(lambda e, d: "RTX 4070 Laptop (박규원)")
row(lambda e, d: e["data"])
row(lambda e, d: e.get("gt", GT1))
row(lambda e, d: FP1 if "gt" not in e else "-")
row(lambda e, d: d["KPI-04"]["mae"])
row(lambda e, d: "")
row(lambda e, d: f"{d['KPI-19']['value']:.4f}")
row(lambda e, d: pct(d["KPI-21"]["front"]["value"]))
row(lambda e, d: pct(d["KPI-21"]["hind"]["value"]))
row(lambda e, d: f"{worst(d)[0]:.4f}")
row(lambda e, d: worst(d)[1])
row(
    lambda e, d: d["KPI-04"]["touched_only"]["mae"]
    if d["KPI-04"]["touched_only"]["mae"] is not None
    else "-(채점 정답에 고친 점 표시 없음)"
)
row(lambda e, d: f4(d["KPI-19"]["touched_only"]))
row(lambda e, d: pct(d["KPI-21"]["front"]["touched_only"]))
row(lambda e, d: pct(d["KPI-21"]["hind"]["touched_only"]))
row(lambda e, d: f4(worst(d, True)[0]))
row(lambda e, d: f"{d['KPI-18']['value']:.4f}")
row(lambda e, d: f"{d['KPI-20']['value']:.4f}")
for _ in range(3):
    row(lambda e, d: "미측정(사진 정확도 실험)")
row(lambda e, d: e["judge"])
row(lambda e, d: e["nxt"])
row(lambda e, d: f"paw_eval/{e['f']}")
last = E[-1]["id"]
(OUT / f"13_실험기록_E075-E{last[2:]}.tsv").write_text(
    "\n".join("\t".join(r) for r in rows) + "\n", encoding="utf-8-sig"
)
names = list(R[E[0]["id"]]["KPI-22"].keys())
jr = [[f"{e['id']} {s}" for e in E for s in ("맞힌 비율", "고친 점만 맞힌 비율", "고친 점 개수")]]
for n in names:
    r = []
    for e in E:
        v = R[e["id"]]["KPI-22"][n]
        r += [
            f"{v['value']:.4f}",
            "" if v.get("touched_only") is None else f"{v['touched_only']:.4f}",
            str(v.get("n_touched", 0)),
        ]
    jr.append(r)
(OUT / f"14_관절별_E075-E{last[2:]}.tsv").write_text(
    "\n".join("\t".join(r) for r in jr) + "\n", encoding="utf-8-sig"
)
print(len(E), "실험", E[0]["id"], "~", last, "/", len(rows), "줄")
for e in E:
    print(e["id"], R[e["id"]]["KPI-04"]["mae"], e["what"][:45])
