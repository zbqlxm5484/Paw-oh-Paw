import argparse
import copy
import json
from pathlib import Path

N_IN = 22
N_OUT = 46
MARGIN = 0.15


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump(d, p):
    Path(p).write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def subset(d, sessions):
    keep = {im["id"] for im in d["images"] if im["session"] in sessions}
    out = copy.deepcopy(d)
    out["images"] = [im for im in d["images"] if im["id"] in keep]
    out["annotations"] = [a for a in d["annotations"] if a["image_id"] in keep]
    return out


def wide_box(bbox, im):
    x, y, w, h = bbox
    m = MARGIN * max(w, h)
    x1, y1 = max(0.0, x - m), max(0.0, y - m)
    x2, y2 = min(float(im["width"]), x + w + m), min(float(im["height"]), y + h + m)
    return [x1, y1, x2 - x1, y2 - y1]


def to_train(d, preds, label, occluded, box, untouched):
    out = copy.deepcopy(d)
    ims = {im["id"]: im for im in out["images"]}
    kept = 0
    for a in out["annotations"]:
        k = a["keypoints"]
        touched = (a.get("attributes") or {}).get("touched") or [1] * N_IN
        src = preds[a["id"]] if label == "self" else k
        pts = []
        for i in range(N_IN):
            v = int(k[3 * i + 2])
            if v == 1 and not occluded:
                v = 0
            if v == 2 and untouched == "drop" and not touched[i]:
                v = 0
            x, y = (src[3 * i], src[3 * i + 1]) if v else (0, 0)
            kept += v > 0
            pts += [x, y, v]
        a["keypoints"] = pts + [0, 0, 0] * (N_OUT - N_IN)
        a["num_keypoints"] = sum(1 for i in range(N_OUT) if a["keypoints"][3 * i + 2] > 0)
        if box == "eval":
            a["bbox"] = wide_box(a["bbox"], ims[a["image_id"]])
    cat = out["categories"][0]
    cat["keypoints"] = cat["keypoints"][:N_IN] + [f"kp_{i}" for i in range(N_IN, N_OUT)]
    return out, kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True)
    ap.add_argument("--preds", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ww")
    ap.add_argument("--ww-train")
    a = ap.parse_args()
    d = load(a.gt)
    preds = {p["ann_id"]: p["keypoints"] for p in load(a.preds)["predictions"]}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sessions = sorted({im["session"] for im in d["images"]})
    folds = [set(sessions[0::2]), set(sessions[1::2])]
    dump({"f0": sorted(folds[0]), "f1": sorted(folds[1])}, out / "folds.json")
    if a.ww:
        w = load(a.ww)
        keep = {x["image_id"] for x in w["annotations"] if (x.get("attributes") or {}).get("grade") in ("good", "ambiguous")}
        w["images"] = [im for im in w["images"] if im["id"] in keep]
        w["annotations"] = [x for x in w["annotations"] if x["image_id"] in keep]
        dump(w, out / "gt_ww.json")
        print("gt_ww.json", len(w["images"]), "images")
    if a.ww_train:
        wt = load(a.ww_train)
        for a_ in wt["annotations"]:
            a_["keypoints"] = a_["keypoints"][:3 * N_IN]
        wt["categories"][0]["keypoints"] = wt["categories"][0]["keypoints"][:N_IN]
        for box in ("gt", "eval"):
            t, kept = to_train(wt, {}, "gt", 0, box, "keep")
            dump(t, out / f"tr_fww_gt_occ0_box{box}_untkeep.json")
            print(f"tr_fww box{box}", len(t["images"]), "images", kept, "points")
    for f, s in [*enumerate(folds), ("all", set(sessions))]:
        part = subset(d, s)
        dump(part, out / f"gt_f{f}.json")
        for label in ("gt", "self"):
            for occ in (0, 1):
                for box in ("gt", "eval"):
                    for unt in ("keep", "drop"):
                        if label == "self" and unt == "drop":
                            continue
                        t, kept = to_train(part, preds, label, occ, box, unt)
                        name = f"tr_f{f}_{label}_occ{occ}_box{box}_unt{unt}.json"
                        dump(t, out / name)
                        print(name, len(t["images"]), "images", kept, "points")


if __name__ == "__main__":
    main()
