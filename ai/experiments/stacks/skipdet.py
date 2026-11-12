import time

import numpy as np


def register(stacks, base, best_dog):
    class SkipDet(base):
        def __init__(self, cfg, model_dir, device):
            super().__init__(cfg, model_dir, device)
            self.k = max(1, int(cfg["stack"].get("det_interval", 1)))
            self.info = dict(self.info, det_interval=self.k, box_fill="linear")

        def _detect(self, frames, idxs):
            from mmengine.dataset import pseudo_collate
            from mmengine.registry import DefaultScope
            out = {}
            for i in range(0, len(idxs), self.batch):
                chunk = idxs[i:i + self.batch]
                with DefaultScope.overwrite_default_scope("mmdet"), self.torch.no_grad():
                    res = self.det.test_step(pseudo_collate([self.dpipe(dict(img=frames[j], img_id=n))
                                                             for n, j in enumerate(chunk)]))
                for j, r in zip(chunk, res):
                    out[j] = best_dog(r, self.conf)
            return out

        def warm(self, frames):
            from mmengine.dataset import pseudo_collate
            n = min(len(frames), self.batch)
            boxes = self._detect(frames, list(range(n)))
            for k in range(1, self.batch + 1):
                self._detect(frames, [j % len(frames) for j in range(k)])
            b = next((x for x in boxes.values() if x is not None), np.array([100.0, 100.0, 500.0, 500.0]))
            for k in range(1, self.batch + 1):
                with self.torch.no_grad():
                    self.pose.test_step(pseudo_collate([
                        self.ppipe(dict(img=frames[j % len(frames)], bbox=np.array([b], float), bbox_score=np.ones(1),
                                        bbox_id=0, **self.pose.dataset_meta)) for j in range(k)]))
            self(frames)
            if self.cuda:
                self.torch.cuda.synchronize()

        def __call__(self, frames, keep=None):
            from mmengine.dataset import pseudo_collate
            torch, clk = self.torch, time.perf_counter
            n = len(frames)
            t0 = clk()
            keys = sorted(set(range(0, n, self.k)) | {n - 1})
            boxes = self._detect(frames, keys)
            fill = []
            for a, b in zip(keys, keys[1:]):
                if b - a <= 1:
                    continue
                if boxes[a] is not None and boxes[b] is not None:
                    for j in range(a + 1, b):
                        t = (j - a) / (b - a)
                        boxes[j] = (1 - t) * boxes[a] + t * boxes[b]
                else:
                    fill.extend(range(a + 1, b))
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
                with torch.no_grad():
                    pres = self.pose.test_step(pseudo_collate([
                        self.ppipe(dict(img=frames[j], bbox=np.array([boxes[j]], float), bbox_score=np.ones(1),
                                        bbox_id=0, **self.pose.dataset_meta)) for j in chunk]))
                out.update(zip(chunk, pres))
            if self.cuda:
                torch.cuda.synchronize()
            t2 = clk()
            if keep is not None:
                for j in range(n):
                    o = out.get(j)
                    keep.append((None, None) if o is None else (
                        np.asarray(boxes[j]).tolist(),
                        np.column_stack([o.pred_instances.keypoints[0], o.pred_instances.keypoint_scores[0]]).tolist()))
            self.last_detect_calls = len(keys) + len(fill)
            return t1 - t0, t2 - t1, len(have)

    stacks["mmdet-mmpose-skip"] = SkipDet
