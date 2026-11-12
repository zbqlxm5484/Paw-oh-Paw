#!/bin/bash
# 100 시험 라벨 76장(크림오프 개 14마리)으로 fs-v4 이어 학습, 3시드 (10-26). 설정은 curve.sh n107 과 같음(100에폭).
set -e
cd /w
mkdir -p /w/pilot
for s in 0 1 2; do
  python train.py --config ft_creamoff.py --work-dir /w/pilot/s${s} --cfg-options \
    train_dataloader.dataset.ann_file=/pilot/train46.json train_dataloader.dataset.data_root=/pilot/ \
    val_dataloader.dataset.ann_file=/pilot/train46.json val_dataloader.dataset.data_root=/pilot/ \
    test_dataloader.dataset.ann_file=/pilot/train46.json test_dataloader.dataset.data_root=/pilot/ \
    train_cfg.max_epochs=100 train_cfg.val_interval=100 randomness.seed=$s \
    "param_scheduler.1.end=100" default_hooks.checkpoint.save_best=None default_hooks.checkpoint.interval=100 \
    > /w/pilot/s${s}.log 2>&1
  python train.py --strip /w/pilot/s${s}/epoch_100.pth --out /w/pilot/s${s}/pose.pth
  rm -f /w/pilot/s${s}/epoch_*.pth
  echo "done s$s"
done
