import argparse

import torch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--ft", required=True)
    ap.add_argument("--alpha", type=float, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    bc = torch.load(a.base, map_location="cpu", weights_only=False)
    b = bc["state_dict"]
    f = torch.load(a.ft, map_location="cpu", weights_only=False)["state_dict"]
    out = {}
    for k, v in f.items():
        w = b.get(k)
        if w is not None and v.is_floating_point() and w.shape == v.shape:
            out[k] = (1 - a.alpha) * w.float() + a.alpha * v.float()
        else:
            out[k] = v
    torch.save({"meta": {**(bc.get("meta") or {}), "wise": vars(a)}, "state_dict": out}, a.out)


if __name__ == "__main__":
    main()
