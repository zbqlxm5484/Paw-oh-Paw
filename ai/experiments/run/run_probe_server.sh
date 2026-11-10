set -uo pipefail
ROOT=${ROOT:-$HOME/exp}
export CUDA_VISIBLE_DEVICES=${GPU:-6}
source $HOME/venv/creamoff/bin/activate
python $ROOT/run/patch_probe.py $ROOT
python $ROOT/run/make_probe_models.py $ROOT
cd $ROOT/paw_eval
python -c "import speed; print('stacks:', sorted(speed.STACKS))"
R=$ROOT/results/probe_1029
M=$ROOT/models
mkdir -p $R
nvidia-smi --query-gpu=index,name,memory.used,utilization.gpu --format=csv
date
python video_kpi.py track --model models/fs-v4.toml --video-root $ROOT/videos --out $R/base.track.json 2>&1 | tail -1
for m in $(cat $M/names.txt); do
  date
  python video_kpi.py track --model $M/$m.toml --video-root $ROOT/videos --out $R/$m.track.json 2>&1 | tail -1
  echo "-- $m"
  python video_kpi.py score --track $R/base.track.json --compare $R/$m.track.json --out $R/$m.video.json 2>&1 | tail -8
done
date
echo "== 끝"
