#!/bin/bash
# 10-26 교차 채점: (1) 기업 정답 반쪽 학습(gtcv_f*) → 다른 반쪽 채점, fs-v4-flip 도 같은 반쪽 (2) 묶음 하나 뺀 학습(lobo_b*) → 뺀 묶음의 팀 라벨로 채점
set -e
cd "$(dirname "$0")"
PY=.venv/Scripts/python; O=results/cv1026; mkdir -p $O
sc() { $PY predict.py --model $1 --gt $2 --images $3 --out $O/$4.preds.json --device cuda:0 > /dev/null; $PY score.py --gt $2 --pred $O/$4.preds.json --out $O/$4.json > /dev/null; echo "scored $4"; }
mk() { mkdir -p models/curve/c_r_$1 && cp ${CVAT_LABELING_DIR:-/c/cvat-labeling}/train_ww/runs/$1/pose.pth models/curve/c_r_$1/pose.pth
       sed -e "s/c_n1144_s0/c_r_$1/g" -e "1s/.*/# $1 + flip test. 10-26/" models/curve_c_n1144_s0.toml > models/curve_c_r_$1.toml; }
GTI=../dataset/keypoints_260820
for f in 0 1; do t=$((1 - f))
  sc models/fs-v4-flip.toml ../../splits/gtcv/gt_fold$t.json $GTI flip_gthalf$t
  for s in 0 1 2; do mk gtcv_f${f}_s$s; sc models/curve_c_r_gtcv_f${f}_s$s.toml ../../splits/gtcv/gt_fold$t.json $GTI gtcv_f${f}_s$s; done
done
for b in 1 2 3 4 5; do
  sc models/fs-v4-flip.toml ../../splits/lobo/test_b$b.json ../../splits/pilot100 flip_b$b
  mk lobo_b${b}_s0; sc models/curve_c_r_lobo_b${b}_s0.toml ../../splits/lobo/test_b$b.json ../../splits/pilot100 lobo_b$b
done
