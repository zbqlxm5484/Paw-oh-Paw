set -uo pipefail
bash /exp/run/setup.sh
cd /work/ssafy/paw_eval
R=/exp/results
G=../dataset/keypoints_260820
nvidia-smi --query-gpu=name,driver_version,memory.used --format=csv
date

echo "== 1. FP16 정확도"
python predict.py --model /exp/models/fs-v4-fp16.toml --gt $G/annotations.json --images $G --device cuda:0 --out $R/fp16.preds.json
python score.py --gt $G/annotations.json --pred $R/fp16.preds.json --out $R/fp16.json
python score.py --compare /ssafy/재현기록-261021/fs-v4.json $R/fp16.json

echo "== 2. 영상 지표"
python video_kpi.py track --model models/fs-v4.toml --video-root ../dataset/videos --out $R/base.track.json 2>&1 | tail -1
for m in det512 det416 det320 skip2 skip3 skip5 skip8; do
  date
  python video_kpi.py track --model /exp/models/fs-v4-$m.toml --video-root ../dataset/videos --out $R/$m.track.json 2>&1 | tail -1
  echo "-- $m"
  python video_kpi.py score --track $R/base.track.json --compare $R/$m.track.json --out $R/$m.video.json 2>&1 | tail -8
done

echo "== 3. 처리 성능"
date
python speed.py --models models/fs-v4.toml /exp/models/fs-v4-fp16.toml /exp/models/fs-v4-det512.toml /exp/models/fs-v4-det416.toml /exp/models/fs-v4-det320.toml /exp/models/fs-v4-skip2.toml /exp/models/fs-v4-skip3.toml /exp/models/fs-v4-skip5.toml /exp/models/fs-v4-skip8.toml --video-root ../dataset/videos --out $R/speed_all.json --concurrency 1
date
echo "== 끝"
