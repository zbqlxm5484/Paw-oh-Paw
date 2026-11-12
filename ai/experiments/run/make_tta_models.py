import sys
from pathlib import Path

root = Path(sys.argv[1]).expanduser().resolve()
paw = root / "paw_eval" / "models" / "fs-v4"
out = root / "models"
out.mkdir(parents=True, exist_ok=True)
flip = out / "pose_flip.py"
flip.write_text(f'_base_ = ["{paw / "pose.py"}"]\nmodel = dict(test_cfg=dict(flip_test=True))\n', encoding="utf-8")
E036 = "tta_scales = [0.85, 0.9, 1.0, 1.1, 1.15]\ntta_rot = 8\n"
variants = [
    ("k1-fp32-e036", 1, False, "skip", True, E036, "hind"),
    ("k3-fp16-probe-hind", 3, True, "probe", False, "", "hind"),
    ("k3-fp16-probe-flip-hind", 3, True, "probe", True, "", "hind"),
    ("k3-fp16-probe-e036", 3, True, "probe", True, E036, "hind"),
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
        f'post = "{post}"\n', encoding="utf-8")
(out / "tta_names.txt").write_text("\n".join(v[0] for v in variants) + "\n", encoding="utf-8")
print([v[0] for v in variants])
