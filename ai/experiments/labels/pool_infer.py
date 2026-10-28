"""36 후보 영상에 오토라벨 모델을 STEP 프레임 간격으로 돌려 /work/pool/pool_dump.jsonl 에 쌓는다(이어 돌리기 가능)."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import PIL.Image

sys.path.insert(0, "/work/tools")
import cvat_aa

STEP = 2
root = Path("/work/pool")
dump = root / "pool_dump.jsonl"
done = set()
if dump.exists():
    done = {json.loads(l)["frame_name"].rsplit("_f", 1)[0] for l in open(dump, encoding="utf-8")}
fn = cvat_aa.create(dump=str(dump))
vids = sorted((root / "videos").glob("*.mp4"))
for n, v in enumerate(vids, 1):
    if v.stem in done:
        continue
    cap = cv2.VideoCapture(str(v))
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if i % STEP == 0:
            fn.detect(
                SimpleNamespace(frame_name=f"{v.stem}_f{i:06d}.jpg", conf_threshold=None),
                PIL.Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)),
            )
        i += 1
    print(f"[{n}/{len(vids)}] {v.stem} {i} frames", flush=True)
fn._dump_fh.close()
