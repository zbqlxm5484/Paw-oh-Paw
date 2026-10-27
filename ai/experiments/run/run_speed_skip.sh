set -uo pipefail
bash /exp/run/setup.sh
cd /work/ssafy/paw_eval
R=/exp/results
date
python speed.py --models models/fs-v4.toml /exp/models/fs-v4-skip2.toml /exp/models/fs-v4-skip3.toml /exp/models/fs-v4-skip5.toml /exp/models/fs-v4-skip8.toml --video-root ../dataset/videos --out $R/speed_skip.json --concurrency 1
date
echo "== 끝"
