import contextlib
import time

import numpy as np


def register(stacks, base, best_dog):
    class SkipDet2(base):
        def __init__(self, cfg, model_dir, device):
            super().__init__(cfg, model_dir, device)
            st = cfg["stack"]
            self.k = max(1, int(st.get("det_interval", 1)))
            self.fp16 = bool(st.get("fp16", False)) and self.cuda
            self.gap = str(st.get("empty_gap", "skip"))
            self.scales = [float(s) for s in st.get("tta_scales", [1.0])]
            r = float(st.get("tta_rot", 0))
            self.rots = [r, -r] if r else []
            self.post = st.get("post")
            self.tta = self.scales != [1.0] or bool(self.rots)
            self.info = dict(self.info, det_interval=self.k, box_fill="linear", empty_gap=self.gap, fp16=self.fp16,
                             tta_scales=self.scales, tta_rot=r, post=self.post)

        def _plain(self):
            return self.k == 1 and not self.fp16 and not self.tta and not self.post

        def _amp(self):
            if self.fp16:
                return self.torch.autocast(device_type="cuda", dtype=self.torch.float16)
            return contextlib.nullcontext()

        def _box(self, r):
            b = best_dog(r, self.conf)
            return None if b is None else np.asarray(b, dtype=np.float64)

        def _detect(self, frames, idxs):
            from mmengine.dataset import pseudo_collate
            from mmengine.registry import DefaultScope
            out = {}
            for i in range(0, len(idxs), self.batch):
                chunk = idxs[i:i + self.batch]
                with DefaultScope.overwrite_default_scope("mmdet"), self.torch.no_grad(), self._amp():
                    res = self.det.test_step(pseudo_collate([self.dpipe(dict(img=frames[j], img_id=n))
                                                             for n, j in enumerate(chunk)]))
                for j, r in zip(chunk, res):
                    out[j] = self._box(r)
            return out

        def _item(self, img, box):
            return self.ppipe(dict(img=img, bbox=np.array([box], float), bbox_score=np.ones(1),
                                   bbox_id=0, **self.pose.dataset_meta))

        def _pose(self, frames, boxes, chunk):
            import cv2
            from mmengine.dataset import pseudo_collate
            items = []
            for j in chunk:
                x1, y1, x2, y2 = boxes[j]
                cx, cy, w, h = (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1
                for s in self.scales:
                    items.append(self._item(frames[j], [cx - w * s / 2, cy - h * s / 2, cx + w * s / 2, cy + h * s / 2]))
                for d in self.rots:
                    m = cv2.getRotationMatrix2D((cx, cy), d, 1.0)
                    img = cv2.warpAffine(frames[j], m, (frames[j].shape[1], frames[j].shape[0]),
                                         borderMode=cv2.BORDER_REPLICATE)
                    items.append(self._item(img, [x1, y1, x2, y2]))
            with self.torch.no_grad(), self._amp():
                res = self.pose.test_step(pseudo_collate(items))
            k = len(self.scales) + len(self.rots)
            out = []
            for n, j in enumerate(chunk):
                x1, y1, x2, y2 = boxes[j]
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                kps = [np.asarray(res[n * k + m].pred_instances.keypoints[0], dtype=np.float64)
                       for m in range(len(self.scales))]
                for r, d in enumerate(self.rots):
                    p = np.asarray(res[n * k + len(self.scales) + r].pred_instances.keypoints[0], dtype=np.float64)
                    th = np.radians(d)
                    dx, dy = p[:, 0] - cx, p[:, 1] - cy
                    kps.append(np.stack([cx + np.cos(th) * dx - np.sin(th) * dy,
                                         cy + np.sin(th) * dx + np.cos(th) * dy], 1))
                sc = np.asarray(res[n * k].pred_instances.keypoint_scores[0], dtype=np.float64)
                out.append(np.column_stack([np.mean(kps, axis=0), sc]))
            return out

        def _fix(self, out):
            import lr_fix
            legs = lr_fix.LEG_SETS["hind"]["hind"]
            seq = [(f, out[f][:22].tolist()) for f in sorted(out)]
            states = lr_fix.viterbi(seq, legs, 0.02, 3)
            for f, kp in seq:
                if states.get(f):
                    for a, b in zip(*legs):
                        kp[a], kp[b] = kp[b], kp[a]
                    out[f][:22] = np.asarray(kp)

        def warm(self, frames):
            if self._plain():
                return super().warm(frames)
            n = min(len(frames), self.batch)
            boxes = self._detect(frames, list(range(n)))
            for k in range(1, self.batch + 1):
                self._detect(frames, [j % len(frames) for j in range(k)])
            b = next((x for x in boxes.values() if x is not None), np.array([100.0, 100.0, 500.0, 500.0]))
            fake = {j: b for j in range(len(frames))}
            for k in range(1, self.batch + 1):
                self._pose(frames, fake, [j % len(frames) for j in range(k)])
            self(frames)
            if self.cuda:
                self.torch.cuda.synchronize()

        def __call__(self, frames, keep=None):
            if self._plain():
                self.last_detect_calls = len(frames)
                return super().__call__(frames, keep)
            torch, clk = self.torch, time.perf_counter
            n = len(frames)
            t0 = clk()
            keys = sorted(set(range(0, n, self.k)) | {n - 1})
            boxes = self._detect(frames, keys)
            fill = []
            probe = {}
            for a, b in zip(keys, keys[1:]):
                if b - a <= 1:
                    continue
                if boxes[a] is not None and boxes[b] is not None:
                    for j in range(a + 1, b):
                        t = (j - a) / (b - a)
                        boxes[j] = (1 - t) * boxes[a] + t * boxes[b]
                elif boxes[a] is None and boxes[b] is None:
                    if self.gap == "probe":
                        probe[(a, b)] = (a + b) // 2
                    else:
                        for j in range(a + 1, b):
                            boxes[j] = None
                else:
                    fill.extend(range(a + 1, b))
            if probe:
                found = self._detect(frames, sorted(set(probe.values())))
                boxes.update(found)
                for (a, b), m in probe.items():
                    if found[m] is not None:
                        fill.extend(j for j in range(a + 1, b) if j != m)
            if fill:
                boxes.update(self._detect(frames, fill))
            if self.cuda:
                torch.cuda.synchronize()
            t1 = clk()
            have = [j for j in range(n) if boxes.get(j) is not None]
            self.found_idx = have
            out = {}
            for i in range(0, len(have), self.batch):
                chunk = have[i:i + self.batch]
                out.update(zip(chunk, self._pose(frames, boxes, chunk)))
            if self.cuda:
                torch.cuda.synchronize()
            if self.post == "hind":
                self._fix(out)
            t2 = clk()
            if keep is not None:
                for j in range(n):
                    o = out.get(j)
                    keep.append((None, None) if o is None else (np.asarray(boxes[j]).tolist(), o.tolist()))
            self.last_detect_calls = len(keys) + len(fill) + len(set(probe.values()))
            return t1 - t0, t2 - t1, len(have)

    stacks["mmdet-mmpose-skip2"] = SkipDet2
