#!/bin/bash
# 속도 측정(speed1023b) 끝난 뒤 영상 상자 채점: E-045(fp16 계산 매 프레임) + 작은 탐지기 E-029/E-030/E-032(뒷다리 보정 빼고) + 비교용 flip
cd ${CREAMOFF_ROOT:-/c/Users/SSAFY/Desktop/PJT}/creamoff_data/paw_eval
until grep -q ALLDONE results/speed1023b.log; do sleep 30; done
export PYTHONUTF8=1; P=.venv/Scripts/python.exe
GT=../dataset/keypoints_260820/annotations.json; WW=../../splits/wowwow/wowwow_val.json
run() { # tag model half
  for set in gt ww; do
    if [ $set = gt ]; then L=gt_videos.txt; G=$GT; R=../dataset/videos; else L=ww_val_videos.txt; G=$WW; R=../dataset_1021/videos; fi
    $P det_stride.py track --model $2 --stride 1 $3 --videos $L --video-root $R --out results/v${set}_$1.track.json > results/v${set}_$1.log 2>&1
    $P track_to_preds.py --track results/v${set}_$1.track.json --gt $G --out results/v${set}_$1.preds.json
    echo "== $set $1"; $P score.py --gt $G --pred results/v${set}_$1.preds.json --out results/v${set}_$1.json 2>&1 | grep -E "KPI-(04|18|19|21)"
  done
}
{
run s1h models/fs-v4.toml --half
run flip models/fs-v4-flip.toml ""
run tiny25 models/fs-v4-dettiny-ft2.toml ""
run tiny08 models/fs-v4-dettiny-ft2-t08.toml ""
run combo08 models/combo-t08-flip.toml ""
echo VBOXDONE
} > results/vbox1023.log 2>&1
