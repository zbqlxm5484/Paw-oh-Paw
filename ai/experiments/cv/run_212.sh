set -uo pipefail
bash /exp/run/setup.sh > /dev/null 2>&1
cd /work/ssafy/paw_eval
mkdir -p /exp/results/p212_1102
date

python /exp/cv/make_212.py /exp/cv/queue_212.jsonl

python /exp/cv/run_queue.py /exp/cv/queue_212.jsonl
date
echo "== 끝"
