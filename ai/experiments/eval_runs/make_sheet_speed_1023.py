"""처리 성능 탭 E-034~E-045 를 팀 시트 형식으로 내보낸다(10-23). 항목 이름 열 없이 실험 번호 줄부터, 시트 AL열에 붙인다.
E-034~E-039 는 10-23 tta_speed.py 한 번의 측정(results/speed1023b_*.json, fs-v4 기준을 처음·끝 두 번)에서 온 값이고,
E-040~E-045 는 10-22 det_stride.py 측정값(10_처리성능_E029-E045.tsv)을 그대로 옮긴다. 비율은 각자 같은 측정 안의 fs-v4 기준."""

import json
from pathlib import Path

OUT = Path.home() / "Downloads" / "구글시트_붙여넣기_1022_오후"
R = Path("results")
S = "0.85,0.9,1,1.1,1.15"


def load(n):
    return json.loads((R / f"speed1023b_{n}.json").read_text(encoding="utf-8"))


b0, b1 = load("base0")["1"], load("base1")["1"]
base = (b0["total_s"] + b1["total_s"]) / 2
a = load("a")
drift = f"같은 측정의 fs-v4 기준 {b0['total_s']:.3f}·{b1['total_s']:.3f}초(처음·끝) 평균 {base:.3f}초 대비"
PC, DATE, SRC = "RTX 4070 Laptop (박규원)", "2026-10-23", "paw_eval/results/speed1023b_{}.json"


def col(i, m, src, note):
    return [
        i,
        DATE,
        PC,
        "충전 중",
        "cuda:0",
        f"{m['total_s']:.3f}",
        f"{m['total_s'] / base:.3f}",
        "",
        "",
        "미측정",
        "미측정",
        "150.8",
        f"{m['det_s']:.2f}/{m['pose_s']:.2f}",
        SRC.format(src),
        note,
    ]


def same(i, ref, j="와"):
    return [
        i,
        DATE,
        PC,
        "-",
        "-",
        "-",
        "-",
        "",
        "",
        "-",
        "-",
        "150.8",
        "-",
        "-",
        f"{ref} {j} 같은 방법(채점 정답만 다름)",
    ]


cols = [
    col(
        "E-034",
        load("dark")["1"],
        "dark",
        f"flip + DARK, 배율 1. {drift}. 참고: 같은 측정의 flip 만 {a['1']['total_s']:.3f}초",
    ),
    same("E-035", "E-034"),
    col(
        "E-036",
        load("hind")[S + ",r8+hind"],
        "hind",
        f"flip + 배율 5 + 회전 ±8° + 뒷다리 보정(묶음 추론, tta_speed.py). {drift}",
    ),
    col(
        "E-037",
        a[S + ",r8"],
        "a",
        f"E-036 에서 뒷다리 보정 뺌. {drift}. 참고: 회전 빼고 배율 5까지 {a[S]['total_s']:.3f}초",
    ),
    col("E-038", load("ts")[S + ",r8+ts"], "ts", f"배율 5 + 회전 + 앞뒤 1프레임 평균. {drift}"),
    same("E-039", "E-038", "과"),
]
old = [
    l.split("\t")
    for l in (OUT / "10_처리성능_E029-E045.tsv").read_text(encoding="utf-8-sig").splitlines()
]
cols += [
    [r[i] for r in old] for i, h in enumerate(old[0]) if h in [f"E-0{n}" for n in range(40, 46)]
]
rows = [list(r) for r in zip(*cols)]
(OUT / "10_처리성능_E034-E045.tsv").write_text(
    "\n".join("\t".join(r) for r in rows) + "\n", encoding="utf-8-sig"
)
print(len(cols), "열", [c[0] for c in cols], f"기준 {base:.3f}")
