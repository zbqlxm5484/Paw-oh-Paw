import collections
import csv
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
OUT = Path(sys.argv[2])
SPLIT = sys.argv[3] if len(sys.argv) > 3 else "train"
CAP = int(sys.argv[4]) if len(sys.argv) > 4 else 30
HERE = Path(__file__).parent
NOT_WALKING = {"calib", "weight", "_discard", "disease"}

split = {d["dog"]: d["split"] for d in json.loads((HERE / "dog_split.json").read_text(encoding="utf-8"))["dogs"]}
rows = [r for r in csv.DictReader(open(ROOT / "manifest.csv", encoding="utf-8-sig"))
        if split.get(r["dog"]) == SPLIT and r["label"] not in NOT_WALKING]
by_dog = collections.defaultdict(list)
for r in rows:
    by_dog[r["dog"]].append(r)
rng = random.Random(1027)
lines, count = [], collections.Counter()
for dog, rs in sorted(by_dog.items()):
    rs = sorted(rs, key=lambda r: r["stamp"])
    rng.shuffle(rs)
    for r in rs[:CAP]:
        d = ROOT / r["path"].split("videos/", 1)[-1]
        mp4 = sorted(d.glob("*.mp4"))
        main = [p for p in mp4 if "main" in p.name] or (mp4 if len(mp4) == 1 else [])
        if not main:
            continue
        p = main[0]
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        lines.append(f"{p.relative_to(ROOT).as_posix()} {h}")
        count[dog] += 1
OUT.write_text("# 의사 라벨용 " + SPLIT + " 개 main 영상, 개마다 최대 " + str(CAP) + "촬영\n" + "\n".join(lines) + "\n", encoding="utf-8")
print(len(lines), "videos", dict(count))
