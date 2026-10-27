set -uo pipefail
bash /exp/cv/run_cv2.sh > /exp/cv/queue2.log 2>&1
cd /work/ssafy/paw_eval
[ -f /exp/train/creamoff46_h2.py ] || python /exp/train/make_meta.py --hind-weight 2 --out /exp/train/creamoff46_h2.py
python /exp/cv/make_queue3.py /exp/cv/queue3.jsonl
python /exp/cv/run_queue.py /exp/cv/queue3.jsonl > /exp/cv/queue3.log 2>&1
python /exp/cv/summarize.py > /dev/null
bash /exp/run/run_sweep_1027.sh > /exp/results/sweep_1027.log 2>&1
date
