#!/bin/bash
# runs.sh + 에폭·추가 설정. 인자: 이름:ann파일:data_root:에폭[:추가설정|추가설정...]  SEEDS="0 1 2" (10-26)
set -e
cd /w
mkdir -p /w/runs
for spec in "$@"; do
  IFS=: read v f root ep extra <<< "$spec"
  IFS="|" read -ra X <<< "$extra"
  for s in ${SEEDS:-0 1 2}; do
    [ -f /w/runs/${v}_s${s}/pose.pth ] && continue
    python train.py --config ft_creamoff.py --work-dir /w/runs/${v}_s${s} --cfg-options \
      train_dataloader.dataset.ann_file=$f train_dataloader.dataset.data_root=$root \
      val_dataloader.dataset.ann_file=$f val_dataloader.dataset.data_root=$root \
      test_dataloader.dataset.ann_file=$f test_dataloader.dataset.data_root=$root \
      train_cfg.max_epochs=$ep train_cfg.val_interval=$ep randomness.seed=$s \
      "param_scheduler.1.end=$ep" default_hooks.checkpoint.save_best=None default_hooks.checkpoint.interval=$ep "${X[@]}" \
      > /w/runs/${v}_s${s}.log 2>&1
    python train.py --strip /w/runs/${v}_s${s}/epoch_${ep}.pth --out /w/runs/${v}_s${s}/pose.pth
    rm -f /w/runs/${v}_s${s}/epoch_*.pth
    echo "done $v s$s"
  done
done
