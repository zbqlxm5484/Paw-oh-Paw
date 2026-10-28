#!/bin/bash
# 10-23 밤 다시: 충전기 교체 뒤 속도·메모리 → KPI-15·영상 KPI. 전원 상태를 1분마다 results/power1023b.log 에 남긴다
cd ${CREAMOFF_ROOT:-/c/Users/SSAFY/Desktop/PJT}/creamoff_data/paw_eval
rm -f results/perf1023_*.json results/kpi1023_*.tput.json
( while true; do echo "$(date +%H:%M) $(powershell.exe -NoProfile -Command '$b=Get-CimInstance Win32_Battery; "$($b.BatteryStatus) $($b.EstimatedChargeRemaining)%"')"; sleep 60; done ) > results/power1023b.log 2>&1 &
LOGGER=$!
bash run_perf_1023.sh
bash run_kpi_1023.sh
kill $LOGGER
echo ALLDONE2 >> results/kpi1023.log
