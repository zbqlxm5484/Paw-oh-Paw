import argparse
import os
from pathlib import Path

import torch

DROP = ("optimizer", "message_hub", "param_schedulers")


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


def save_fp16(src, dst):
    src, dst = Path(src), Path(dst)
    c = torch.load(src, map_location="cpu", weights_only=False)
    sd = c["state_dict"]
    c = {k: v for k, v in c.items() if k not in DROP}
    c["state_dict"] = half_shared(sd)
    dst.parent.mkdir(parents=True, exist_ok=True)
    torch.save(c, dst)
    back = torch.load(dst, map_location="cpu", weights_only=False)["state_dict"]
    diff = max((back[k].float() - sd[k].float()).abs().max().item() for k in sd if sd[k].is_floating_point())
    return dict(src=str(src), dst=str(dst), keys=len(sd), storages=(storages(sd), storages(back)),
                mib=(mib(src), mib(dst)), max_abs_diff=diff)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    total = 0.0
    for s in a.src:
        r = save_fp16(s, out / Path(s).name)
        total += r["mib"][1]
        print(f'{Path(s).name}: {r["mib"][0]} -> {r["mib"][1]} MiB, 텐서 {r["keys"]}개, '
              f'저장 공간 {r["storages"][0]} -> {r["storages"][1]}, 최대 차이 {r["max_abs_diff"]:.2e}')
    print(f"합계 {round(total, 2)} MiB")


if __name__ == "__main__":
    main()
