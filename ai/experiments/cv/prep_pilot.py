import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from prep_cv import to_train, dump

D = Path(__file__).parent / "data"
p = json.loads((D / "gt_pilot.json").read_text(encoding="utf-8"))
for im in p["images"]:
    im["file_name"] = "images/" + im["file_name"]
for box in ("gt", "eval"):
    t, kept = to_train(p, {}, "gt", 0, box, "keep")
    dump(t, D / f"tr_fpilot_gt_occ0_box{box}_untkeep.json")
    print(box, len(t["images"]), "images", kept, "points")
