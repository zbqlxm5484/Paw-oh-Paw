#!/bin/bash
# E-034~E-075 처리 성능 일괄: 속도 + GPU 메모리(KPI-16). 영상 상자 실험은 det_stride.py, 사진 채점 실험은 tta_speed.py
cd ${CREAMOFF_ROOT:-/c/Users/SSAFY/Desktop/PJT}/creamoff_data/paw_eval
export PYTHONUTF8=1; P=.venv/Scripts/python.exe; S=0.85,0.9,1,1.1,1.15; V=../dataset/videos; R=results/perf1023
m() { timeout 1800 $P perf_mem.py --out ${R}_$1.json -- "${@:2}"; }
ds() { m $1 $P det_stride.py speed --video-root $V "${@:2}"; }
ts() { m $1 $P tta_speed.py --video-root $V "${@:2}"; }
{
ts t_base0 --model models/fs-v4.toml --scales 1
ds v_base0 --model models/fs-v4.toml --strides 1
ds v_h1 --model models/fs-v4.toml --strides 1 --half
ds v_flip --model models/fs-v4-flip.toml --strides 1
ds v_tiny25 --model models/fs-v4-dettiny-ft2.toml --strides 1
ds v_tiny08 --model models/fs-v4-dettiny-ft2-t08.toml --strides 1
ds v_combo08 --model models/combo-t08-flip.toml --strides 1
ds v_s3 --model models/fs-v4.toml --strides 3
ds v_s4 --model models/fs-v4.toml --strides 4
ds v_s5 --model models/fs-v4.toml --strides 5
ds v_h3 --model models/fs-v4.toml --strides 3 --half
ts t_flip --model models/fs-v4-flip.toml --scales 1
ts t_dark --model models/fs-v4-flip-dark.toml --scales 1
ts t_a --model models/fs-v4-flip.toml --scales $S,r8
ts t_hind --model models/fs-v4-flip.toml --scales $S,r8 --post hind
ts t_ts --model models/fs-v4-flip.toml --scales $S,r8 --post ts
for fl in "" -flip; do for p in 115 105 95 85; do ts t_pad${fl}${p} --model models/fs-v4${fl}-pad${p}.toml --scales 1; done; done
ds v_base1 --model models/fs-v4.toml --strides 1
ts t_base1 --model models/fs-v4.toml --scales 1
echo PERFDONE
} > ${R}.log 2>&1
