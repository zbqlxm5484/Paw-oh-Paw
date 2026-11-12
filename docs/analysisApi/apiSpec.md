# 분석 API 명세서

작성 조유진 · v1 11-12 (S15P31A404-262) · 코드 `analysis_api/` · API 버전 0.6.0

영상 한 건을 받아 반려견의 관절점을 뽑고, 유효 구간을 판별하고, 보행 수치를 계산해 돌려주는 HTTP API다. 팀 서비스(`backend/app/clients/analysis.py`의 `HttpAnalysisClient`)와 납품 뒤 기업 서버가 같은 API를 같은 방식으로 부른다.

이 문서는 **부르는 쪽이 알아야 할 것**(주소, 요청, 응답, 오류, 부르는 순서)을 한곳에 모은 것이다. 결과 JSON의 필드 하나하나는 `resultFormat.md`, 서버를 띄우고 운영하는 법은 `analysis_api/README.md`에 있다.

| 문서 | 내용 |
| --- | --- |
| 이 문서 | 엔드포인트, 인증, 오류, 상태, 부르는 순서, 설정 요약 |
| `docs/analysisApi/resultFormat.md` | 결과 JSON v1과 관절점 파일의 필드, 수치 키와 단위, 사유 코드 |
| `analysis_api/README.md` | 실행, 관절점 출처, 모델 고르기, 저장, 파기 명령, 테스트 |
| `docs/analysisApi/gpuCheck.md` | GPU 서버 점검 기록과 점검 방법 |
| `backend/docs/backend-spec.md` 6절 | 팀 서비스가 이 API를 부르는 방식(여섯 동작, 사본 지우는 순서) |

## 1. 한눈에

| 메서드 | 경로 | 하는 일 | 성공 |
| --- | --- | --- | --- |
| GET | `/health` | 서버·모델 상태 (인증 없음) | 200 |
| POST | `/analyses` | 영상 등록, 분석 시작 | 202 |
| GET | `/analyses/{id}` | 상태 조회 | 200 |
| GET | `/analyses/{id}/result` | 결과 JSON v1 | 200 |
| GET | `/analyses/{id}/files/keypoints` | 관절점 파일 (프레임별 22점·관절 각도) | 200 |
| DELETE | `/analyses/{id}` | 작업 하나 지우기 (영상·결과·기록) | 204 |
| DELETE | `/analyses?shot_id=...` | 촬영 하나로 만든 작업 모두 지우기 | 200 |

- 주소: 서버마다 다르다. 개발 PC `http://127.0.0.1:8010`, GPU 서버 안 `http://127.0.0.1:8010`, 팀 서버에서는 터널 `http://host.docker.internal:18010`
- 형식: 요청은 `multipart/form-data`(등록)와 쿼리, 응답은 모두 JSON(UTF-8)이다. 시각은 한국 시간 ISO 8601(`2026-11-12T09:03:55+09:00`)
- `/docs`(Swagger 화면)와 `/openapi.json`이 인증 없이 열려 있다. 외부에 공개하는 서버라면 앞단에서 막는다(7.4)

## 2. 공통

### 2.1 인증

- 서버에 `ANALYSIS_API_KEY`가 있으면 요청 헤더 `X-API-Key`가 같아야 한다. 없거나 다르면 401 `AUTH_REQUIRED`
- 서버의 `ANALYSIS_API_KEY`가 비어 있으면 인증을 끈다(로컬 개발용). 배포 서버에서는 반드시 넣는다
- `/health`만 인증 없이 연다(Docker 상태 확인용)
- 키는 시간 차이로 새지 않게 일정 시간 비교(`hmac.compare_digest`)를 쓴다. 키를 명령 줄·로그·저장소에 남기지 않는다

### 2.2 오류 형식

이 API가 낸 오류는 모두 한 모양이다.

```json
{"error": {"code": "NOT_FOUND", "message": "없는 분석입니다", "detail": null}}
```

- 부르는 쪽은 `code`로 가르고, `message`는 로그·화면용 한국어 문장이다
- 예외: 없는 경로(404)와 그 경로에 없는 메서드(405)는 FastAPI 기본 모양 `{"detail": "Not Found"}`, `{"detail": "Method Not Allowed"}`로 온다. 팀 서비스는 촬영 단위 지우기의 405를 "이 기능이 없는 옛 판"으로 본다(6.3)

### 2.3 HTTP 오류 코드

| HTTP | `code` | 언제 | 어디서 |
| --- | --- | --- | --- |
| 400 | `INVALID_REQUEST` | 필수 항목이 없거나 형식이 틀림(영상 없음, `shot_id` 없음·빈 값) | 등록, 촬영 지우기 |
| 400 | `INVALID_META` | `meta`가 JSON 객체가 아님 | 등록 |
| 401 | `AUTH_REQUIRED` | `X-API-Key`가 없거나 맞지 않음 | `/health` 말고 전부 |
| 404 | `NOT_FOUND` | 없는 작업(지웠거나 다른 서버의 ID) | 조회, 결과, 관절점, 작업 지우기 |
| 409 | `NOT_READY` | 결과가 없음. `status`가 `done`이 아니면 다 이것이다(`queued`·`running`·`failed`) | 결과, 관절점 |
| 409 | `JOB_IN_PROGRESS` | 분석 중(`queued`·`running`)이라 지울 수 없음 | 작업 지우기, 촬영 지우기 |
| 413 | `TOO_LARGE` | 영상이 `ANALYSIS_UPLOAD_MAX_MB`(기본 100MB)를 넘음 | 등록 |
| 415 | `UNSUPPORTED_MEDIA` | 영상의 `Content-Type`이 `video/`로 시작하지 않음 | 등록 |
| 500 | `DELETE_FAILED` | 폴더를 다 지우지 못함. 다시 부르면 이어서 지운다 | 작업 지우기, 촬영 지우기 |

- 409 `NOT_READY`는 실패한 작업에도 나온다. 결과를 부르기 전에 상태를 먼저 보고, `failed`면 결과를 부르지 않는다
- 분석이 실패한 것은 HTTP 오류가 아니다. 상태 조회가 200에 `status: failed`와 `error.code`(3.2)를 준다

## 3. 작업 상태

### 3.1 흐름

```
POST /analyses ─▶ queued ─▶ running ─▶ done
                                   └─▶ failed (error.code)
```

- 등록은 영상을 저장한 뒤 바로 202를 준다. 분석은 응답이 나간 뒤 서버 안에서 돈다. 부르는 쪽의 요청 시간 한도(팀 서비스 30초) 안에 분석이 끝나지 않기 때문이다
- 작업은 디스크에 남는다. 서버를 다시 켜도 `done`·`failed` 작업은 그대로 조회된다
- 분석 중에 서버가 꺼진 작업은 다시 켤 때 `failed` + `INTERRUPTED`가 된다
- `running`이 `ANALYSIS_JOB_TIMEOUT_SEC`(기본 660초)를 넘으면 조회·지우기 때 `failed` + `TIMEOUT`이 된다. 그 뒤 늦게 끝난 분석 결과는 버린다
- 모델 추론은 `ANALYSIS_MODEL_WORKERS`개(기본 1)까지 동시에 돈다. 넘치게 등록하면 차례로 분석되고, 기다리는 동안은 `running`이다. **기다린 시간도 `ANALYSIS_JOB_TIMEOUT_SEC`에 들어간다.** 한꺼번에 많이 등록하면 뒤쪽 작업은 추론을 시작하기 전에 `TIMEOUT`이 될 수 있다

### 3.2 분석 실패 사유 (`error.code`)

| `error.code` | 뜻 | 부르는 쪽이 할 일 |
| --- | --- | --- |
| `DECODE_FAILED` | 영상을 읽을 수 없음(빈 파일, 손상, 지원하지 않는 코덱) | 영상을 확인해 다시 올림 |
| `POSE_UNAVAILABLE` | 관절점을 얻지 못함(모델 파일 없음, 모델 적재 실패, 영상에서 개를 못 찾음, 관절점 파일에 이 영상이 없음) | 서버 설정 확인. 개가 안 보이면 다시 촬영 |
| `INTERRUPTED` | 분석 중에 서버가 다시 시작됨 | 다시 분석 |
| `TIMEOUT` | 분석이 시간 한도 안에 끝나지 않음 | 다시 분석. 계속 나면 서버 확인 |
| `INTERNAL` | 그 밖의 오류(추론 중 GPU 메모리 부족 등) | 다시 분석. 계속 나면 서버 로그 확인 |

**실패와 무효는 다르다.** 실패(`failed`)는 시스템이 분석을 끝내지 못한 것이라 같은 영상으로 다시 분석한다. 무효(`done`에 `validity: "invalid"`)는 분석은 끝났지만 그 영상으로는 잴 수 없다는 판정이라 다시 촬영한다. 무효 사유는 결과 JSON의 `validity_reason`과 통과마다의 `reason_code`에 있다(`resultFormat.md` 4절).

## 4. 엔드포인트

### 4.1 `GET /health`

인증 없음. 서버가 떠 있는지와 지금 모델을 준다.

```json
{"status": "ok", "model": {"name": "fs-v4", "version": "0.6.0/v1/a4261a10"}, "pose_source": "model", "model_known": true}
```

| 필드 | 뜻 |
| --- | --- |
| `model` | 지금 결과에 붙는 모델 이름과 버전(8절) |
| `pose_source` | 관절점을 어디서 얻나: `model`(영상에서 모델로 추론), `track`(미리 뽑은 관절점 파일), `sample`(견본 결과, 연동 시험용) |
| `model_known` | 고른 모델이 `models.yaml`에 있고, `model`이면 모델 파일도 다 있음. `false`면 분석이 `POSE_UNAVAILABLE`로 실패한다 |

배포 뒤에는 `status`만 보지 말고 `model_known`이 `true`인지, `pose_source`가 의도한 값인지 함께 본다.

### 4.2 `POST /analyses`

영상 한 건을 등록한다. `multipart/form-data`.

| 부분 | 필수 | 내용 |
| --- | --- | --- |
| `video` | 예 | 영상 파일. `Content-Type`이 `video/`로 시작해야 한다(`video/mp4`, `video/quicktime`). 확장자 `.mp4`·`.mov`로 저장하고 그 밖은 `.mp4`로 둔다 |
| `meta` | 아니오 | JSON 객체 문자열. `shot_id`(촬영 ID)를 넣으면 촬영 단위 지우기(4.7)에 쓴다. **`shot_id`는 문자열로 보낸다**(`"s-001"`, UUID 문자열). 숫자(`123`)로 보내면 그대로 저장돼, 쿼리 문자열과 비교하는 촬영 단위 지우기에 걸리지 않는다. 팀 서비스는 `{"shot_id": "...", "size_class": "SMALL"}`을 보낸다. 다른 키는 저장만 하고 분석에 쓰지 않는다 |

응답 202:

```json
{"id": "7c1f3a52-9d4e-4b8a-a2f1-0c6e5b9d1a77", "status": "queued"}
```

- `id`는 UUID다. 이후 모든 호출에 쓴다
- 오류: 400 `INVALID_REQUEST`(영상 없음), 400 `INVALID_META`, 401, 413 `TOO_LARGE`, 415 `UNSUPPORTED_MEDIA`
- 업로드가 끊기거나 크기를 넘으면 그때까지 받은 영상을 지운다
- 같은 영상을 다시 올리면 새 작업이 생긴다(중복을 막지 않는다). 응답을 못 받고 다시 보냈다면 앞의 작업이 서버에 남을 수 있으니, `shot_id`를 넣어 두고 촬영 단위로 지운다

curl 예:

```
curl -X POST http://127.0.0.1:8010/analyses -H "X-API-Key: $ANALYSIS_API_KEY" \
  -F "video=@shot.mp4;type=video/mp4" -F 'meta={"shot_id":"s-001"}'
```

### 4.3 `GET /analyses/{id}`

상태 조회. 응답 200:

```json
{
  "id": "7c1f3a52-9d4e-4b8a-a2f1-0c6e5b9d1a77",
  "shot_id": "s-001",
  "status": "failed",
  "error": {"code": "DECODE_FAILED", "message": "영상을 읽을 수 없습니다", "detail": null},
  "model": {"name": "fs-v4", "version": "0.6.0/v1/a4261a10"},
  "created_at": "2026-11-12T09:03:55+09:00",
  "updated_at": "2026-11-12T09:03:56+09:00"
}
```

| 필드 | 뜻 |
| --- | --- |
| `status` | `queued`, `running`, `done`, `failed` |
| `error` | `failed`일 때만 `{code, message, detail}`(3.2), 그 밖에는 `null` |
| `model` | 이 작업에 쓴 모델. 등록 때 정해진다 |
| `shot_id` | 등록 때 `meta.shot_id`. 없으면 `null` |

오류: 401, 404 `NOT_FOUND`.

### 4.4 `GET /analyses/{id}/result`

`status`가 `done`일 때 결과 JSON v1을 준다. 모양과 필드는 `resultFormat.md` 1절에서 4절이다. 요약하면:

| 최상위 필드 | 내용 |
| --- | --- |
| `validity`, `validity_reason`, `validity_reason_text` | 촬영 판정(`valid`·`partial`·`invalid`)과 사유 |
| `summary` | 통과 수, 쓴 통과, 뺀 통과 |
| `passes[]` | 통과마다 방향·카메라 쪽·유효 여부·사유·측정 구간·수치(`metrics`) |
| `model`, `versions` | 모델과 엔진 버전(8절) |
| `input` | 영상 정보(프레임 수, fps, 크기) |

- 수치는 유효 통과에만 있고, 잴 수 없으면 0이 아니라 `{"value": null, "reason": "...", "reason_detail": "..."}`다
- 오류: 401, 404, 409 `NOT_READY`(`done`이 아님)

### 4.5 `GET /analyses/{id}/files/keypoints`

`done`일 때 관절점 파일을 준다. 프레임마다 카메라 쪽, 관절점 22개(`[x, y, 확신도]`, 원본 영상 픽셀), 카메라 쪽 다리의 굽힘 각도가 있다. 결과 영상(관절점을 겹쳐 그린 영상)과 관절 각도 그래프를 만들 때 쓴다. 모양은 `resultFormat.md` 5절.

- `frame`은 0부터, 원본을 처음부터 읽은 순서다. 개를 못 찾은 프레임은 `points`가 `null`이다
- 영상 길이에 따라 수 MB가 될 수 있다. 결과보다 늦게, 필요할 때 받는다
- 오류: 401, 404, 409 `NOT_READY`

### 4.6 `DELETE /analyses/{id}`

작업 하나를 지운다. 올린 영상, 상태, 결과, 관절점 파일(작업 폴더째)과 작업 기록(`analyses.jsonl`)의 그 줄이다. 자료 파기·촬영 삭제·측정 취소·다시 분석 때 부른다.

| 응답 | 뜻 | 부르는 쪽 |
| --- | --- | --- |
| 204 | 지움 | 성공 |
| 404 `NOT_FOUND` | 이미 없음 | 성공으로 본다 |
| 409 `JOB_IN_PROGRESS` | 분석 중이라 지울 수 없음 | 끝난 뒤 다시 부른다 |
| 500 `DELETE_FAILED` | 다 지우지 못함 | 다시 부른다 |

### 4.7 `DELETE /analyses?shot_id=...`

그 촬영(등록 때 `meta.shot_id`)으로 만든 작업을 모두 지운다. 다시 분석하면 한 촬영에 작업이 여러 개 생기고, 등록 응답을 못 받아 다시 보낸 작업은 부르는 쪽이 ID를 모르기 때문이다.

응답 200 (지울 작업이 없어도 200에 빈 목록):

```json
{"shot_id": "s-001", "deleted": ["5d0e799d-2baa-4bfd-9f4c-b4e7f0ea9ea7", "aaa8df96-8614-4994-a160-9a44830e281b"]}
```

- 하나라도 분석 중이면 **아무것도 지우지 않고** 409 `JOB_IN_PROGRESS`
- 등록 때 `meta.shot_id`를 문자열로 보낸 작업만 걸린다(4.2)
- `shot_id`가 없거나 비면 400 `INVALID_REQUEST`, 지우다 실패하면 500 `DELETE_FAILED`
- 이 경로는 0.6.0의 S15P31A404-258부터 있다. 그 전 판은 405를 낸다(6.3)
- 서버의 작업 상태 파일을 모두 훑는다. 작업 300개에서 약 0.07초다

## 5. 결과와 관절점 파일

`resultFormat.md`가 기준이다. 부르는 쪽이 특히 알아야 할 규칙만 적는다.

- 결과 JSON은 v1이다. **v1 안에서는 필드를 빼거나 뜻을 바꾸지 않고 더하기만 한다.** 부르는 쪽은 모르는 필드를 무시한다
- 수치 키는 앞·뒷발 `_front`·`_hind`로 오고, 다리는 그 통과의 `camera_side` 쪽이다(오른쪽 통과면 오른쪽 다리)
- 회차 값(여러 통과의 중앙값)과 좌우 비교·대칭 지수는 이 API가 아니라 부르는 쪽(팀 서비스)이 계산한다
- `gait`(보행 유형)는 아직 `null`이다. 보행 유형 판별이 들어가면 채운다
- 아직 비어 있는 수치: 발 경사(`paw_slope_*`), 발 움직임 범위(`paw_excursion_*`)

## 6. 부르는 순서 (클라이언트 구현)

### 6.1 분석 한 건

1. `POST /analyses`로 등록하고 `id`를 저장한다. `meta.shot_id`를 꼭 넣는다
2. `GET /analyses/{id}`를 2초 안팎 간격으로 부른다
3. `done`이면 `GET /analyses/{id}/result`, 필요하면 `GET /analyses/{id}/files/keypoints`
4. `failed`면 `error.code`로 안내한다(3.2). 결과는 부르지 않는다
5. 부르는 쪽 대기 한도를 둔다. 팀 서비스는 600초(`ANALYSIS_TIMEOUT_SEC`)이고, 분석 API의 660초보다 짧게 두어 부르는 쪽이 먼저 끝낸다

| 시간 | 값 | 근거 |
| --- | --- | --- |
| 요청 하나의 한도 | 30초 | 팀 서비스 `ANALYSIS_HTTP_TIMEOUT_SEC`. 등록(영상 업로드 포함)도 이 안에 끝나야 한다 |
| 분석 한 건 | 영상 길이의 약 2배(GPU, fs-v4) | `gpuCheck.md` 2절. 8.6초 영상 16초 |
| 부르는 쪽 대기 한도 | 600초 | 팀 서비스 `ANALYSIS_TIMEOUT_SEC` |
| 서버 시간 한도 | 660초 | `ANALYSIS_JOB_TIMEOUT_SEC` |

### 6.2 다시 시도

- 연결 실패, 요청 시간 초과, 5xx는 다시 시도해도 된다
- 등록을 다시 보낼 때는 앞의 요청이 서버에 닿았을 수 있다. 같은 `shot_id`로 보내 두면 나중에 촬영 단위로 함께 지울 수 있다
- 4xx는 다시 보내도 같다(409 `NOT_READY`·`JOB_IN_PROGRESS`는 기다렸다 다시)

### 6.3 지우기

팀 서비스의 순서(백엔드 명세 6절): 촬영마다 ① `DELETE /analyses?shot_id=...` ② 알고 있는 작업 ID가 ①의 `deleted`에 없으면 `DELETE /analyses/{id}`. ①이 405면 옛 판이라 ②만 한다. 404는 이미 없음이라 성공이다.

## 7. 서버 운영

### 7.1 설정 (환경변수)

| 이름 | 기본값 | 뜻 |
| --- | --- | --- |
| `ANALYSIS_API_KEY` | 비어 있음 | 인증 키(2.1). 부르는 쪽과 같은 값 |
| `ANALYSIS_POSE_SOURCE` | `sample` | `model`, `track`, `sample`(4.1). 운영은 `model` |
| `ANALYSIS_MODEL` | `models.yaml`의 `default`(`fs-v4`) | 모델 이름. 결과 `model.name` |
| `ANALYSIS_MODEL_DIR` | 홈의 `models/company-orig` | `model`일 때 기업 모델 폴더(`run.py`, `det.py`, `pose.py`, `det.pth`, `pose.pth`) |
| `ANALYSIS_TRACK_FILE` | 모델의 `track_file` | `track`일 때 관절점 파일 |
| `ANALYSIS_WEIGHTS_SHA256` | 모델의 `weights_sha256`, `model`이면 `pose.pth`에서 계산 | `model.version` 끝 8자 |
| `ANALYSIS_MODEL_WORKERS` | 1 | `model`일 때 영상을 동시에 추론하는 워커 프로세스 수. 워커마다 모델을 따로 올려 GPU 메모리를 그만큼 더 쓴다(허정원) |
| `ANALYSIS_UPLOAD_MAX_MB` | 100 | 영상 한 건 상한. 부르는 쪽·nginx 상한과 맞춘다 |
| `ANALYSIS_STORAGE_DIR` | 저장소의 `data/analysis_api` | 영상·결과를 두는 곳 |
| `ANALYSIS_JOB_TIMEOUT_SEC` | 660 | 분석 시간 한도(3.1) |

### 7.2 저장과 파기

- 작업마다 `{ANALYSIS_STORAGE_DIR}/{id}/`에 `video.mp4`, `job.json`, `result.json`, `keypoints.json`을 두고, 끝난 작업은 `analyses.jsonl`에 한 줄 남긴다(파일 이름은 남기지 않는다. 반려견 이름이 들어 있을 수 있다)
- 저절로 지우지 않는다. 지우기 API(4.6, 4.7)나 전체 파기 명령(`python purge.py --all --execute`)으로 지운다. 팀 서비스의 자료 파기는 이 API의 사본도 함께 지운다

### 7.3 배포와 점검

- GPU 서버 배포는 CI의 `deploy_gpu`가 한다(허정원, 태그 배포 S15P31A404-239, master 배포와 동결 S15P31A404-307. `.gitlab-ci.yml`, `infra/ci/deploy_gpu.sh`). 두 경우에 돈다
  - `v*` 태그를 찍을 때. 릴리스 폴더 이름은 태그 이름
  - master에 머지됐는데 `analysis_api/`, `engine/`, `infra/ci/deploy_gpu.sh` 중 하나라도 바뀌었을 때. 릴리스 폴더 이름은 `master-{커밋 SHA 8자}`
- develop에 머지만 해서는 올라가지 않는다
- CI/CD 변수 `GPU_DEPLOY_FREEZE=1`이면 태그·master 배포가 모두 멈춘다(동결 중에는 태그를 찍어도 배포되지 않는다). 시연 직전처럼 서버를 바꾸면 안 될 때 쓴다
- 배포가 실패하면 스크립트가 이전 릴리스로 되돌린다
- 배포 뒤 `analysis_api/check_server.py`로 등록부터 지우기까지 한 바퀴 돌려 본다(`gpuCheck.md` 4절)

### 7.4 보안

- 인증 키를 꼭 넣는다. 팀 서버와 GPU 서버 사이는 터널로만 잇고 포트를 밖에 열지 않는다
- `/docs`·`/openapi.json`은 인증 없이 열려 있다. 엔드포인트 목록만 보이고 자료는 없다
- GPU 서버는 팀 서비스 워커만 부르는 내부 서버라 외부에 공개하지 않는다(허정원 11-12). 지금은 터널로만 이어 밖에서 닿지 않아 그대로 둔다
- 호출 인증 보강과 `/docs` 비공개(개발·스테이징에서만 공개) 여부는 허정원이 후속 MR로 정한다
- 영상과 결과는 반려견·기관 자료다. 저장 폴더는 서버 밖으로 복사하지 않고, 과제가 끝나면 전체 파기한다

## 8. 버전

| 무엇 | 예 | 바뀌는 때 |
| --- | --- | --- |
| API 버전 `API_VERSION` | `0.6.0` | 결과 값이 바뀌는 변경(엔진·결과 형식). 필드만 더하고 있던 값이 그대로면 올리지 않는다 |
| `model.version` | `0.6.0/v1/a4261a10` | `{API 버전}/{각도 정의}/{가중치 SHA-256 앞 8자}`. 셋 중 하나라도 바뀌면 바뀐다 |
| `versions` | `{"angle_def": "v1", "gait_events": "v1", "validity": "v1", "gait_metrics": "v2", "joint_rom": "v1"}` | 엔진 모듈마다의 정의 버전 |
| 결과 형식 | v1 | 필드를 빼거나 뜻을 바꿀 때만 v2 |

- 팀 서비스는 `model.name`이나 `model.version`이 다른 회차끼리 변화를 판단하지 않는다(`MODEL_CHANGED`). 모델이나 API 버전을 바꾸면 지난 회차와 비교가 끊긴다

## 9. 변경 이력

| 날짜 | API | 내용 |
| --- | --- | --- |
| 10-22 | | 뼈대: 엔드포인트, 상태값, 공통 오류 형식(S15P31A404-20) |
| 10-28 | | 영상 저장, 인증(`X-API-Key`), 업로드 상한, 응답 뒤 분석(S15P31A404-156) |
| 11-02 | 0.4.0 | 엔진 연결: 유효 판별, 결과 JSON v1, 관절점 파일(S15P31A404-180) |
| 11-03 | 0.4.0 | 작업을 디스크에 남김, `INTERRUPTED`, `models.yaml`로 모델 고르기(S15P31A404-182) |
| 11-04 | 0.5.0 | 보행 수치: 걸음 길이·입각기 비율·보행 속도·주기 수(S15P31A404-183) |
| 11-04 | 0.6.0 | 관절 가동 범위·각도 중앙값·무릎 주기별 가동 범위(S15P31A404-184) |
| 11-05 | 0.6.0 | `DELETE /analyses/{id}`, 전체 파기 명령(S15P31A404-185) |
| 11-06 | 0.6.0 | `pose_source: model`(영상에서 기업 모델로 추론, 허정원 S15P31A404-229) |
| 11-10 | 0.6.0 | `DELETE /analyses?shot_id=`, 실패 사유 `TIMEOUT`(S15P31A404-258) |
| 11-11 | 0.6.0 | 모델 워커 프로세스 풀 `ANALYSIS_MODEL_WORKERS`(허정원) |
| 11-11 | 0.6.0 | 발 높이 `paw_lift_*`, 수치 측정 불가 `reason_detail`, `versions.gait_metrics` v2(S15P31A404-259) |
