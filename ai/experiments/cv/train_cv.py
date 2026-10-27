import argparse
import json
import os
import shutil
from pathlib import Path

import torch
from mmengine.config import Config
from mmengine.runner import Runner


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-json", required=True)
    ap.add_argument("--images", default="/ssafy/dataset/keypoints_260820")
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--wd", type=float, default=0.05)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--rot", type=float, default=30)
    ap.add_argument("--scale", type=float, nargs=2, default=[0.75, 1.25])
    ap.add_argument("--padding", type=float, default=1.15)
    ap.add_argument("--flip-aug", type=int, default=1)
    ap.add_argument("--train", choices=["full", "head", "stage4"], default="full")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--meta", default="/exp/train/creamoff46.py")
    ap.add_argument("--img-dir")
    a = ap.parse_args()

    root = Path("/data/cv_train")
    root.mkdir(parents=True, exist_ok=True)
    link = root / "images"
    if link.is_symlink() or link.exists():
        link.unlink()
    os.symlink(Path(a.img_dir) if a.img_dir else Path(a.images) / "images", link)
    shutil.copy(a.train_json, root / "train.json")

    cfg = Config.fromfile("/exp/train/ft_base.py")
    cfg.work_dir = a.work_dir
    cfg.randomness = dict(seed=a.seed)
    cfg.train_cfg = dict(by_epoch=True, max_epochs=a.epochs, val_interval=1000)
    ds = cfg.train_dataloader.dataset
    ds.data_root = str(root)
    ds.ann_file = "train.json"
    ds.metainfo = dict(from_file=a.meta)
    cfg.train_dataloader.batch_size = a.batch
    pipe = ds.pipeline
    for p in pipe:
        if p["type"] == "GetBBoxCenterScale":
            p["padding"] = a.padding
        if p["type"] == "RandomBBoxTransform":
            p["rotate_factor"] = a.rot
            p["scale_factor"] = list(a.scale)
    if not a.flip_aug:
        ds.pipeline = [p for p in pipe if p["type"] != "RandomFlip"]
    cfg.optim_wrapper.optimizer = dict(type="AdamW", lr=a.lr, weight_decay=a.wd)
    keys = {}
    if a.train in ("head", "stage4"):
        keys["backbone"] = dict(lr_mult=0, decay_mult=0)
    if a.train == "stage4":
        keys["backbone.stage4"] = dict(lr_mult=1, decay_mult=1)
    cfg.optim_wrapper.paramwise_cfg = dict(norm_decay_mult=0, bias_decay_mult=0, custom_keys=keys)
    cfg.param_scheduler = [
        dict(type="LinearLR", start_factor=1.0e-3, by_epoch=False, begin=0, end=min(200, a.epochs * 5)),
        dict(type="CosineAnnealingLR", eta_min=a.lr * 0.05, begin=0, end=a.epochs, T_max=a.epochs, by_epoch=True),
    ]
    cfg.default_hooks.checkpoint = dict(type="CheckpointHook", interval=a.epochs, max_keep_ckpts=1, save_optimizer=False)
    cfg.default_hooks.logger = dict(type="LoggerHook", interval=50)

    load = torch.load
    torch.load = lambda *x, **k: load(*x, **{**k, "weights_only": False})
    runner = Runner.from_cfg(cfg)
    runner.train()
    torch.load = load
    meta = torch.load(cfg.load_from, map_location="cpu", weights_only=False).get("meta") or {}
    sd = {k: v.detach().cpu() for k, v in runner.model.state_dict().items()}
    torch.save({"meta": {**meta, "cv_args": vars(a)}, "state_dict": sd}, Path(a.work_dir) / "final.pth")
    Path(a.work_dir, "args.json").write_text(json.dumps(vars(a), ensure_ascii=False), encoding="utf-8")
    for p in Path(a.work_dir).glob("epoch_*.pth"):
        p.unlink()


if __name__ == "__main__":
    main()
