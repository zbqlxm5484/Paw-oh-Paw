import argparse
import pprint

import torch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="/work/ssafy/paw_eval/models/fs-v4/pose.pth")
    ap.add_argument("--out", default="/exp/train/creamoff46.py")
    ap.add_argument("--hind-weight", type=float, default=1.0)
    a = ap.parse_args()
    m = torch.load(a.ckpt, map_location="cpu", weights_only=False)["meta"]["dataset_meta"]
    n = m["num_keypoints"]
    names = [m["keypoint_id2name"][i] for i in range(n)]
    upper = set(int(i) for i in m.get("upper_body_ids", []))
    colors = m.get("keypoint_colors")
    kinfo = {}
    for i, name in enumerate(names):
        j = int(m["flip_indices"][i])
        kinfo[i] = dict(name=name, id=i,
                        color=[int(c) for c in colors[i]] if colors is not None else [255, 255, 255],
                        type="upper" if i in upper else "lower",
                        swap="" if j == i else names[j])
    sk = {}
    links = m.get("skeleton_links") or []
    lcolors = m.get("skeleton_link_colors")
    for k, (p, q) in enumerate(links):
        sk[k] = dict(link=(names[int(p)], names[int(q)]), id=k,
                     color=[int(c) for c in lcolors[k]] if lcolors is not None else [255, 255, 255])
    weights = [float(w) for w in m["dataset_keypoint_weights"]] if m.get("dataset_keypoint_weights") is not None else [1.0] * n
    for i in range(14, 22):
        weights[i] *= a.hind_weight
    info = dict(dataset_name="creamoff46", paper_info=dict(), keypoint_info=kinfo, skeleton_info=sk,
                joint_weights=weights, sigmas=[float(s) for s in m["sigmas"]])
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("dataset_info = " + pprint.pformat(info, width=120, sort_dicts=False) + "\n")
    print("meta ->", a.out, "| keypoints", n, "| hind weight", a.hind_weight)


if __name__ == "__main__":
    main()
