# 로컬 실험 스크립트

GPU 서버를 받기 전에 노트북(RTX 4070, Docker)에서 돌린 경량화, 시간 평활, 미세조정 준비 실험 코드입니다. 결과와 해석은 위키 `90-원본/작업-기록/261021-경량화와-평활-시험-결과`에, 다시 점검할 점은 `NOTES.md`에 있습니다.

기업 자료(`paw_eval`, 가중치, 영상, 정답)는 들어 있지 않습니다. 실행할 때 기업 전달본 폴더를 컨테이너에 연결해서 씁니다.

## 폴더

| 폴더 | 내용 |
| --- | --- |
| `run` | 실행 스크립트. `setup.sh`가 `paw_eval`을 `/work`로 복사하고 탐지 건너뛰기 실행부를 `speed.py`에 등록합니다 |
| `stacks` | 탐지 건너뛰기 실행부. `skipdet.py`는 키프레임에서만 탐지하고 사이는 상자를 보간합니다. `skipdet2.py`는 여기에 fp16 계산, 빈 구간 확인(probe), 추론 증강(배율, 회전), 뒷다리 좌우 바로잡기를 더한 것으로 11-04 기업 점검 묶음이 쓰는 판입니다 |
| `smooth` | 시간 평활(`smooth_track.py`), 평활이 점을 움직인 양 확인(`blur_check.py`), 좌표 정규화(`normalize.py`) |
| `train` | 미세조정 설정(`ft_base.py`)과 46점 학습 데이터 만들기, CPU 점검 스크립트 |
| `cv` | 제니 반쪽 교차 학습 실험 틀(10-27). `run_queue.py`가 대기열 파일(한 줄에 실험 하나)을 읽어 학습, 채점, 기록을 이어서 돌립니다. 결과는 위키 실험 결과 종합의 10-27 절 |
| `pl` | 영상 좌우 바로잡기(비터비, `viterbi.py`)와 의사 라벨 준비. 라벨 없는 학습 쪽 개 영상을 추적해 믿을 만한 프레임만 학습 데이터로 고릅니다 |
| `eval_runs` | 기업 `paw_eval`에 얹어 쓴 추론 증강(배율·회전·flip), 후처리(좌우 바로잡기·평활·가장자리 상자 거르기), 탐지 간격·fp16 실행부, 처리 성능·KPI 일괄 실행, 팀 시트 내보내기(10-20~10-26, 박규원) |
| `finetune` | fs-v4 이어 학습 실행부(`train.py`, `ft_creamoff.py`), 22점→46점 변환, 학습셋별 3시드 일괄 학습(10-22~10-26, 박규원) |
| `labels` | 라벨 기준 실험: 라벨 맞추기 pilot20, 시험 라벨 검수, 와우와우 기준 차이 보정, 기업 정답·와우와우를 오토라벨과 비교한 방향 통계와 그림, CVAT 보조 스크립트(10-20~10-28, 박규원) |
| `normalize` | 좌표 정규화 실험: KPI-02 화면 위치 효과 가르기, 매트 평면 투영, 비스듬 보행·카메라 오차 합성 확인 그림(10-19~10-26, 박규원) |

실험마다 날짜, 목적, 스크립트, 결과 위치는 `LOG.md`에 한 줄씩 적습니다.

## 실행

기업 Docker 이미지 `cvat-autolabel:creamoff-2.73.1`에서 돌립니다. 컨테이너 안 경로는 아래처럼 맞춥니다.

- `/ssafy`: 기업 전달본 폴더(`paw_eval`, `dataset`, `model`). 읽기 전용
- `/exp`: 이 폴더

```
docker run --rm --gpus all -e PYTHONUTF8=1 -v "<전달본 폴더>:/ssafy:ro" -v "<이 폴더>:/exp" cvat-autolabel:creamoff-2.73.1 bash -c "bash /exp/run/setup.sh && cd /work/ssafy/paw_eval && python /exp/run/make_models.py"
docker run --rm --gpus all -e PYTHONUTF8=1 -v "<전달본 폴더>:/ssafy:ro" -v "<이 폴더>:/exp" cvat-autolabel:creamoff-2.73.1 bash /exp/run/run_all.sh
```

- `make_models.py`를 먼저 돌려야 `models/`(FP16 가중치, 해상도별 탐지기 설정, 건너뛰기 설정)가 생깁니다. FP16 가중치는 `save_fp16.py`로 만듭니다(아래 FP16 절).
- `run_all.sh`의 FP16 비교는 재현 기록 결과(`/ssafy/재현기록-261021/fs-v4.json`)가 있어야 돌아갑니다.
- `train/smoke.sh`, `train/smoke_wow.sh`는 학습이 도는지만 보는 점검용입니다. 결과를 성능으로 쓰지 않습니다.
- 학습 상자는 채점과 같게 정답 상자를 긴 변의 15%씩 넓힌 뒤 1.25배로 넣습니다(`make_train_set.py`, `pad_coco.py`의 `--box-margin`, `ft_base.py`의 `padding`). 10-26까지의 학습은 1.15배로만 넣어 이어 학습할수록 나빠졌습니다.
- 교차 실험: `bash /exp/cv/run_cv.sh`(대기열 1), `bash /exp/cv/run_night.sh`(대기열 2, 3과 속도 측정). 정리는 `python cv/summarize.py`, 그림은 `python cv/report.py <출력.html>`
- 의사 라벨: `pl/make_list.py`로 영상 목록을 만든 뒤 `bash /exp/pl/run_pl.sh`. 개 단위 분할 결과(`pl/dog_split.json`)는 `ai/data_prep/split_by_dog.py`로 만들어 둡니다

### FP16 저장과 fp16 계산

둘은 다른 것이고 따로 켭니다.

| | FP16 저장 | fp16 계산 |
| --- | --- | --- |
| 하는 일 | 가중치 파일의 실수 텐서를 16비트로 저장. 같은 저장 공간을 쓰는 텐서는 한 번만 저장하고 옵티마이저 상태는 뺌 | 탐지와 관절점 계산을 `torch.autocast(cuda, float16)` 안에서 돌림 |
| 바뀌는 지표 | 모델 파일 크기(KPI-17) | 처리 시간(KPI-14) |
| 코드 | `run/save_fp16.py` | `stacks/skipdet2.py`의 `_amp()`, 모델 설정 `[stack]`의 `fp16 = true` |
| 결과 | fs-v4 탐지기 94.62에서 47.40 MiB, 관절점 56.20에서 28.14 MiB, 합계 75.54 MiB(E-104) | 매 프레임 탐지 기준 0.675배(10-29 노트북, 현행과 번갈아 3바퀴) |

```
python /exp/run/save_fp16.py <det.pth> <pose.pth> --out <출력 폴더>
```

- 저장한 파일을 mmengine으로 불러오면 모델의 FP32 파라미터에 복사되므로 속도와 메모리는 그대로입니다. fs-v4 관절점은 다시 불러온 파라미터와 원본의 최대 차이가 0.0076입니다(11-05 컨테이너 확인).
- fp16 계산은 CUDA에서만 켜집니다. CPU면 설정에 `fp16 = true`가 있어도 무시합니다.
- 사진 정확도 채점(`predict.py`)은 정답 상자로 관절점만 돌리므로 fp16 계산이 들어가지 않습니다. 영상 처리(`speed.py`)에만 영향이 있습니다.
- 학습한 가중치도 같은 스크립트로 줄입니다. 학습 체크포인트의 옵티마이저 상태가 빠지므로 원본보다 많이 작아집니다.

### `eval_runs`, `finetune`, `labels`, `normalize`

이 네 폴더는 컨테이너가 아니라 Windows 의 기업 전달본 옆에서 돌린 것이 많습니다. 경로는 환경 변수로 바꿔 씁니다(안 주면 작성자 PC 경로).

| 환경 변수 | 뜻 |
| --- | --- |
| `CREAMOFF_ROOT` | 작업 폴더. 아래에 `creamoff_data/`(기업 전달본: `paw_eval`, `dataset`, `dataset_1021`), `splits/`(학습·검증 분할) 이 있다고 봅니다 |
| `CVAT_LABELING_DIR` | 기업 CVAT 라벨링 묶음 폴더(기업 안내서와 같은 이름) |
| `CREAMOFF_OUT` | 팀 시트에 붙여 넣을 TSV 를 쓰는 폴더 |

- `eval_runs/*.py`: `paw_eval` 폴더 안에 복사해서 돌립니다(`predict.py`·`speed.py`를 불러 씀). `run_*.sh`는 `paw_eval`에서 실행합니다.
- `finetune/`: `ft_creamoff.py` 옆에 기업 전달본 `model/pose.py`를 복사해 둡니다(기업 파일이라 올리지 않음). 학습은 `cvat-autolabel:creamoff-2.73.1` 컨테이너에서 `runs.sh 이름:ann파일:data_root ...`. **10-26까지의 이 폴더 학습은 정답 상자를 넓히지 않고 mmpose 기본 1.25배로 넣었습니다.** 채점(긴 변 15% 넓힌 뒤 1.25배)보다 좁게 잘린 사진으로 배운 것이라, 이 결과로 "이어 학습은 손해"라고 단정하지 않습니다(위 상자 여백 항목 참고).
- `labels/`의 CVAT 보조 스크립트(`assign.py`, `pilot_fetch.py`, `review_task.py` 등)는 CVAT 프로필 `local`이 저장된 autolabel 컨테이너에서 돌립니다.

## 올리지 않는 것

`models/`, `results/`, `train/creamoff46.py`, `cv/`와 `pl/`의 데이터, 결과, 영상 목록은 실행하면 생기는 산출물이거나 기업 자료에서 나온 것이라 `.gitignore`에 넣었습니다. `creamoff46.py`는 `train/make_meta.py`가 현행 모델 가중치에서 만듭니다.

## `smooth/normalize.py`

**박규원 님의 `ai/normalize/normalize.py`(a6ded31)를 수정 없이 복사한 파일입니다.** 실험 컨테이너에는 이 폴더만 연결해서 평활과 같이 돌리려고 옆에 두었습니다. 원본이 바뀌면 다시 복사하고, 고칠 일이 있으면 원본에서 고칩니다.
