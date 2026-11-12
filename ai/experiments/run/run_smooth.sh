set -uo pipefail
bash /exp/run/setup.sh > /dev/null 2>&1
cd /work/ssafy/paw_eval
R=/exp/results
B=$R/base.track.json
S=/exp/smooth/smooth_track.py
N=/exp/smooth/normalize.py
echo "== 시간 평활 (기준 = 현행 base.track.json)"
for w in 5 7 9 13; do
  python $S --track $B --out $R/sg$w.track.json --window $w --order 2 > /dev/null
  echo "-- savgol window $w"
  python video_kpi.py score --track $B --compare $R/sg$w.track.json --out $R/sg$w.video.json 2>&1 | tail -6
done
echo "== 좌표 정규화(박규원 v0) 단독, 정규화 + 평활"
for opt in "--no-scale-x" "--no-scale-x --iso"; do
  tag=$(echo $opt | tr -d ' -')
  python $N --track $B --out $R/n_$tag.track.json $opt | head -1
  python video_kpi.py score --track $B --compare $R/n_$tag.track.json --out $R/n_$tag.video.json 2>&1 | tail -6
  python $S --track $R/n_$tag.track.json --out $R/n_${tag}_sg7.track.json --window 7 --order 2 --source norm > /dev/null
  echo "-- $tag + sg7"
  python video_kpi.py score --track $B --compare $R/n_${tag}_sg7.track.json --out $R/n_${tag}_sg7.video.json 2>&1 | tail -6
done
echo "== 끝"
