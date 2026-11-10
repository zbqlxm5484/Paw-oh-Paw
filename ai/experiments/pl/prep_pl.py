import json
import sys
from pathlib import Path

sys.path.insert(0, "/exp/cv")
from prep_cv import dump, to_train

for name in sys.argv[1:]:
    d = json.loads(Path(f"/exp/pl/{name}/pseudo.json").read_text(encoding="utf-8"))
    t, kept = to_train(d, {}, "gt", 0, "eval", "keep")
    dump(t, Path(f"/exp/cv/data/tr_fpl_{name}.json"))
    print(name, len(t["images"]), "images", kept, "points")
