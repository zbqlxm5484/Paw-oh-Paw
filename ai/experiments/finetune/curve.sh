#!/bin/bash
# 학습 곡선: 장수 × 시드. 장수가 적어도 학습 횟수(iter)가 비슷하게 에폭을 늘린다
set -e
cd /w
run(){ n=$1; s=$2; ann=$3; ep=$4
  python train.py --config ft_creamoff.py --work-dir /w/curve/n${n}_s${s} --cfg-options \
    train_dataloader.dataset.ann_file=$ann train_dataloader.dataset.data_root=/data/ \
    val_dataloader.dataset.ann_file=/splits/wowwow_val46.json val_dataloader.dataset.data_root=/data/ \
    test_dataloader.dataset.ann_file=/splits/wowwow_val46.json test_dataloader.dataset.data_root=/data/ \
    train_cfg.max_epochs=$ep train_cfg.val_interval=$ep randomness.seed=$s \
    "param_scheduler.1.end=$ep" default_hooks.checkpoint.save_best=None default_hooks.checkpoint.interval=$ep \
    > /w/curve/n${n}_s${s}.log 2>&1
  python train.py --strip /w/curve/n${n}_s${s}/epoch_${ep}.pth --out /w/curve/n${n}_s${s}/pose.pth
  rm -f /w/curve/n${n}_s${s}/epoch_*.pth
  echo "done n$n s$s"
}
mkdir -p /w/curve
for s in 0 1 2; do
  run 107 $s /splits/curve_n107_s${s}.json 100
  run 214 $s /splits/curve_n214_s${s}.json 50
  run 500 $s /splits/curve_n500_s${s}.json 22
  run 1144 $s /splits/wowwow_train46.json 10
done
