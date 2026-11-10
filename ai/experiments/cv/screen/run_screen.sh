set -uo pipefail
source ~/venv/creamoff/bin/activate
export CUDA_VISIBLE_DEVICES=6 PYTHONUTF8=1
SCR=~/work/exp/cv/screen
cd ~/work/ssafy/paw_eval
date
( python video_kpi.py track --model models/fs-v4.toml --videos $SCR/videos_jenny.txt --video-root ~/work/ssafy/dataset/videos --device cuda:0 --out $SCR/trk_jenny.json \
  && python video_kpi.py track --model models/fs-v4.toml --videos $SCR/videos_ww.txt --video-root ~/work/ssafy/dataset/videos --device cuda:0 --out $SCR/trk_ww.json ) > $SCR/track.log 2>&1 &
TRK=$!
python ~/work/exp/cv/run_queue.py $SCR/queue_team.jsonl > $SCR/team.log 2>&1
python ~/work/exp/cv/wise.py --base models/fs-v4/pose.pth --ft ~/work/exp/cv/runs/SCR_team_full_s42/final.pth --alpha 0.3 --out $SCR/wise_0.3.pth
python ~/work/exp/cv/wise.py --base models/fs-v4/pose.pth --ft ~/work/exp/cv/runs/SCR_team_full_s42/final.pth --alpha 0.5 --out $SCR/wise_0.5.pth
wait $TRK
echo "추적 끝 $(date)"
cd $SCR && python screen.py
date
echo "== 끝"
