import sys

import torch

base = torch.load("/ssafy/model/pose.pth", map_location="cpu", weights_only=False)
base = base.get("state_dict", base)
for path in sys.argv[1:]:
    sd = torch.load(path, map_location="cpu", weights_only=False)["state_dict"]
    groups = {}
    for k, v in sd.items():
        if k not in base or not v.is_floating_point():
            continue
        g = k.split(".")[0]
        d = (v.float() - base[k].float()).abs().max().item()
        n, m, t = groups.get(g, (0, 0.0, 0))
        groups[g] = (n + (d > 0), max(m, d), t + 1)
    print(path, {g: f"{n}/{t} changed, max {m:.2e}" for g, (n, m, t) in groups.items()})
