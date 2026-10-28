"""처리 성능 탭: 10-26 E-075~E-103. 실험들은 모델 구조·추론 설정(flip)이 같고 가중치 숫자만 다르다.
run_perf_1026.sh 한 번의 측정(16:09~16:45 KST, 충전 중)에서 대표 모델 4개를 fs-v4·fs-v4-flip 과 같이 쟀고, 각 열에는 가장 가까운 대표 측정값을 넣는다.
비율 기준: fs-v4 처음·끝 두 번 평균(시간). 메모리는 처음 값(끝 측정은 시작 전 GPU 에 2,617MiB 가 남아 있어 제외)."""

import json
import os
import sys
from pathlib import Path

_OUT = os.environ.get("CREAMOFF_OUT", "C:/Users/SSAFY/Downloads")

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(f"{_OUT}/구글시트_붙여넣기_1026/")
DATE, PC, POWER = "2026-10-26", "RTX 4070 Laptop (박규원)", "충전 중(배터리 100%, 충전기 연결)"
M = {
    p.stem[len("perf1026_") :]: json.loads(p.read_text(encoding="utf-8"))
    for p in Path("results").glob("perf1026_*.json")
}
BT = (M["t_base0"]["total_s"] + M["t_base1"]["total_s"]) / 2
BM = M["t_base0"]["kpi16_mib"]
SIZE = f"{(99216095 + 58927579) / 2**20:.1f}"
REP = {"c_offset": "r_offset", "ww50": "r_ww50", "auto": "r_p96_auto"}


def rep(name):
    for k, v in REP.items():
        if k in name:
            return v
    return "r_h_base"


acc = [
    l.split("\t")
    for l in sorted(OUT.glob("13_실험기록_*.tsv"))[0].read_text(encoding="utf-8-sig").splitlines()
]
cols = list(zip(*acc))
tp = {
    k: json.loads(Path(f"results/perf1026_{k}.tput.json").read_text(encoding="utf-8"))["KPI-15"]
    for k in ("t_flip", "r_h_base")
}
out = []
for c in cols:
    i, name = c[0], c[4]
    if name == "fs-v4-flip":
        m, src, note = M["t_flip"], "t_flip", "fs-v4 + flip 직접 측정"
        k15 = tp["t_flip"]
    else:
        r = rep(name)
        m, src = M[r], r
        direct = {
            "r_offset": "c_offset_s0",
            "r_ww50": "c_r_ww50_base_s0",
            "r_p96_auto": "c_r_p96_auto_s0",
            "r_h_base": "c_r_h_base_s0",
        }[r]
        note = (
            (
                "직접 측정"
                if name == direct
                else f"같은 구조·같은 추론 설정(flip)이라 대표 모델 {direct} 측정값"
            )
            + ". 측정한 학습 모델 4개 3.970~4.116초로 fs-v4-flip 4.027초와 ±3% 안 = 가중치만 바뀌어 속도 차이 없음"
        )
        k15 = tp["r_h_base"]
    t = m["total_s"]
    out.append(
        [
            i,
            DATE,
            PC,
            POWER,
            "cuda:0",
            f"{t:.3f}",
            f"{t / BT:.3f}",
            f"{k15['videos_per_hour']:.0f}",
            str(k15["n"]),
            f"{m['kpi16_mib']:.0f}",
            f"{m['kpi16_mib'] / BM:.3f}",
            SIZE,
            f"탐지 {m['det_s']:.2f}초 · 관절점 {m['pose_s']:.2f}초",
            f"paw_eval/results/perf1026_{src}.json"
            + (f", perf1026_{'t_flip' if name == 'fs-v4-flip' else 'r_h_base'}.tput.json"),
            f"{note}. 기준 fs-v4 {M['t_base0']['total_s']:.3f}·{M['t_base1']['total_s']:.3f}초(처음·끝) 평균 {BT:.3f}초, 메모리 {BM:.0f}MiB(처음 값). KPI-15 는 동시 1·2·4·6 중 건당 시간 2배 이하 최대(1개)",
        ]
    )
rows = [list(r) for r in zip(*out)]
(OUT / f"15_처리성능_{out[0][0].replace('-', '')}-{out[-1][0].replace('-', '')}.tsv").write_text(
    "\n".join("\t".join(r) for r in rows) + "\n", encoding="utf-8-sig"
)
print(len(out), "열", out[0][0], "~", out[-1][0], "/ 줄", len(rows), "/ 기준", round(BT, 3), BM)
