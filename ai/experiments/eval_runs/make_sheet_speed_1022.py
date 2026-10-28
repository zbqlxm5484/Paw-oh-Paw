import os
import sys

_OUT = os.environ.get("CREAMOFF_OUT", "C:/Users/SSAFY/Downloads")

sys.stdout.reconfigure(encoding="utf-8")
OUT = f"{_OUT}/구글시트_붙여넣기_1022/3_처리성능_E011-E017.tsv"
base = 3.155
t = {
    "E-011": 3.155,
    "E-012": 3.242,
    "E-013": 3.273,
    "E-014": 3.273,
    "E-015": 3.281,
    "E-016": 3.281,
    "E-017": 3.243,
}
mem = {
    "E-011": 1131,
    "E-012": 1133,
    "E-013": 1133,
    "E-014": 1133,
    "E-015": 1133,
    "E-016": 1133,
    "E-017": 1133,
}
split = {
    "E-011": "2.97/0.17",
    "E-012": "3.00/0.28",
    "E-013": "3.00/0.26",
    "E-014": "3.00/0.26",
    "E-015": "3.02/0.26",
    "E-016": "3.02/0.26",
    "E-017": "3.00/0.28 + 후처리 0.001",
}
size = {
    "E-011": "150.8",
    "E-012": "150.8",
    "E-013": "150.8",
    "E-014": "150.8",
    "E-015": "150.8",
    "E-016": "150.8",
    "E-017": "150.8",
}
note = {
    "E-011": "10-22 같은 측정 안의 현행 기준(3.155초). 10-20 3.136초와 맞음",
    "E-012": "flip test 로 포즈만 1.6배(0.17→0.28초), 전체 +2.8%",
    "E-013": "구조가 fs-v4-flip 과 같아 속도도 같음(+3.7%). 크기는 가중치만 남긴 파일",
    "E-014": "E-013 과 같은 모델",
    "E-015": "E-013 과 같음(+4.0%)",
    "E-016": "E-015 와 같은 모델",
    "E-017": "E-012 + 뒷다리 좌우 바로잡기 후처리(CPU, 영상당 중앙 0.8ms·최대 3.0ms, 전부 바꾸는 방식의 절반)",
}
ids = list(t)
rows = [
    ids,
    ["2026-10-22"] * 7,
    ["RTX 4070 Laptop (박규원)"] * 7,
    ["충전 중"] * 7,
    ["cuda:0"] * 7,
    [f"{t[i]:.3f}" for i in ids],
    [f"{t[i] / base:.3f}" for i in ids],
    [""] * 7,
    [""] * 7,
    [str(mem[i]) for i in ids],
    [f"{mem[i] / 1131:.3f}" for i in ids],
    [size[i] for i in ids],
    [split[i] for i in ids],
    [
        "paw_eval/results/speed_1022.json" + (", lr_fix_time --legs hind" if i == "E-017" else "")
        for i in ids
    ],
    [note[i] for i in ids],
]
open(OUT, "w", encoding="utf-8-sig").write("\n".join("\t".join(r) for r in rows) + "\n")
print(len(rows), "행")
