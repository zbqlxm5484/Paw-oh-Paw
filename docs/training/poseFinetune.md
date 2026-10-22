# 관절점 모델(fs-v4) 이어 학습 메모 (10-20 시험, 10-22 정리)

작성 박규원 · S15P31A404-71·72 시험에서 나온 것 · 이어 학습을 하는 사람이 먼저 읽을 것

## 1. BN 통계를 꼭 고정하세요

mmpose `train` 으로 fs-v4 를 이어 학습하면 **BatchNorm 통계(running mean/var)가 새 데이터로 바뀌어요.** 학습률을 0 에 가깝게 두고 1에폭만 돌려도 망가져요.

| 설정 | KPI-04 각도 MAE | PCK@0.10 |
|---|---|---|
| fs-v4 그대로 | 8.03° | 0.8985 |
| 학습률 ≈0, 1에폭, BN 고정 안 함 | **10.96°** | 0.788 |

설정 파일에 한 줄 넣어 막아요.

```python
model = dict(backbone=dict(norm_eval=True))  # BN 통계 고정
```

- `CosineAnnealingLR` 의 `eta_min` 이 설정한 `lr` 보다 크면 그만큼 학습돼요. "학습률 0 시험"을 할 때는 `eta_min` 도 같이 내려 주세요.
- 평가는 기업 `paw_eval`(`predict.py` → `score.py`)로, fs-v4 와 같은 정답·같은 설정으로 나란히 재요.

## 2. 10-20 시험 결과 (기업 정답 205장, GPU)

| 시험 | KPI-04 | 앞발끝 뒤바뀜 | 뒷발끝 뒤바뀜 | 판단 |
|---|---|---|---|---|
| fs-v4 기준선 | 8.03° | 3.96% | 13.0% | — |
| AI-Hub 71878 옆 촬영 3에폭, BN 고정 | 9.52° | 33% | 34% | 나빠짐 |
| 자가 학습(가짜 라벨 1,163장) 10에폭, BN 고정 | 9.90° | 1.86% | — | 나빠짐 |
| AI-Hub + 가짜 라벨×5 섞기 | 9.62° | 1.86% | 14.2% | 나빠짐 |
| **flip test**(학습 없음) | **7.89°** | 2.80% | 13.5% | 이득 |
| **flip test + 영상 좌우 보정** | **7.93°** | 2.33% | **5.7%** | 이득 |

- 학습 시험은 셋 다 기준선을 못 이겼어요. 사람 라벨(크림오프 추가 3,000장) 없이 데이터를 늘리는 쪽은 더 시도하지 않아요.
- **AI-Hub 옆 촬영은 카메라 쪽 다리만 라벨**이 있어요. 그대로 학습하면 반대쪽 다리 채널이 보이는 다리로 끌려가서 좌우 뒤바뀜이 33% 까지 늘어요.
- flip test 는 설정의 `test_cfg=dict(flip_test=True)` 하나로 켜요. fs-v4 체크포인트에 46점 `flip_indices` 가 들어 있어요. 포즈 추론 시간은 2배지만 전체 처리 시간의 6% 정도예요.

## 3. AI-Hub 71878 옆 촬영 파일 만들기

변환 결과(JSON)는 레포에 올리지 않아요(수십 MB). 아래 순서로 다시 만들어요.

```bash
# 1) AI-Hub 원본 → 22점 COCO (좌우 검증 끝난 설정)
python ai/data_prep/aihub_to_coco.py --aihub71878 <71878 루트> --out <출력 폴더> --side-view-map Left=left,Right=right
# 2) 옆 촬영(Left/Right)만 남기기
python ai/data_prep/filter_views.py --coco <출력 폴더>/aihub71878_train.json --out <출력 폴더>/aihub71878_train_side.json
python ai/data_prep/filter_views.py --coco <출력 폴더>/aihub71878_val.json   --out <출력 폴더>/aihub71878_val_side.json
python ai/data_prep/filter_views.py --coco <출력 폴더>/aihub71878_test.json  --out <출력 폴더>/aihub71878_test_side.json
```

10-19 에 만든 파일과 같은지 확인했어요(val 4,893장, Left 2,432 · Right 2,461). 좌우가 맞는지는 `ai/data_prep/check_sides.py` 로 그림을 그려 봐요.
