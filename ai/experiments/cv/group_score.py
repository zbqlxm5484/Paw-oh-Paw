import collections
import csv
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/work/ssafy/paw_eval")
from score import score

GT = Path("/exp/cv/data/gt_pilot.json")
MODELS = {"fs-v4": "/exp/cv/runs/WW_B0/pilot_flip0.preds.json", "G3(제니 205장)": "/exp/cv/runs/WW_G3/pilot_flip0.preds.json"}
OUT = Path("/exp/cv/group_score.json")

weight = {r["dog"]: float(r["weight_kg"]) for r in csv.DictReader(open("/ssafy/dataset/videos/manifest.csv", encoding="utf-8-sig"))}
size = lambda kg: "소형(<10kg)" if kg < 10 else "중형(10~25kg)" if kg < 25 else "대형(25kg+)"
names = {"hjw": "허정원", "kjy": "김지윤", "cyw": "조영운", "cyj": "조유진", "jjh": "장준환"}

g = json.loads(GT.read_text(encoding="utf-8"))
ims = {im["id"]: im for im in g["images"]}
groups = collections.defaultdict(set)
for im in g["images"]:
    groups[("개", f"{im['dog']} {weight.get(im['dog'], 0):g}kg")].add(im["id"])
    groups[("체급", size(weight.get(im["dog"], 0)))].add(im["id"])
    groups[("라벨러", names.get(im["labeler"], im["labeler"]))].add(im["id"])
    groups[("전체", "전체")].add(im["id"])

res = []
tmp = Path(tempfile.mkdtemp())
for (kind, key), ids in sorted(groups.items()):
    sub = dict(g, images=[ims[i] for i in ids], annotations=[a for a in g["annotations"] if a["image_id"] in ids])
    p = tmp / "gt.json"
    p.write_text(json.dumps(sub, ensure_ascii=False), encoding="utf-8")
    row = {"kind": kind, "key": key, "images": len(ids)}
    for m, pred in MODELS.items():
        k = score(str(p), pred)["kpi"]
        row[m] = {"angle": k["KPI-04"]["mae"], "front": k["KPI-21"]["front"]["value"], "front_n": k["KPI-21"]["front"]["n"],
                  "hind": k["KPI-21"]["hind"]["value"], "hind_n": k["KPI-21"]["hind"]["n"], "pck10": k["KPI-18"]["value"]}
    res.append(row)
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
for r in res:
    a, b = r["fs-v4"], r["G3(제니 205장)"]
    f = lambda v: "-" if v is None else f"{v * 100:.0f}%"
    print(f"{r['kind']:4} {r['key']:16} n={r['images']:3} | fs-v4 각도 {a['angle'] or 0:5.1f} 앞 {f(a['front'])}({a['front_n']}) 뒤 {f(a['hind'])}({a['hind_n']}) PCK10 {a['pck10'] or 0:.2f} | G3 각도 {b['angle'] or 0:5.1f} 뒤 {f(b['hind'])}")
