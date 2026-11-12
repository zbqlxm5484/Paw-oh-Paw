set -uo pipefail
bash /exp/run/setup.sh > /dev/null 2>&1
cd /work/ssafy/paw_eval
D=/exp/cv/data
R=/exp/results/seed_1029
mkdir -p $R
date
for mode in head full; do
  for k in a b; do
    W=$R/${mode}_$k
    rm -rf $W
    if [ $mode = head ]; then
      python /exp/cv/train_cv.py --train-json $D/tr_f0_gt_occ0_boxeval_untkeep.json --work-dir $W --train head --lr 5e-5 --epochs 100 --batch 32 --rot 15 --scale 0.8 1.2 --padding 1.25 --seed 42 > $W.log 2>&1
    else
      python /exp/cv/train_cv.py --train-json $D/tr_f0_gt_occ0_boxeval_untkeep.json --work-dir $W --train full --padding 1.25 --seed 42 > $W.log 2>&1
    fi
    echo "-- $mode $k exit $?"
    date
  done
done
python /exp/run/seed_compare.py $R
echo "== 끝"
