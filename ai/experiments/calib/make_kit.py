import json
import random
import shutil
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr

G = Path(sys.argv[1])
PREDS = Path(sys.argv[2])
KIT = Path(sys.argv[3])
KEY = Path(sys.argv[4])
PER_CAM = 5
KP_CONF = 0.3

gt = json.loads((G / "annotations.json").read_text(encoding="utf-8"))
names = gt["categories"][0]["keypoints"]
preds = {p["ann_id"]: p["keypoints"] for p in json.loads(PREDS.read_text(encoding="utf-8"))["predictions"]}
anns = {a["image_id"]: a for a in gt["annotations"]}
rng = random.Random(1027)
chosen = []
for cam in ("main", "sub1", "sub2", "sub3"):
    ims = [im for im in gt["images"] if im["camera"] == cam and im["id"] in anns]
    rng.shuffle(ims)
    seen = set()
    for im in ims:
        if im["session"] in seen:
            continue
        seen.add(im["session"])
        chosen.append(im)
        if len(seen) == PER_CAM:
            break

(KIT / "images").mkdir(parents=True, exist_ok=True)
KEY.mkdir(parents=True, exist_ok=True)
lines = ['<?xml version="1.0" encoding="utf-8"?>', "<annotations>", "  <version>1.1</version>"]
for n, im in enumerate(chosen):
    name = Path(im["file_name"]).name
    shutil.copy(G / im["file_name"], KIT / "images" / name)
    k = preds[anns[im["id"]]["id"]]
    lines.append(f'  <image id="{n}" name={quoteattr(name)} width="{im["width"]}" height="{im["height"]}">')
    lines.append('    <skeleton label="dog" source="auto" z_order="0">')
    for i, nm in enumerate(names):
        occ = 1 if k[3 * i + 2] < KP_CONF else 0
        lines.append(f'      <points label="{nm}" source="auto" outside="0" occluded="{occ}" points="{k[3 * i]:.2f},{k[3 * i + 1]:.2f}">')
        lines.append("      </points>")
    lines.append('      <attribute name="grade">unreviewed</attribute>')
    lines.append('      <attribute name="reason">-</attribute>')
    lines.append("    </skeleton>")
    lines.append("  </image>")
lines.append("</annotations>")
(KIT / "annotations.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")

key = dict(gt, images=chosen, annotations=[anns[im["id"]] for im in chosen])
(KEY / "gt_calib.json").write_text(json.dumps(key, ensure_ascii=False), encoding="utf-8")
pre = {"predictions": [{"ann_id": anns[im["id"]]["id"], "keypoints": preds[anns[im["id"]]["id"]]} for im in chosen]}
(KEY / "prelabel.json").write_text(json.dumps(pre, ensure_ascii=False), encoding="utf-8")
print(len(chosen), "images", sorted({im["camera"] for im in chosen}), len({im["session"] for im in chosen}), "sessions")
