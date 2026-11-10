import json
import os
import sys

SRC = "/ssafy/dataset/keypoints_wowwow/annotations.json"
OUT = sys.argv[1] if len(sys.argv) > 1 else "/exp/results/wowwow"
GRADES = {"good", "ambiguous"}
VAL_DATES = {"260816", "260817"}

d = json.load(open(SRC, encoding="utf-8"))
ims = {i["id"]: i for i in d["images"]}
keep = [a for a in d["annotations"] if (a.get("attributes") or {}).get("grade") in GRADES]
os.makedirs(OUT, exist_ok=True)
for name, pick in (("all", lambda dt: True), ("train", lambda dt: dt not in VAL_DATES), ("val", lambda dt: dt in VAL_DATES)):
    anns = [a for a in keep if pick(ims[a["image_id"]]["date"])]
    ids = {a["image_id"] for a in anns}
    doc = dict(d, images=[i for i in d["images"] if i["id"] in ids], annotations=anns)
    json.dump(doc, open(f"{OUT}/gt_{name}.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(name, "images", len(doc["images"]), "annotations", len(anns))
