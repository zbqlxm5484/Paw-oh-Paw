import argparse
import json
import math
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).parent))
from viterbi import body_len, correct

N = 22


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--video-root", required=True)
    ap.add_argument("--list", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--step", type=int, default=6)
    ap.add_argument("--per-video", type=int, default=8)
    ap.add_argument("--min-mean", type=float, default=0.5)
    ap.add_argument("--min-score", type=float, default=0.3)
    ap.add_argument("--max-jump", type=float, default=0.15)
    ap.add_argument("--no-viterbi", action="store_true")
    a = ap.parse_args()

    out = Path(a.out)
    (out / "images").mkdir(parents=True, exist_ok=True)
    rel = {Path(l.rsplit(" ", 1)[0]).name: l.rsplit(" ", 1)[0] for l in Path(a.list).read_text(encoding="utf-8").splitlines()
           if l.strip() and not l.startswith("#")}
    tr = json.loads(Path(a.track).read_text(encoding="utf-8"))
    coco = {"images": [], "annotations": [], "categories": [json.loads(Path("/ssafy/dataset/keypoints_260820/annotations.json").read_text(encoding="utf-8"))["categories"][0]]}
    stats = {"videos": 0, "frames": 0, "flipped_front": 0, "flipped_hind": 0, "points": 0}
    for v in tr["videos"]:
        frames = v["frames"]
        if a.no_viterbi:
            kps = [None if f is None else f["kp"] for f in frames]
            flips = {"front": [0] * len(frames), "hind": [0] * len(frames)}
        else:
            kps, flips = correct(frames)
        stats["flipped_front"] += sum(flips["front"])
        stats["flipped_hind"] += sum(flips["hind"])
        W, H = v["width"], v["height"]
        picks = []
        for i in range(1, len(frames) - 1, a.step):
            f, k, kp_prev, kp_next = frames[i], kps[i], kps[i - 1], kps[i + 1]
            if f is None or kp_prev is None or kp_next is None:
                continue
            x1, y1, x2, y2 = f["box"]
            if x1 < 0.02 * W or x2 > 0.98 * W or y1 < 0.02 * H or y2 > 0.98 * H:
                continue
            if sum(p[2] for p in k) / N < a.min_mean:
                continue
            L = body_len(k)
            vis = []
            for j in range(N):
                mx, my = (kp_prev[j][0] + kp_next[j][0]) / 2, (kp_prev[j][1] + kp_next[j][1]) / 2
                jump = math.hypot(k[j][0] - mx, k[j][1] - my) / L
                vis.append(2 if k[j][2] >= a.min_score and jump <= a.max_jump else 0)
            if sum(v_ > 0 for v_ in vis) < 12 or not (vis[2] and vis[13]):
                continue
            picks.append((i, k, vis))
        picks = picks[:a.per_video]
        if not picks:
            continue
        cap = cv2.VideoCapture(str(Path(a.video_root) / rel[v["video"]]))
        stem = Path(v["video"]).stem
        for i, k, vis in picks:
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ok, img = cap.read()
            if not ok:
                continue
            name = f"{stem}_f{i:06d}.jpg"
            cv2.imwrite(str(out / "images" / name), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            iid = len(coco["images"]) + 1
            xs, ys = [p[0] for p in k], [p[1] for p in k]
            coco["images"].append({"id": iid, "file_name": f"images/{name}", "width": int(W), "height": int(H),
                                   "session": stem.split("-main")[0][:13], "frame_idx": i})
            flat = []
            for j in range(N):
                flat += [k[j][0], k[j][1], vis[j]] if vis[j] else [0, 0, 0]
            coco["annotations"].append({"id": iid, "image_id": iid, "category_id": 1, "iscrowd": 0, "keypoints": flat,
                                        "num_keypoints": sum(1 for x in vis if x), "bbox": [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)],
                                        "area": (max(xs) - min(xs)) * (max(ys) - min(ys)), "attributes": {"touched": [1] * N, "source": "pseudo"}})
            stats["frames"] += 1
            stats["points"] += sum(1 for x in vis if x)
        cap.release()
        stats["videos"] += 1
    (out / "pseudo.json").write_text(json.dumps(coco, ensure_ascii=False), encoding="utf-8")
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(stats)


if __name__ == "__main__":
    main()
