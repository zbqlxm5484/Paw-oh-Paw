import argparse
import collections
import json
import os

N_IN, N_OUT = 22, 46
BOX_MARGIN = 0.15


def load(src):
    d = json.load(open(f"{src}/annotations.json", encoding="utf-8"))
    return d, {i["id"]: i for i in d["images"]}


def wide_box(bbox, im, margin):
    x, y, w, h = bbox
    m = margin * max(w, h)
    x1, y1 = max(0.0, x - m), max(0.0, y - m)
    x2, y2 = min(float(im["width"]), x + w + m), min(float(im["height"]), y + h + m)
    return [x1, y1, x2 - x1, y2 - y1]


def build(d, ims, grades, touched_only, visible_only, ids, margin=BOX_MARGIN):
    out = []
    kept_pts = dropped_untouched = dropped_occluded = 0
    for a in d["annotations"]:
        if a["image_id"] not in ids:
            continue
        at = a.get("attributes") or {}
        if grades and at.get("grade") not in grades:
            continue
        t = at.get("touched") or [0] * N_IN
        k, kp = a["keypoints"], []
        n = 0
        for i in range(N_IN):
            x, y, v = k[3 * i], k[3 * i + 1], int(k[3 * i + 2])
            if v == 1 and visible_only:
                v = 0
                dropped_occluded += 1
            elif v == 2 and touched_only and not t[i]:
                v = 0
                dropped_untouched += 1
            n += v > 0
            kp += [x, y, v]
        if n < 3:
            continue
        kp += [0, 0, 0] * (N_OUT - N_IN)
        a2 = dict(a, keypoints=kp, num_keypoints=n, bbox=wide_box(a["bbox"], ims[a["image_id"]], margin))
        out.append(a2)
        kept_pts += n
    return out, kept_pts, dropped_untouched, dropped_occluded


def subset(d, anns):
    ids = {a["image_id"] for a in anns}
    cat = dict(d["categories"][0])
    cat["keypoints"] = cat["keypoints"][:N_IN] + [f"kp_{i}" for i in range(N_IN, N_OUT)]
    return dict(d, images=[i for i in d["images"] if i["id"] in ids], annotations=anns, categories=[cat])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="/ssafy/dataset/keypoints_wowwow")
    ap.add_argument("--out", default="/data/wow_set")
    ap.add_argument("--grades", default="good,ambiguous")
    ap.add_argument("--val-dates", default="260816,260817")
    ap.add_argument("--keep-untouched", action="store_true")
    ap.add_argument("--keep-occluded", action="store_true")
    ap.add_argument("--box-margin", type=float, default=BOX_MARGIN)
    a = ap.parse_args()
    d, ims = load(a.src)
    grades = set(a.grades.split(",")) if a.grades else None
    val_dates = set(a.val_dates.split(",")) if a.val_dates else set()
    os.makedirs(a.out, exist_ok=True)
    link = f"{a.out}/images"
    if not os.path.exists(link):
        os.symlink(f"{a.src}/images", link)
    rep = {}
    for name, pick in (("train", lambda im: im["date"] not in val_dates), ("val", lambda im: im["date"] in val_dates)):
        ids = {i for i, im in ims.items() if pick(im)}
        anns, kept, du, do = build(d, ims, grades, not a.keep_untouched, not a.keep_occluded, ids, a.box_margin)
        doc = subset(d, anns)
        json.dump(doc, open(f"{a.out}/{name}_46.json", "w", encoding="utf-8"), ensure_ascii=False)
        c = collections.Counter(ims[x["image_id"]]["date"] for x in anns)
        cam = collections.Counter(ims[x["image_id"]]["camera"] for x in anns)
        sess = {ims[x["image_id"]]["session"] for x in anns}
        rep[name] = dict(images=len(doc["images"]), annotations=len(anns), points=kept, dropped_untouched=du,
                         dropped_occluded=do, sessions=len(sess), dates=dict(c), cameras=dict(cam))
        print(name, rep[name])
    sess_tr = {ims[i]["session"] for i in ims if ims[i]["date"] not in val_dates}
    sess_va = {ims[i]["session"] for i in ims if ims[i]["date"] in val_dates}
    assert not (sess_tr & sess_va), "촬영이 학습과 검증에 섞임"
    json.dump(rep, open(f"{a.out}/report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
