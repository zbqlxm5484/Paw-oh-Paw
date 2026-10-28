"""측정 명령 하나를 자식 프로세스로 돌리며 GPU 메모리(KPI-16)를 함께 잰다. speed.py 의 GpuMem 과 같은 방식:
돌리기 전 GPU 사용량을 바닥으로 보고, 도는 동안 최대값에서 뺀다. 속도는 자식이 찍은 마지막 '영상당 X초' 줄에서 읽는다.
    python perf_mem.py --out results/perf1023_x.json -- .venv/Scripts/python.exe det_stride.py speed ...
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import speed


def main():
    i = sys.argv.index("--")
    out, cmd = Path(sys.argv[sys.argv.index("--out") + 1]), sys.argv[i + 1 :]
    cmd[0] = str(Path(cmd[0]).resolve())  # 윈도우 CreateProcess 는 상대 경로 실행 파일을 못 찾는다
    mem = speed.GpuMem(0)
    base = mem.level()
    t_a = time.monotonic()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    t_b = time.monotonic()
    after, peak = mem.level(2.0), mem.peak(t_a, t_b)
    mem.close()
    print(r.stdout[-2000:], r.stderr[-2000:] if r.returncode else "")
    m = re.findall(r"영상당 ([\d.]+)초 \(탐지 ([\d.]+) / 관절점 ([\d.]+)\)", r.stdout)
    t = [float(x) for x in m[-1]] if m else [None] * 3
    res = {
        "cmd": " ".join(cmd),
        "total_s": t[0],
        "det_s": t[1],
        "pose_s": t[2],
        "gpu_base_mib": base,
        "gpu_peak_mib": peak,
        "gpu_after_mib": after,
        "kpi16_mib": peak - base,
        "returncode": r.returncode,
    }
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out, res["total_s"], res["kpi16_mib"])


if __name__ == "__main__":
    main()
