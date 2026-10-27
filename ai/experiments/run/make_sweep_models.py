from pathlib import Path

PAW = Path("/work/ssafy/paw_eval/models/fs-v4")
OUT = Path("/exp/models/sweep")
OUT.mkdir(parents=True, exist_ok=True)
KS = (1, 2, 3, 4, 5, 6, 8)

names = []
for fp16 in (False, True):
    for k in KS:
        name = f"k{k}-{'fp16' if fp16 else 'fp32'}"
        (OUT / f"{name}.toml").write_text(
            f'name = "{name}"\n'
            f'backend = "mmpose"\n'
            f'config = "{PAW / "pose.py"}"\n'
            f'weights = "{PAW / "pose.pth"}"\n'
            f'device = "cpu"\n\n'
            f'[stack]\n'
            f'backend = "mmdet-mmpose-skip2"\n'
            f'det_config = "{PAW / "det.py"}"\n'
            f'det_weights = "{PAW / "det.pth"}"\n'
            f'det_conf = 0.25\n'
            f'batch = 8\n'
            f'det_interval = {k}\n'
            f'fp16 = {"true" if fp16 else "false"}\n', encoding="utf-8")
        names.append(name)
(OUT / "names.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
print(names)
