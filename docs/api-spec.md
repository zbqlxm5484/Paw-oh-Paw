# 크림오프 팀 서비스 API 명세

| 항목 | 내용 |
| --- | --- |
| 버전 | v1.0 (2026-10-20) |
| 기준 | 백엔드 기능 명세 v1.3의 15절(API 상세), 11.5·11.6, 13·14절 |
| 작성 | 조영운(백엔드) |
| 읽는 사람 | 장준환(화면), 김지윤(API 시험) |
| 함께 주는 파일 | `openapi.yaml` (같은 내용을 OpenAPI 3.1로 쓴 파일) |

화면이 부를 API 26개의 요청·응답 모양을 화면 쪽에서 필요한 것만 모았다. 서버 안쪽(DB, 워커, 파일 저장 방식)은 뺐다. 이 문서와 백엔드 명세가 다르면 백엔드 명세가 맞고, 바뀌면 이 문서와 `openapi.yaml`을 같이 고친다.

---

## 1. 공통 규칙

### 1.1 주소와 형식

- 주소는 모두 `/api/v1`로 시작한다. 예: `GET /api/v1/dogs`. 이 문서의 주소는 `/api/v1`을 뺀 나머지만 적었다.
- 요청·응답은 JSON이고 필드 이름은 snake\_case다. 예: `valid_passes`.
- ID는 UUID 문자열이다. 예: `"3f2a9c1e-5b7d-4e8a-9c21-7d4e5f6a8b90"`.
- 시각은 UTC ISO 8601이고 `Z`로 끝난다. 예: `"2026-10-20T00:30:00Z"`. 한국 시간으로 바꿔 보여 주는 일은 화면이 한다.
- 날짜는 `YYYY-MM-DD`다. 예: `"2026-10-20"`. 측정일(`measured_on`)처럼 날짜만 있는 값은 이미 한국 날짜다.
- 숫자는 JSON 숫자로 온다. 표시 자릿수는 화면이 정한다.
- 값이 없는 필드도 키를 빼지 않고 `null`로 온다.
- 상태·종류 값은 대문자 영어다. 예: `ANALYZING`. 한국어로 바꿔 보여 주는 일은 화면이 한다(10절 값 목록).

### 1.2 로그인과 토큰

1. `POST /auth/login`으로 기관 코드·아이디·비밀번호를 보내면 `access_token`과 만료 시각 `expires_at`이 온다.
2. 이후 모든 요청에 `Authorization: Bearer <access_token>` 헤더를 붙인다.
3. 토큰은 기본 12시간(서버 설정값) 뒤 만료된다. 정확한 시각은 `expires_at`을 본다. 새로 받는 기능(refresh token)은 없다. `expires_at`이 지나거나 401 `AUTH_EXPIRED`가 오면 로그인 화면으로 보낸다.

토큰 없이 부르는 것: 로그인, `/health`, `/metrics`, 서명 주소로 여는 결과 영상과 보고서 PDF.

### 1.3 응답 모양

- **성공**: 객체를 감싸지 않고 그대로 준다. 만들기 201, 조회·수정 200, 삭제 204(본문 없음).
- **페이지 목록**: 반려견 목록과 측정 이력 두 곳만 이 모양이다. `total`을 보고 쪽 수를 계산한다.

```json
{"items": [ ... ], "total": 45, "page": 1, "size": 20}
```

- **오류**: 모든 오류가 같은 모양이다. 화면은 `message`를 그대로 보여 주면 되고, 분기는 `code`로 한다.

```json
{
  "error": {
    "code": "VIDEO_PORTRAIT",
    "message": "가로로 촬영한 영상만 올릴 수 있습니다.",
    "detail": {"width": 1080, "height": 1920}
  }
}
```

- **입력 오류(422 `VALIDATION_ERROR`)**: 어느 필드가 틀렸는지 `detail.fields`에 온다. `field`는 필드 이름, `type`은 틀린 종류다.

```json
{"error": {"code": "VALIDATION_ERROR", "message": "입력값을 확인해 주세요.",
  "detail": {"fields": [{"field": "weight_kg", "type": "less_than_equal"}]}}}
```

### 1.4 모든 API에서 날 수 있는 오류

엔드포인트마다 다시 적지 않는다.

| HTTP | code | 화면에서 할 일 |
| --- | --- | --- |
| 401 | `AUTH_REQUIRED`, `AUTH_EXPIRED` | 로그인 화면으로 |
| 403 | `ACCOUNT_DISABLED` | 계정이 막혔다고 알리고 로그인 화면으로 |
| 404 | `NOT_FOUND` | 없는 ID, 다른 기관의 ID, 주소에 든 ID가 UUID 형식이 아님. 셋을 구분하지 않는다 |
| 422 | `VALIDATION_ERROR` | `detail.fields`로 틀린 입력칸 표시 |
| 500 | `INTERNAL_ERROR` | 잠시 후 다시 시도하라고 안내 |

### 1.5 사유 객체 Reason

실패·제외·경고 사유는 모두 같은 모양이다. 화면은 `message`를 보여 준다. 사유가 없으면 `null`이다.

```json
{"code": "STOPPED", "message": "중간에 멈췄습니다."}
```

쓰는 자리: `fail_reason`, `validity_reason`, `exclude_reason`, `unmeasurable_reason`, `reason`, `note`, `warnings[]`, `notices[]`. 코드 목록은 11절.

### 1.6 영상·PDF 주소(서명 주소)

`<video>`·`<iframe>` 태그는 토큰 헤더를 붙이지 못한다. 그래서 조회 API가 "5분 동안만 열리는 주소"를 내려 준다.

- `video_url`, `file_url`, `download_url`을 태그의 `src`·`href`에 그대로 넣는다.
- 주소가 `/api/v1`로 시작하면(상대 주소) 앞에 서버 주소(예: `http://localhost:8000`)만 붙이고, `http`로 시작하면(절대 주소, AWS S3) 그대로 쓴다. 그 밖에는 주소를 고치지 않는다.
- 함께 오는 `url_expires_at`이 지나면 열리지 않는다. 서버가 서명한 주소면 403 `FILE_LINK_EXPIRED`, AWS S3 주소면 S3가 자기 형식의 403을 준다. 어느 쪽이든 그 주소를 준 조회 API를 다시 불러 새 주소를 받는다.
- 파일이 아직 없으면 주소와 `url_expires_at`이 `null`이다.

### 1.7 다시 불러오기(폴링)

| 화면 | 부를 API | 간격 | 멈출 때 |
| --- | --- | --- | --- |
| S3 측정 | `GET /sessions/{session_id}` | 2~3초 | `status`가 DONE이면 S5로, FAILED면 `fail_reason`을 보여 주고 멈춘다 |
| S6 보고서 | `GET /sessions/{session_id}/reports` | 3초 | `session_status`가 DONE이고 PENDING·GENERATING인 판본이 없을 때. 회차가 아직 집계 중이면 `reports`가 빈 배열이므로 계속 부른다 |

### 1.8 개발 환경

- 서버를 띄우면 `/docs`에 시험 화면(Swagger)이 생긴다. 서버가 없을 때는 `openapi.yaml`로 가짜 서버(mock)를 띄워 화면을 먼저 만들 수 있다(14절).
- 화면 개발 서버 주소는 서버의 `CORS_ORIGINS`에 들어 있어야 한다. 기본값은 Vite 개발 서버인 `http://localhost:5173`이다. 주소가 다르면 백엔드에 알려 준다.

---

## 2. 엔드포인트 한눈에

| # | 메서드·주소 | 하는 일 | 화면 | 성공 | 이 API만의 오류 |
| --- | --- | --- | --- | --- | --- |
| 1 | `POST /auth/login` | 로그인, 토큰 발급 | 로그인 | 200 | 401 `LOGIN_FAILED`, 403 `ACCOUNT_DISABLED` |
| 2 | `GET /auth/me` | 로그인한 담당자·기관 | 공통 | 200 | — |
| 3 | `GET /dogs` | 반려견 목록·검색 | S1 | 200 | — |
| 4 | `POST /dogs` | 반려견 등록 | S2 | 201 | — |
| 5 | `GET /dogs/{dog_id}` | 반려견 상세 | S2·S7 | 200 | — |
| 6 | `PATCH /dogs/{dog_id}` | 반려견 수정, 기준 회차 지정 | S2·S7 | 200 | 400 `BASELINE_INVALID` |
| 7 | `POST /dogs/{dog_id}/sessions` | 회차 시작 | S3 | 201 | 409 `SESSION_ALREADY_OPEN` |
| 8 | `GET /dogs/{dog_id}/sessions` | 측정 이력 | S7 | 200 | — |
| 9 | `GET /sessions/{session_id}` | 회차 상태·방향별 진행·촬영 목록 | S3 | 200 | — |
| 10 | `DELETE /sessions/{session_id}` | 측정 취소 | S3 | 204 | 409 `SESSION_CLOSED`, `SHOT_IN_PROGRESS` |
| 11 | `POST /sessions/{session_id}/shots` | 영상 업로드 | S3 | 201 | 12.1의 업로드 오류 |
| 12 | `POST /sessions/{session_id}/complete` | 측정 종료 | S3 | 200 | 409 `SESSION_CLOSED`, `SESSION_EMPTY` |
| 13 | `GET /shots/{shot_id}` | 촬영 상세 | S4 | 200 | — |
| 14 | `POST /shots/{shot_id}/retry` | 실패한 촬영 다시 분석 | S3·S4 | 200 | 409 `SHOT_NOT_FAILED`, `SESSION_CLOSED` |
| 15 | `DELETE /shots/{shot_id}` | 촬영 삭제 | S3·S4 | 204 | 409 `SESSION_CLOSED`, `SHOT_IN_PROGRESS` |
| 16 | `GET /shots/{shot_id}/video` | 결과 영상 재생 (서명 주소) | S4 | 200·206 | 403 `FILE_LINK_EXPIRED` |
| 17 | `GET /shots/{shot_id}/angles` | 프레임별 관절 각도 (권장) | S5 | 200 | — |
| 18 | `GET /sessions/{session_id}/result` | 회차 수치·다리 비교 요약 | S5 | 200 | 409 `SESSION_NOT_DONE` |
| 19 | `GET /sessions/{session_id}/reports` | 판본별 보고서 상태 | S6 | 200 | — |
| 20 | `POST /reports/{report_id}/regenerate` | 보고서 다시 만들기 | S6 | 200 | 409 `REPORT_IN_PROGRESS` |
| 21 | `GET /reports/{report_id}/file` | PDF 미리보기·내려받기 (서명 주소) | S6 | 200 | 403 `FILE_LINK_EXPIRED` |
| 22 | `GET /dogs/{dog_id}/compare` | 회차 비교 | S8 | 200 | 400 `COMPARE_INVALID` |
| 23 | `GET /dogs/{dog_id}/trends` | 수치 추이 | S8 | 200 | — |
| 24 | `POST /admin/purge` | 자료 파기 (관리자) | — | 200 | 403 `FORBIDDEN`, 409 `SHOT_IN_PROGRESS` |
| 25 | `GET /health` | 서버 상태 | — | 200·503 | — |
| 26 | `GET /metrics` | 요청 수·처리 시간 (선택) | — | 200 | — |

화면 번호: S1 반려견 목록, S2 반려견 등록·상세, S3 측정, S4 촬영 상세, S5 회차 결과, S6 보고서, S7 측정 이력, S8 비교·추이.

---

## 3. 공통 객체

여러 API가 같은 모양으로 주는 객체다. 값은 예시이고 `"…"`는 UUID다. "\<ShotOut>"처럼 쓴 자리에는 그 객체가 통째로 들어간다.

### StaffOut — 로그인한 담당자

```json
{
  "id": "…",
  "login_id": "kim01",
  "name": "김담당",
  "role": "STAFF",
  "institution": {"id": "…", "code": "CREAM01", "name": "크림 재활센터"}
}
```

### DogOut — 반려견 (목록과 상세가 같은 모양)

```json
{
  "id": "…",
  "name": "보리",
  "breed": "골든 리트리버",
  "weight_kg": 28.4,
  "size_class": "LARGE",
  "size_class_manual": false,
  "birth_year": 2019,
  "sex": "FEMALE_SPAYED",
  "rehab_start_date": "2026-10-01",
  "focus_limb": "RH",
  "baseline_session_id": null,
  "memo": null,
  "session_count": 3,
  "last_measured_on": "2026-10-20",
  "open_session_id": null,
  "created_at": "2026-10-19T00:30:00Z",
  "updated_at": "2026-10-19T00:30:00Z"
}
```

- `session_count`: 이 반려견의 회차 수(상태 상관없이). `last_measured_on`: 가장 최근 회차의 측정일. 없으면 `null`.
- `open_session_id`: 측정 중(MEASURING)인 회차가 있으면 그 ID. 목록에서 "측정 중" 표시와 이어서 측정하기에 쓴다.
- `size_class_manual`: 담당자가 체급을 직접 고쳤으면 true. false면 등록 체중으로 자동 분류한 값이다(10kg 미만 SMALL, 25kg 미만 MEDIUM, 25kg 이상 LARGE. 견종은 보지 않는다).
- `baseline_session_id`: 담당자가 지정한 기준 회차. `null`이면 가장 이른 완료 회차가 기준이다.
- `memo`: 내부 메모. 담당자 화면에만 보이고 보고서에는 들어가지 않는다.

### SessionOut — 회차

```json
{
  "id": "…",
  "dog_id": "…",
  "staff": {"id": "…", "name": "김담당"},
  "measured_on": "2026-10-20",
  "weight_kg": 28.1,
  "status": "MEASURING",
  "fail_reason": null,
  "model_name": null,
  "model_version": null,
  "completed_at": null,
  "aggregated_at": null,
  "created_at": "2026-10-20T00:10:00Z"
}
```

### ShotOut — 촬영 1건 (통과 목록 PassOut을 품는다)

```json
{
  "id": "…",
  "seq_no": 6,
  "status": "DONE",
  "fail_reason": null,
  "validity": "PARTIAL",
  "validity_reason": {"code": "FEW_VALID_PASSES", "message": "쓸 수 있는 통과가 일부만 있습니다."},
  "video_status": "READY",
  "below_min_spec": false,
  "passes": [
    {"pass_no": 1, "camera_side": "LEFT", "gait_type": "TROT", "is_valid": true,
     "exclude_reason": null, "start_frame": 30, "end_frame": 171},
    {"pass_no": 2, "camera_side": "LEFT", "gait_type": "OTHER", "is_valid": false,
     "exclude_reason": {"code": "RUNNING", "message": "뛰었습니다. 천천히 걷게 해 주세요."},
     "start_frame": 190, "end_frame": 260}
  ],
  "uploaded_at": "2026-10-20T00:14:02Z",
  "analyzed_at": "2026-10-20T00:14:31Z"
}
```

- `status`가 DONE이 되기 전에는 `passes`가 빈 배열이고 `validity`가 `null`이다.
- `validity`: 촬영 판정. VALID(유효), PARTIAL(일부 유효), INVALID(무효). INVALID·PARTIAL이면 `validity_reason.message`로 다시 찍을지 안내한다.
- `video_status`: 결과 영상(골격 + 얼굴 가림)의 상태. 판정 결과가 먼저 나오고 결과 영상은 조금 뒤에 READY가 된다. FAILED여도 판정 결과는 그대로 쓴다.
- `camera_side`: 카메라 쪽에 보인 몸의 방향. LEFT면 왼쪽 다리(LF·LH), RIGHT면 오른쪽 다리(RF·RH)를 잰다.
- `passes`는 `pass_no` 오름차순이다.

### ShotDetailOut — 촬영 상세 (ShotOut의 모든 필드 + 아래)

```json
{
  "width": 1920,
  "height": 1080,
  "fps": 59.94,
  "duration_sec": 4.2,
  "bitrate_kbps": 15800,
  "codec": "hevc",
  "model_name": "pga-pose",
  "model_version": "v1",
  "submitted_at": "2026-10-20T00:14:03Z",
  "video_ready_at": "2026-10-20T00:14:48Z",
  "video_url": "/api/v1/shots/…/video?exp=1792455600&sig=9f2c…",
  "url_expires_at": "2026-10-20T00:20:00Z"
}
```

- `video_url`은 `video_status`가 READY일 때만 있다. 아니면 `url_expires_at`과 함께 `null`이다.
- `width`·`height`는 화면에 보이는 방향 기준이다.
- 원본 영상의 주소는 어떤 응답에도 없다. 화면에는 얼굴을 가린 결과 영상만 나간다.

### ReportOut — 보고서 판본 1개

```json
{
  "id": "…",
  "session_id": "…",
  "edition": "VET",
  "status": "DONE",
  "fail_reason": null,
  "generation_ms": 8400,
  "template_version": "1.0",
  "model_version": "v1",
  "updated_at": "2026-10-20T00:31:10Z",
  "file_url": "/api/v1/reports/…/file?exp=1792456800&sig=41ab…",
  "download_url": "/api/v1/reports/…/file?exp=1792456800&sig=41ab…&download=true",
  "url_expires_at": "2026-10-20T00:40:00Z"
}
```

- `edition`: OWNER(보호자용), VET(수의사용).
- `file_url`(미리보기)·`download_url`(내려받기)·`url_expires_at`은 `status`가 DONE일 때만 있다.

---

## 4. 인증

### `POST /auth/login` — 로그인

```json
// 요청
{"institution_code": "CREAM01", "login_id": "kim01", "password": "…"}

// 응답 200
{
  "access_token": "eyJhbGciOi…",
  "token_type": "bearer",
  "expires_at": "2026-10-20T12:10:00Z",
  "staff": "<StaffOut>"
}
```

- 기관 코드·아이디·비밀번호 중 무엇이 틀려도 401 `LOGIN_FAILED` 하나로 온다. 화면도 어느 칸이 틀렸는지 표시하지 않는다.
- 기관 코드와 아이디는 대소문자를 구분한다.
- 비밀번호까지 맞았는데 사용이 중지된 계정이면 403 `ACCOUNT_DISABLED`다.
- 회원가입 API는 없다. 계정은 관리자가 미리 만든다.

### `GET /auth/me` — 로그인한 담당자

응답 200 **StaffOut**. 새로고침 뒤 토큰이 아직 쓸 수 있는지 확인할 때도 쓴다.

---

## 5. 반려견

### `GET /dogs?q=보리&page=1&size=20` — 목록·검색

| 쿼리 | 필수 | 규칙 |
| --- | --- | --- |
| `q` | 선택 | 최대 50자. 이름에 이 글자가 들어 있으면 찾는다(대소문자 무시) |
| `page` | 선택 | 1 이상, 기본 1 |
| `size` | 선택 | 1~100, 기본 20 |

- 응답 200: `{"items": [DogOut, …], "total": 45, "page": 1, "size": 20}`
- 정렬: 최근 측정일이 늦은 순서, 한 번도 안 잰 반려견은 뒤. 같으면 등록이 늦은 순서.

### `POST /dogs` — 등록

```json
// 요청
{
  "name": "보리",
  "breed": "골든 리트리버",
  "weight_kg": 28.4,
  "birth_year": 2019,
  "sex": "FEMALE_SPAYED",
  "rehab_start_date": "2026-10-01",
  "focus_limb": "RH",
  "memo": null
}
```

- 응답 201 **DogOut**. 필드 규칙은 12.2.
- `size_class`를 빼면 서버가 체중으로 정한다(10kg 미만 SMALL, 25kg 미만 MEDIUM, 25kg 이상 LARGE). 보내면 그 값을 쓰고 `size_class_manual`이 true가 된다.
- `baseline_session_id`는 등록 때 받지 않는다. 회차가 아직 없기 때문이다.

### `GET /dogs/{dog_id}` — 상세

응답 200 **DogOut**.

### `PATCH /dogs/{dog_id}` — 수정, 기준 회차 지정

```json
// 요청: 바꿀 필드만 보낸다
{"weight_kg": 27.9, "baseline_session_id": "…"}
```

- 응답 200 **DogOut**.
- 보내지 않은 필드는 그대로다. 값을 비우려면 `null`을 보낸다. `name`·`breed`·`weight_kg`은 비울 수 없다.
- `weight_kg`를 바꾸면 체급을 직접 고친 적이 없을 때만 새 체중으로 체급이 다시 정해진다. `breed`를 바꿔도 체급은 그대로다.
- `size_class`에 값을 보내면 직접 고친 것으로 저장되고, `null`을 보내면 자동 분류로 돌아간다.
- `baseline_session_id`는 이 반려견의 완료(DONE) 회차여야 한다. 아니면 400 `BASELINE_INVALID`다. `null`을 보내면 지정을 풀고 가장 이른 완료 회차가 기준이 된다.

---

## 6. 회차 측정

측정 화면(S3)의 흐름: 회차 시작 → 영상 올리기를 반복하면서 2~3초마다 회차 조회 → 측정 종료 → 결과 화면(S5).

### `POST /dogs/{dog_id}/sessions` — 회차 시작

```json
// 요청: 두 필드 모두 선택
{"measured_on": "2026-10-20", "weight_kg": 28.1}
```

- 응답 201 **SessionOut**(`status`는 MEASURING).
- `measured_on`을 빼면 오늘(한국 날짜)이다. 미래 날짜는 안 된다.
- `weight_kg`(그날 체중)을 빼면 `null`이고, 보고서는 반려견의 등록 체중을 쓴다.
- 이미 측정 중인 회차가 있으면 409 `SESSION_ALREADY_OPEN`이고 `detail.session_id`에 그 회차 ID가 온다. 화면은 그 회차로 이동한다.

### `GET /sessions/{session_id}` — 회차 상태·진행·촬영 목록

측정하는 내내 2~3초마다 부른다. 한 번에 화면 전체를 그릴 수 있게 모두 담았다. 응답 200 **SessionDetailOut** = SessionOut의 모든 필드 + 아래.

```json
{
  "dog": {"id": "…", "name": "보리", "breed": "골든 리트리버", "weight_kg": 28.4, "size_class": "LARGE"},
  "progress": {
    "LEFT":  {"valid_passes": 5, "recommended": 8},
    "RIGHT": {"valid_passes": 3, "recommended": 8}
  },
  "notices": [],
  "shots": ["<ShotOut>", "<ShotOut>"]
}
```

- `progress`: 방향별로 쓸 수 있는 통과 수(`valid_passes`)와 권장 수(`recommended`, 지금 8). 진행 막대에 쓴다. 권장 수는 나중에 체급별 값으로 바뀔 수 있다.
- `notices`: 양쪽 모두 권장 수를 채우면 `RECOMMENDED_MET`(측정을 끝내도 된다), 한쪽만 찍혔으면 `ONE_SIDE_ONLY`(반대 방향으로도 걷게 하라)가 온다.
- `shots`: 이 회차의 촬영 전부, 최신이 위(`seq_no` 내림차순). 페이지는 없다.
- `status`가 MEASURING·AGGREGATING인 동안 계속 부른다. DONE이면 S5로, FAILED면 `fail_reason`을 보여 주고 멈춘다.

### `DELETE /sessions/{session_id}` — 측정 취소

- 응답 204. 회차와 그 안의 촬영을 모두 지운다.
- 회차가 MEASURING이 아니면 409 `SESSION_CLOSED`, 분석 중(SUBMITTED·ANALYZING)인 촬영이 있으면 409 `SHOT_IN_PROGRESS`다.

### `POST /sessions/{session_id}/shots` — 영상 업로드

- 요청: `multipart/form-data`, 필드 이름 `file` 하나. 파일을 고르든 바로 찍든 같은 API다.
- 서버가 검사하고 저장한 뒤 바로 답한다. 분석은 뒤에서 이어진다. 결과는 회차 조회로 확인한다.
- 검사에 걸리면 오류가 오고 아무것도 저장되지 않는다(12.1).

```json
// 응답 201: ShotOut의 모든 필드 + warnings
{
  "id": "…",
  "seq_no": 10,
  "status": "UPLOADED",
  "fail_reason": null,
  "validity": null,
  "validity_reason": null,
  "video_status": "PENDING",
  "below_min_spec": true,
  "passes": [],
  "uploaded_at": "2026-10-20T00:20:11Z",
  "analyzed_at": null,
  "warnings": [
    {"code": "BELOW_MIN_SPEC", "message": "최저 사양(640×360, 30fps, 4 Mbps)보다 낮은 영상입니다. 결과가 부정확할 수 있습니다."}
  ]
}
```

- `warnings`가 있어도 분석은 진행된다. 화면은 경고만 보여 준다.

### `POST /sessions/{session_id}/complete` — 측정 종료

- 요청 본문 없음. 응답 200 **SessionOut**(`status`는 AGGREGATING, `completed_at` 채움).
- 마지막 촬영의 분석이 끝나기를 기다리지 않고 바로 답한다. 집계와 보고서는 서버가 이어서 만든다. 화면은 회차 조회를 계속 부르다가 DONE이 되면 S5로 간다.
- 회차가 MEASURING이 아니면 409 `SESSION_CLOSED`, 촬영이 하나도 없으면 409 `SESSION_EMPTY`다.

### `GET /shots/{shot_id}` — 촬영 상세

응답 200 **ShotDetailOut**. 영상 타임라인에 유효 구간을 표시할 때는 `fps`와 각 통과의 `start_frame`·`end_frame`을 쓴다(초 = 프레임 ÷ fps).

### `POST /shots/{shot_id}/retry` — 실패한 촬영 다시 분석

- 요청 본문 없음. 응답 200 **ShotOut**(`status`는 UPLOADED).
- 촬영이 FAILED가 아니면 409 `SHOT_NOT_FAILED`, 회차가 MEASURING이 아니면 409 `SESSION_CLOSED`다.

### `DELETE /shots/{shot_id}` — 촬영 삭제

- 응답 204. 남은 촬영의 번호(`seq_no`)는 다시 매기지 않는다.
- 회차가 MEASURING이 아니면 409 `SESSION_CLOSED`, 촬영이 분석 중(SUBMITTED·ANALYZING)이면 409 `SHOT_IN_PROGRESS`다.

### `GET /shots/{shot_id}/video?exp=…&sig=…` — 결과 영상 재생

- 화면이 직접 부르지 않는다. ShotDetailOut의 `video_url`을 `<video src>`에 넣으면 브라우저가 부른다. 토큰은 필요 없다.
- `video/mp4`이고 앞뒤로 넘기기(Range, 206 응답)가 된다.
- 주소가 만료됐거나 고쳐졌으면 403 `FILE_LINK_EXPIRED`다. 촬영 상세를 다시 불러 새 주소를 받는다.

### `GET /shots/{shot_id}/angles` — 프레임별 관절 각도 (권장)

S5의 관절 각도 곡선 그래프에 쓴다.

```json
// 응답 200
{
  "shot_id": "…",
  "fps": 59.94,
  "passes": [
    {
      "pass_no": 1,
      "camera_side": "RIGHT",
      "gait_type": "TROT",
      "start_frame": 42,
      "angles": {
        "shoulder": [112.4, 113.0, null, 114.1],
        "elbow": [], "carpus": [], "hip": [], "stifle": [], "tarsus": []
      }
    }
  ]
}
```

- 유효 통과의 유효 구간만 담는다. 배열의 i번째 값은 `start_frame + i` 프레임의 각도(°)이고, 관절점을 못 찾은 프레임은 `null`이다. 그래프는 `null`에서 선을 끊는다.
- 다리는 `camera_side` 쪽이다(RIGHT면 오른쪽 앞다리·뒷다리).
- 촬영이 DONE이 아니면 `passes`가 빈 배열이다.
- 분석 API가 프레임별 각도를 주기로 정해져야 쓸 수 있다(조유진과 합의 중).

---

## 7. 회차 결과·보고서

### `GET /sessions/{session_id}/result` — 회차 수치와 다리 비교 요약

회차가 DONE이 아니면 409 `SESSION_NOT_DONE`이다. 응답 200 **SessionResultOut** = SessionOut의 모든 필드 + 아래.

```json
{
  "pass_counts": {"measured": 18, "used": 12, "excluded": 6},
  "shot_counts": {"total": 16, "failed": 1, "invalid": 2},
  "exclude_summary": [
    {"code": "RUNNING", "message": "뛰었습니다. 천천히 걷게 해 주세요.", "count": 4},
    {"code": "STOPPED", "message": "중간에 멈췄습니다.", "count": 2}
  ],
  "notices": [],
  "gaits": [
    {
      "gait_type": "TROT",
      "metrics": [
        {"metric_code": "rom_stifle", "limb": "LH", "value": 31.0, "unit": "deg",
         "measurable": true, "unmeasurable_reason": null, "n_passes": 6},
        {"metric_code": "rom_stifle", "limb": "RH", "value": 38.2, "unit": "deg",
         "measurable": true, "unmeasurable_reason": null, "n_passes": 6},
        {"metric_code": "paw_lift", "limb": "LF", "value": null, "unit": "pct_body",
         "measurable": false, "n_passes": 6,
         "unmeasurable_reason": {"code": "LOW_CONFIDENCE", "message": "관절점 인식이 불안정해 계산하지 못했습니다."}}
      ],
      "limb_compare": [
        {"pair": "HIND", "metric_code": "rom_stifle", "unit": "deg",
         "left": 31.0, "right": 38.2, "diff": -7.2, "symmetry_index": 20.81,
         "comparable": true, "reason": null},
        {"pair": "FORE", "metric_code": "paw_lift", "unit": "pct_body",
         "left": null, "right": 12.4, "diff": null, "symmetry_index": null,
         "comparable": false, "reason": {"code": "LOW_CONFIDENCE", "message": "…"}}
      ]
    }
  ]
}
```

- `pass_counts`: 회차의 전체 통과(`measured`), 그중 쓴 것(`used`)과 뺀 것(`excluded`). `exclude_summary`는 뺀 이유별 개수이고 많은 순서다.
- `shot_counts`: 촬영 수, 그중 실패(FAILED)와 무효(INVALID) 수.
- `gaits`: 보행 유형별 묶음(WALK, TROT 순서, 값이 있는 유형만). `metrics`는 10.4 표 순서, 같은 수치 안에서는 LF·RF·LH·RH 순서다.
- **측정 불가**는 `value`가 `null`이고 `measurable`이 false이며 사유가 `unmeasurable_reason`에 온다. 0으로 그리지 말고 "측정 불가 + 사유"로 보여 준다.
- `limb_compare`(다리 비교 요약): 앞다리 쌍(FORE: LF·RF)과 뒷다리 쌍(HIND: LH·RH)의 좌우 차이다. `diff` = 왼쪽 − 오른쪽, `symmetry_index`는 좌우 차이 비율(%)이다. **`symmetry_index`가 큰 순서로 정렬해서 오므로 맨 위가 "차이가 가장 큰 다리"다.** 그다음에 비교는 되지만 `symmetry_index`가 `null`인 항목(왼쪽 + 오른쪽이 0일 때)이 오고, 비교할 수 없는 항목(`comparable`이 false)은 맨 뒤에 `reason`과 함께 온다.
- 서버는 "아프다", "좋아졌다" 같은 판단 단어를 내지 않는다. 화면도 쓰지 않는다.
- `notices`: 한쪽 방향만 찍혔으면 `ONE_SIDE_ONLY`가 온다.

### `GET /sessions/{session_id}/reports` — 판본별 보고서 상태

```json
// 응답 200
{
  "session_id": "…",
  "session_status": "DONE",
  "reports": ["<ReportOut OWNER>", "<ReportOut VET>"]
}
```

- `reports`는 OWNER, VET 순서다. 회차가 DONE이 되기 전에는 빈 배열이다.
- 3초마다 부른다. `session_status`가 DONE이 되고 PENDING·GENERATING인 판본이 없어지면 멈춘다.

### `POST /reports/{report_id}/regenerate` — 보고서 다시 만들기

- 요청 본문 없음. 응답 200 **ReportOut**(`status`는 PENDING).
- 만드는 중(GENERATING)이면 409 `REPORT_IN_PROGRESS`다.

### `GET /reports/{report_id}/file?exp=…&sig=…` — PDF 미리보기·내려받기

- 화면이 직접 부르지 않는다. 미리보기는 `file_url`을 `<iframe src>`나 새 탭에, 내려받기는 `download_url`을 링크에 넣는다. 토큰은 필요 없다.
- 내려받는 파일 이름은 `{반려견 이름}_{측정일}_{보호자용|수의사용}.pdf`로 서버가 정한다.
- 보고서가 DONE이 아니면 404 `NOT_FOUND`, 주소가 만료됐으면 403 `FILE_LINK_EXPIRED`다.

---

## 8. 이력·비교·추이

### `GET /dogs/{dog_id}/sessions?page=1&size=20` — 측정 이력

- 응답 200: `{"items": [SessionHistoryItem, …], "total": 5, "page": 1, "size": 20}`. 측정일이 늦은 순서이고, 같으면 만든 시각이 늦은 순서다.

```json
// SessionHistoryItem
{
  "id": "…",
  "measured_on": "2026-10-20",
  "weight_kg": 28.1,
  "status": "DONE",
  "is_baseline": true,
  "valid_passes": {"LEFT": 8, "RIGHT": 8},
  "model_version": "v1",
  "reports": {"OWNER": "DONE", "VET": "FAILED"}
}
```

- `is_baseline`: 기준 회차인지. `reports`: 판본별 상태, 아직 없으면 `null`.

### `GET /dogs/{dog_id}/compare?target=…&base=BASELINE&gait_type=TROT` — 회차 비교

| 쿼리 | 필수 | 뜻 |
| --- | --- | --- |
| `target` | 선택 | 비교할 회차 ID. 기본은 가장 최근 완료 회차 |
| `base` | 선택 | `BASELINE`(기본, 기준 회차), `PREVIOUS`(target 바로 앞 완료 회차), 또는 회차 ID |
| `gait_type` | 선택 | 주면 그 보행 유형만 |

```json
// 응답 200
{
  "dog_id": "…",
  "base":   {"session_id": "…", "measured_on": "2026-10-01", "model_version": "v1", "kind": "BASELINE"},
  "target": {"session_id": "…", "measured_on": "2026-10-20", "model_version": "v1"},
  "model_changed": false,
  "items": [
    {"metric_code": "rom_stifle", "limb": "RH", "gait_type": "TROT", "unit": "deg",
     "base_value": 38.2, "target_value": 42.0, "diff": 3.8,
     "judgement": "UNKNOWN",
     "note": {"code": "RANGE_NOT_SET", "message": "변화 판단 기준이 아직 정해지지 않았습니다."}}
  ]
}
```

- `diff` = `target_value` − `base_value`. `kind`는 `BASELINE`·`PREVIOUS`·`SESSION`(회차 ID로 지정) 중 하나다.
- 정렬: 보행 유형, 다리(반려견의 관심 다리 먼저, 나머지는 LF·RF·LH·RH·NONE), 수치 순서.
- `judgement`(변화 판정)와 `note`:

| `judgement` | 뜻 | 함께 오는 `note` |
| --- | --- | --- |
| `INCREASE` / `DECREASE` | 오차 범위를 넘게 늘었다 / 줄었다 | `null` |
| `WITHIN_RANGE` | 오차 범위 안이다 | `null` |
| `UNKNOWN` | 판단하지 않았다. 값과 `diff`는 있다 | `MODEL_CHANGED`(분석 방식이 바뀜) 또는 `RANGE_NOT_SET`(기준 미정) |
| `NOT_COMPARABLE` | 한쪽에 값이 없거나 측정 불가. `diff`는 `null` | `NO_DATA` 또는 측정 불가 사유 |

- 지금은 기업의 오차 범위 값을 받기 전이라, 비교할 수 있는 항목은 `UNKNOWN` + `RANGE_NOT_SET`으로 온다. 값이 없거나 측정 불가인 항목은 `NOT_COMPARABLE`, 두 회차의 분석 방식이 다르면 `UNKNOWN` + `MODEL_CHANGED`다.
- "좋아짐·나빠짐"이 아니라 "증가·감소"로만 표시한다.
- 비교할 수 없는 요청은 400 `COMPARE_INVALID`이고 `detail.reason`으로 빈 화면 문구를 고른다:
  - `NO_DONE_SESSION`: 완료 회차가 하나도 없다.
  - `SAME_SESSION`: base와 target이 같다(회차가 하나뿐일 때 등).
  - `NO_PREVIOUS`: `base=PREVIOUS`인데 앞 회차가 없다.
  - `NOT_DONE`: 지정한 회차가 완료되지 않았다.

### `GET /dogs/{dog_id}/trends?metric_code=rom_stifle&gait_type=TROT` — 수치 추이

| 쿼리 | 필수 | 뜻 |
| --- | --- | --- |
| `metric_code` | 필수 | 10.4의 수치 코드 |
| `gait_type` | 필수 | 같은 보행 유형끼리만 잇는다 |
| `limb` | 선택 | 주면 그 다리만 |
| `from`, `to` | 선택 | 측정일 기간(그날 포함) |

```json
// 응답 200
{
  "dog_id": "…",
  "metric_code": "rom_stifle",
  "unit": "deg",
  "gait_type": "TROT",
  "series": [
    {"limb": "RH", "points": [
      {"session_id": "…", "measured_on": "2026-10-01", "value": 38.2, "measurable": true,
       "unmeasurable_reason": null, "model_version": "v1"},
      {"session_id": "…", "measured_on": "2026-10-20", "value": 42.0, "measurable": true,
       "unmeasurable_reason": null, "model_version": "v1"}
    ]}
  ],
  "lr_diff": [
    {"pair": "HIND", "points": [
      {"session_id": "…", "measured_on": "2026-10-01", "diff": -7.2, "symmetry_index": 20.81}
    ]}
  ]
}
```

- 완료 회차만, 측정일 오름차순이다. 그 회차에 값이 없으면 점이 없고, 측정 불가면 `value`가 `null`인 점이 온다.
- `series`는 관심 다리가 먼저, 나머지는 LF·RF·LH·RH 순서다.
- `lr_diff`(좌우 차이 추이)는 양쪽이 모두 측정된 회차만 점이 있다. 다리 구분이 없는 수치(`walk_speed`, `gait_cycles`)는 빈 배열이다.
- 점마다 `model_version`이 있다. 앞 점과 다르면 "분석 방식이 바뀜"을 표시한다.

---

## 9. 운영 (화면에서 거의 쓰지 않음)

### `POST /admin/purge` — 자료 파기 (관리자만)

```json
// 요청
{"scope": "DOG", "target_id": "…", "dry_run": true}

// 응답 200
{"scope": "DOG", "target_id": "…", "dry_run": true,
 "rows": 214, "files": 49, "bytes": 391000000, "purge_log_id": null}
```

- `scope`: `DOG`(반려견 하나, `target_id` 필요) 또는 `INSTITUTION`(자기 기관 전체, `target_id` 생략).
- `dry_run` 기본값은 true다. 지울 양만 세고 아무것도 지우지 않는다. 실제로 지우려면 false를 보낸다.
- 관리자가 아니면 403 `FORBIDDEN`, 분석 중인 촬영이 있으면 409 `SHOT_IN_PROGRESS`다.

### `GET /health` — 서버 상태

토큰 없음. 응답 200 `{"status": "ok", "db": "ok", "storage": "ok", "version": "1.0.0"}`. 문제가 있으면 503이고 실패한 항목이 `"error"`다.

### `GET /metrics` — 요청 수·처리 시간 (선택)

Prometheus 텍스트 형식. 내부망에서만 연다.

---

## 10. 값 목록

### 10.1 상태 값

| 대상 | 필드 | 값 | 뜻 |
| --- | --- | --- | --- |
| 회차 | `status` | `MEASURING` | 측정 중. 영상을 올릴 수 있다 |
| | | `AGGREGATING` | 측정 종료 뒤 수치를 집계하는 중 |
| | | `DONE` | 완료. 결과·보고서를 볼 수 있다 |
| | | `FAILED` | 집계 실패. `fail_reason`을 보여 준다 |
| 촬영 | `status` | `UPLOADED` | 올라옴, 분석 대기 |
| | | `SUBMITTED` | 분석 서버에 보냄 |
| | | `ANALYZING` | 분석 중 |
| | | `DONE` | 분석 끝. 판정 결과가 있다 |
| | | `FAILED` | 실패. `fail_reason`과 "다시 분석" 버튼을 보여 준다 |
| 촬영 | `validity` | `VALID` / `PARTIAL` / `INVALID` | 유효 / 일부 유효 / 무효 |
| 촬영 | `video_status` | `PENDING` / `READY` / `FAILED` | 결과 영상 만드는 중 / 준비됨 / 실패 |
| 보고서 | `status` | `PENDING` / `GENERATING` / `DONE` / `FAILED` | 대기 / 만드는 중 / 완료 / 실패 |

### 10.2 버튼을 막을 조건

서버도 막지만, 화면에서 미리 버튼을 끄면 409를 덜 본다.

| 버튼 | 누를 수 있는 때 |
| --- | --- |
| 영상 올리기, 측정 종료 | 회차가 MEASURING (측정 종료는 촬영이 1건 이상) |
| 측정 취소 | 회차가 MEASURING이고 SUBMITTED·ANALYZING 촬영이 없다 |
| 다시 분석 | 촬영이 FAILED이고 회차가 MEASURING |
| 촬영 삭제 | 회차가 MEASURING이고 촬영이 SUBMITTED·ANALYZING이 아니다 |
| 보고서 다시 만들기 | 그 판본이 GENERATING이 아니다 |
| 회차 결과 보기 | 회차가 DONE |

### 10.3 종류 값

| 필드 | 값 |
| --- | --- |
| `role` | `ADMIN`, `STAFF` |
| `size_class` | `SMALL`(소형), `MEDIUM`(중형), `LARGE`(대형) |
| `sex` | `MALE`, `FEMALE`, `MALE_NEUTERED`(중성화 수컷), `FEMALE_SPAYED`(중성화 암컷) |
| `focus_limb`, `limb` | `LF`(왼앞), `RF`(오른앞), `LH`(왼뒤), `RH`(오른뒤). `limb`에는 몸 전체 수치용 `NONE`도 있다 |
| `camera_side` | `LEFT`, `RIGHT` |
| `gait_type` | `WALK`(평보), `TROT`(속보), `PACE`(측대보), `OTHER`(기타) |
| `edition` | `OWNER`(보호자용), `VET`(수의사용) |
| `pair` | `FORE`(앞다리 LF·RF), `HIND`(뒷다리 LH·RH) |

### 10.4 수치 코드

| `metric_code` | 수치 | `unit` | `limb` |
| --- | --- | --- | --- |
| `rom_shoulder` | 어깨 관절 가동 범위 | `deg` | LF, RF |
| `rom_elbow` | 팔꿈치 가동 범위 | `deg` | LF, RF |
| `rom_carpus` | 앞발목 가동 범위 | `deg` | LF, RF |
| `rom_hip` | 고관절 가동 범위 | `deg` | LH, RH |
| `rom_stifle` | 무릎 가동 범위 | `deg` | LH, RH |
| `rom_tarsus` | 뒷발목 가동 범위 | `deg` | LH, RH |
| `angle_median_<관절>` | 위 6개 관절 각도의 중앙값. 예: `angle_median_stifle` | `deg` | 관절에 맞는 다리 |
| `stifle_cv` | 무릎 움직임 일관성 | `pct` | LH, RH |
| `paw_lift` | 발 높이(최대 들림) | `pct_body` | LF, RF, LH, RH |
| `paw_excursion` | 발 움직임 범위 | `pct_body` | LF, RF, LH, RH |
| `stride_length` | 걸음 길이 | `pct_body` | LF, RF, LH, RH |
| `stance_ratio` | 입각기 비율 | `pct` | LF, RF, LH, RH |
| `walk_speed` | 보행 속도 | `body_per_sec` | NONE |
| `gait_cycles` | 측정된 보행 주기 수 | `count` | NONE |

단위: `deg`(°), `pct`(%), `pct_body`(몸통 길이 대비 %), `body_per_sec`(몸통 길이/초), `count`(회). 거리 수치는 cm가 아니라 몸통 길이 대비 값이다. 수치 이름은 분석 API 형식이 확정되면(조유진과 합의) 바뀔 수 있다.

---

## 11. 오류·사유 코드

화면은 `message`를 그대로 보여 주면 된다. 문구는 서버의 문구 파일이 기준이라 바뀔 수 있다. 화면에서 따로 분기할 코드만 아래 "화면 동작"에 적었다.

### 11.1 응답 오류

| code | HTTP | 기본 문구 | 화면 동작 |
| --- | --- | --- | --- |
| `VIDEO_FORMAT` | 400 | MP4 또는 MOV 영상만 올릴 수 있습니다. | |
| `VIDEO_UNREADABLE` | 400 | 영상을 읽을 수 없습니다. 다시 촬영해 주세요. | |
| `VIDEO_CODEC` | 400 | H.264 또는 H.265로 찍은 영상만 올릴 수 있습니다. | |
| `VIDEO_PORTRAIT` | 400 | 가로로 촬영한 영상만 올릴 수 있습니다. | |
| `VIDEO_DURATION` | 400 | 영상 길이는 {min\_sec}~{max\_sec}초여야 합니다. | |
| `BASELINE_INVALID` | 400 | 기준 회차는 이 반려견의 완료된 회차여야 합니다. | |
| `COMPARE_INVALID` | 400 | 비교할 수 없는 회차입니다. | `detail.reason`으로 빈 화면 고르기(8절) |
| `AUTH_REQUIRED` | 401 | 로그인이 필요합니다. | 로그인 화면으로 |
| `AUTH_EXPIRED` | 401 | 로그인 시간이 지났습니다. 다시 로그인해 주세요. | 로그인 화면으로 |
| `LOGIN_FAILED` | 401 | 기관 코드, 아이디 또는 비밀번호가 맞지 않습니다. | |
| `ACCOUNT_DISABLED` | 403 | 사용이 중지된 계정입니다. | 로그인 화면으로 |
| `FORBIDDEN` | 403 | 이 기능을 사용할 권한이 없습니다. | |
| `FILE_LINK_EXPIRED` | 403 | 링크가 만료되었습니다. 화면을 새로 불러와 주세요. | 조회 API를 다시 불러 새 주소 받기 |
| `NOT_FOUND` | 404 | 요청한 정보를 찾을 수 없습니다. | |
| `SESSION_CLOSED` | 409 | 측정이 끝난 회차입니다. | 회차를 다시 조회 |
| `SESSION_ALREADY_OPEN` | 409 | 이 반려견은 이미 측정 중인 회차가 있습니다. | `detail.session_id` 회차로 이동 |
| `SESSION_EMPTY` | 409 | 촬영이 1건 이상 있어야 측정을 끝낼 수 있습니다. | |
| `SESSION_NOT_DONE` | 409 | 회차 집계가 끝난 뒤에 할 수 있습니다. | |
| `SHOT_IN_PROGRESS` | 409 | 분석 중인 촬영이 있어 지금은 지울 수 없습니다. 분석이 끝난 뒤 다시 시도해 주세요. | |
| `SHOT_NOT_FAILED` | 409 | 실패한 촬영만 다시 분석할 수 있습니다. | |
| `REPORT_IN_PROGRESS` | 409 | 보고서를 만드는 중입니다. 잠시 후 다시 시도해 주세요. | |
| `VIDEO_TOO_LARGE` | 413 | 영상 파일이 너무 큽니다. 최대 {max\_mb} MB까지 올릴 수 있습니다. | |
| `VALIDATION_ERROR` | 422 | 입력값을 확인해 주세요. | `detail.fields`로 입력칸 표시 |
| `INTERNAL_ERROR` | 500 | 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요. | |

`{min_sec}`처럼 중괄호가 든 문구는 서버가 값을 채워서 보낸다.

### 11.2 처리 실패 사유 (`fail_reason`)

뒤에서 처리하다 실패하면 응답이 아니라 객체의 `fail_reason`에 남는다. 상태를 다시 조회할 때 보인다.

| code | 어디에 | 기본 문구 |
| --- | --- | --- |
| `ANALYSIS_SUBMIT_FAILED` | 촬영 | 분석 서버에 보내지 못했습니다. 다시 분석을 눌러 주세요. |
| `ANALYSIS_FAILED` | 촬영 | 분석에 실패했습니다. |
| `ANALYSIS_TIMEOUT` | 촬영 | 분석이 너무 오래 걸려 중단했습니다. |
| `VIDEO_RENDER_FAILED` | 촬영(`video_status`=FAILED) | 결과 영상을 만들지 못했습니다. 판정 결과는 그대로 볼 수 있습니다. |
| `AGGREGATION_FAILED` | 회차 | 회차 수치를 계산하지 못했습니다. |
| `REPORT_CHECK_FAILED` | 보고서 | 보고서 검사를 통과하지 못해 내보내지 않았습니다. |
| `REPORT_FAILED` | 보고서 | 보고서를 만들지 못했습니다. |

### 11.3 판정·제외 사유

분석 결과로 나오는 사유다. 촬영은 `validity_reason`, 통과는 `exclude_reason`, 수치는 `unmeasurable_reason`에 온다. 기업의 유효·무효 기준 문서를 받으면 목록이 바뀔 수 있다.

| code | 대상 | 기본 문구 |
| --- | --- | --- |
| `MAT_NOT_FOUND` | 촬영 | 측정 구간(매트)을 찾지 못했습니다. 매트가 화면에 다 보이게 다시 찍어 주세요. |
| `NO_VALID_PASS` | 촬영 | 쓸 수 있는 통과가 없습니다. 다시 찍어 주세요. |
| `FEW_VALID_PASSES` | 촬영 | 쓸 수 있는 통과가 일부만 있습니다. |
| `RUNNING` | 통과 | 뛰었습니다. 천천히 걷게 해 주세요. |
| `STOPPED` | 통과 | 중간에 멈췄습니다. |
| `SITTING` | 통과 | 중간에 앉거나 엎드렸습니다. |
| `TURNED` | 통과 | 중간에 돌아섰습니다. |
| `TOWARD_CAMERA` | 통과 | 카메라 쪽으로 걸었습니다. 옆으로 일직선으로 걷게 해 주세요. |
| `PARTIAL_PASS` | 통과 | 측정 구간을 일부만 지났습니다. |
| `NORMALIZATION_LIMIT` | 통과 | 카메라와의 각도나 거리가 커서 보정할 수 없습니다. |
| `NOT_SIDE_VIEW` | 통과 | 옆모습이 찍히지 않았습니다. |
| `OCCLUDED` | 통과 | 몸이 가려졌습니다. |
| `OVERLAP` | 통과 | 다른 동물이나 사람과 겹쳤습니다. |
| `NO_DOG` | 통과 | 반려견이 화면에 없습니다. |
| `GAIT_PACE` | 통과 | 측대보라 수치 계산에서 뺐습니다. |
| `GAIT_OTHER` | 통과 | 평보·속보가 아니라 수치 계산에서 뺐습니다. |
| `NO_PASS_FOR_LIMB` | 수치 | 이 다리를 잴 유효 통과가 없습니다. 반대 방향으로도 걷게 해 주세요. |
| `NOT_ENOUGH_CYCLES` | 수치 | 보행 주기가 부족해 계산하지 못했습니다. |
| `LOW_CONFIDENCE` | 수치 | 관절점 인식이 불안정해 계산하지 못했습니다. |
| `UNKNOWN_REASON` | 모두 | 사유를 알 수 없습니다. |

### 11.4 경고·안내

오류가 아니다. 요청은 처리되고 `warnings`·`notices`·`note`에 온다.

| code | 어디에 | 기본 문구 |
| --- | --- | --- |
| `BELOW_MIN_SPEC` | 업로드 응답 `warnings` | 최저 사양(640×360, 30fps, 4 Mbps)보다 낮은 영상입니다. 결과가 부정확할 수 있습니다. |
| `ASPECT_NOT_16_9` | 업로드 응답 `warnings` | 화면 비율이 16:9가 아닙니다. 결과가 부정확할 수 있습니다. |
| `RECOMMENDED_MET` | 회차 `notices` | 방향별 권장 통과 수를 채웠습니다. 측정을 끝내도 됩니다. |
| `ONE_SIDE_ONLY` | 회차·회차 결과 `notices` | 좌우 비교: 측정 조건상 비교할 수 없습니다. 반대 방향으로도 걷게 해 주세요. |
| `NO_DATA` | 비교 `note`, 다리 비교 `reason` | 이 회차에는 이 수치가 없습니다. |
| `MODEL_CHANGED` | 비교 `note` | 두 회차의 분석 방식이 달라 변화를 판단하지 않았습니다. |
| `RANGE_NOT_SET` | 비교 `note` | 변화 판단 기준이 아직 정해지지 않았습니다. |

---

## 12. 입력 규칙

화면에서 먼저 검사하면 사용자가 서버 오류를 덜 본다. 최종 검사는 서버가 한다.

### 12.1 영상 업로드

서버는 아래 순서로 검사하고 처음 걸린 하나만 오류로 준다.

| 순서 | 검사 | 허용 | 어기면 |
| --- | --- | --- | --- |
| 1 | 회차 상태 | MEASURING | 409 `SESSION_CLOSED` |
| 2 | 파일 크기 | 최대 100 MB | 413 `VIDEO_TOO_LARGE` |
| 3 | 확장자 | `.mp4`, `.mov` (대소문자 무시) | 400 `VIDEO_FORMAT` |
| 4 | 파일 읽기 | 영상으로 읽힌다 | 400 `VIDEO_UNREADABLE` |
| 5 | 코덱 | H.264, H.265(HEVC) | 400 `VIDEO_CODEC` |
| 6 | 방향 | 가로(너비 > 높이, 회전 정보 반영) | 400 `VIDEO_PORTRAIT` |
| 7 | 길이 | 1~30초 | 400 `VIDEO_DURATION` |
| 8 | 최저 사양 | 640×360, 30fps, 4 Mbps 이상 | 받되 경고 `BELOW_MIN_SPEC` |
| 9 | 화면 비율 | 16:9 (±2%) | 받되 경고 `ASPECT_NOT_16_9` |

- `file` 필드가 아예 없으면 422 `VALIDATION_ERROR`다.
- 화면에서 미리 막기 좋은 것: 2(크기), 3(확장자). 촬영 화면이라면 가로 촬영 안내.

### 12.2 반려견 등록·수정

| 필드 | 필수 | 규칙 |
| --- | --- | --- |
| `name` | 등록 때 | 1~50자. 앞뒤 공백은 서버가 지운다. 같은 이름이 있어도 된다 |
| `breed` | 등록 때 | 1~50자 |
| `weight_kg` | 등록 때 | 0.5~100.0, 소수 둘째 자리까지 |
| `size_class` | 선택 | `SMALL`·`MEDIUM`·`LARGE` |
| `birth_year` | 선택 | 1990~올해 |
| `sex` | 선택 | `MALE`·`FEMALE`·`MALE_NEUTERED`·`FEMALE_SPAYED` |
| `rehab_start_date` | 선택 | 오늘(한국 날짜)까지 |
| `focus_limb` | 선택 | `LF`·`RF`·`LH`·`RH` |
| `baseline_session_id` | 선택(수정 때만) | 이 반려견의 완료 회차 |
| `memo` | 선택 | 최대 1,000자 |

### 12.3 회차 시작

| 필드 | 필수 | 규칙 |
| --- | --- | --- |
| `measured_on` | 선택 | 기본 오늘, 미래 날짜 불가 |
| `weight_kg` | 선택 | 0.5~100.0 |

### 12.4 로그인·목록

| 입력 | 규칙 |
| --- | --- |
| `institution_code` | 1~20자 |
| `login_id` | 1~50자 |
| `password` | 화면에서는 빈칸만 막는다 |
| `page` | 1 이상 |
| `size` | 1~100 (기본 20) |
| `q` | 최대 50자 |

---

## 13. 화면 흐름 예시

한 마리를 처음 등록해 측정하고 결과를 보는 흐름이다.

1. 로그인: `POST /auth/login` → 토큰 저장
2. S1 목록: `GET /dogs` (검색은 `q`)
3. S2 등록: `POST /dogs` → 응답의 `id`로 상세
4. S3 측정 시작: `POST /dogs/{dog_id}/sessions` (이미 열린 회차가 있으면 409의 `detail.session_id`로 이동)
5. S3 촬영 반복: `POST /sessions/{session_id}/shots`로 올리고, 2~3초마다 `GET /sessions/{session_id}`로 진행 막대·판정 갱신
   - 촬영이 FAILED면 `POST /shots/{shot_id}/retry`, 잘못 올렸으면 `DELETE /shots/{shot_id}`
   - 촬영을 누르면 S4: `GET /shots/{shot_id}` → `video_url`로 결과 영상 재생
6. S3 종료: `POST /sessions/{session_id}/complete` → 계속 회차 조회, DONE이 되면 S5
7. S5 결과: `GET /sessions/{session_id}/result` (+ 그래프는 `GET /shots/{shot_id}/angles`)
8. S6 보고서: `GET /sessions/{session_id}/reports`를 3초마다, DONE이면 `file_url`·`download_url`
9. S7 이력: `GET /dogs/{dog_id}/sessions`, 기준 회차 지정은 `PATCH /dogs/{dog_id}`
10. S8 비교·추이: `GET /dogs/{dog_id}/compare`, `GET /dogs/{dog_id}/trends`

---

## 14. 가짜 서버(mock)로 먼저 붙이기

백엔드가 준비되기 전에도 `openapi.yaml`로 같은 모양의 가짜 서버를 띄울 수 있다. 응답은 이 문서의 예시 값이다.

```bash
npx @stoplight/prism-cli mock openapi.yaml --port 4010
```

- 가짜 서버는 주소 앞에 `/api/v1`을 붙이지 않는다. 예: `http://localhost:4010/dogs`. 그래서 화면의 API 기본 주소를 설정값 하나로 두고, 가짜 서버일 때는 `http://localhost:4010`, 실제 서버일 때는 `http://localhost:8000/api/v1`로 바꾼다.
- 토큰은 아무 값이나 `Authorization: Bearer x`로 붙이면 된다. 없으면 401이 온다.
- 가짜 서버는 상태를 기억하지 않는다. 등록해도 목록이 바뀌지 않고, 늘 같은 예시 값을 준다. 입력이 틀렸을 때의 오류 모양도 실제 서버(1.3)와 다르다.

TypeScript 타입이 필요하면 아래로 뽑는다.

```bash
npx openapi-typescript openapi.yaml -o src/api/schema.d.ts
```

---

## 15. 확인할 것 (장준환)

| 번호 | 질문 | 왜 |
| --- | --- | --- |
| 1 | 필드 이름 snake\_case, 2~3초 폴링 그대로 괜찮은가? (백엔드 명세 Q10) | 화면 연결 방식 |
| 2 | 화면 S1~S8에 필요한데 응답에 없는 필드가 있는가? | 서버 구현 전에 넣는 게 싸다 |
| 3 | 화면 개발 서버 주소가 `http://localhost:5173`인가? | CORS 허용 목록 |

바뀔 수 있는 것: 10-20 멘토링 뒤, 분석을 촬영 1건마다 할지 몇 건씩 묶어서 할지 실험해 정하기로 했다. 결과에 따라 촬영의 상태가 바뀌는 시점은 달라질 수 있지만, 응답 모양은 그대로 두는 것이 목표다. 바뀌면 이 문서의 버전을 올려 알린다.
