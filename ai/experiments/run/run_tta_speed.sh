set -uo pipefail
bash /exp/run/setup.sh
python /exp/run/patch_sweep.py
python /exp/run/make_probe_models.py /work/ssafy
python /exp/run/make_tta_models.py /work/ssafy
cd /work/ssafy/paw_eval
R=/exp/results/tta_1029
M=/work/ssafy/models
mkdir -p $R
python /exp/run/tta_check.py 2>&1 | grep -E "회귀|프레임|Error|Traceback"
[ "${CHECK_ONLY:-0}" = 1 ] && exit 0
nvidia-smi --query-gpu=name,driver_version,memory.used,power.draw,clocks.sm,temperature.gpu --format=csv
date
python speed.py --models models/fs-v4.toml $M/k3-fp16-probe-hind.toml $M/k3-fp16-probe-flip-hind.toml $M/k3-fp16-probe-e036.toml $M/k1-fp32-e036.toml --video-root ../dataset/videos --out $R/speed.json --concurrency 1
nvidia-smi --query-gpu=power.draw,clocks.sm,temperature.gpu --format=csv
date
echo "== 끝"
