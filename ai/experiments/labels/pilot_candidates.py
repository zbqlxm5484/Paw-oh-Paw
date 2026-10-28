"""32 라벨 맞추기 후보: 영상마다 STEP 프레임 간격으로 jpg 저장 + 오토라벨 점 덤프."""

import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import PIL.Image

sys.path.insert(0, "/work/tools")
import cvat_aa

STEP = 6
root = Path("/work/pilot")
out = root / "cand"
out.mkdir(exist_ok=True)
dump = root / "cand_dump.jsonl"
if dump.exists():
    dump.unlink()
fn = cvat_aa.create(dump=str(dump))
for v in sorted((root / "videos").glob("*.mp4")):
    cap = cv2.VideoCapture(str(v))
    i = 0
    n = 0
    (out / v.stem).mkdir(exist_ok=True)
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if i % STEP == 0:
            name = f"{v.stem}_f{i:06d}.jpg"
            cv2.imencode(".jpg", fr)[1].tofile(str(out / v.stem / name))
            fn.detect(
                SimpleNamespace(frame_name=name, conf_threshold=None),
                PIL.Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)),
            )
            n += 1
        i += 1
    print(v.stem, "frames", i, "sampled", n, flush=True)
fn._dump_fh.close()
