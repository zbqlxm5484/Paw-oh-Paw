"""selftest 다름 진단: 점별 차이·확신도, 같은 GPU 2회 재현성."""

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import PIL.Image

sys.path.insert(0, "/work/tools")
import cvat_aa

HERE = Path("/work/tools/selftest")
ref = {
    r["frame_name"]: r for r in map(json.loads, open(HERE / "reference.jsonl", encoding="utf-8"))
}
names = json.load(open("/work/tools/cvat_dog_skeleton_review.json", encoding="utf-8"))
names = (
    [s["name"] for s in names[0]["sublabels"]]
    if isinstance(names, list) and names and "sublabels" in names[0]
    else [str(i) for i in range(22)]
)
runs = []
for k in range(2):
    out = Path(tempfile.mkdtemp()) / "o.jsonl"
    fn = cvat_aa.create(dump=str(out))
    for n in ref:
        fn.detect(SimpleNamespace(frame_name=n, conf_threshold=None), PIL.Image.open(HERE / n))
    fn._dump_fh.close()
    runs.append({g["frame_name"]: g for g in map(json.loads, open(out, encoding="utf-8"))})
for n, r in ref.items():
    if r["keypoints"] is None:
        continue
    a = np.array(r["keypoints"])[:22]
    b = np.array(runs[0][n]["keypoints"])[:22]
    c = np.array(runs[1][n]["keypoints"])[:22]
    d = np.abs(a[:, :2] - b[:, :2]).max(1)
    rr = np.abs(b[:, :2] - c[:, :2]).max(1).max()
    print(f"{n}  2회 재현 차 {rr:.2f}px")
    for i in np.where(d > 0.1)[0]:
        sc = f" 확신도 ref {a[i,2]:.2f} / 여기 {b[i,2]:.2f}" if a.shape[1] > 2 else ""
        print(f"    {i:2d} {names[i] if i < len(names) else i:34s} {d[i]:6.2f}px{sc}")
