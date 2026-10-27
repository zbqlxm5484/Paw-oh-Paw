set -uo pipefail
bash /exp/run/setup.sh > /dev/null 2>&1
cd /work/ssafy/paw_eval
D=/exp/cv/data
G=/ssafy/dataset/keypoints_260820
date
nvidia-smi --query-gpu=power.draw,power.limit,clocks.sm,temperature.gpu --format=csv
python /exp/cv/prep_cv.py --gt $G/annotations.json --preds $D/fs-v4.preds.json --out $D --ww /ssafy/dataset/keypoints_wowwow/annotations.json --ww-train /exp/results/gt_train.json | grep -v "^tr_f[01]"
python /exp/cv/make_queue2.py /exp/cv/queue2.jsonl
python /exp/cv/run_queue.py /exp/cv/queue2.jsonl
python /exp/cv/summarize.py > /dev/null
date
