#!/bin/bash
# 처리 성능 측정(run_perf_1023.sh) 끝난 뒤: 설정마다 KPI-15(처리량) + 영상 KPI-01/02/24(video_kpi_videos.txt 27건)
cd ${CREAMOFF_ROOT:-/c/Users/SSAFY/Desktop/PJT}/creamoff_data/paw_eval
export PYTHONUTF8=1; P=.venv/Scripts/python.exe; V=../dataset/videos; R=results/kpi1023
S='0.85,0.9,1,1.1,1.15'
run() { # tag model variant
  export PAW_VARIANT="$3"
  echo "== $1 $2 $3"
  if [ ! -f ${R}_$1.vkpi.json ]; then          # 영상 KPI 는 전원과 무관해 이미 있으면 다시 안 돈다
    timeout 2400 $P kpi_variant.py track --model $2 --video-root $V --out ${R}_$1.track.json > ${R}_$1.track.log 2>&1
    $P video_kpi.py score --track ${R}_$1.track.json --out ${R}_$1.vkpi.json 2>&1 | tail -4
  fi
  timeout 3600 $P kpi_variant.py tput --model $2 --video-root $V --out ${R}_$1.tput.json 2>&1 | tail -6
}
st() { echo "{\"kind\":\"stride\",\"stride\":$1,\"half\":$2}"; }
tt() { echo "{\"kind\":\"tta\",\"scales\":[$1],\"rots\":[$2],\"post\":$3}"; }
{
run v_base models/fs-v4.toml "$(st 1 false)"
run v_h1 models/fs-v4.toml "$(st 1 true)"
run v_flip models/fs-v4-flip.toml "$(st 1 false)"
run v_tiny25 models/fs-v4-dettiny-ft2.toml "$(st 1 false)"
run v_tiny08 models/fs-v4-dettiny-ft2-t08.toml "$(st 1 false)"
run v_combo08 models/combo-t08-flip.toml "$(st 1 false)"
run v_s3 models/fs-v4.toml "$(st 3 false)"
run v_s4 models/fs-v4.toml "$(st 4 false)"
run v_s5 models/fs-v4.toml "$(st 5 false)"
run v_h3 models/fs-v4.toml "$(st 3 true)"
run t_base models/fs-v4.toml "$(tt 1 '' null)"
run t_flip models/fs-v4-flip.toml "$(tt 1 '' null)"
run t_dark models/fs-v4-flip-dark.toml "$(tt 1 '' null)"
run t_a models/fs-v4-flip.toml "$(tt $S '8,-8' null)"
run t_hind models/fs-v4-flip.toml "$(tt $S '8,-8' '"hind"')"
run t_ts models/fs-v4-flip.toml "$(tt $S '8,-8' '"ts"')"
for fl in "" -flip; do for p in 115 105 95 85; do run t_pad${fl}${p} models/fs-v4${fl}-pad${p}.toml "$(tt 1 '' null)"; done; done
echo KPIDONE
} > ${R}.log 2>&1
