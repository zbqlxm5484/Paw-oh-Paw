"""같은 모델로 빠르게: N 프레임마다 한 번만 개를 찾고, 사이 프레임은 앞뒤 상자를 이어(선형 보간) 쓴다(10-22).
기업 speed.py 실행부(MMDetMMPose)를 그대로 물려받고 탐지 횟수만 줄인다. 기업 도구는 안 건드린다.

    python det_stride.py track --model models/fs-v4.toml --stride 2 --videos video_kpi_videos.txt \
        --video-root ../dataset/videos --out results/stride2.track.json      # video_kpi score 에 그대로
    python det_stride.py speed --model models/fs-v4.toml --strides 1 2 3 --video-root ../dataset/videos

보간: 사이 프레임은 양쪽 탐지 상자가 다 있으면 선형 보간, 한쪽만 있으면 가까운 쪽 상자를 그대로 쓴다.
"""

import argparse
import statistics
import sys
import time
from types import SimpleNamespace

import numpy as np
import speed

sys.stdout.reconfigure(encoding="utf-8")


class Stride(speed.MMDetMMPose):
    stride = 1
    half = False  # True 면 탐지·관절점 계산을 fp16(autocast)으로

    def __call__(self, frames, keep=None):
        from mmengine.dataset import pseudo_collate
        from mmengine.registry import DefaultScope

        torch, clk = self.torch, time.perf_counter
        n, k = len(frames), max(1, self.stride)
        t0 = clk()
        det_idx = list(range(0, n, k))
        if det_idx[-1] != n - 1:
            det_idx.append(n - 1)  # 끝 프레임은 늘 탐지(보간 범위를 닫는다)
        found_box = {}
        for i in range(0, len(det_idx), self.batch):
            ids = det_idx[i : i + self.batch]
            with (
                DefaultScope.overwrite_default_scope("mmdet"),
                torch.no_grad(),
                torch.autocast("cuda", dtype=torch.float16, enabled=self.half),
            ):
                res = self.det.test_step(
                    pseudo_collate([self.dpipe(dict(img=frames[j], img_id=j)) for j in ids])
                )
            for j, r in zip(ids, res):
                b = speed.best_dog(r, self.conf)
                if b is not None:
                    found_box[j] = np.asarray(b, float)
        if self.cuda:
            torch.cuda.synchronize()
        t1 = clk()
        boxes = [None] * n
        dl = sorted(found_box)
        for j in range(n):
            if j in found_box:
                boxes[j] = found_box[j]
                continue
            prev = max((d for d in dl if d < j), default=None)
            nxt = min((d for d in dl if d > j), default=None)
            near = lambda d: d is not None and abs(d - j) < k
            if near(prev) and near(nxt):
                w = (j - prev) / (nxt - prev)
                boxes[j] = (1 - w) * found_box[prev] + w * found_box[nxt]
            elif near(prev) or near(nxt):
                boxes[j] = found_box[prev if near(prev) else nxt]
        have = [j for j in range(n) if boxes[j] is not None]
        self.found_idx = have
        pres = []
        for i in range(0, len(have), self.batch):
            ids = have[i : i + self.batch]
            with torch.no_grad(), torch.autocast("cuda", dtype=torch.float16, enabled=self.half):
                pres += self.pose.test_step(
                    pseudo_collate(
                        [
                            self.ppipe(
                                dict(
                                    img=frames[j],
                                    bbox=np.array([boxes[j]], float),
                                    bbox_score=np.ones(1),
                                    bbox_id=0,
                                    **self.pose.dataset_meta,
                                )
                            )
                            for j in ids
                        ]
                    )
                )
        if self.cuda:
            torch.cuda.synchronize()
        t2 = clk()
        if keep is not None:
            out = dict(zip(have, pres))
            for j in range(n):
                o = out.get(j)
                keep.append(
                    (None, None)
                    if o is None
                    else (
                        boxes[j].tolist(),
                        np.column_stack(
                            [o.pred_instances.keypoints[0], o.pred_instances.keypoint_scores[0]]
                        ).tolist(),
                    )
                )
        return t1 - t0, t2 - t1, len(have)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("track")
    t.add_argument("--model", required=True)
    t.add_argument("--stride", type=int, required=True)
    t.add_argument("--videos", required=True)
    t.add_argument("--video-root", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--half", action="store_true")
    s = sub.add_parser("speed")
    s.add_argument("--model", required=True)
    s.add_argument("--strides", type=int, nargs="+", required=True)
    s.add_argument("--video-root", required=True)
    s.add_argument("--videos", default="speed_videos.txt")
    s.add_argument("--rounds", type=int, default=3)
    s.add_argument("--half", action="store_true")
    a = ap.parse_args()

    if a.cmd == "track":
        Stride.stride = a.stride
        Stride.half = a.half
        speed.STACKS["mmdet-mmpose"] = Stride  # video_kpi.track 이 이 실행부를 쓰게
        import video_kpi

        video_kpi.track(
            SimpleNamespace(
                model=a.model, videos=a.videos, video_root=a.video_root, out=a.out, device="cuda:0"
            )
        )
        return

    import tomllib
    from pathlib import Path

    cfg = tomllib.loads(Path(a.model).read_text(encoding="utf-8"))
    m = Stride(cfg, Path(a.model).parent, "cuda:0")
    m.half = a.half
    vids = [speed.read_frames(p) for p in speed.load_videos(a.videos, a.video_root)]
    m.warm(vids[0])
    for st in a.strides:
        m.stride = st
        for f in vids:  # 이 간격의 묶음 크기들 예열
            m(f)
        per = []
        for _ in range(a.rounds):
            tot = [m(f) for f in vids]
            per.append(
                (
                    statistics.mean(x[0] + x[1] for x in tot),
                    statistics.mean(x[0] for x in tot),
                    statistics.mean(x[1] for x in tot),
                )
            )
        med = sorted(per)[len(per) // 2]
        print(
            f"{'fp16 ' if a.half else ''}탐지 간격 {st}: 영상당 {med[0]:.3f}초 (탐지 {med[1]:.2f} / 관절점 {med[2]:.2f})",
            flush=True,
        )


if __name__ == "__main__":
    main()
