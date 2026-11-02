# 분석 API

영상 한 건을 받아 분석하고, 진행 상태와 결과(관절점·판별·보행 수치)를 돌려주는 FastAPI 서버다. 팀 서비스(`backend/`)는 `backend/app/clients/analysis.py`의 `HttpAnalysisClient`로 이 API를 부른다. 납품 때는 기업 서버가 같은 자리에서 부른다.

형식 근거: `docs/analysisApi/resultFormat.md`(결과 JSON v1), 「분석 API 형식과 구현 계획」(10-21), 「분석 API 초안 검토 답변」(10-22)

## 지금 단계 (3/4)

| 단계 | 내용 | 상태 |
| --- | --- | --- |
| (1/4) 뼈대 | 엔드포인트, 상태값, 공통 오류 형식 | 완료 |
| (2/4) 등록·상태 | 영상 저장, 인증, 업로드 한도, 응답 뒤 분석 | 완료 |
| (3/4) 엔진 연결 | 관절점 → 유효 판별(`engine/validity.py`) → 결과 JSON v1·관절점 파일 | **지금** |
| (4/4) 모델 전환·결과 기록 | 모델 전환 설정, 결과 기록, 연동 시험 | 다음 |

| 파일 | 맡은 일 |
| --- | --- |
| `main.py` | HTTP, 인증, 영상 저장, 작업 상태 |
| `pipeline.py` | 영상 → 관절점 → 엔진(유효 판별, 관절 각도) → 결과 JSON과 관절점 파일 |

## 관절점을 어디서 얻나 (`ANALYSIS_POSE_SOURCE`)

| 값 | 하는 일 | 쓰는 때 |
| --- | --- | --- |
| `sample` (기본) | `samples/`의 견본 결과를 돌려준다. `model.name`이 `sample-pipeline` | 팀 서비스 연동 시험. 모델·관절점 파일 없이 |
| `track` | 미리 뽑아 둔 관절점 파일(`ANALYSIS_TRACK_FILE`, 기업 `video_kpi.py track` 형식)에서 올린 영상을 찾아 **실제 엔진**을 돌린다 | GPU·모델 없이 실제 판별 결과를 볼 때 |

`track`은 올린 영상의 SHA-256과 같은 영상을 먼저 찾고, 없으면 파일 이름으로 찾는다. 둘 다 없으면 `failed` + `POSE_UNAVAILABLE`이다. 영상에서 바로 관절점을 뽑는 경로(MMPose)는 실행 환경이 정해지면 `pipeline.py`에 더한다.

지금 결과에서 비어 있는 것: `metrics`는 `{}`(걸음 길이·입각기 비율, 가동 범위 계산 뒤), `gait`는 null(보행 유형 판별 뒤), `input.codec`는 null.

## 실행

`analysis_api` 폴더에서 실행한다. 엔진은 저장소 루트의 `engine/`을 그대로 불러 쓴다. 팀 서비스(8000)와 겹치지 않게 8010 포트를 쓴다.

```powershell
pip install -r requirements-dev.txt
uvicorn main:app --reload --port 8010
```

관절점 파일로 실제 엔진을 돌려 보려면 실행 전에 환경변수를 넣는다. 관절점 파일은 기업 데이터에서 나온 것이라 `data/` 아래에 두고 git에 올리지 않는다.

```powershell
$env:ANALYSIS_POSE_SOURCE = "track"
$env:ANALYSIS_TRACK_FILE = "..\data\tracks\fs-v4.track.json"
uvicorn main:app --reload --port 8010
```

브라우저에서 `http://127.0.0.1:8010/docs`를 열면 엔드포인트를 직접 불러 볼 수 있다.

팀 서비스와 붙여 보려면 `backend/.env`에 아래처럼 넣는다.

```
ANALYSIS_API_MODE=http
ANALYSIS_API_BASE_URL=http://127.0.0.1:8010
ANALYSIS_API_KEY=
```

## 설정 (환경변수)

| 이름 | 기본값 | 뜻 |
| --- | --- | --- |
| `ANALYSIS_API_KEY` | 비어 있음 | 비어 있으면 인증을 끈다(로컬 개발). 있으면 요청의 `X-API-Key` 헤더가 같아야 하고, 아니면 401 `AUTH_REQUIRED`. 팀 서비스의 `ANALYSIS_API_KEY`와 같은 값을 넣는다 |
| `ANALYSIS_UPLOAD_MAX_MB` | 100 | 영상 한 건 상한. 넘으면 413 `TOO_LARGE`. 팀 서비스 `UPLOAD_MAX_MB`, nginx `client_max_body_size`와 맞춘다 |
| `ANALYSIS_STORAGE_DIR` | 저장소의 `data/analysis_api` | 올린 영상을 `{작업 ID}/video.mp4`(또는 `.mov`)로 둔다. `data/`는 git에 올라가지 않는다 |
| `ANALYSIS_POSE_SOURCE` | `sample` | 위 표 |
| `ANALYSIS_TRACK_FILE` | 비어 있음 | `track`일 때 읽을 관절점 파일 |
| `ANALYSIS_MODEL_NAME` | `fs-v4` | 결과 `model.name`. 관절점 파일 `meta.model.name`이 있으면 그것을 쓴다 |
| `ANALYSIS_WEIGHTS_SHA256` | 비어 있음 | 관절점을 뽑은 가중치의 SHA-256. 앞 8자가 `model.version` 끝에 붙는다(`0.4.0/v1/a4261a10`). 비어 있으면 `unknown` |

`/health`는 Docker 상태 확인용이라 인증 없이 열려 있다.

## 처리 흐름

1. `POST /analyses`: 영상을 저장소에 쓰고 작업을 `queued`로 만든 뒤 바로 `202`와 작업 ID를 돌려준다
2. 응답이 나간 뒤 분석이 돈다. `running` → `done`, 실패하면 `failed`와 `error.code`
3. 팀 서비스가 `GET /analyses/{id}`로 상태를 조회하고, `done`이면 결과와 관절점 파일을 받는다

분석을 요청 안에서 돌리지 않는 이유는 팀 서비스가 30초(`ANALYSIS_HTTP_TIMEOUT_SEC`) 안에 답을 받아야 하기 때문이다.

실패(`failed`)와 무효(`done` + `validity: invalid`)는 다르다. 실패는 시스템이 분석을 끝내지 못한 경우라 다시 분석하고, 무효는 분석은 됐지만 영상을 쓸 수 없는 경우라 다시 촬영한다.

| 실패 사유 `error.code` | 뜻 |
| --- | --- |
| `DECODE_FAILED` | 영상을 읽을 수 없음 |
| `POSE_UNAVAILABLE` | 이 영상의 관절점을 얻지 못함 (`track`에서 관절점 파일이 없거나 영상을 못 찾음) |
| `INTERNAL` | 분석 중 알 수 없는 오류 |

## 테스트

저장소 루트의 `pyproject.toml`은 `tests/`만 모으므로, 이 폴더에서 따로 돌린다.

```powershell
python -m pytest -q
```

`test_pipeline.py`는 가상 개 한 마리의 관절점 파일을 만들어 `track` 경로를 확인한다(결과 v1 필드, 카메라 쪽 다리 각도만, `POSE_UNAVAILABLE`).

## 아직 남은 것

- 작업 상태를 메모리(`JOBS`)에 둬서 서버를 끄면 사라진다. 결과 기록 단계(4/4)에서 바꾼다
- 지금은 응답 뒤 같은 프로세스 안에서 분석한다(FastAPI `BackgroundTasks`). 분석이 무거워지면 작업 큐로 옮긴다
- Dockerfile과 compose 서비스, CI에서 이 폴더 테스트 돌리기는 허정원과 정한다. 이미지에는 `engine/`도 함께 넣어야 한다
