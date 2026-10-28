#!/bin/bash
# 100 시험 라벨 학습 3시드를 기업 정답(260820)·와우와우 검증에 채점 (10-26). curve n1144 와 같은 방식.
set -e
cd "$(dirname "$0")"
PY=.venv/Scripts/python
for s in 0 1 2; do
  n=c_pilot_s$s
  mkdir -p models/curve/$n && cp ${CVAT_LABELING_DIR:-/c/cvat-labeling}/train_ww/pilot/s$s/pose.pth models/curve/$n/pose.pth
  $PY predict.py --model models/curve_$n.toml --gt ../dataset/keypoints_260820/annotations.json --images ../dataset/keypoints_260820 --out results/curve/$n.gt.preds.json --device cuda:0
  $PY score.py --gt ../dataset/keypoints_260820/annotations.json --pred results/curve/$n.gt.preds.json --out results/curve/$n.gt.json > /dev/null
  $PY predict.py --model models/curve_$n.toml --gt ${CREAMOFF_ROOT:-C:/Users/SSAFY/Desktop/PJT}/splits/wowwow/wowwow_val.json --images ../dataset_1021/keypoints_wowwow --out results/curve/$n.ww.preds.json --device cuda:0
  $PY score.py --gt ${CREAMOFF_ROOT:-C:/Users/SSAFY/Desktop/PJT}/splits/wowwow/wowwow_val.json --pred results/curve/$n.ww.preds.json --out results/curve/$n.ww.json > /dev/null
  echo "scored $n"
done
