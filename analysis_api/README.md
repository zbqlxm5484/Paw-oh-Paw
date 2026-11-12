# 분석 API

영상 한 건을 받아 분석하고, 진행 상태와 결과(관절점·판별·보행 수치)를 돌려주는 FastAPI 서버다. 팀 서비스(`backend/`)는 `backend/app/clients/analysis.py`의 `HttpAnalysisClient`로 이 API를 부른다. 납품 때는 기업 서버가 같은 자리에서 부른다.

부르는 쪽을 위한 명세(엔드포인트·오류·상태·부르는 순서)는 `docs/analysisApi/apiSpec.md`다. 이 README는 서버를 띄우고 운영하는 법을 적는다.

형식 근거: `docs/analysisApi/resultFormat.md`(결과 JSON v1), 「분석 API 형식과 구현 계획」(10-21), 「분석 API 초안 검토 답변」(10-22)

## 단계 (4/4 완료)

| 단계 | 내용 | 상태 |
| --- | --- | --- |
| (1/4) 뼈대 | 엔드포인트, 상태값, 공통 오류 형식 | 완료 |
| (2/4) 등록·상태 | 영상 저장, 인증, 업로드 한도, 응답 뒤 분석 | 완료 |
| (3/4) 엔진 연결 | 관절점 → 유효 판별(`engine/validity.py`) → 결과 JSON v1·관절점 파일 | 완료 |
| (4/4) 모델 전환·결과 기록 | `models.yaml`로 모델 고르기, 작업 상태·결과를 디스크에 남기기, 끝난 작업 기록 | 완료 |

| 파일 | 맡은 일 |
| --- | --- |
| `main.py` | HTTP, 인증, 영상 저장, 작업 상태 |
| `pipeline.py` | 영상 → 관절점 → 엔진(유효 판별, 관절 각도) → 결과 JSON과 관절점 파일 |
| `store.py` | 작업 상태·결과·관절점 파일을 디스크에 쓰고 읽기, 끝난 작업 기록(`analyses.jsonl`) |
| `models.yaml` | 쓸 수 있는 모델 목록과 기본 모델 |

## 관절점을 어디서 얻나 (`ANALYSIS_POSE_SOURCE`)

| 값 | 하는 일 | 쓰는 때 |
| --- | --- | --- |
| `sample` (기본) | `samples/`의 견본 결과를 돌려준다. `model.name`이 `sample-pipeline` | 팀 서비스 연동 시험. 모델·관절점 파일 없이 |
| `track` | 미리 뽑아 둔 관절점 파일(고른 모델의 `track_file`, 기업 `video_kpi.py track` 형식)에서 올린 영상을 찾아 **실제 엔진**을 돌린다 | GPU·모델 없이 실제 판별 결과를 볼 때 |
| `model` | 올린 영상의 프레임마다 기업 모델(RTMDet 개 탐지 + RTMPose 관절 22점, `ANALYSIS_MODEL_DIR`의 `run.py`)로 관절점을 뽑아 같은 엔진을 돌린다. 추론은 한 번에 하나씩 한다 | GPU 서버 운영(허정원 S15P31A404-229) |

`track`은 올린 영상의 SHA-256과 같은 영상을 먼저 찾고, 없으면 파일 이름으로 찾는다. 둘 다 없으면 `failed` + `POSE_UNAVAILABLE`이다.

`track`은 시연·개발용이다. 쓸 때 주의할 것:

- 파일 이름으로 찾을 때는 내용을 확인하지 않는다. 서로 다른 영상이 같은 이름이면 엉뚱한 관절점으로 그럴듯한 결과가 나온다. 결과를 믿어야 할 때는 관절점을 뽑은 원본 영상 그대로 올린다(SHA-256으로 찾힘)
- 관절점 파일은 처음 읽은 내용을 기억해 둔다. 서버를 켜 둔 채 파일을 바꾸면 서버를 다시 켜야 새 내용이 쓰인다
- 관절점 파일 `meta.model.name`이 고른 모델과 다르면 `POSE_UNAVAILABLE`이다. 다른 모델로 뽑은 관절점에 이 모델 이름을 붙이지 않기 위해서다
- 폰으로 새로 찍은 영상은 관절점 파일에 없으니 `POSE_UNAVAILABLE`이다. 엔진 결과를 보이려면 관절점을 만든 원본 영상 파일을 그대로 올린다

## 모델 고르기 (`models.yaml`)

`models.yaml`에 쓸 수 있는 모델(`fs-v4`, `fs-v4-flip`)과 기본 모델(`default`)이 있다. `ANALYSIS_MODEL`로 다른 모델을 고르고 서버를 다시 켠다. 모델마다 관절점 파일(`track_file`, 저장소 루트 기준)과 가중치 해시(`weights_sha256`)를 둔다.

- 모델을 바꾸면 결과의 `model.name`·`model.version`이 바뀐다. 팀 서비스는 모델이 다른 회차끼리 변화를 판단하지 않는다(`MODEL_CHANGED`)
- `models.yaml`에 없는 이름을 고르면 다른 모델로 바꿔 돌리지 않고 `POSE_UNAVAILABLE`로 실패한다. `/health`의 `model_known`이 false로 보인다
- `pipeline.py`의 `API_VERSION`은 결과가 바뀌는 변경(엔진·결과 형식)일 때만 올린다. `model.version`에 들어가서, 올리면 그 전 회차와 비교하지 않게 되기 때문이다. 4/4는 결과를 바꾸지 않아 0.4.0 그대로였고, 보행 수치를 채운 #183에서 0.5.0, 가동 범위를 채운 #184에서 0.6.0으로 올렸다. 발 높이를 더한 #259는 있던 수치의 값을 바꾸지 않아 0.6.0 그대로 두고 `versions.gait_metrics`만 v2로 올렸다(지난 회차와 비교가 끊기지 않게)

지금 결과에서 비어 있는 것: `metrics`의 발 경사·발 움직임 범위(걸음 길이·입각기 비율·보행 속도·주기 수(#183), 가동 범위·각도 중앙값·무릎 주기별 가동 범위(#184), 발 높이와 측정 불가 문장(#259)은 채움), `gait`는 null(보행 유형 판별 뒤), `input.codec`는 null.

## 실행

`analysis_api` 폴더에서 실행한다. 엔진은 저장소 루트의 `engine/`을 그대로 불러 쓴다. 팀 서비스(8000)와 겹치지 않게 8010 포트를 쓴다.

```powershell
pip install -r requirements-dev.txt
uvicorn main:app --reload --port 8010
```

관절점 파일로 실제 엔진을 돌려 보려면 실행 전에 환경변수를 넣는다. 관절점 파일은 기업 데이터에서 나온 것이라 `data/` 아래에 두고 git에 올리지 않는다.

```powershell
$env:ANALYSIS_POSE_SOURCE = "track"
uvicorn main:app --reload --port 8010
```

관절점 파일은 `models.yaml`의 `track_file` 자리(`data/tracks/fs-v4.track.json` 등)에 둔다. 다른 곳에 있으면 `$env:ANALYSIS_TRACK_FILE`로 그 경로를 준다.

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
| `ANALYSIS_MODEL` | `models.yaml`의 `default` | 쓸 모델 이름. 결과 `model.name`이 된다 |
| `ANALYSIS_MODEL_DIR` | 홈의 `models/company-orig` | `model`일 때 기업 모델 폴더(`run.py`, `det.py`, `pose.py`, `det.pth`, `pose.pth`). 하나라도 없으면 `/health`의 `model_known`이 false, 분석은 `POSE_UNAVAILABLE` |
| `ANALYSIS_TRACK_FILE` | 고른 모델의 `track_file` | `track`일 때 읽을 관절점 파일. 주면 `models.yaml` 값보다 먼저 쓴다 |
| `ANALYSIS_WEIGHTS_SHA256` | 고른 모델의 `weights_sha256`, `model`이면 `pose.pth`에서 계산 | 관절점을 뽑은 가중치의 SHA-256. 주면 `models.yaml` 값보다 먼저 쓴다. 앞 8자가 `model.version` 끝에 붙는다(`0.6.0/v1/a4261a10`). 비어 있으면 버전 끝은 `unknown`, `model.weights_sha256`은 null |
| `ANALYSIS_JOB_TIMEOUT_SEC` | 660 | 분석이 이보다 오래 `running`이면 `failed` + `TIMEOUT`. 팀 서비스 `ANALYSIS_TIMEOUT_SEC`(600)보다 60초 길게 둔다: 팀 서비스가 먼저 실패로 처리하고, 그 뒤 다시 분석·지우기가 409로 막히는 시간이 1분을 넘지 않게 한다. GPU 추론이 멈춰도 작업이 계속 running으로 남아 지우기·다시 분석이 막히지 않게 하려는 것이다 |

`/health`는 Docker 상태 확인용이라 인증 없이 열려 있다. 지금 모델(`model`), 관절점 출처(`pose_source`), 모델이 `models.yaml`에 있는지(`model_known`)를 함께 준다.

## 작업 기록 (`ANALYSIS_STORAGE_DIR`)

```
data/analysis_api/
  analyses.jsonl          끝난 작업 한 줄씩 (모델, 엔진 버전, 판정, 실패 사유, 영상 SHA-256, 걸린 시간. 파일 이름은 남기지 않음)
  {작업 ID}/
    video.mp4             올린 영상
    job.json              작업 상태
    result.json           결과 JSON v1 (done일 때)
    keypoints.json        관절점 파일 (done일 때)
```

- 분석 API를 다시 켜도 끝난 작업(done·failed)은 그대로 조회된다. 메모리에 없으면 디스크에서 읽는다
- 분석 중(queued·running)에 꺼진 작업은 다시 켤 때 `failed` + `INTERRUPTED`로 바꾼다. 팀 서비스는 다시 분석으로 안내한다
- `analyses.jsonl`은 모델을 바꿔 가며 돌린 결과를 나중에 비교하는 기록이다. 영상의 SHA-256이 들어 있어 같은 영상끼리 맞춰 볼 수 있다
- 파일은 임시 이름으로 다 쓴 뒤 이름을 바꿔 넣어, 쓰는 도중에 꺼져도 반쯤 쓴 파일이 남지 않는다
- 기업 영상 이름에는 반려견 이름이 들어 있어 `analyses.jsonl`에 파일 이름을 남기지 않는다. 같은 영상끼리는 SHA-256으로 맞춘다

## 지우기 (자료 파기)

팀 서비스 자료 파기(`backend/scripts/purge.py`, `POST /admin/purge`)는 팀 서비스 쪽 파일과 DB만 지운다. 같은 영상과 결과가 분석 API 저장소에도 남으므로 여기서도 지운다(백엔드 명세 7절·15.9).

| 무엇을 | 방법 |
| --- | --- |
| 작업 하나 | `DELETE /analyses/{id}`: 올린 영상·작업 상태·결과·관절점 파일(폴더째)과 `analyses.jsonl`의 그 줄. 성공 204. 분석 중(queued·running)이면 409 `JOB_IN_PROGRESS`, 없으면 404(부르는 쪽은 "이미 없음"으로 본다), 폴더를 다 지우지 못하면 500 `DELETE_FAILED`(기록 줄은 남기고 다시 시도) |
| 촬영 하나 | `DELETE /analyses?shot_id=...`: 그 촬영(등록 때 `meta.shot_id`)으로 만든 작업을 모두 지운다. 다시 분석하면 한 촬영에 작업이 여러 개 생기므로, 예전 작업까지 지우려는 것이다. 200 `{"shot_id", "deleted": [작업 ID]}`(없으면 빈 목록). 하나라도 분석 중이면 아무것도 지우지 않고 409 `JOB_IN_PROGRESS` |
| 전체 | `python purge.py --all`은 지울 양만 센다. `python purge.py --all --execute`는 확인 문구 `PURGE`를 받고 저장소 아래 작업 폴더(이름이 작업 ID인 UUID 모양인 폴더. `job.json`이 없는, 업로드 도중 끊긴 폴더도)와 `analyses.jsonl`을 지운다(`--yes`면 묻지 않음). 이름이 UUID가 아닌 폴더·파일은 지우지 않고 개수만 알린다(`ANALYSIS_STORAGE_DIR`를 `data/`처럼 넓게 잘못 줘도 `data/tracks/`가 남는다). 분석 중인 작업이 있으면 지우지 않는다. 분석 API를 끈 뒤 돌린다 |

관절점 파일(`data/tracks/`)과 `models.yaml`은 지우지 않는다. 관절점 파일도 기업 데이터에서 나온 것이라 과제 종료 때는 따로 지운다.

## 처리 흐름

1. `POST /analyses`: 영상을 저장소에 쓰고 작업을 `queued`로 만든 뒤 바로 `202`와 작업 ID를 돌려준다
2. 응답이 나간 뒤 분석이 돈다. `running` → `done`, 실패하면 `failed`와 `error.code`
3. 팀 서비스가 `GET /analyses/{id}`로 상태를 조회하고, `done`이면 결과와 관절점 파일을 받는다

분석을 요청 안에서 돌리지 않는 이유는 팀 서비스가 30초(`ANALYSIS_HTTP_TIMEOUT_SEC`) 안에 답을 받아야 하기 때문이다.

실패(`failed`)와 무효(`done` + `validity: invalid`)는 다르다. 실패는 시스템이 분석을 끝내지 못한 경우라 다시 분석하고, 무효는 분석은 됐지만 영상을 쓸 수 없는 경우라 다시 촬영한다.

| 실패 사유 `error.code` | 뜻 |
| --- | --- |
| `DECODE_FAILED` | 영상을 읽을 수 없음 |
| `POSE_UNAVAILABLE` | 이 영상의 관절점을 얻지 못함 (`track`에서 관절점 파일이 없거나, 영상을 못 찾거나, 관절점 파일의 모델이 다름) |
| `INTERRUPTED` | 분석 중에 분석 API가 다시 시작됨 |
| `INTERNAL` | 분석 중 알 수 없는 오류(추론 중 GPU 메모리 부족 등) |
| `TIMEOUT` | 분석이 `ANALYSIS_JOB_TIMEOUT_SEC` 안에 끝나지 않음. 상태 조회·지우기 때 판단한다. 시간 초과 뒤에 늦게 끝난 분석의 결과는 버리고, 그사이 지운 작업의 폴더를 다시 만들지 않는다. 멈춘 GPU 추론 자체를 끊지는 못하므로, 계속 멈춰 있으면 분석 API를 다시 켠다 |

등록·조회 말고 지우기에서 나는 오류: 409 `JOB_IN_PROGRESS`(분석 중인 작업은 지울 수 없음), 500 `DELETE_FAILED`(폴더를 다 지우지 못함).

업로드가 도중에 끊기면 그때까지 쓴 영상을 지운다(크기 초과 413과 같다). `analyses.jsonl`에 깨진 줄(쓰는 도중 꺼진 것)이 있으면 읽을 때 건너뛰고, 작업을 지울 때 함께 버린다.

## 테스트

저장소 루트의 `pyproject.toml`은 `tests/`만 모으므로, 이 폴더에서 따로 돌린다.

```powershell
python -m pytest -q
```

`test_pipeline.py`는 가상 개 한 마리의 관절점 파일을 만들어 `track` 경로를 확인한다(결과 v1 필드, 카메라 쪽 다리 각도만, `POSE_UNAVAILABLE`). `test_store.py`는 메모리를 비워 다시 켠 것처럼 만든 뒤 작업이 남는지, 끊긴 작업이 `INTERRUPTED`가 되는지, `analyses.jsonl`, 모델 고르기를 확인한다.

## 떠 있는 서버 점검 (`check_server.py`)

GPU 서버에 배포한 분석 API를 팀 서비스 워커와 같은 순서(등록 → 2초마다 상태 조회 → 결과·관절점 파일 → 지우기)로 불러, 결과가 결과 JSON v1 모양인지와 걸린 시간을 본다. 표준 라이브러리만 쓴다.

```
ANALYSIS_API_KEY=... python check_server.py --url http://127.0.0.1:8010 --video a.mp4 --video b.mp4
python check_server.py --url ... --video a.mp4 --track ../data/tracks/fs-v4.track.json   # 미리 뽑은 관절점과 비교
```

- 키는 환경변수 `ANALYSIS_API_KEY`로만 받는다(명령 줄에 남지 않게)
- 점검한 작업은 끝나면 지운다(`--keep`이면 남김). 점검 영상의 사본이 서버에 남지 않게 하려는 것이다
- `--track`을 주면 같은 영상의 미리 뽑은 관절점과 프레임 수·개를 찾은 프레임 수·관절점 위치 차이(px)를 비교한다. model 모드가 오프라인 추론과 같은 관절점을 내는지 보는 것이다
- 하나라도 걸리면 끝 코드 1. 점검 기록은 `docs/analysisApi/gpuCheck.md`

## 아직 남은 것

- 지금은 응답 뒤 같은 프로세스 안에서 분석한다(FastAPI `BackgroundTasks`). 모델 추론은 잠금으로 한 번에 하나씩 돈다. 동시에 많이 들어오면 차례로 기다리므로, 늘어나면 작업 큐로 옮긴다
- 오래된 작업·영상을 기간이 지나면 저절로 지우기(지금은 지우기 API·전체 파기 명령으로만)
- `/docs`·`/openapi.json`이 인증 없이 열려 있다. 외부에 여는 서버라면 앞단에서 막는다(`apiSpec.md` 7.4)
