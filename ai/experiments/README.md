# 로컬 실험 스크립트

GPU 서버를 받기 전에 노트북(RTX 4070, Docker)에서 돌린 경량화, 시간 평활, 미세조정 준비 실험 코드입니다. 결과와 해석은 위키 `90-원본/작업-기록/261021-경량화와-평활-시험-결과`에, 다시 점검할 점은 `NOTES.md`에 있습니다.

기업 자료(`paw_eval`, 가중치, 영상, 정답)는 들어 있지 않습니다. 실행할 때 기업 전달본 폴더를 컨테이너에 연결해서 씁니다.

## 폴더

| 폴더 | 내용 |
| --- | --- |
| `run` | 실행 스크립트. `setup.sh`가 `paw_eval`을 `/work`로 복사하고 탐지 건너뛰기 실행부를 `speed.py`에 등록합니다 |
| `stacks` | 탐지 건너뛰기 실행부(`skipdet.py`). 키프레임에서만 탐지하고 사이는 상자를 보간합니다 |
| `smooth` | 시간 평활(`smooth_track.py`), 평활이 점을 움직인 양 확인(`blur_check.py`), 좌표 정규화(`normalize.py`) |
| `train` | 미세조정 설정(`ft_base.py`)과 46점 학습 데이터 만들기, CPU 점검 스크립트 |

## 실행

기업 Docker 이미지 `cvat-autolabel:creamoff-2.73.1`에서 돌립니다. 컨테이너 안 경로는 아래처럼 맞춥니다.

- `/ssafy`: 기업 전달본 폴더(`paw_eval`, `dataset`, `model`). 읽기 전용
- `/exp`: 이 폴더

```
docker run --rm --gpus all -e PYTHONUTF8=1 -v "<전달본 폴더>:/ssafy:ro" -v "<이 폴더>:/exp" cvat-autolabel:creamoff-2.73.1 bash -c "bash /exp/run/setup.sh && cd /work/ssafy/paw_eval && python /exp/run/make_models.py"
docker run --rm --gpus all -e PYTHONUTF8=1 -v "<전달본 폴더>:/ssafy:ro" -v "<이 폴더>:/exp" cvat-autolabel:creamoff-2.73.1 bash /exp/run/run_all.sh
```

- `make_models.py`를 먼저 돌려야 `models/`(FP16 가중치, 해상도별 탐지기 설정, 건너뛰기 설정)가 생깁니다.
- `run_all.sh`의 FP16 비교는 재현 기록 결과(`/ssafy/재현기록-261021/fs-v4.json`)가 있어야 돌아갑니다.
- `train/smoke.sh`, `train/smoke_wow.sh`는 학습이 도는지만 보는 점검용입니다. 결과를 성능으로 쓰지 않습니다.

## 올리지 않는 것

`models/`, `results/`, `train/creamoff46.py`는 실행하면 생기는 산출물이라 `.gitignore`에 넣었습니다. `creamoff46.py`는 `train/make_meta.py`가 현행 모델 가중치에서 만듭니다.

## `smooth/normalize.py`

**박규원 님의 `ai/normalize/normalize.py`(a6ded31)를 수정 없이 복사한 파일입니다.** 실험 컨테이너에는 이 폴더만 연결해서 평활과 같이 돌리려고 옆에 두었습니다. 원본이 바뀌면 다시 복사하고, 고칠 일이 있으면 원본에서 고칩니다.
