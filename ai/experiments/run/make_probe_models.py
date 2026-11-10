import sys
from pathlib import Path

root = Path(sys.argv[1]).expanduser().resolve()
paw = root / "paw_eval" / "models" / "fs-v4"
out = root / "models"
out.mkdir(parents=True, exist_ok=True)
variants = [("k3-fp16-skip", 3, True, "skip"), ("k3-fp16-probe", 3, True, "probe"),
            ("k2-fp16-probe", 2, True, "probe"), ("k3-fp32-probe", 3, False, "probe")]
for name, k, fp16, gap in variants:
    (out / f"{name}.toml").write_text(
        f'name = "{name}"\n'
        f'backend = "mmpose"\n'
        f'config = "{paw / "pose.py"}"\n'
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
        f'empty_gap = "{gap}"\n', encoding="utf-8")
(out / "names.txt").write_text("\n".join(v[0] for v in variants) + "\n", encoding="utf-8")
print([v[0] for v in variants])
