# 3D 강아지 모델

| 파일 | 원본 | 만든 사람 | 라이선스 |
|---|---|---|---|
| shiba.glb | https://poly.pizza/m/y4wdQpg767 (Shiba Inu) | Quaternius | CC0 1.0 (공공 영역) |
| husky.glb | https://poly.pizza/m/wcWiuEqwzq (Husky) | Quaternius | CC0 1.0 (공공 영역) |

10-28 내려받음. 동작: Walk, Gallop, Idle 등. 다리 뼈: FrontShoulder/FrontUpperLeg/FrontLowerLeg.L·R, BackShoulder/BackLeg/BackUpperLeg/BackLowerLeg.L·R.
소형·중형은 shiba, 대형은 husky 로 쓴다(gait3d.html).

`gait_demo.json`: 3D "측정 걸음"·보고서 무릎 곡선 기본값. 공개 논문(Catavitello et al. 2015 PLOS ONE, CC BY 4.0, `gait_ref_plos.json`) 속보 평균 곡선에
고관절만 합성(AI-Hub 71878 시연 회차 가동 범위에 맞춤)으로 넣었다. `prototype/tools/build_demo_clip.py`. 회사 데이터는 쓰지 않는다.

`gait_jenny.json`(회사 데이터, 제니 영상 72개에서 만든 걸음)은 git 에 올리지 않는다(.gitignore). 로컬 비교용으로만 남긴다.
