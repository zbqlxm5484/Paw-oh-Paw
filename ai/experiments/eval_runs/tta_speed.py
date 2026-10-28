"""여러 배율 추론(실험 8)의 처리 시간을 기업 speed.py 실행부 그대로 잰다(10-22). 기업 도구는 안 건드린다.

    python tta_speed.py --model models/fs-v4-flip.toml --video-root ../dataset/videos --scales 1 / 0.9,1,1.1 / 0.85,0.9,1,1.1,1.15

개를 찾은 프레임마다 상자를 배율 수만큼 만들어 한 묶음으로 관절점 모델에 넣는다. 탐지는 그대로다.
10-23: 묶음 끝에 r8 을 붙이면 배율 1 로 ±8° 돌린 프레임도 같이 넣는다(rotate_tta.py 와 같은 회전·되돌리기).
    --post hind(뒷다리 좌우 보정, lr_fix.py) / ts(앞뒤 1프레임 평균, temporal_smooth.py) 는 영상 하나 끝난 뒤 시간을 따로 잰다.
    python tta_speed.py --model models/fs-v4-flip.toml --video-root ../dataset/videos --scales 0.85,0.9,1,1.1,1.15,r8 --post hind
"""

import argparse
import json
import statistics
import sys
import time
import tomllib
from pathlib import Path

import cv2
import lr_fix
import numpy as np
import speed
import temporal_smooth

sys.stdout.reconfigure(encoding="utf-8")


class TTA(speed.MMDetMMPose):
    scales = [1.0]
    rots = []  # 배율 1 로 더 넣을 회전 각도
    post = None  # None | "hind" | "ts"

    def __call__(self, frames, keep=None):
        from mmengine.dataset import pseudo_collate
        from mmengine.registry import DefaultScope

        torch, clk = self.torch, time.perf_counter
        t_det = t_pose = 0.0
        found, self.found_idx = 0, []
        seq = []  # (프레임 번호, 22점) 후처리용
        fbox = {}  # 프레임 번호 -> 상자(keep 용)
        for i in range(0, len(frames), self.batch):
            chunk = frames[i : i + self.batch]
            t0 = clk()
            with DefaultScope.overwrite_default_scope("mmdet"), torch.no_grad():
                res = self.det.test_step(
                    pseudo_collate([self.dpipe(dict(img=f, img_id=j)) for j, f in enumerate(chunk)])
                )
            boxes = [speed.best_dog(r, self.conf) for r in res]
            if self.cuda:
                torch.cuda.synchronize()
            t1 = clk()
            have = [j for j, b in enumerate(boxes) if b is not None]
            fbox.update({i + j: [float(v) for v in boxes[j]] for j in have})
            self.found_idx += [i + j for j in have]
            if have:
                items = []
                for j in have:
                    x1, y1, x2, y2 = boxes[j]
                    cx, cy, w, h = (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1
                    for s in self.scales:
                        b = np.array(
                            [[cx - w * s / 2, cy - h * s / 2, cx + w * s / 2, cy + h * s / 2]],
                            float,
                        )
                        items.append(
                            self.ppipe(
                                dict(
                                    img=chunk[j],
                                    bbox=b,
                                    bbox_score=np.ones(1),
                                    bbox_id=0,
                                    **self.pose.dataset_meta,
                                )
                            )
                        )
                    b = np.array([[x1, y1, x2, y2]], float)
                    for d in self.rots:  # 상자 가운데로 프레임을 돌려 같은 상자로 추론
                        m = cv2.getRotationMatrix2D((cx, cy), d, 1.0)
                        img = cv2.warpAffine(
                            chunk[j],
                            m,
                            (chunk[j].shape[1], chunk[j].shape[0]),
                            borderMode=cv2.BORDER_REPLICATE,
                        )
                        items.append(
                            self.ppipe(
                                dict(
                                    img=img,
                                    bbox=b,
                                    bbox_score=np.ones(1),
                                    bbox_id=0,
                                    **self.pose.dataset_meta,
                                )
                            )
                        )
                with torch.no_grad():
                    pres = self.pose.test_step(pseudo_collate(items))
                k = len(self.scales) + len(self.rots)
                for n, j in enumerate(have):  # 회전분은 되돌리고 전부 평균(시간에 포함)
                    x1, y1, x2, y2 = boxes[j]
                    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                    kps = [
                        pres[n * k + m].pred_instances.keypoints[0] for m in range(len(self.scales))
                    ]
                    for r, d in enumerate(self.rots):
                        p = pres[n * k + len(self.scales) + r].pred_instances.keypoints[0]
                        th = np.radians(d)
                        dx, dy = p[:, 0] - cx, p[:, 1] - cy
                        kps.append(
                            np.stack(
                                [
                                    cx + np.cos(th) * dx - np.sin(th) * dy,
                                    cy + np.sin(th) * dx + np.cos(th) * dy,
                                ],
                                1,
                            )
                        )
                    kp = np.mean(kps, axis=0)
                    sc = pres[n * k].pred_instances.keypoint_scores[0]
                    seq.append(
                        (
                            i + j,
                            [[float(kp[q, 0]), float(kp[q, 1]), float(sc[q])] for q in range(22)],
                        )
                    )
            if self.cuda:
                torch.cuda.synchronize()
            t_det, t_pose, found = t_det + t1 - t0, t_pose + clk() - t1, found + len(have)
        t0 = clk()
        if self.post == "hind":  # lr_fix --legs hind --penalty 0.02 --gap 3 (E-036 과 같은 값)
            states = lr_fix.viterbi(seq, lr_fix.LEG_SETS["hind"]["hind"], 0.02, 3)
            for f, kp in seq:
                if states.get(f):
                    for a, b in zip(*lr_fix.LEG_SETS["hind"]["hind"]):
                        kp[a], kp[b] = kp[b], kp[a]
        elif self.post == "ts":  # temporal_smooth --k 1 --w 0.25 (E-038 과 같은 값)
            by, done = dict(seq), {}
            for f, center in seq:
                acc = [[c[0], c[1], 1.0] for c in center]
                for g in (f - 1, f + 1):
                    if g in by:
                        nb = temporal_smooth.align(center, by[g])
                        for q in range(22):
                            if nb[q][2] >= temporal_smooth.CONF:
                                acc[q][0] += 0.25 * nb[q][0]
                                acc[q][1] += 0.25 * nb[q][1]
                                acc[q][2] += 0.25
                sm = [(a[0] / a[2], a[1] / a[2]) for a in acc]
                if keep is not None:  # 시간 재기용 실행과 결과를 같게 하려고 평균값을 남긴다
                    done[f] = [[x, y, c[2]] for (x, y), c in zip(sm, center)]
            if keep is not None:
                seq = [(f, done[f]) for f, _ in seq]
        t_pose += clk() - t0
        if keep is not None:  # video_kpi.track 형식(10-23 추가): 프레임마다 (상자, 22점)
            kp = dict(seq)
            keep += [(fbox[j], kp[j]) if j in kp else (None, None) for j in range(len(frames))]
        return t_det, t_pose, found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--video-root", required=True)
    ap.add_argument("--videos", default="speed_videos.txt")
    ap.add_argument("--scales", nargs="+", required=True, help="배율 묶음마다 쉼표로: 1 0.9,1,1.1")
    ap.add_argument("--post", choices=["hind", "ts"])
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--out")
    a = ap.parse_args()
    cfg = tomllib.loads(Path(a.model).read_text(encoding="utf-8"))
    m = TTA(cfg, Path(a.model).parent, "cuda:0")
    m.post = a.post
    vids = [speed.read_frames(p) for p in speed.load_videos(a.videos, a.video_root)]
    m.warm(vids[0])
    out = {}
    for spec in a.scales:
        parts = spec.split(",")
        m.scales = [float(s) for s in parts if not s.startswith("r")]
        m.rots = [sg * float(s[1:]) for s in parts if s.startswith("r") for sg in (1, -1)]
        n = len(m.scales) + len(m.rots)
        for k in range(1, m.batch * n + 1, m.batch):  # 큰 묶음 예열
            m(vids[0][: max(1, k // n)])
        per = []
        for _ in range(a.rounds):
            tot = [m(f) for f in vids]
            per.append(
                (
                    statistics.mean(t[0] + t[1] for t in tot),
                    statistics.mean(t[0] for t in tot),
                    statistics.mean(t[1] for t in tot),
                )
            )
        med = sorted(per)[len(per) // 2]
        spec = spec + (f"+{a.post}" if a.post else "")
        out[spec] = {"total_s": med[0], "det_s": med[1], "pose_s": med[2]}
        print(f"배율 {spec:22s} 영상당 {med[0]:.3f}초 (탐지 {med[1]:.2f} / 관절점 {med[2]:.2f})")
    if a.out:
        Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
