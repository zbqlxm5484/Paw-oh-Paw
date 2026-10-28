#!/bin/bash
# 여러 학습셋을 같은 설정(BN 고정, 100에폭, 3시드)으로 학습. 인자: 이름:ann파일:data_root ... (10-26)
set -e
cd /w
mkdir -p /w/runs
for spec in "$@"; do
  IFS=: read v f root <<< "$spec"
  for s in 0 1 2; do
    [ -f /w/runs/${v}_s${s}/pose.pth ] && continue
    python train.py --config ft_creamoff.py --work-dir /w/runs/${v}_s${s} --cfg-options \
      train_dataloader.dataset.ann_file=$f train_dataloader.dataset.data_root=$root \
      val_dataloader.dataset.ann_file=$f val_dataloader.dataset.data_root=$root \
      test_dataloader.dataset.ann_file=$f test_dataloader.dataset.data_root=$root \
      train_cfg.max_epochs=100 train_cfg.val_interval=100 randomness.seed=$s \
      "param_scheduler.1.end=100" default_hooks.checkpoint.save_best=None default_hooks.checkpoint.interval=100 \
      > /w/runs/${v}_s${s}.log 2>&1
    python train.py --strip /w/runs/${v}_s${s}/epoch_100.pth --out /w/runs/${v}_s${s}/pose.pth
    rm -f /w/runs/${v}_s${s}/epoch_*.pth
    echo "done $v s$s"
  done
done
