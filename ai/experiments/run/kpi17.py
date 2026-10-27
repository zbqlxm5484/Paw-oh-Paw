import os
import sys
from pathlib import Path

import torch

SRC = Path("/work/ssafy/paw_eval/models/fs-v4")
OUT = Path("/exp/models/fs-v4-fp16s")
OUT.mkdir(parents=True, exist_ok=True)


def mib(p):
    return round(os.path.getsize(p) / 2**20, 2)


def half_shared(sd):
    seen = {}
    out = {}
    for k, v in sd.items():
        if not v.is_floating_point():
            out[k] = v
            continue
        key = (v.untyped_storage().data_ptr(), v.storage_offset(), tuple(v.shape), tuple(v.stride()))
        if key not in seen:
            seen[key] = v.half()
        out[k] = seen[key]
    return out


def storages(sd):
    return len({v.untyped_storage().data_ptr() for v in sd.values()})


for name in ("det", "pose"):
    c = torch.load(SRC / f"{name}.pth", map_location="cpu", weights_only=False)
    sd = c["state_dict"]
    c["state_dict"] = half_shared(sd)
    torch.save(c, OUT / f"{name}.pth")
    back = torch.load(OUT / f"{name}.pth", map_location="cpu", weights_only=False)["state_dict"]
    diff = max((back[k].float() - sd[k].float()).abs().max().item() for k in sd if sd[k].is_floating_point())
    print(name, "keys", len(sd), "storages", storages(sd), "->", storages(back), "|", mib(SRC / f"{name}.pth"), "->", mib(OUT / f"{name}.pth"), "MiB | max abs diff", f"{diff:.2e}")

total = sum(mib(OUT / f"{n}.pth") for n in ("det", "pose"))
print("fp16 shared total MiB", round(total, 2), "MB", round(total * 2**20 / 1e6, 2))

for p in sys.argv[1:]:
    c = torch.load(p, map_location="cpu", weights_only=False)
    print("trained ckpt", p, mib(p), "MiB keys", sorted(c.keys()))
    c = {"meta": c.get("meta"), "state_dict": half_shared(c["state_dict"])}
    q = Path("/tmp") / ("fp16_" + Path(p).name)
    torch.save(c, q)
    print("trained ckpt fp16", mib(q), "MiB; with det fp16s", round(mib(q) + mib(OUT / "det.pth"), 2), "MiB")
