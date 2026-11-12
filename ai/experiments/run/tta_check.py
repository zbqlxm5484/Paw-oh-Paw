import sys
import tomllib
from pathlib import Path

import numpy as np

sys.path.insert(0, "/exp/stacks")
sys.path.insert(0, "/work/ssafy/paw_eval")
import speed
from skipdet2_old import register as reg_old

reg_old(speed.STACKS, speed.MMDetMMPose, speed.best_dog)
M = Path("/work/ssafy/models")
vids = [speed.read_frames(p) for p in speed.load_videos("speed_videos.txt", "../dataset/videos")][:2]


def run(toml, backend=None):
    cfg = tomllib.loads(toml.read_text(encoding="utf-8"))
    if backend:
        cfg["stack"]["backend"] = backend
    m = speed.STACKS[cfg["stack"]["backend"]](cfg, toml.parent, "cuda:0")
    outs = []
    for f in vids:
        keep = []
        m(f, keep)
        outs.append((keep, m.last_detect_calls))
    return outs


def pts(keep):
    return {j: np.asarray(k)[:22, :2] for j, (b, k) in enumerate(keep) if k is not None}


old = run(M / "k3-fp16-probe.toml", "mmdet-mmpose-skip2-old")
new = run(M / "k3-fp16-probe.toml")
for (ko, co), (kn, cn) in zip(old, new):
    a, b = pts(ko), pts(kn)
    d = max((np.abs(a[j] - b[j]).max() for j in a), default=0)
    print(f"회귀: 프레임 {len(a)}/{len(b)}, 호출 {co}/{cn}, 최대 차이 {d:.4f}px")
for name in ["k3-fp16-probe-hind", "k3-fp16-probe-flip-hind", "k3-fp16-probe-e036"]:
    tt = run(M / f"{name}.toml")
    for (kn, cn), (kt, ct) in zip(new, tt):
        a, b = pts(kn), pts(kt)
        d = [float(np.median(np.hypot(*(a[j] - b[j]).T))) for j in a if j in b]
        print(f"{name}: 프레임 {len(a)}/{len(b)}, 호출 {cn}/{ct}, 기본 대비 중앙 이동 {np.median(d):.2f}px")
