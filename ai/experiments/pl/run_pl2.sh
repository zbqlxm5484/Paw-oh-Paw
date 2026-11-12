set -uo pipefail
bash /exp/run/setup.sh > /dev/null 2>&1
cd /work/ssafy/paw_eval
P=/exp/pl
date
[ -f $P/set_vith/pseudo.json ] || python $P/select_frames.py --track $P/track_train.json --video-root /ssafy/dataset/videos --list $P/videos_train.txt --out $P/set_vith --pairs hind
python $P/prep_pl.py set_vith set_raw
python $P/make_queue4.py /exp/cv/queue4.jsonl
python /exp/cv/run_queue.py /exp/cv/queue4.jsonl > /exp/cv/queue4.log 2>&1
python /exp/cv/summarize.py > /dev/null
date
bash /exp/run/run_sweep_1027.sh > /exp/results/sweep_1027.log 2>&1
date
