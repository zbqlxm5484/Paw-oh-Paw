"""영상 추론 결과(track)에서 정답 사진 프레임의 점을 꺼내 predict.py 형식으로 쓴다(10-22). 기업 도구는 안 건드린다.

    python track_to_preds.py --track results/gt_videos.stride3.track.json --gt <정답> --out stride3.preds.json
    python score.py --gt <정답> --pred stride3.preds.json

predict.py 는 정답 상자로 점을 찍어서 탐지 간격의 영향이 안 보인다. 여기서는 영상에서 탐지(또는 보간)한 상자로 찍은
점을 그대로 쓴다. 그 프레임에서 개를 못 찾았으면 (0, 0) 으로 채워 틀린 것으로 센다(score.py 는 빈 예측을 받지 않는다).
"""

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--gt", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    gt = json.loads(Path(a.gt).read_text(encoding="utf-8"))
    images = {im["id"]: im for im in gt["images"]}
    tracks = {}
    for v in json.loads(Path(a.track).read_text(encoding="utf-8"))["videos"]:
        stem = Path(v["video"]).stem
        tracks[(stem[:13], stem.rsplit("-", 1)[1])] = v
    rows, no_video, no_dog = [], 0, 0
    for an in gt["annotations"]:
        im = images[an["image_id"]]
        v = tracks.get((im["session"], im["camera"]))
        f = im["frame_idx"]
        fr = v["frames"][f] if v is not None and 0 <= f < len(v["frames"]) else None
        if v is None:
            no_video += 1
        elif fr is None:
            no_dog += 1
        kp = [c for p in fr["kp"] for c in p[:3]] if fr else [0.0] * 66
        rows.append({"ann_id": an["id"], "keypoints": kp})
    Path(a.out).write_text(
        json.dumps({"meta": {"track_to_preds": {"track": a.track}}, "predictions": rows}),
        encoding="utf-8",
    )
    print(f"-> {a.out}  정답 {len(rows)} · 영상 없음 {no_video} · 개 못 찾음 {no_dog}")


if __name__ == "__main__":
    main()
