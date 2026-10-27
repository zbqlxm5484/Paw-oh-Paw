set -uo pipefail
bash /exp/run/setup.sh > /dev/null 2>&1
cd /work/ssafy/paw_eval
D=/exp/cv/data
G=/ssafy/dataset/keypoints_260820
mkdir -p $D
date
nvidia-smi --query-gpu=power.draw,power.limit,clocks.sm,temperature.gpu --format=csv
[ -f /exp/train/creamoff46.py ] || python /exp/train/make_meta.py --out /exp/train/creamoff46.py
[ -f $D/fs-v4.preds.json ] || python predict.py --model models/fs-v4.toml --device cuda:0 --gt $G/annotations.json --images $G --out $D/fs-v4.preds.json
python /exp/cv/prep_cv.py --gt $G/annotations.json --preds $D/fs-v4.preds.json --out $D
python /exp/cv/make_queue.py /exp/cv/queue1.jsonl
python /exp/cv/run_queue.py "${1:-/exp/cv/queue1.jsonl}"
python /exp/cv/summarize.py
date
