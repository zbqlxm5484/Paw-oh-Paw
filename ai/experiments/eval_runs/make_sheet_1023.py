"""10-23 실험(영상 상자 채점·상자 여백)을 팀 시트 형식으로 내보낸다. 항목 이름 열 없이 실험 번호 줄부터.
번호는 E-045 부터다(E-045 는 10-22 에 처리 성능만 붙인 매 프레임 fp16 계산과 같은 설정이라 그 번호를 이어 씀). 그 사이 누가 실험을 붙였으면 밀어서 쓴다.
영상 상자 채점(VB)은 정답 상자+15% 채점과 절대값이 다르니 서로만 비교한다(10-22 E-040~E-044 와 같은 방식)."""

import hashlib
import json
import os
import sys
from pathlib import Path

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")
_OUT = os.environ.get("CREAMOFF_OUT", "C:/Users/SSAFY/Downloads")


sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(f"{_OUT}/구글시트_붙여넣기_1023/")
OUT.mkdir(exist_ok=True)
GT1, FP1 = "keypoints_260820 (205장, 221건)", "a08e9d47b680"
GT2 = "keypoints_wowwow 검증 288장 (사람 확인분, 5분 간격 묶음 분할)"
FP2 = hashlib.sha256(open(f"{_PJT}/splits/wowwow/wowwow_val.json", "rb").read()).hexdigest()[:12]
VB = " [영상 상자로 채점]"
DATE = "2026-10-23"


def mae(f):
    return json.load(open(f, encoding="utf-8"))["kpi"]["KPI-04"]["mae"]


E = []


def vk(tag):
    """영상 KPI-01·02·24: run_kpi_1023.sh 가 같은 실행부로 video_kpi_videos.txt 27건을 추적해 잰 값(채점 정답과 무관)."""
    f = Path(f"results/kpi1023_{tag}.vkpi.json")
    if not f.exists():
        return ["미측정(충전기 출력 부족으로 중단, 다시 잴 것)"] * 3
    k = json.load(open(f, encoding="utf-8"))["results"][0]["kpi"]
    return [
        f"{k['KPI-01']['median_cv']:.4f}",
        f"{k['KPI-02']['median_deg']:.2f}",
        str(k["KPI-24"]["swaps"]),
    ]


def pair(what, name, model, diff, fg, fw, judge_g, judge_w, nxt="-", vb=True, vt=None):
    """같은 설정을 기업 정답·와우와우 정답으로 한 열씩(E-034/E-035 관례)."""
    tag = VB if vb else ""
    E.append(
        dict(
            what=what + tag, name=name, model=model, diff=diff, f=fg, judge=judge_g, nxt=nxt, vt=vt
        )
    )
    E.append(
        dict(
            what="[와우와우 정답] " + what + tag,
            name=name,
            model=model,
            diff="바로 앞 실험과 같은 방법, 채점 정답만 와우와우",
            f=fw,
            gt=GT2,
            gfp=FP2,
            judge=judge_w,
            nxt="-",
            vt=vt,
        )
    )


b, bw = mae("results/vgt_s1.json"), mae("results/vww_s1.json")
pair(
    "fp16 계산(torch.autocast), 매 프레임 탐지",
    "fs-v4 (det_stride 1, fp16 autocast)",
    "models/fs-v4.toml",
    "E-040 + 탐지·관절점 계산을 16비트로. 처리 성능은 같은 번호 E-045(10-22 측정 2.013초, 0.654)",
    "results/vgt_s1h.json",
    "results/vww_s1h.json",
    f"정확도 손해 없음 (E-040 {b}→{mae('results/vgt_s1h.json')}°). 같은 구조로 속도 35% 줄임",
    f"손해 없음 ({bw}→{mae('results/vww_s1h.json')}°)",
    "fp16 계산 채택 검토(팀 논의)",
    vt="v_h1",
)
pair(
    "flip, 매 프레임 탐지",
    "fs-v4-flip (det_stride 1)",
    "models/fs-v4-flip.toml",
    "E-040 + flip test. 탐지 상자는 E-040 과 같음(5,297 프레임 중 13개만 다름)",
    "results/vgt_flip.json",
    "results/vww_flip.json",
    f"★ 영상 상자에선 flip 이 오히려 나쁨 ({b}→{mae('results/vgt_flip.json')}°). 정답 상자 채점(E-011 7.89 < 8.02)과 반대",
    f"나쁨 ({bw}→{mae('results/vww_flip.json')}°)",
    "인수 시험이 어느 상자로 채점하는지 확인",
    vt="v_flip",
)
pair(
    "가벼운 탐지기 2판 tiny (문턱 0.25) = E-029 탐지기",
    "fs-v4-dettiny-ft2 (det_stride 1)",
    "models/fs-v4-dettiny-ft2.toml",
    "E-040 에서 탐지기만 E-029 것으로",
    "results/vgt_tiny25.json",
    "results/vww_tiny25.json",
    f"관절점 정확도 손해 ({b}→{mae('results/vgt_tiny25.json')}°). ※ 구조 유지 원칙으로 채택 안 함",
    f"손해 ({bw}→{mae('results/vww_tiny25.json')}°)",
    vt="v_tiny25",
)
pair(
    "가벼운 탐지기 2판 tiny (문턱 0.08) = E-030 탐지기",
    "fs-v4-dettiny-ft2-t08 (det_stride 1)",
    "models/fs-v4-dettiny-ft2-t08.toml",
    "E-040 에서 탐지기만 E-030 것으로",
    "results/vgt_tiny08.json",
    "results/vww_tiny08.json",
    f"손해 ({b}→{mae('results/vgt_tiny08.json')}°). ※ 채택 안 함",
    f"손해 ({bw}→{mae('results/vww_tiny08.json')}°)",
    vt="v_tiny08",
)
pair(
    "E-032 조합에서 뒷다리 보정 뺀 것: tiny(0.08) + flip",
    "combo-dettiny-ft2-t08-flip (det_stride 1)",
    "models/combo-t08-flip.toml",
    "E-030 탐지기 + flip. 영상 추적에 뒷다리 보정이 아직 없어 뺌",
    "results/vgt_combo08.json",
    "results/vww_combo08.json",
    f"손해 (flip 만 {mae('results/vgt_flip.json')}→{mae('results/vgt_combo08.json')}°). ※ 채택 안 함",
    f"({mae('results/vww_flip.json')}→{mae('results/vww_combo08.json')}°)",
    vt="v_combo08",
)

P = "results/vbox_photo/"
E.append(
    dict(
        what="사진 채점, 상자만 영상 탐지 상자(여백 0)",
        name="fs-v4",
        model="models/fs-v4.toml",
        diff="E-000 의 정답 상자+15% 대신 같은 사진 프레임의 영상 탐지 상자를 그대로(predict.py BOX_MARGIN 0, 기업 파일은 안 고치고 실행 때만 바꿈)",
        f=P + "fs-v4_m0.json",
        judge=f"★ 8.02→{mae(P + 'fs-v4_m0.json')}°. 정답 상자보다 탐지 상자가 이 모델에 맞음",
        nxt="flip 과 비교(다음 열)",
        vt="t_base",
    )
)
E.append(
    dict(
        what="사진 채점, 영상 탐지 상자(여백 0) + flip",
        name="fs-v4-flip",
        model="models/fs-v4-flip.toml",
        diff="바로 앞 + flip test",
        f=P + "fs-v4-flip_m0.json",
        judge=f"flip 이 나빠짐 ({mae(P + 'fs-v4_m0.json')}→{mae(P + 'fs-v4-flip_m0.json')}°). 영상 경로 문제가 아님을 확인",
        nxt="-",
        vt="t_flip",
    )
)
E.append(
    dict(
        what="사진 채점, 영상 탐지 상자 + 15% 여백",
        name="fs-v4",
        model="models/fs-v4.toml",
        diff="탐지 상자에 기업 채점과 같은 15% 여백",
        f=P + "fs-v4_m0.15.json",
        judge=f"크게 나빠짐 ({mae(P + 'fs-v4_m0.15.json')}°)",
        nxt="-",
        vt="t_base",
    )
)
E.append(
    dict(
        what="사진 채점, 영상 탐지 상자 + 15% 여백 + flip",
        name="fs-v4-flip",
        model="models/fs-v4-flip.toml",
        diff="바로 앞 + flip test",
        f=P + "fs-v4-flip_m0.15.json",
        judge=f"{mae(P + 'fs-v4-flip_m0.15.json')}°",
        nxt="-",
        vt="t_flip",
    )
)

for fl in ("", "-flip"):
    for p in (115, 105, 95, 85):
        m = f"fs-v4{fl}-pad{p}"
        base_g = 7.89 if fl else 8.02
        pair(
            f"입력 상자 확대 배율 1.25→{p / 100}" + (" + flip" if fl else ""),
            m,
            f"models/{m}.toml",
            f"{'E-011' if fl else 'E-000'} 에서 관절점 설정의 GetBBoxCenterScale padding 만 바꿈(상자를 덜 키워 꽉 자름). 기업 채점 그대로",
            f"results/pad/gt_{m}.json",
            f"results/pad/ww_{m}.json",
            f"나빠짐 ({base_g}→{mae(f'results/pad/gt_{m}.json')}°). 꽉 자르는 건 답이 아님",
            f"{mae(f'results/pad/ww_{m}.json')}°",
            vb=False,
            vt=f"t_pad{fl}{p}",
        )

for i, e in enumerate(E):
    e["id"] = f"E-{45 + i:03d}"
R = {e["id"]: json.load(open(e["f"], encoding="utf-8"))["kpi"] for e in E}
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


rows = [[e["id"] for e in E]]


def add(fn):
    rows.append([str(fn(e, R[e["id"]])) for e in E])


add(lambda e, d: DATE)
add(lambda e, d: "박규원")
add(lambda e, d: e["what"])
add(lambda e, d: e["name"])
add(lambda e, d: e["model"])
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
add(lambda e, d: vk(e["vt"])[0])
add(lambda e, d: vk(e["vt"])[1])
add(lambda e, d: vk(e["vt"])[2])
add(lambda e, d: e["judge"])
add(lambda e, d: e["nxt"])
add(
    lambda e, d: f"paw_eval/{e['f']}"
    + (
        f", paw_eval/results/kpi1023_{e['vt']}.vkpi.json(영상 KPI)"
        if Path(f"results/kpi1023_{e['vt']}.vkpi.json").exists()
        else ""
    )
)
last = E[-1]["id"]
(OUT / f"11_실험기록_E045-E{last[2:]}.tsv").write_text(
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
(OUT / f"12_관절별_E045-E{last[2:]}.tsv").write_text(
    "\n".join("\t".join(r) for r in jr) + "\n", encoding="utf-8-sig"
)
print(len(E), "실험", E[0]["id"], "~", last, "/", len(rows), "줄 /", len(names), "관절")
for e in E:
    print(e["id"], R[e["id"]]["KPI-04"]["mae"], e["what"][:50])

TAB, NL = chr(9), chr(10)
# 이미 시트에 붙은 E-034~E-044 실험 기록 보완: 영상 KPI-01·02·24 를 같은 방식으로 채우고, E-038·E-039 모델 이름이
# '+' 로 시작해 시트에서 수식(#ERROR!)으로 읽힌 것을 고친다. 나머지 칸은 붙여 둔 값 그대로.
old = [
    l.split(TAB)
    for l in Path(f"{_OUT}/구글시트_붙여넣기_1022_오후/8_실험기록_E029-E044.tsv")
    .read_text(encoding="utf-8-sig")
    .splitlines()
]
oc = {c[0]: list(c) for c in zip(*old)}
VT = {
    "E-034": "t_dark",
    "E-035": "t_dark",
    "E-036": "t_hind",
    "E-037": "t_a",
    "E-038": "t_ts",
    "E-039": "t_ts",
    "E-040": "v_base",
    "E-041": "v_s3",
    "E-042": "v_s4",
    "E-043": "v_s5",
    "E-044": "v_h3",
}
for i, t in VT.items():
    c = oc[i]
    c[33:36] = vk(t)
    if Path(f"results/kpi1023_{t}.vkpi.json").exists():
        c[-1] += f", paw_eval/results/kpi1023_{t}.vkpi.json(영상 KPI)"
    if c[4].startswith("+"):
        c[4] = "fs-v4-flip + 배율 5 + 회전 ±8 " + c[4]
fix = [list(r) for r in zip(*[oc[i] for i in VT])]
(OUT / "11_실험기록_E034-E044_보완.tsv").write_text(
    NL.join(TAB.join(r) for r in fix) + NL, encoding="utf-8-sig"
)
print("보완", list(VT), "모델 이름", oc["E-038"][4])
