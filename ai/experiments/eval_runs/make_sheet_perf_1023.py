"""처리 성능 탭: E-046~E-074 새 열(E-045 는 10-22 에 붙은 매 프레임 fp16 계산, E-046 은 그 와우와우 채점판) + E-034~E-045 보완(KPI-15·16 채움, E-035·E-039 '-' 대신 짝 실험 값). 항목 이름 열 없이 실험 번호 줄부터.
값은 run_perf_1023.sh 한 번의 측정(results/perf1023_*.json, 16:17~19:09). 영상 상자 실험은 det_stride.py(매 프레임 탐지 기준 v_base),
사진 채점 실험은 tta_speed.py(fs-v4 배율 1 기준 t_base)로 쟀고, 비율은 각자 같은 측정의 기준(처음·끝 두 번 평균) 대비.
와우와우 채점판은 바로 앞 실험과 설정이 같아 같은 측정값을 쓴다.
주의: 측정 내내 충전기가 연결돼 있었지만 출력이 모자라 배터리가 닳았다(17:03 절전). 전원 상태에 그대로 적는다.
json 은 recover_1023.py 로 로그 요약에서 복원해 탐지/관절점 나눔이 없다. KPI-15 는 5개 설정만 쟀다(충전 문제로 중단)."""

import json
import os
import sys
from pathlib import Path

_OUT = os.environ.get("CREAMOFF_OUT", "C:/Users/SSAFY/Downloads")


sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(f"{_OUT}/구글시트_붙여넣기_1023/")
DATE, PC = "2026-10-23", "RTX 4070 Laptop (박규원)"
POWER = "충전기 연결·배터리 소모 중"
NA = "미측정(충전기 출력 부족으로 중단, 다시 잴 것)"


def load(t):
    return json.loads(Path(f"results/perf1023_{t}.json").read_text(encoding="utf-8"))


M = {
    p.stem[len("perf1023_") :]: json.loads(p.read_text(encoding="utf-8"))
    for p in Path("results").glob("perf1023_*.json")
}
BASE = {
    k: {f: (M[k + "_base0"][f] + M[k + "_base1"][f]) / 2 for f in ("total_s", "kpi16_mib")}
    for k in ("v", "t")
}
TOOL = {"v": "det_stride.py 매 프레임 탐지", "t": "tta_speed.py 배율 1"}


def tput(tag):
    """KPI-15: 같은 실행부를 N=1,2,4,6 프로세스로 동시에 돌려 건당 시간이 N=1 의 2배 이하인 N 중 처리량 최대(speed.pick_kpi15)."""
    f = Path(f"results/kpi1023_{tag}.tput.json")
    if not f.exists():
        return [NA, NA]
    k = json.loads(f.read_text(encoding="utf-8"))["KPI-15"]
    return [f"{k['videos_per_hour']:.0f}", str(k["n"])]


def ref(tag):
    k = tag[0]
    b0, b1 = M[k + "_base0"], M[k + "_base1"]
    return (
        f"{TOOL[k]} fs-v4 기준 {b0['total_s']:.3f}·{b1['total_s']:.3f}초(처음·끝) 평균 {BASE[k]['total_s']:.3f}초, "
        f"메모리 {BASE[k]['kpi16_mib']:.0f}MiB 대비. 배터리 소모 중 측정이라 처음·끝 차이 {abs(b0['total_s'] - b1['total_s']) / BASE[k]['total_s']:.0%}"
    )


def col(i, tag, size, note):
    b = BASE[tag[0]]
    if tag.endswith("base"):
        m = b
        src = f"paw_eval/results/perf1023_{tag}0.json, perf1023_{tag}1.json"
    else:
        m = M[tag]
        src = f"paw_eval/results/perf1023_{tag}.json"
    src += f", kpi1023_{tag}.tput.json" if Path(f"results/kpi1023_{tag}.tput.json").exists() else ""
    t = m["total_s"]
    return [
        i,
        DATE,
        PC,
        POWER,
        "cuda:0",
        NA if t is None else f"{t:.3f}",
        NA if t is None else f"{t / b['total_s']:.3f}",
        *tput(tag),
        f"{m['kpi16_mib']:.0f}",
        f"{m['kpi16_mib'] / b['kpi16_mib']:.3f}",
        size,
        "유실(결과 파일 복원 때 빠짐)",
        src,
        f"{note}. {ref(tag)}" + (". 처리 시간은 측정 중 절전으로 끊겨 없음" if t is None else ""),
    ]


TWIN = "바로 앞 실험과 설정이 같아 같은 측정값(채점 정답만 와우와우)"
cols = []


def pair(i, tag, size, note):
    n = int(i[2:])
    cols.append(col(i, tag, size, note))
    cols.append(col(f"E-{n + 1:03d}", tag, size, TWIN))


pair("E-045", "v_h1", "150.8", "fp16 계산(torch.autocast), 매 프레임 탐지")
pair("E-047", "v_flip", "150.8", "flip, 매 프레임 탐지")
pair("E-049", "v_tiny25", "75.1", "가벼운 탐지기 2판 tiny(문턱 0.25), 매 프레임 탐지")
pair("E-051", "v_tiny08", "75.1", "가벼운 탐지기 2판 tiny(문턱 0.08), 매 프레임 탐지")
pair("E-053", "v_combo08", "75.1", "tiny(0.08) + flip, 매 프레임 탐지")
cols.append(
    col(
        "E-055",
        "t_base",
        "150.8",
        "사진 채점 실험이라 영상 처리는 현행 fs-v4 그대로(상자 여백은 채점 때만 바뀜)",
    )
)
cols.append(
    col(
        "E-056",
        "t_flip",
        "150.8",
        "flip. 상자 여백은 채점 때만 바뀌어 영상 처리는 fs-v4-flip 그대로",
    )
)
cols.append(col("E-057", "t_base", "150.8", "E-055 와 같은 모델(여백만 다름)"))
cols.append(col("E-058", "t_flip", "150.8", "E-056 과 같은 모델(여백만 다름)"))
n = 59
for fl in ("", "-flip"):
    for p in (115, 105, 95, 85):
        pair(
            f"E-{n:03d}",
            f"t_pad{fl}{p}",
            "150.8",
            f"입력 상자 확대 배율 1.25→{p / 100}" + (" + flip" if fl else ""),
        )
        n += 2
assert [c[0] for c in cols] == [f"E-{k:03d}" for k in range(45, 75)]

# E-034~E-045 보완: 시간은 이미 시트에 붙은 값 그대로, KPI-15·16 만 오늘 측정으로 채우고 E-035·E-039 는 짝 값으로
src = Path(f"{_OUT}/구글시트_붙여넣기_1022_오후/10_처리성능_E034-E045.tsv")
old = [l.split("\t") for l in src.read_text(encoding="utf-8-sig").splitlines()]
oc = {c[0]: list(c) for c in zip(*old)}
MEMTAG = {
    "E-034": "t_dark",
    "E-036": "t_hind",
    "E-037": "t_a",
    "E-038": "t_ts",
    "E-040": "v_base",
    "E-041": "v_s3",
    "E-042": "v_s4",
    "E-043": "v_s5",
    "E-044": "v_h3",
    "E-045": "v_h1",
}
for i, tag in MEMTAG.items():
    c, b = oc[i], BASE[tag[0]]
    mm = b["kpi16_mib"] if tag.endswith("base") else M[tag]["kpi16_mib"]
    c[9], c[10] = f"{mm:.0f}", f"{mm / b['kpi16_mib']:.3f}"
    c[7:9] = tput(tag)
    c[13] += " / 메모리: " + (
        f"perf1023_{tag}0.json, perf1023_{tag}1.json"
        if tag.endswith("base")
        else f"perf1023_{tag}.json"
    )
    c[14] += (
        f" / KPI-15·16 은 10-23 같은 설정 재측정({TOOL[tag[0]]} fs-v4 {b['kpi16_mib']:.0f}MiB 대비, "
        f"충전기 출력 부족으로 배터리 소모 중 측정)"
    )
for tw, src_i, j in (("E-035", "E-034", "와"), ("E-039", "E-038", "과")):
    oc[tw] = [tw] + oc[src_i][1:14] + [f"{src_i} {j} 설정이 같아 같은 측정값(채점 정답만 와우와우)"]
order = [f"E-{k:03d}" for k in range(34, 46)]
rows = [list(r) for r in zip(*[oc[i] for i in order])]
(OUT / "10_처리성능_E034-E045_보완.tsv").write_text(
    "\n".join("\t".join(r) for r in rows) + "\n", encoding="utf-8-sig"
)
# 새 열: E-045 는 시트에 이미 있어(위 보완에 포함) 빼고, E-046(와우와우 채점판)은 보완한 E-045 값을 그대로
cols[1] = ["E-046"] + oc["E-045"][1:14] + ["E-045 와 설정이 같아 같은 측정값(채점 정답만 와우와우)"]
cols = cols[1:]
rows = [list(r) for r in zip(*cols)]
(OUT / "13_처리성능_E046-E074.tsv").write_text(
    "\n".join("\t".join(r) for r in rows) + "\n", encoding="utf-8-sig"
)
old_copy = OUT / "10_처리성능_E034-E045.tsv"
if old_copy.exists():
    old_copy.unlink()
print("기준", BASE)
