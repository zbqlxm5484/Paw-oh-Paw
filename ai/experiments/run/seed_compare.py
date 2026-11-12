import sys
from pathlib import Path

import torch

R = Path(sys.argv[1])
for mode in ("head", "full"):
    a = torch.load(R / f"{mode}_a/final.pth", map_location="cpu", weights_only=False)["state_dict"]
    b = torch.load(R / f"{mode}_b/final.pth", map_location="cpu", weights_only=False)["state_dict"]
    diff = {k: (a[k].float() - b[k].float()).abs().max().item() for k in a if a[k].is_floating_point()}
    same = sum(1 for v in diff.values() if v == 0)
    top = sorted(diff.items(), key=lambda x: -x[1])[:3]
    print(f"{mode}: 텐서 {len(diff)}개 중 완전히 같음 {same}개, 최대 차이 {max(diff.values()):.3e}")
    for k, v in top:
        print(f"  {k} {v:.3e}")
