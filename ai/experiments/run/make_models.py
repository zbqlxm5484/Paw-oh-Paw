import os
from pathlib import Path

import torch
from mmengine.config import Config

PAW = Path("/work/ssafy/paw_eval/models/fs-v4")
OUT = Path("/exp/models")
OUT.mkdir(parents=True, exist_ok=True)


def toml(name, det_config, det_weights, pose_weights=PAW / "pose.pth", backend="mmdet-mmpose", extra=""):
    (OUT / f"{name}.toml").write_text(
        f'name = "{name}"\n'
        f'backend = "mmpose"\n'
        f'config = "{PAW / "pose.py"}"\n'
        f'weights = "{pose_weights}"\n'
        f'device = "cpu"\n\n'
        f'[stack]\n'
        f'backend = "{backend}"\n'
        f'det_config = "{det_config}"\n'
        f'det_weights = "{det_weights}"\n'
        f'det_conf = 0.25\n'
        f'batch = 8\n' + extra, encoding="utf-8")


fp = OUT / "fs-v4-fp16"
fp.mkdir(exist_ok=True)
for n in ("pose", "det"):
    c = torch.load(PAW / f"{n}.pth", map_location="cpu", weights_only=False)
    c["state_dict"] = {k: (v.half() if v.is_floating_point() else v) for k, v in c["state_dict"].items()}
    torch.save(c, fp / f"{n}.pth")
    print(n, round(os.path.getsize(PAW / f"{n}.pth") / 2**20, 2), "->", round(os.path.getsize(fp / f"{n}.pth") / 2**20, 2), "MiB")
toml("fs-v4-fp16", PAW / "det.py", fp / "det.pth", pose_weights=fp / "pose.pth")

for size in (512, 416, 320):
    cfg = Config.fromfile(str(PAW / "det.py"))
    pipe = cfg.test_dataloader.dataset.pipeline
    resize = [p for p in pipe if p["type"].endswith("Resize")][0]
    pad = [p for p in pipe if p["type"].endswith("Pad")][0]
    resize["scale"] = (size, size)
    pad["size"] = (size, size)
    path = OUT / f"det{size}.py"
    cfg.dump(str(path))
    toml(f"fs-v4-det{size}", path, PAW / "det.pth")
    print("det", size, "->", path.name)

for k in (2, 3, 5, 8):
    toml(f"fs-v4-skip{k}", PAW / "det.py", PAW / "det.pth", backend="mmdet-mmpose-skip", extra=f"det_interval = {k}\n")
    print("skip", k)

print(sorted(p.name for p in OUT.glob("*.toml")))
