set -uo pipefail
bash /exp/run/setup.sh
python /exp/run/patch_sweep.py
python /exp/run/make_sweep_models.py
cd /work/ssafy/paw_eval
R=/exp/results/sweep_1027
M=/exp/models/sweep
mkdir -p $R
NAMES=$(cat $M/names.txt)

nvidia-smi --query-gpu=name,driver_version,memory.used,power.draw,power.limit,clocks.sm,temperature.gpu --format=csv
date

echo "== 처리 성능"
MODELS="models/fs-v4.toml"
for m in $NAMES; do MODELS="$MODELS $M/$m.toml"; done
python speed.py --models $MODELS --video-root ../dataset/videos --out $R/speed.json --concurrency 1
nvidia-smi --query-gpu=power.draw,clocks.sm,temperature.gpu --format=csv
date
python /exp/run/plot_sweep.py $R
echo "== 끝"
