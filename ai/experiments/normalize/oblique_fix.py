"""비스듬한 통과 처리 방법별 KPI-01·02 (S15P31A404-102, 10-29).

    python oblique_fix.py <track.json> [<track.json> ...]           # 실제 촬영
    python oblique_fix.py --synth <synth_pts 폴더>                    # 합성 카메라(yaw·pitch·roll·zoom)

paw_eval video_kpi 의 통과·KPI 규칙을 그대로 쓰고(통과 하나씩 kpi01_02), 방법마다 같은 통과에서 값을 모은다.
- raw    : 정규화 없음
- v0     : normalize.py 기본(가로·세로 크기 보정, 기울기 보정 끔)
- tilt   : v0 + 비스듬함(oblique.py) 사유에 path 가 있는 통과만 기울기 보정
- excl   : v0 + 비스듬한 통과를 KPI 에서 뺌(표시만)
- tilt_all: v0 + 모든 통과 기울기 보정(참고)
- iso    : 가로 늘리기 없이 세로 비율(거리 변화)을 가로·세로에 같이(normalize --no-scale-x --iso)
- ob_iso : 비스듬한 통과만 iso, 나머지는 v0
KPI-01 = (통과, 체절) 길이 변동계수 중앙값, KPI-02 = (통과, 관절) 왼쪽·오른쪽 1/3 각도 차 중앙값.
"""

import json
import os
import statistics
import sys
from pathlib import Path

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")
sys.path.insert(0, rf"{_PJT}/creamoff_data/paw_eval")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "normalize"))
import normalize as N  # noqa: E402
import oblique as O  # noqa: E402
import video_kpi as K  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
METHODS = ["raw", "v0", "tilt", "excl", "tilt_all", "iso", "ob_iso"]


def per_pass(d):
    """-> [(통과 비스듬함 정보, {방법: (cv 목록, diff 목록)})]"""
    out = []
    for v in d["videos"]:
        for a, b, h in N.find_passes(v):
            p = N.fit_pass(v, a, b, h)
            if p["n_fit"] < N.MIN_FRAMES:
                continue
            ob = O.measure_pass(v, a, b, h) or {"oblique": False, "reasons": []}
            kps = [(i, f) for i, f in enumerate(v["frames"]) if a <= i <= b and f]
            res = {}
            for m in METHODS:
                vv = dict(v, frames=list(v["frames"]))
                for i, f in kps:
                    f2 = dict(f)
                    f2.pop("norm", None)
                    if m != "raw":
                        tilt = m == "tilt_all" or (m == "tilt" and "path" in ob["reasons"])
                        iso = m == "iso" or (m == "ob_iso" and ob["oblique"])
                        n = N.apply(f["kp"], p, use_x=not iso, tilt=tilt, iso=iso)
                        if n:
                            f2["norm"] = n
                    vv["frames"][i] = f2
                ps = [q for q in K.find_passes(vv) if q[0] <= b and q[1] >= a]
                cv, df = K.kpi01_02(vv, ps) if not (m == "excl" and ob["oblique"]) else ([], [])
                res[m] = (cv, df)
            out.append((v["video"], ob, res))
    return out


def summary(rows, tag):
    print(f"[{tag}] 통과 {len(rows)}개 · 비스듬함 {sum(o['oblique'] for _, o, _ in rows)}개"
          f" (path {sum('path' in o['reasons'] for _, o, _ in rows)}, yaw {sum('yaw' in o['reasons'] for _, o, _ in rows)})")
    base = None
    for m in METHODS:
        cv = [x for _, _, r in rows for x in r[m][0]]
        df = [x for _, _, r in rows for x in r[m][1]]
        k1 = statistics.median(cv) if cv else None
        k2 = statistics.median(df) if df else None
        if m == "raw":
            base = (k1, k2)
        red = lambda x, y: f"{(1 - y / x) * 100:+.0f}%" if x and y is not None else "-"
        print(f"  {m:8} KPI-01 {k1:.4f} ({red(base[0], k1)}, n {len(cv)})  KPI-02 {k2:.2f}° ({red(base[1], k2)}, n {len(df)})")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--synth":
        folder = Path(args[1])
        groups = {}
        for f in sorted(folder.glob("*.track.json")):
            kind = f.name.split("-main.")[-1].split("+")[0].split("-")[0]   # yaw / pitch / roll / zoom / shift_x ...
            groups.setdefault(kind, []).append(f)
        for kind, fs in groups.items():
            rows = []
            for f in fs:
                rows += per_pass(json.loads(f.read_text(encoding="utf-8")))
            summary(rows, f"합성 {kind} ({len(fs)}개)")
    else:
        for p in args:
            summary(per_pass(json.loads(Path(p).read_text(encoding="utf-8"))), Path(p).name)
