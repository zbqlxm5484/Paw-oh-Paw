set -uo pipefail
bash /exp/run/setup.sh > /dev/null 2>&1
cd /work/ssafy/paw_eval
R=/exp/results/flip
mkdir -p $R
cat > models/fs-v4/pose_flip.py <<EOF
_base_ = ['pose.py']
model = dict(test_cfg=dict(flip_test=True))
EOF
sed 's#config = "fs-v4/pose_flip.py"#config = "fs-v4/pose_flip.py"#; s#config = "fs-v4/pose.py"#config = "fs-v4/pose_flip.py"#; s#name = "fs-v4"#name = "fs-v4-flip"#' models/fs-v4.toml > models/fs-v4-flip.toml
grep -n "config\|name" models/fs-v4-flip.toml | head -4
G=../dataset/keypoints_260820
for M in fs-v4 fs-v4-flip; do
  echo "== 정확도 $M"
  python predict.py --model models/$M.toml --gt $G/annotations.json --images $G --device cuda:0 --out $R/$M.preds.json 2>&1 | tail -1
  python score.py --gt $G/annotations.json --pred $R/$M.preds.json --out $R/$M.json 2>&1 | grep -v -i warn | sed -n 1,9p
done
echo "== 비교 (기준 대 flip)"
python score.py --compare $R/fs-v4.json $R/fs-v4-flip.json 2>&1 | grep -v -i warn
echo "== 처리 성능"
date
python speed.py --models models/fs-v4.toml models/fs-v4-flip.toml --video-root ../dataset/videos --out $R/speed.json --concurrency 1 2>&1 | grep -v -i warn | tail -25
date
echo "== 끝"
