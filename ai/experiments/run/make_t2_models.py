import sys
from pathlib import Path

root = Path(sys.argv[1]).expanduser().resolve()
paw = root / "paw_eval" / "models" / "fs-v4"
out = root / "models"
out.mkdir(parents=True, exist_ok=True)
flip = out / "pose_flip.py"
flip.write_text(f'_base_ = ["{paw / "pose.py"}"]\nmodel = dict(test_cfg=dict(flip_test=True))\n', encoding="utf-8")
T2 = "tta_scales = [0.9, 1.0, 1.1]\n"
variants = [
    ("k3-fp16-probe-t2-hind", 3, True, "probe", True, T2, "hind"),
    ("k3-fp16-probe-t2", 3, True, "probe", True, T2, ""),
    ("k1-fp32-t2", 1, False, "skip", True, T2, ""),
]
for name, k, fp16, gap, use_flip, tta, post in variants:
    (out / f"{name}.toml").write_text(
        f'name = "{name}"\n'
        f'backend = "mmpose"\n'
        f'config = "{flip if use_flip else paw / "pose.py"}"\n'
        f'weights = "{paw / "pose.pth"}"\n'
        f'device = "cpu"\n\n'
        f'[stack]\n'
        f'backend = "mmdet-mmpose-skip2"\n'
        f'det_config = "{paw / "det.py"}"\n'
        f'det_weights = "{paw / "det.pth"}"\n'
        f'det_conf = 0.25\n'
        f'batch = 8\n'
        f'det_interval = {k}\n'
        f'fp16 = {"true" if fp16 else "false"}\n'
        f'empty_gap = "{gap}"\n'
        f'{tta}'
        + (f'post = "{post}"\n' if post else ""), encoding="utf-8")
print([v[0] for v in variants])
