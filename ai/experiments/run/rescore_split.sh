set -uo pipefail
bash /exp/run/setup.sh > /dev/null 2>&1
cd /work/ssafy/paw_eval
python /exp/run/make_gt_subsets.py
R=/exp/results/wowwow
G=../dataset/keypoints_wowwow
for s in train val; do
  echo "== $s"
  python predict.py --model models/fs-v4.toml --gt $R/gt_$s.json --images $G --device cuda:0 --out $R/fs-v4.$s.preds.json 2>&1 | tail -1
  python score.py --gt $R/gt_$s.json --pred $R/fs-v4.$s.preds.json --out $R/fs-v4.$s.json 2>&1 | grep -v Warn
done
