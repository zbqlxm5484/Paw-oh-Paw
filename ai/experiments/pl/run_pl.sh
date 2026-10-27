set -uo pipefail
bash /exp/run/setup.sh > /dev/null 2>&1
cd /work/ssafy/paw_eval
P=/exp/pl
G=/ssafy/dataset/keypoints_260820
M=/work/ssafy/paw_eval/models/fs-v4
cat > $P/fs-v4-flip-stack.toml <<EOF
name = "fs-v4-flip"
backend = "mmpose"
config = "/exp/cv/pose_flip.py"
weights = "$M/pose.pth"
device = "cuda:0"

[stack]
backend = "mmdet-mmpose"
det_config = "$M/det.py"
det_weights = "$M/det.pth"
det_conf = 0.25
batch = 8
EOF
date
python $P/jenny_check.py list $P/videos_jenny.txt
[ -f $P/track_jenny.json ] || python video_kpi.py track --model $P/fs-v4-flip-stack.toml --videos $P/videos_jenny.txt --video-root /ssafy/dataset/videos --out $P/track_jenny.json 2>&1 | tail -2
[ -f $P/jenny_flip.preds.json ] || python predict.py --model $P/fs-v4-flip-stack.toml --gt $G/annotations.json --images $G --out $P/jenny_flip.preds.json | tail -1
for pairs in hind front,hind; do
  tag=${pairs/,/_}
  python $P/jenny_check.py apply $P/track_jenny.json $P/jenny_flip.preds.json $P/jenny_vit_$tag.preds.json $pairs
  python score.py --gt $G/annotations.json --pred $P/jenny_vit_$tag.preds.json --out $P/jenny_vit_$tag.json | grep -E "KPI-04|뒤바뀜"
done
python score.py --gt $G/annotations.json --pred $P/jenny_flip.preds.json --out $P/jenny_flip.json | grep -E "KPI-04|뒤바뀜"
date
[ -f $P/track_train.json ] || python video_kpi.py track --model $P/fs-v4-flip-stack.toml --videos $P/videos_train.txt --video-root /ssafy/dataset/videos --out $P/track_train.json 2>&1 | tail -2
date
python $P/select_frames.py --track $P/track_train.json --video-root /ssafy/dataset/videos --list $P/videos_train.txt --out $P/set_vit
python $P/select_frames.py --track $P/track_train.json --video-root /ssafy/dataset/videos --list $P/videos_train.txt --out $P/set_raw --no-viterbi
date
