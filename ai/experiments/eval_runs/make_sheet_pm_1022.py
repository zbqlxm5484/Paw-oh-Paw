"""10-22 오후 실험(E-024~E-032, 팀 시트 E-018~E-023 은 김지윤 실험이라 그 뒤 번호)을 팀 시트 형식으로 내보낸다. 항목 이름 열 없이 실험 번호 줄부터."""

import json
import os
import sys
from pathlib import Path

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")
_OUT = os.environ.get("CREAMOFF_OUT", "C:/Users/SSAFY/Downloads")


sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(f"{_OUT}/구글시트_붙여넣기_1022_오후/")
GT1, FP1 = "keypoints_260820 (205장, 221건)", "a08e9d47b680"
GT2 = "keypoints_wowwow 검증 288장 (사람 확인분, 5분 간격 묶음 분할)"
FP2 = (
    __import__("hashlib")
    .sha256(open(f"{_PJT}/splits/wowwow/wowwow_val.json", "rb").read())
    .hexdigest()[:12]
)
POSE = [
    dict(
        id="E-024",
        f="results/mstta/gt/m_0.9_1.1.json",
        what="flip + 상자 3가지 배율(0.9·1.0·1.1) 평균 (추론할 때 증강)",
        name="fs-v4-flip + 배율 3",
        diff="E-002 + 상자 크기를 바꿔 3번 추론한 좌표 평균 (multiscale_tta.py)",
        judge="개선 (각도 7.89→7.62°, 엄격 PCK 0.719→0.755). 뒷발끝은 조금 늘어남",
        nxt="뒷다리 보정과 합침(E-026)",
    ),
    dict(
        id="E-025",
        f="results/mstta/gt/m_0.85_0.9_1.1_1.15.json",
        what="flip + 상자 5가지 배율(0.85~1.15) 평균",
        name="fs-v4-flip + 배율 5",
        diff="E-024 에서 배율 0.85·1.15 추가",
        judge="개선 (각도 7.62°, 고친 점 12.91°)",
        nxt="뒷다리 보정과 합침(E-027)",
    ),
    dict(
        id="E-026",
        f="results/mstta/gt/m_0.9_1.1_hind.json",
        what="flip + 배율 3 + 뒷다리만 좌우 바로잡기",
        name="fs-v4-flip + 배율 3 + lr_fix(hind)",
        diff="E-024 + E-017 의 후처리",
        judge="개선 (각도 7.41°, 엄격 PCK 0.761 최고)",
        nxt="-",
    ),
    dict(
        id="E-027",
        f="results/mstta/gt/m_0.85_0.9_1.1_1.15_hind.json",
        what="★ flip + 배율 5 + 뒷다리만 좌우 바로잡기",
        name="fs-v4-flip + 배율 5 + lr_fix(hind)",
        diff="E-025 + E-017 의 후처리",
        judge="현재 최선 (각도 7.36°, 현행 대비 −8.3%, 고친 점 12.16°)",
        nxt="가벼운 탐지기(E-030)와 합친 전체 속도 확인",
    ),
    dict(
        id="E-028",
        f="results/mstta/ww/m_0.85_0.9_1.1_1.15.json",
        what="[와우와우 정답] flip + 배율 5 — 다른 촬영에서도 좋아지는지",
        name="fs-v4-flip + 배율 5",
        diff="E-025 와 같은 방법, 채점 정답만 와우와우",
        gt=GT2,
        gfp=FP2,
        judge="개선 (flip 17.68→17.29°, 고친 점 22.34→22.04°). 다른 촬영에서도 같은 방향",
        nxt="-",
    ),
]
pct = lambda x: f"{100 * x:.1f}%"


def worst(d, touched=False):
    j = d["KPI-22"]
    if touched:
        return min(
            (v["touched_only"], n)
            for n, v in j.items()
            if v.get("touched_only") is not None and v.get("n_touched")
        )
    return min((v["value"], n) for n, v in j.items())


R = {e["id"]: json.load(open(e["f"], encoding="utf-8"))["kpi"] for e in POSE}
rows = [[e["id"] for e in POSE]]


def add(fn):
    rows.append([str(fn(e, R[e["id"]])) for e in POSE])


add(lambda e, d: "2026-10-22")
add(lambda e, d: "박규원")
add(lambda e, d: e["what"])
add(lambda e, d: e["name"])
add(lambda e, d: "models/fs-v4-flip.toml")
add(lambda e, d: "a4261a107bc8")
add(lambda e, d: "-(기업 전달본)")
add(lambda e, d: e["diff"])
add(lambda e, d: "-")
add(lambda e, d: "cuda:0")
add(lambda e, d: "2.1.2+cu121")
add(lambda e, d: "1.3.2")
add(lambda e, d: "0.1.0")
add(lambda e, d: "v1")
add(lambda e, d: "RTX 4070 Laptop (박규원)")
add(lambda e, d: "-(학습 안 함)")
add(lambda e, d: e.get("gt", GT1))
add(lambda e, d: e.get("gfp", FP1))
add(lambda e, d: d["KPI-04"]["mae"])
add(lambda e, d: "")
add(lambda e, d: f"{d['KPI-19']['value']:.4f}")
add(lambda e, d: pct(d["KPI-21"]["front"]["value"]))
add(lambda e, d: pct(d["KPI-21"]["hind"]["value"]))
add(lambda e, d: f"{worst(d)[0]:.4f}")
add(lambda e, d: worst(d)[1])
add(lambda e, d: d["KPI-04"]["touched_only"]["mae"])
add(lambda e, d: f"{d['KPI-19']['touched_only']:.4f}")
add(lambda e, d: pct(d["KPI-21"]["front"]["touched_only"]))
add(lambda e, d: pct(d["KPI-21"]["hind"]["touched_only"]))
add(lambda e, d: f"{worst(d, True)[0]:.4f}")
add(lambda e, d: f"{d['KPI-18']['value']:.4f}")
add(lambda e, d: f"{d['KPI-20']['value']:.4f}")
add(lambda e, d: "미측정")
add(lambda e, d: "미측정")
add(lambda e, d: "미측정")
add(lambda e, d: e["judge"])
add(lambda e, d: e["nxt"])
add(lambda e, d: "paw_eval/" + e["f"])
(OUT / "5_실험기록_E024-E028.tsv").write_text(
    "\n".join("\t".join(r) for r in rows) + "\n", encoding="utf-8-sig"
)

names = list(R["E-024"]["KPI-22"].keys())
jr = [
    [f"{e['id']} {s}" for e in POSE for s in ("맞힌 비율", "고친 점만 맞힌 비율", "고친 점 개수")]
]
for n in names:
    r = []
    for e in POSE:
        v = R[e["id"]]["KPI-22"][n]
        r += [
            f"{v['value']:.4f}",
            "" if v.get("touched_only") is None else f"{v['touched_only']:.4f}",
            str(v.get("n_touched", 0)),
        ]
    jr.append(r)
(OUT / "6_관절별_E024-E028.tsv").write_text(
    "\n".join("\t".join(r) for r in jr) + "\n", encoding="utf-8-sig"
)

# 처리 성능: 관절점 E-024~E-028 + 탐지기 E-029~E-032
tta = json.load(open("results/tta_speed_1022.json", encoding="utf-8"))
base = json.load(open("results/combo_speed_base.json", encoding="utf-8"))["1"]["total_s"]
_b2 = Path("results/combo2_fs-v4.json")
base2 = (
    json.load(open(_b2, encoding="utf-8"))["1"]["total_s"] if _b2.exists() else base
)  # 조합(E-032) 비율용, 같은 작업에서 잰 현행
det = {
    r["name"]: r["kpi"]
    for r in json.load(open("results/speed_dettiny_ft2.json", encoding="utf-8"))["results"]
}
det_base = det["fs-v4"]["KPI-14"]["median_s"]
combo_p = Path("results/combo_speed.json")
combo = json.load(open(combo_p, encoding="utf-8")) if combo_p.exists() else {}
S3, S5 = "0.9,1,1.1", "0.85,0.9,1,1.1,1.15"
cols = []


def sp(i, t, r, mem, size, split, loc, note):
    cols.append(
        [
            i,
            "2026-10-22",
            "RTX 4070 Laptop (박규원)",
            "충전 중",
            "cuda:0",
            t,
            r,
            "",
            "",
            mem,
            f"{float(mem) / 1131:.3f}" if mem.replace(".", "").isdigit() else mem,
            size,
            split,
            loc,
            note,
        ]
    )


def tt(key):
    return tta[key]["total_s"]


sp(
    "E-024",
    f"{tt(S3):.3f}",
    f"{tt(S3) / base:.3f}",
    "미측정",
    "150.8",
    f"{tta[S3]['det_s']:.2f}/{tta[S3]['pose_s']:.2f}",
    "paw_eval/results/tta_speed_1022.json",
    "배율 3가지를 한 묶음으로 관절점 모델에 넣음. flip(같은 측정 3.334초) 대비 +6%. 비율은 같은 날 같은 도구로 잰 fs-v4 3.224초 기준",
)
sp(
    "E-025",
    f"{tt(S5):.3f}",
    f"{tt(S5) / base:.3f}",
    "미측정",
    "150.8",
    f"{tta[S5]['det_s']:.2f}/{tta[S5]['pose_s']:.2f}",
    "paw_eval/results/tta_speed_1022.json",
    "flip 대비 +16%",
)
sp(
    "E-026",
    f"{tt(S3):.3f}",
    f"{tt(S3) / base:.3f}",
    "미측정",
    "150.8",
    f"{tta[S3]['det_s']:.2f}/{tta[S3]['pose_s']:.2f} + 후처리 0.001",
    "paw_eval/results/tta_speed_1022.json",
    "E-024 + 뒷다리 후처리(영상당 0.8ms)",
)
sp(
    "E-027",
    f"{tt(S5):.3f}",
    f"{tt(S5) / base:.3f}",
    "미측정",
    "150.8",
    f"{tta[S5]['det_s']:.2f}/{tta[S5]['pose_s']:.2f} + 후처리 0.001",
    "paw_eval/results/tta_speed_1022.json",
    "E-025 + 뒷다리 후처리(영상당 0.8ms)",
)
sp("E-028", "-", "-", "-", "150.8", "-", "-", "E-025 와 같은 방법(채점 정답만 다름)")
for i, nm, note in (
    (
        "E-029",
        "fs-v4-dettiny-ft2",
        "탐지기만 2판 tiny(카메라 4대·와우와우 30fps 포함 7,434장, 12에폭, lr 5e-4, 문턱 0.25). KPI-23 최악 −11.8%p 불합격(14개 영상 하락). 놓친 104장 중 101장이 화면 끝에 걸린 개 ※ 기존 모델 구조 유지 원칙(10-22 확정)에 따라 채택 안 함(탐지기 구조가 다름)",
    ),
    (
        "E-030",
        "fs-v4-dettiny-ft2-t08",
        "E-029 의 점수 문턱 0.25→0.08. KPI-23 통과(최악 0.0%p, 놓친 장 5). 대신 현행이 못 찾던 476장에 새 상자(450장이 화면 끝, 사람 다리를 잡은 것도 섞임) ※ 기존 모델 구조 유지 원칙(10-22 확정)에 따라 채택 안 함(탐지기 구조가 다름)",
    ),
):
    k = det[nm]["KPI-14"]
    sp(
        i,
        f"{k['median_s']:.3f}",
        f"{k['median_s'] / det_base:.3f}",
        str(int(det[nm]["KPI-16"]["max_mib"])),
        "75.1",
        f"{k['det_s']:.2f}/{k['pose_s']:.2f}",
        "paw_eval/results/speed_dettiny_ft2.json, kpi_dettiny_ft2*.json",
        note,
    )
sp(
    "E-031",
    "E-030 와 같음",
    "E-030 와 같음",
    "E-030 와 같음",
    "75.1",
    "-",
    "paw_eval/edge_filter.py, results/kpi_dettiny_ft2_t08_ef.json",
    "E-030 + 화면 끝 가는 헛상자 거르기(끝에 닿고 폭/높이<0.25, 관절점 확신도<0.30). 헛것 232/476 제거, KPI-23 최악 −0.50%p(200프레임 영상 1장, 경계) ※ 기존 모델 구조 유지 원칙(10-22 확정)에 따라 채택 안 함(탐지기 구조가 다름)",
)
if combo:
    for key, lab in (("1", "flip"), (S3, "flip + 배율 3"), (S5, "flip + 배율 5")):
        pass
    c1 = combo["1"]
    sp(
        "E-032",
        f"{c1['total_s']:.3f}",
        f"{c1['total_s'] / base2:.3f}",
        "미측정",
        "75.1",
        f"{c1['det_s']:.2f}/{c1['pose_s']:.2f} + 후처리 0.001",
        "paw_eval/results/combo_speed.json, combo2_*.json",
        "※ 기존 모델 구조 유지 원칙(10-22 확정)에 따라 채택 안 함(탐지기 구조가 다름). 전체 조합: 2판 tiny(문턱 0.08) + flip + 뒷다리 보정 → KPI-14 통과(관절점 정확도는 E-017 과 같음, KPI-04 7.87°). 같은 작업에서 잰 현행 3.077초 기준. 배율을 더하면: "
        + " / ".join(
            f"{lab} {combo[k]['total_s']:.3f}초({combo[k]['total_s'] / base2:.1%})"
            for k, lab in (("1", "flip만"), (S3, "배율 3"), (S5, "배율 5"))
            if k in combo
        ),
    )
else:
    sp("E-032", "측정 중", "", "", "75.1", "", "", "전체 조합 속도 측정 중")
rows3 = [list(r) for r in zip(*cols)]
(OUT / "7_처리성능_E024-E032.tsv").write_text(
    "\n".join("\t".join(r) for r in rows3) + "\n", encoding="utf-8-sig"
)
print(len(rows) - 1, "항목 /", len(jr) - 1, "관절 /", len(rows3), "행(처리 성능)")
