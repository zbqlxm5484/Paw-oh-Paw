#!/bin/bash
# 시험 라벨 96장(5묶음) 최소 수정판(몸통 점 되돌림 + 작은 이동 되돌림). 3시드 (10-26)
set -e
cd /w
mkdir -p /w/pilotmin
for v in min05 min10; do
  f=/pilot/train46_$v.json
  for s in 0 1 2; do
    python train.py --config ft_creamoff.py --work-dir /w/pilotmin/${v}_s${s} --cfg-options \
      train_dataloader.dataset.ann_file=$f train_dataloader.dataset.data_root=/pilot/ \
      val_dataloader.dataset.ann_file=$f val_dataloader.dataset.data_root=/pilot/ \
      test_dataloader.dataset.ann_file=$f test_dataloader.dataset.data_root=/pilot/ \
      train_cfg.max_epochs=100 train_cfg.val_interval=100 randomness.seed=$s \
      "param_scheduler.1.end=100" default_hooks.checkpoint.save_best=None default_hooks.checkpoint.interval=100 \
      > /w/pilotmin/${v}_s${s}.log 2>&1
    python train.py --strip /w/pilotmin/${v}_s${s}/epoch_100.pth --out /w/pilotmin/${v}_s${s}/pose.pth
    rm -f /w/pilotmin/${v}_s${s}/epoch_*.pth
    echo "done $v s$s"
  done
done
