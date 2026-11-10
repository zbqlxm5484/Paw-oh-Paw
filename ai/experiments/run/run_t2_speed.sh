set -uo pipefail
bash /exp/run/setup.sh
python /exp/run/patch_sweep.py
python /exp/run/make_probe_models.py /work/ssafy
python /exp/run/make_tta_models.py /work/ssafy
python /exp/run/make_t2_models.py /work/ssafy
cd /work/ssafy/paw_eval
R=/exp/results/t2_1103
M=/work/ssafy/models
mkdir -p $R
nvidia-smi --query-gpu=name,driver_version,memory.used,power.draw,clocks.sm,temperature.gpu --format=csv
date
python speed.py --models models/fs-v4.toml $M/k3-fp16-probe-hind.toml $M/k3-fp16-probe-t2-hind.toml $M/k3-fp16-probe-t2.toml $M/k3-fp16-probe-e036.toml $M/k1-fp32-t2.toml --video-root ../dataset/videos --out $R/speed.json --concurrency 1
nvidia-smi --query-gpu=power.draw,clocks.sm,temperature.gpu --format=csv
date
echo "== 끝"
