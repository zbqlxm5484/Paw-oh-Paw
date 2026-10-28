#!/bin/bash
# /w/runs/<이름>_s<시드> 모델을 기업 정답에 flip 으로 채점. 인자: 이름들 (10-26)
set -e
cd "$(dirname "$0")"
PY=.venv/Scripts/python
GT=../dataset/keypoints_260820/annotations.json
for v in "$@"; do for s in 0 1 2; do
  n=c_r_${v}_s$s
  [ -f results/curve/$n.gt.json ] && continue
  mkdir -p models/curve/$n && cp ${CVAT_LABELING_DIR:-/c/cvat-labeling}/train_ww/runs/${v}_s$s/pose.pth models/curve/$n/pose.pth
  sed -e "s/c_n1144_s0/$n/g" -e "1s/.*/# $v (시드 $s) + flip test. 10-26/" models/curve_c_n1144_s0.toml > models/curve_$n.toml
  $PY predict.py --model models/curve_$n.toml --gt $GT --images ../dataset/keypoints_260820 --out results/curve/$n.gt.preds.json --device cuda:0 > /dev/null
  $PY score.py --gt $GT --pred results/curve/$n.gt.preds.json --out results/curve/$n.gt.json > /dev/null
  echo "scored $n"
done; done
