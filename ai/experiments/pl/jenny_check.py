import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from viterbi import PAIRS, correct

ROOT = Path("/ssafy/dataset/videos")
GT = json.loads(Path("/ssafy/dataset/keypoints_260820/annotations.json").read_text(encoding="utf-8"))
HERE = Path(__file__).parent


def video_list(out):
    keys = sorted({(im["session"], im["camera"]) for im in GT["images"]})
    lines = []
    for stamp, cam in keys:
        d = next(p for p in (ROOT / "daekyeung" / stamp[:6]).iterdir() if p.name.startswith(stamp))
        mp4 = [p for p in d.glob("*.mp4") if f"-{cam}" in p.name]
        p = mp4[0]
        lines.append(f"{p.relative_to(ROOT).as_posix()} {hashlib.sha256(p.read_bytes()).hexdigest()}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(len(lines), "videos")


def apply(track, preds_in, preds_out, pairs):
    tr = json.loads(Path(track).read_text(encoding="utf-8"))
    flips = {}
    for v in tr["videos"]:
        _, f = correct(v["frames"], pairs=pairs)
        name = v["video"]
        stamp = name[:13]
        cam = next(c for c in ("main", "sub1", "sub2", "sub3") if f"-{c}" in name)
        flips[(stamp, cam)] = f
    ims = {im["id"]: im for im in GT["images"]}
    anns = {a["id"]: a for a in GT["annotations"]}
    p = json.loads(Path(preds_in).read_text(encoding="utf-8"))
    n = 0
    for pr in p["predictions"]:
        im = ims[anns[pr["ann_id"]]["image_id"]]
        f = flips.get((im["session"], im["camera"]))
        if f is None:
            continue
        k = pr["keypoints"]
        for name in pairs:
            if f[name][im["frame_idx"]]:
                left, right = PAIRS[name]
                for a, b in zip(left, right):
                    k[3 * a:3 * a + 3], k[3 * b:3 * b + 3] = k[3 * b:3 * b + 3], k[3 * a:3 * a + 3]
                n += 1
    Path(preds_out).write_text(json.dumps(p), encoding="utf-8")
    print(preds_out, "swapped", n)


if __name__ == "__main__":
    if sys.argv[1] == "list":
        video_list(Path(sys.argv[2]))
    else:
        apply(sys.argv[2], sys.argv[3], sys.argv[4], tuple(sys.argv[5].split(",")))
