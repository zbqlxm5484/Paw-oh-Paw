import torch

base = torch.load("/ssafy/model/pose.pth", map_location="cpu", weights_only=False)
base = base.get("state_dict", base)
for mode in ("head_a", "head_b", "full_a"):
    sd = torch.load(f"/exp/results/seed_1029/{mode}/final.pth", map_location="cpu", weights_only=False)["state_dict"]
    groups = {}
    for k, v in sd.items():
        if k not in base or not v.is_floating_point():
            continue
        g = k.split(".")[0] + ("." + k.split(".")[1] if k.startswith("backbone") else "")
        d = (v.float() - base[k].float()).abs().max().item()
        n, m = groups.get(g, (0, 0.0))
        groups[g] = (n + (d > 0), max(m, d))
    print(mode, {g: f"{n} changed, max {m:.2e}" for g, (n, m) in groups.items()})
