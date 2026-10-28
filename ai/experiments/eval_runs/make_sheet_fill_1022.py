import os
import sys

_OUT = os.environ.get("CREAMOFF_OUT", "C:/Users/SSAFY/Downloads")

sys.stdout.reconfigure(encoding="utf-8")
OUT = f"{_OUT}/구글시트_붙여넣기_1022/4_탭1_기존열_KPI01-02-24_E001-E007.tsv"
M = "미측정"
rows = [
    ["항목", "E-001", "E-002", "E-003", "E-004", "E-005", "E-006", "E-007"],
    ["KPI-01 다리 길이 흔들림 (변동계수)", "0.1240", "0.1186", "0.1365", "0.1306", M, M, M],
    ["KPI-02 화면 왼쪽·오른쪽 각도 차 (°)", "14.55", "14.36", "14.62", "14.72", M, M, M],
    ["KPI-24 좌우 다리 바뀐 횟수", "90", "61", "2", "0", M, M, M],
]
open(OUT, "w", encoding="utf-8-sig").write("\n".join("\t".join(r) for r in rows) + "\n")
