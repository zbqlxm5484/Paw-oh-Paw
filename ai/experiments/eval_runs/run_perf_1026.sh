#!/bin/bash
# 10-26 이어 학습 실험(E-075~)의 처리 성능: 구조·추론 설정(flip)이 같으므로 대표 모델을 같은 측정 안에서 재 fs-v4-flip 과 같은지 확인.
# 속도 + GPU 메모리(KPI-16)는 tta_speed.py(배율 1), KPI-15 는 kpi_variant.py tput. 기준 fs-v4 를 처음·끝 두 번.
cd ${CREAMOFF_ROOT:-/c/Users/SSAFY/Desktop/PJT}/creamoff_data/paw_eval
export PYTHONUTF8=1; P=.venv/Scripts/python.exe; V=../dataset/videos; R=results/perf1026
m() { timeout 1800 $P perf_mem.py --out ${R}_$1.json -- "${@:2}"; }
ts() { m $1 $P tta_speed.py --video-root $V "${@:2}"; }
tp() { timeout 3600 $P kpi_variant.py tput --model $2 --video-root $V --out ${R}_$1.tput.json 2>&1 | tail -3; }
{
date
ts t_base0 --model models/fs-v4.toml --scales 1
ts t_flip --model models/fs-v4-flip.toml --scales 1
ts r_h_base --model models/curve_c_r_h_base_s0.toml --scales 1
ts r_offset --model models/curve_c_offset_s0.toml --scales 1
ts r_p96_auto --model models/curve_c_r_p96_auto_s0.toml --scales 1
ts r_ww50 --model models/curve_c_r_ww50_base_s0.toml --scales 1
tp t_flip models/fs-v4-flip.toml
tp r_h_base models/curve_c_r_h_base_s0.toml
ts t_base1 --model models/fs-v4.toml --scales 1
date
echo PERFDONE
} > ${R}.log 2>&1
