"""탐지 간격·fp16(det_stride.Stride)이나 배율·회전·후처리(tta_speed.TTA)를 붙인 실행부로
기업 도구의 KPI-15(speed.run_tput)와 영상 KPI 용 추적(video_kpi.track)을 돌린다(10-23). 기업 도구는 안 건드린다.
실행부 설정은 환경 변수 PAW_VARIANT(JSON)로 넘긴다. KPI-15 자식 프로세스도 이 파일로 띄워 같은 설정을 쓴다.
    PAW_VARIANT='{"kind":"stride","stride":1,"half":true}' python kpi_variant.py tput --model models/fs-v4.toml --video-root ../dataset/videos --out x.json
    PAW_VARIANT='{"kind":"tta","scales":[1],"rots":[8,-8],"post":"hind"}' python kpi_variant.py track --model ... --videos video_kpi_videos.txt --video-root ... --out x.track.json
"""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import speed

V = json.loads(os.environ.get("PAW_VARIANT", '{"kind":"stride","stride":1}'))
if V["kind"] == "stride":
    from det_stride import Stride as Be

    Be.stride, Be.half = V.get("stride", 1), V.get("half", False)
else:
    from tta_speed import TTA as Be

    Be.scales, Be.rots, Be.post = V.get("scales", [1.0]), V.get("rots", []), V.get("post")
speed.STACKS["mmdet-mmpose"] = Be
speed.__file__ = __file__  # speed.Child 가 이 파일을 자식으로 띄우게


def main():
    if sys.argv[1] == "--child":
        return speed.child(json.loads(sys.argv[2]))
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["tput", "track"])
    ap.add_argument("--model", required=True)
    ap.add_argument("--video-root", required=True)
    ap.add_argument("--videos")
    ap.add_argument("--out", required=True)
    ap.add_argument("--concurrency", default="1,2,4,6")
    ap.add_argument("--reps", type=int, default=10)
    a = ap.parse_args()
    if a.cmd == "track":
        import video_kpi

        return video_kpi.track(
            SimpleNamespace(
                model=a.model,
                videos=a.videos or "video_kpi_videos.txt",
                video_root=a.video_root,
                out=a.out,
                device="cuda:0",
            )
        )
    videos = speed.load_videos(a.videos or "speed_videos.txt", a.video_root)
    log = open(Path(a.out).with_suffix(".log"), "w", encoding="utf-8")
    by_n = []
    for n in [int(x) for x in a.concurrency.split(",")]:
        try:
            r = speed.run_tput(Path(a.model), videos, "cuda:0", n, a.reps, log)
        except (SystemExit, Exception) as e:  # GPU 메모리 부족 등으로 자식이 죽으면 거기까지
            print(f"N={n} 실패: {e}", flush=True)
            break
        print(
            f"N={n} 건당 {r['per_video_s']:.3f}초 · 시간당 {r['videos_per_hour']:.0f}건", flush=True
        )
        by_n.append(r)
    out = {"variant": V, "model": a.model, "KPI-15": speed.pick_kpi15(by_n)}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("->", a.out, round(out["KPI-15"]["videos_per_hour"]), "N", out["KPI-15"]["n"])


if __name__ == "__main__":
    main()
