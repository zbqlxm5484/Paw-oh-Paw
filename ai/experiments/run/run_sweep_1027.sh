set -uo pipefail
bash /exp/run/setup.sh
python /exp/run/patch_sweep.py
python /exp/run/make_sweep_models.py
cd /work/ssafy/paw_eval
python -c "import speed; print('stacks:', sorted(speed.STACKS))"
R=/exp/results/sweep_1027
M=/exp/models/sweep
mkdir -p $R
NAMES=$(cat $M/names.txt)

gpu() {
  echo "## gpu $1 $(date -u +%FT%TZ)"
  nvidia-smi --query-gpu=power.draw,power.limit,clocks.sm,temperature.gpu,pstate --format=csv
}

nvidia-smi --query-gpu=name,driver_version,memory.used --format=csv
date

echo "== 1. 영상 지표"
gpu track-base-before
python video_kpi.py track --model models/fs-v4.toml --video-root ../dataset/videos --out $R/base.track.json 2>&1 | tail -1
gpu track-base-after
for m in $NAMES; do
  date
  gpu track-$m-before
  python video_kpi.py track --model $M/$m.toml --video-root ../dataset/videos --out $R/$m.track.json 2>&1 | tail -1
  gpu track-$m-after
  echo "-- $m"
  python video_kpi.py score --track $R/base.track.json --compare $R/$m.track.json --out $R/$m.video.json 2>&1 | tail -8
done

echo "== 2. 처리 성능"
date
gpu speed-before
MODELS="models/fs-v4.toml"
for m in $NAMES; do MODELS="$MODELS $M/$m.toml"; done
python speed.py --models $MODELS --video-root ../dataset/videos --out $R/speed.json --concurrency 1
gpu speed-after
date
echo "== 끝"
