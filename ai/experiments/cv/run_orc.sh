set -uo pipefail
bash /exp/run/setup.sh > /dev/null 2>&1
cd /work/ssafy/paw_eval
mkdir -p /exp/results/orc_1102
date
[ -f /exp/cv/data/fs-v4.tta.preds.json ] || python /exp/cv/oracle_tta.py
python /exp/cv/oracle_make.py
python /exp/cv/make_queue_orc.py /exp/cv/queue_orc.jsonl ${SEEDS:-42}
python /exp/cv/run_queue.py /exp/cv/queue_orc.jsonl
date
echo "== 끝"
