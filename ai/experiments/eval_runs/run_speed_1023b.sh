#!/bin/bash
cd ${CREAMOFF_ROOT:-/c/Users/SSAFY/Desktop/PJT}/creamoff_data/paw_eval
P=.venv/Scripts/python.exe; S=0.85,0.9,1,1.1,1.15; V=../dataset/videos; R=results/speed1023b
{
$P tta_speed.py --model models/fs-v4.toml --video-root $V --scales 1 --out ${R}_base0.json
$P tta_speed.py --model models/fs-v4-flip.toml --video-root $V --scales 1 $S $S,r8 --out ${R}_a.json
$P tta_speed.py --model models/fs-v4-flip.toml --video-root $V --scales $S,r8 --post hind --out ${R}_hind.json
$P tta_speed.py --model models/fs-v4-flip.toml --video-root $V --scales $S,r8 --post ts --out ${R}_ts.json
$P tta_speed.py --model models/fs-v4-flip-dark.toml --video-root $V --scales 1 --out ${R}_dark.json
$P tta_speed.py --model models/fs-v4.toml --video-root $V --scales 1 --out ${R}_base1.json
echo ALLDONE
} > ${R}.log 2>&1
