#!/bin/bash
# 96 보정 학습셋(wowwow_train46_offset) 을 curve.sh n1144 와 같은 설정·시드로 학습 (10-26).
set -e
cd /w
mkdir -p /w/offset_fold
for f in 0 1; do for s in 0 1 2; do
  python train.py --config ft_creamoff.py --work-dir /w/offset_fold/f${f}_s${s} --cfg-options \
    train_dataloader.dataset.ann_file=/splits/wowwow_train46_offset_fold${f}.json train_dataloader.dataset.data_root=/data/ \
    val_dataloader.dataset.ann_file=/splits/wowwow_val46.json val_dataloader.dataset.data_root=/data/ \
    test_dataloader.dataset.ann_file=/splits/wowwow_val46.json test_dataloader.dataset.data_root=/data/ \
    train_cfg.max_epochs=10 train_cfg.val_interval=10 randomness.seed=$s \
    "param_scheduler.1.end=10" default_hooks.checkpoint.save_best=None default_hooks.checkpoint.interval=10 \
    > /w/offset_fold/f${f}_s${s}.log 2>&1
  python train.py --strip /w/offset_fold/f${f}_s${s}/epoch_10.pth --out /w/offset_fold/f${f}_s${s}/pose.pth
  rm -f /w/offset_fold/f${f}_s${s}/epoch_*.pth
  echo "done f$f s$s"
done; done
