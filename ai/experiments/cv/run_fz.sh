set -uo pipefail
bash /exp/run/setup.sh > /dev/null 2>&1
cd /work/ssafy/paw_eval
date
python /exp/cv/run_queue.py /exp/cv/queue_fz.jsonl
python /exp/run/backbone_check_fz.py /exp/cv/runs/G3_fz_f0/final.pth /exp/cv/runs/G3_fz_f1/final.pth
grep -h "lr:" /exp/cv/runs/G3_fz_f0/*/*.log | tail -1 | cut -c1-200
date
echo "== 끝"
