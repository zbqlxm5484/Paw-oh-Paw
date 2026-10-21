# fs-v4 평가 재현 기록 (10-22)

크림오프 문서 「기존 모델 평가 재현·개선 착수 기준」 3절의 네 가지를 정리했어요. 측정 박규원 · 결과 파일은 `docs/eval/fs-v4-repro/`

**결론: 판정 대상 7개 값이 전부 GPU 기준값의 ±5% 안이라 재현된 것으로 봐요.** 가장 많이 벗어난 값도 +0.25%(KPI-04)예요.

## 1. 측정값 표

| 항목 | GPU (기준) | CPU (참고) | 판정 | 팀 측정값 (GPU) | 기준 대비 | 결과 |
|---|---|---|---|---|---|---|
| KPI-04 관절 각도 MAE | 8.01° | 8.02° | ±5% | 8.03° | +0.25% | 통과 |
| KPI-18 PCK@0.10 | 0.8985 | 0.8985 | ±5% | 0.8985 | 0% | 통과 |
| KPI-19 PCK@0.05 | 0.7024 | 0.7035 | ±5% | 0.7028 | +0.06% | 통과 |
| KPI-20 오차 중앙값 | 0.0350 | 0.0350 | ±5% | 0.0350 | 0% | 통과 |
| KPI-21 앞발끝 뒤바뀜 | 0.0396 | 0.0396 | ±5% | 0.0396 | 0% | 통과 |
| KPI-21 뒷발끝 뒤바뀜 | 0.1304 | 0.1304 | ±5% | 0.1304 | 0% | 통과 |
| KPI-17 모델 파일 크기 | 150.8 MiB | 150.8 MiB | ±5% | 150.8 MiB | 0% | 통과 |
| KPI-14 추론 시간 | 장비마다 다름 | — | 기록만 | 3.817초/건 (탐지 3.571 · 포즈 0.250) | — | — |
| KPI-16 GPU 메모리 | 장비마다 다름 | — | 기록만 | 1,136 MiB | — | — |

"고친 점만" 값(사람이 옮긴 점만 채점): KPI-04 13.34° · KPI-18 0.6066 · KPI-19 0.2849 · KPI-20 0.085 · KPI-21 앞 0.0684 / 뒤 0.2336.

CPU 로 잰 값(10-15)도 CPU 참고값과 같아요: KPI-04 8.02° · KPI-18 0.8985 · KPI-19 0.7035 · KPI-20 0.0350 · KPI-21 0.0396 / 0.1304.

## 2. 실행한 명령

`paw_eval` 폴더(Windows, Git Bash)에서 1절 명령 그대로 돌렸어요. 다른 점은 두 가지예요.

```bash
cp ../model/pose.pth ../model/det.pth models/fs-v4/
python predict.py --model models/fs-v4.toml \
  --gt ../dataset/keypoints_260820/annotations.json --images ../dataset/keypoints_260820 \
  --device cuda:0 --out fs-v4.preds.json
python score.py --gt ../dataset/keypoints_260820/annotations.json --pred fs-v4.preds.json --out fs-v4.json
python speed.py --models models/fs-v4.toml --video-root ../dataset/videos --out speed.json --concurrency 1,2,4
```

- `speed.py` 에 `--concurrency 1,2,4` 를 붙였어요. GPU 메모리가 8 GB 라 문서 안내(12 GB 미만)대로 했어요.
- 가상 환경은 `install_autolabel.sh` 가 아니라 `paw_eval/README.md` 의 설치 방법(아래 3절)으로 만들었어요. RTX 40 시리즈라 이 조합으로 GPU 가 돌아요.

## 3. 환경과 차이

| 항목 | 크림오프 기준 | 팀 측정 |
|---|---|---|
| GPU | RTX 5090 (32 GB) | RTX 4070 Laptop (8 GB), 드라이버 591.44, 충전기 연결 |
| OS | Windows 11 Pro + WSL2 Ubuntu | Windows 11 Enterprise (WSL 없이) |
| Python | 3.11.15 | 3.11.16 |
| PyTorch | 2.7.0+cu128 | 2.1.2+cu121 |
| mmpose / mmcv | 1.3.2 / 2.2.0 | 1.3.2 / 2.1.0 |

±5% 를 벗어난 값은 없어요. 판이 달라 생긴 차이는 KPI-04 의 0.02° 정도로 보여요.

KPI-14 는 이번에 3.817초가 나왔어요. 같은 노트북에서 10-15·10-20 에는 3.01~3.15초였어요. 이번 측정 중에 큰 파일(약 15 GB)을 받고 있었고 Docker 도 켜져 있어서 디스크·CPU 부하가 겹쳤던 것으로 보여요. 기록만 하는 항목이라 그대로 적었어요. 현행 대비 비율을 낼 때는 개선 모델과 같은 조건에서 다시 잴게요.

## 4. 결과 파일

`docs/eval/fs-v4-repro/` 에 넣었어요. 두 파일 다 같은 노트북에서 냈어요.

- `fs-v4.json` (`score.py`)
- `speed.json` (`speed.py`)

참고로 SHA256 도 적어 둬요.
- `pose.pth` a4261a107bc8e2f6a0418e8ffb02f510eb396c892aae1843092883b9fd63882f
- `det.pth` 43d5fe66500287602549dd9fccf7f028d7a7e19ffb7c314f873b98eec9427ea8
- `keypoints_260820/annotations.json` a08e9d47b6804305630a0ea1b79275ab5604b414d14368ae37f96613aa765fb7
