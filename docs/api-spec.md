# 크림오프 팀 서비스 API 명세

| 항목 | 내용 |
| --- | --- |
| 버전 | v1.1 (2026-11-02) |
| 기준 | 백엔드 기능 명세 v1.13의 15절(API 상세), 11.5·11.6, 13·14절 |
| 작성 | 조영운(백엔드) |
| 읽는 사람 | 박규원(화면), 장준환(디자인), 김지윤(API 시험) |
| 함께 주는 파일 | `openapi.yaml` (같은 내용을 OpenAPI 3.1로 쓴 파일) |

화면이 부를 API 45개의 요청·응답 모양을 화면 쪽에서 필요한 것만 모았다. 서버 안쪽(DB, 워커, 파일 저장 방식)은 뺐다. 이 문서와 백엔드 명세가 다르면 백엔드 명세가 맞고, 바뀌면 이 문서와 `openapi.yaml`을 같이 고친다.

v1.0에서 바뀐 것: 로그인에서 기관 코드를 뺌(1.2, 4절). `role`에 `CLIENT`를 더하고 계산값 `effective_role`을 추가함(1.2, 10.3). `PATCH /dogs/{dog_id}`에 `version` 필수(5절). 회원가입·비밀번호·크림오프 관리자 API 15개 추가(2절 27~41번). 오류 코드 9개 추가(11.1). `gaits`에 OTHER 추가(7절).

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

1. `POST /auth/login`으로 아이디·비밀번호를 보내면 `access_token`과 만료 시각 `expires_at`이 온다. 회원가입(`POST /auth/signup`)의 응답도 같은 모양이다.
2. 이후 모든 요청에 `Authorization: Bearer <access_token>` 헤더를 붙인다.
3. 토큰은 기본 12시간(서버 설정값) 뒤 만료된다. 정확한 시각은 `expires_at`을 본다. 새로 받는 기능(refresh token)은 없다. `expires_at`이 지나거나 401 `AUTH_EXPIRED`가 오면 로그인 화면으로 보낸다.

토큰 없이 부르는 것: 로그인, 디바이스 코드 확인, 회원가입, 비밀번호 재설정 둘, `/health`, `/metrics`, 서명 주소로 여는 결과 영상과 보고서 PDF.

역할: 화면은 `role`이 아니라 `effective_role`로 분기한다(10.3). 계약이 끝난 `CLIENT`는 `GUEST`로 계산되어 로그인과 `GET /auth/me`만 쓸 수 있고, 나머지는 403 `CONTRACT_EXPIRED`다. `/admin/*` 조회는 `ADMIN`·`STAFF`, 쓰기는 `ADMIN`만 쓸 수 있다.

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

- **입력 오류(422 `VALIDATION_ERROR`)**: 어느 필드가 틀렸는지 `detail.fields`에 온다. `field`는 필드 이름, `type`은 틀린 종류다. 요청 본문이 통째로 없으면 `field`가 `"body"`로 온다("요청 내용이 없습니다"로 보여 주면 된다).

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
| 403 | `CONTRACT_EXPIRED` | 계약 만료 안내. `GET /auth/me`에서는 나지 않는다 |
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

- 개발 환경(`.env`의 `API_DOCS_ENABLED=true`)에서는 `/docs`에 시험 화면(Swagger)이 생긴다. 배포 서버에서는 꺼져 있고, 공식 명세는 이 문서와 `openapi.yaml`이다. 서버가 없을 때는 `openapi.yaml`로 가짜 서버(mock)를 띄워 화면을 먼저 만들 수 있다(14절).
- 화면 개발 서버 주소는 서버의 `CORS_ORIGINS`에 들어 있어야 한다. 기본값은 Vite 개발 서버인 `http://localhost:5173`이다. 주소가 다르면 백엔드에 알려 준다.

---

## 2. 엔드포인트 한눈에

| # | 메서드·주소 | 하는 일 | 화면 | 성공 | 이 API만의 오류 |
| --- | --- | --- | --- | --- | --- |
| 1 | `POST /auth/login` | 로그인(아이디·비밀번호), 토큰 발급 | 로그인 | 200 | 401 `LOGIN_FAILED`, 403 `ACCOUNT_DISABLED` |
| 2 | `GET /auth/me` | 내 정보(`effective_role` 포함. `GUEST`도 된다) | 공통 | 200 | — |
| 3 | `GET /dogs` | 반려견 목록·검색 | S1 | 200 | — |
| 4 | `POST /dogs` | 반려견 등록 | S2 | 201 | — |
| 5 | `GET /dogs/{dog_id}` | 반려견 상세 | S2·S7 | 200 | — |
| 6 | `PATCH /dogs/{dog_id}` | 반려견 수정, 기준 회차 지정(`version` 필수) | S2·S7 | 200 | 400 `BASELINE_INVALID`, 409 `DOG_MODIFIED` |
| 7 | `POST /dogs/{dog_id}/sessions` | 회차 시작 | S3 | 201 | 409 `SESSION_ALREADY_OPEN` |
| 8 | `GET /dogs/{dog_id}/sessions` | 측정 이력 | S7 | 200 | — |
| 9 | `GET /sessions/{session_id}` | 회차 상태·방향별 진행·촬영 목록 | S3 | 200 | — |
| 10 | `DELETE /sessions/{session_id}` | 측정 취소 | S3 | 204 | 409 `SESSION_CLOSED`, `SHOT_IN_PROGRESS`, 503 `ANALYSIS_UNAVAILABLE` |
| 11 | `POST /sessions/{session_id}/shots` | 영상 업로드 | S3 | 201 | 12.1의 업로드 오류 |
| 12 | `POST /sessions/{session_id}/complete` | 측정 종료 | S3 | 200 | 409 `SESSION_CLOSED`, `SESSION_EMPTY` |
| 13 | `GET /shots/{shot_id}` | 촬영 상세 | S4 | 200 | — |
| 14 | `POST /shots/{shot_id}/retry` | 실패한 촬영 다시 분석 | S3·S4 | 200 | 409 `SHOT_NOT_FAILED`, `SESSION_CLOSED`, `SHOT_IN_PROGRESS`, 503 `ANALYSIS_UNAVAILABLE` |
| 15 | `DELETE /shots/{shot_id}` | 촬영 삭제 | S3·S4 | 204 | 409 `SESSION_CLOSED`, `SHOT_IN_PROGRESS`, 503 `ANALYSIS_UNAVAILABLE` |
| 16 | `GET /shots/{shot_id}/video` | 결과 영상 재생 (서명 주소) | S4 | 200·206 | 403 `FILE_LINK_EXPIRED` |
| 17 | `GET /shots/{shot_id}/angles` | 프레임별 관절 각도 (권장) | S5 | 200 | — |
| 18 | `GET /sessions/{session_id}/result` | 회차 수치·다리 비교 요약 | S5 | 200 | 409 `SESSION_NOT_DONE` |
| 19 | `GET /sessions/{session_id}/reports` | 판본별 보고서 상태 | S6 | 200 | — |
| 20 | `POST /reports/{report_id}/regenerate` | 보고서 다시 만들기 | S6 | 200 | 409 `REPORT_IN_PROGRESS` |
| 21 | `GET /reports/{report_id}/file` | PDF 미리보기·내려받기 (서명 주소) | S6 | 200 | 403 `FILE_LINK_EXPIRED` |
| 22 | `GET /dogs/{dog_id}/compare` | 회차 비교 | S8 | 200 | 400 `COMPARE_INVALID` |
| 23 | `GET /dogs/{dog_id}/trends` | 수치 추이 | S8 | 200 | — |
| 24 | `POST /admin/purge` | 자료 파기 (관리자) | — | 200 | 403 `FORBIDDEN`, 409 `SHOT_IN_PROGRESS`, 503 `ANALYSIS_UNAVAILABLE` |
| 25 | `GET /health` | 서버 상태 | — | 200·503 | — |
| 26 | `GET /metrics` | 요청 수·처리 시간 (선택) | — | 200 | — |
| 27 | `POST /auth/device-codes/verify` | 디바이스 코드 확인 (토큰 없음) | 가입 | 200 | 404 `DEVICE_CODE_INVALID` |
| 28 | `POST /auth/signup` | 회원가입 (토큰 없음) | 가입 | 201 | 404 `DEVICE_CODE_INVALID`, 409 `LOGIN_ID_TAKEN` |
| 29 | `GET /admin/institutions` | 기관 목록 (`ADMIN`·`STAFF`) | 관리 | 200 | 403 `FORBIDDEN` |
| 30 | `POST /admin/institutions` | 기관 만들기 (`ADMIN`) | 관리 | 201 | 403 `FORBIDDEN`, 422 `VALIDATION_ERROR`(기관 코드 중복은 `fields`에 `code`) |
| 31 | `PATCH /admin/institutions/{institution_id}` | 기관 이름·계약 종료일 수정 (`ADMIN`) | 관리 | 200 | 403 `FORBIDDEN` |
| 32 | `GET /admin/institutions/{institution_id}/device-codes` | 코드 목록 (`ADMIN`·`STAFF`) | 관리 | 200 | 403 `FORBIDDEN` |
| 33 | `POST /admin/institutions/{institution_id}/device-codes` | 코드 발급 (`ADMIN`) | 관리 | 201 | 403 `FORBIDDEN`, 409 `DEVICE_CODE_EXISTS` |
| 34 | `PATCH /admin/device-codes/{device_code_id}` | 메모 수정 (`ADMIN`) | 관리 | 200 | 403 `FORBIDDEN` |
| 35 | `POST /admin/device-codes/{device_code_id}/revoke` | 코드 회수, 멱등 (`ADMIN`) | 관리 | 200 | 403 `FORBIDDEN` |
| 36 | `GET /admin/institutions/{institution_id}/staff` | 기관의 계정 목록 (`ADMIN`·`STAFF`) | 관리 | 200 | 403 `FORBIDDEN` |
| 37 | `PATCH /admin/staff/{staff_id}` | 계정 중지·재개 (`ADMIN`) | 관리 | 200 | 403 `FORBIDDEN`, 409 `SELF_DISABLE` |
| 38 | `PATCH /auth/password` | 비밀번호 변경 | 내 정보 | 200 | 400 `PASSWORD_MISMATCH` |
| 39 | `PATCH /auth/me` | 이름·이메일 수정 | 내 정보 | 200 | — |
| 40 | `POST /auth/password-reset/request` | 재설정 링크 메일 보내기 (토큰 없음) | 재설정 | 204 | 503 `MAIL_UNAVAILABLE` |
| 41 | `POST /auth/password-reset/confirm` | 링크의 토큰으로 비밀번호 바꾸기 (토큰 없음) | 재설정 | 204 | 400 `RESET_TOKEN_INVALID` |
| 42 | `DELETE /dogs/{dog_id}` | 반려견을 휴지통에 넣기 | — | 204 | 409 `SHOT_IN_PROGRESS` |
| 43 | `POST /dogs/{dog_id}/restore` | 휴지통에서 복원 | — | 200 | — |
| 44 | `DELETE /dogs/{dog_id}/permanent` | 휴지통의 반려견 영구 삭제(되돌릴 수 없음) | — | 204 | 409 `SHOT_IN_PROGRESS`, 503 `ANALYSIS_UNAVAILABLE` |
| 45 | `DELETE /auth/me` | 회원 탈퇴 | 계정 | 204 | 400 `PASSWORD_MISMATCH`, 409 `LAST_ACCOUNT` |

화면 번호: S1 반려견 목록, S2 반려견 등록·상세, S3 측정, S4 촬영 상세, S5 회차 결과, S6 보고서, S7 측정 이력, S8 비교·추이.

2026-11-02 develop 기준으로 8, 17, 19~24, 26번은 아직 구현 전이다.

---

## 3. 공통 객체

여러 API가 같은 모양으로 주는 객체다. 값은 예시이고 `"…"`는 UUID다. "\<ShotOut>"처럼 쓴 자리에는 그 객체가 통째로 들어간다.

### StaffOut — 로그인한 담당자

```json
{
  "id": "…",
  "login_id": "kim01",
  "name": "김담당",
  "email": "kim01@example.com",
  "role": "CLIENT",
  "effective_role": "CLIENT",
  "notif_on": true,
  "institution": {
    "id": "…", "code": "INST-7F3K2Q", "name": "크림 재활센터",
    "contract_ends_at": "2027-10-30", "contract_status": "ACTIVE"
  }
}
```

- `effective_role`: 화면은 이 값으로 분기한다. `GUEST`면 만료 안내, `ADMIN`·`STAFF`면 관리 화면 진입(10.3).
- `contract_ends_at`: 계약 마지막 날(당일 포함). `null`은 기한 없음이다.

### DeviceCodeOut — 디바이스 코드 (크림오프 관리자 API)

```json
{
  "id": "…", "code": "7F3K2-QW9PA-X2M8N-H4CDE", "institution_id": "…",
  "active_accounts": 2, "revoked_at": null,
  "note": null, "created_at": "2026-10-30T02:00:00Z"
}
```

- 코드 전체가 든 자리는 발급 응답과 코드 목록뿐이다.

### InstitutionAdminOut — 기관 (크림오프 관리자 API)

```json
{
  "id": "…", "code": "INST-7F3K2Q", "name": "크림 재활센터",
  "contract_ends_at": "2027-10-30", "contract_status": "ACTIVE",
  "staff_count": 2, "device_code_count": 1, "created_at": "…"
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
  "version": 0,
  "session_count": 3,
  "last_measured_on": "2026-10-20",
  "open_session_id": null,
  "deleted_at": null,
  "purge_at": null,
  "created_at": "2026-10-19T00:30:00Z",
  "updated_at": "2026-10-19T00:30:00Z"
}
```

- `session_count`: 이 반려견의 회차 수(상태 상관없이). `last_measured_on`: 가장 최근 회차의 측정일. 없으면 `null`.
- `open_session_id`: 측정 중(MEASURING)인 회차가 있으면 그 ID. 목록에서 "측정 중" 표시와 이어서 측정하기에 쓴다.
- `size_class_manual`: 담당자가 체급을 직접 고쳤으면 true. false면 등록 체중으로 자동 분류한 값이다(10kg 미만 SMALL, 25kg 미만 MEDIUM, 25kg 이상 LARGE. 견종은 보지 않는다).
- `baseline_session_id`: 담당자가 지정한 기준 회차. `null`이면 가장 이른 완료 회차가 기준이다.
- `memo`: 내부 메모. 담당자 화면에만 보이고 보고서에는 들어가지 않는다.
- `version`: 수정할 때 그대로 돌려보낸다(5절 `PATCH`). 수정될 때마다 1 늘어난다.

### SessionOut — 회차

```json
{
  "id": "…",
  "dog_id": "…",
  "staff": {"id": "…", "name": "김담당"},
  "measured_on": "2026-10-20",
  "weight_kg": 28.1,
  "size_class": "LARGE",
  "status": "MEASURING",
  "fail_reason": null,
  "model_name": null,
  "model_version": null,
  "completed_at": null,
  "aggregated_at": null,
  "created_at": "2026-10-20T00:10:00Z"
}
```

- `size_class`: 회차를 시작한 시점의 체급. 그날 체중(없으면 등록 체중)으로 정하고, 담당자가 직접 지정한 체급이 있으면 그 값이다. 뒤에 반려견 체급이 바뀌어도 이 값은 그대로라 반려견 화면의 체급과 다를 수 있다. 회차 결과·보고서의 체급별 기준은 이 값을 쓴다.

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
{"login_id": "kim01", "password": "…"}

// 응답 200
{
  "access_token": "eyJhbGciOi…",
  "token_type": "bearer",
  "expires_at": "2026-10-20T12:10:00Z",
  "staff": "<StaffOut>"
}
```

- 아이디·비밀번호 중 무엇이 틀려도 401 `LOGIN_FAILED` 하나로 온다. 화면도 어느 칸이 틀렸는지 표시하지 않는다.
- 아이디는 대소문자를 구분한다. 기관 코드는 받지 않는다(보내도 무시한다).
- 비밀번호까지 맞았는데 사용이 중지된 계정이면 403 `ACCOUNT_DISABLED`다.
- 계약이 끝난 `CLIENT`도 로그인되고 `staff.effective_role`이 `GUEST`다. 화면은 이 값을 보고 만료 안내로 보낸다.

### `GET /auth/me` — 내 정보

응답 200 **StaffOut**. 새로고침 뒤 토큰이 아직 쓸 수 있는지 확인할 때도 쓴다. `GUEST`도 부를 수 있다.

### `PATCH /auth/me` — 이름·이메일·알림 설정 수정

요청 `{"name"?, "email"?, "notif_on"?}`. 보낸 필드만 바꾸고 `null`은 받지 않는다(규칙은 12.7). 응답 200 **StaffOut**.

- `notif_on`은 알림을 받을지의 설정값(`true`/`false`)이고 계정마다 따로다. 서버는 저장만 하고 알림을 보내지 않는다. **StaffOut**의 `notif_on`으로 돌아온다(로그인 응답 포함).

### `DELETE /auth/me` — 회원 탈퇴

요청 `{"password": "…"}`(현재 비밀번호). 응답 204(본문 없음).

- 비밀번호가 틀리면 400 `PASSWORD_MISMATCH`, 기관의 마지막 활성 계정이면 409 `LAST_ACCOUNT`다. 둘 다 아무것도 바뀌지 않는다.
- 탈퇴하면 계정이 중지된다. 그 뒤 로그인과 이미 받은 토큰은 **403 `ACCOUNT_DISABLED`**다(401이 아니다). 화면은 204를 받으면 토큰을 버리고 로그인 화면으로 보낸다.
- 반려견·회차는 기관의 자료라 그대로 남는다. 계약이 끝난 기관의 담당자도 탈퇴할 수 있다.

### `PATCH /auth/password` — 비밀번호 변경

```json
// 요청
{"current_password": "…", "new_password": "…"}

// 응답 200 StaffOut
```

- 현재 비밀번호가 틀리면 400 `PASSWORD_MISMATCH`다. 새 비밀번호 규칙은 12.7.
- 이미 받은 토큰은 그대로 쓸 수 있다.

### `POST /auth/device-codes/verify` — 디바이스 코드 확인 (토큰 없음)

```json
// 요청
{"code": "7f3k2-qw9pa-x2m8n-h4cde"}

// 응답 200
{"institution": {"id": "…", "name": "크림 재활센터"}}
```

- 코드 형식이 틀렸거나, 없거나, 회수됐거나, 기관 계약이 끝났으면 모두 404 `DEVICE_CODE_INVALID` 하나로 온다.
- 남은 자리 수(`remaining_accounts`)는 없어졌다. 코드 하나로 만들 수 있는 계정 수에 상한이 없다.
- 하이픈·공백·소문자는 서버가 정리하므로 입력 그대로 보내면 된다. 몇 번 불러도 결과가 같다.

### `POST /auth/signup` — 회원가입 (토큰 없음)

```json
// 요청
{"code": "7F3K2-QW9PA-X2M8N-H4CDE", "login_id": "kim01", "password": "…", "name": "김담당", "email": "kim01@example.com",
 "terms": {"version": "2026-11-01", "service": true, "privacy": true, "device_location": true, "marketing": false}}

// 응답 201: POST /auth/login의 응답과 같다
```

- `terms`는 약관 동의다. `service`·`privacy`·`device_location`(필수 3개)은 `true`여야 하고 아니면 422다. `marketing`(선택)은 기본 `false`다. `version`은 화면이 보여 준 약관의 버전(1~20자)이다.
- `terms`를 보내지 않아도 지금은 가입된다. 다만 서버에 동의 기록이 남지 않는다. 웹과 앱이 보내기 시작하면 필수로 바꾼다.

- 가입 계정은 모두 `CLIENT`이고 코드의 기관에 속한다. 가입 즉시 로그인된 상태다. 로그인 화면으로 보내고 싶으면 토큰을 버리면 된다.
- 코드 오류는 확인 API와 같고, 아이디가 겹치면(다른 기관이어도) 409 `LOGIN_ID_TAKEN`이다. 입력 규칙은 12.5.
- 이메일은 형식만 검사하고 인증 메일은 보내지 않는다.

### `POST /auth/password-reset/request` — 재설정 링크 메일 보내기 (토큰 없음)

요청 `{"login_id": "kim01"}`. 응답 204(본문 없음)이고 계정이 있든 없든 같다. 화면은 "등록된 이메일로 안내를 보냈습니다"를 보여 준다.

- 메일 서버가 설정되지 않았거나 발송에 실패하면 503 `MAIL_UNAVAILABLE`이다.
- 메일의 링크는 `{화면 주소}/reset-password?token={토큰}`이고 30분 동안 쓸 수 있다. 계약이 끝난 계정에도 보낸다.

### `POST /auth/password-reset/confirm` — 토큰으로 비밀번호 바꾸기 (토큰 없음)

요청 `{"token": "…", "new_password": "…"}`. 응답 204(본문 없음)이고 화면은 로그인 화면으로 보낸다. 토큰이 잘못됐거나 만료되면 400 `RESET_TOKEN_INVALID`다.

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
// 요청: version은 필수(읽었을 때의 값), 나머지는 바꿀 필드만 보낸다
{"version": 3, "weight_kg": 27.9, "baseline_session_id": "…"}
```

- 응답 200 **DogOut**.
- `version`이 저장된 값과 다르면 409 `DOG_MODIFIED`이고 아무것도 바뀌지 않는다. 다른 담당자가 먼저 고친 경우이니 다시 불러온 뒤 시도한다. `version`이 없으면 422다.
- 보내지 않은 필드는 그대로다. 값을 비우려면 `null`을 보낸다. `name`·`breed`·`weight_kg`은 비울 수 없다.
- `weight_kg`를 바꾸면 체급을 직접 고친 적이 없을 때만 새 체중으로 체급이 다시 정해진다. `breed`를 바꿔도 체급은 그대로다.
- `size_class`에 값을 보내면 직접 고친 것으로 저장되고, `null`을 보내면 자동 분류로 돌아간다.
- `baseline_session_id`는 이 반려견의 완료(DONE) 회차여야 한다. 아니면 400 `BASELINE_INVALID`다. `null`을 보내면 지정을 풀고 가장 이른 완료 회차가 기준이 된다.

### 휴지통

삭제 버튼은 반려견을 지우지 않고 휴지통에 넣는다. 휴지통의 반려견은 목록·상세·회차·결과 어디에서도 404다. 30일이 지나면 서버가 영구 삭제하고, 그 전에는 복원할 수 있다.

계약이 끝난 기관은 종료일에서 90일이 지나면 서버가 측정 자료와 가입 계정을 지운다. 기관과 디바이스 코드는 남는다. 그 전에 계약을 연장하면 지워지지 않는다.

- **휴지통 목록:** `GET /dogs?trash=true`. 응답 모양은 반려견 목록과 같다. 항목의 `deleted_at`은 휴지통에 넣은 시각, `purge_at`은 영구 삭제 예정 시각이다(휴지통에 없는 반려견은 둘 다 `null`).
- **`DELETE /dogs/{dog_id}` — 휴지통에 넣기:** 응답 204. 분석 중인 촬영이 있으면 409 `SHOT_IN_PROGRESS`다. 이미 휴지통에 있거나 없는 반려견은 404다.
- **`POST /dogs/{dog_id}/restore` — 복원:** 본문 없음. 응답 200 **DogOut**. 회차·영상·보고서가 그대로 돌아온다. 휴지통에 없는 반려견은 404다. 영구 삭제가 먼저 시작됐으면 그것이 끝난 뒤 404로 답한다.
- **`version`:** 휴지통에 넣을 때와 복원할 때 1씩 오른다. 복원한 뒤 `PATCH /dogs/{dog_id}`를 부를 때는 복원 응답의 `version`을 쓴다. 전에 들고 있던 값으로 보내면 409 `DOG_MODIFIED`다.
- **`DELETE /dogs/{dog_id}/permanent` — 영구 삭제:** 응답 204. **되돌릴 수 없으니 화면에서 확인을 받은 뒤 부른다.** 휴지통에 있는 반려견만 된다(아니면 404). 분석 서버의 사본을 지우지 못하면 503 `ANALYSIS_UNAVAILABLE`이고 휴지통에 그대로 남는다. 잠시 뒤 다시 부르면 된다. 휴지통 전체 비우기는 목록의 반려견마다 부른다.

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
- 응답의 `size_class`는 그날 체중(없으면 등록 체중)으로 정한 회차 체급이다. 반려견 화면의 체급과 다를 수 있다(감량한 개는 그 뒤 회차부터 중형).
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
- 서버는 분석 서버에 남은 이 회차의 사본을 먼저 지운다. 지우지 못하면 503 `ANALYSIS_UNAVAILABLE`이고 회차는 그대로다. 잠시 뒤 다시 누르면 된다. 드물게, 화면에는 실패로 보이는 촬영을 분석 서버가 아직 처리하고 있으면 409 `SHOT_IN_PROGRESS`가 온다. 이때도 잠시 뒤 다시 누른다.

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
- 서버는 실패했던 분석의 사본을 분석 서버에서 먼저 지운다. 지우지 못하면 503 `ANALYSIS_UNAVAILABLE`, 분석 서버가 그 촬영을 아직 처리하고 있으면 409 `SHOT_IN_PROGRESS`이고 촬영은 FAILED 그대로다. 둘 다 잠시 뒤 다시 누르면 된다(시간 초과로 실패한 촬영에서 날 수 있다).

### `DELETE /shots/{shot_id}` — 촬영 삭제

- 응답 204. 남은 촬영의 번호(`seq_no`)는 다시 매기지 않는다.
- 회차가 MEASURING이 아니면 409 `SESSION_CLOSED`, 촬영이 분석 중(SUBMITTED·ANALYZING)이면 409 `SHOT_IN_PROGRESS`다.
- 서버는 분석 서버에 남은 이 촬영의 사본을 먼저 지운다. 지우지 못하면 503 `ANALYSIS_UNAVAILABLE`이고 촬영은 그대로다. 잠시 뒤 다시 누르면 된다.

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
- `gaits`: 보행 유형별 묶음(WALK, TROT, OTHER 순서, 값이 있는 유형만). OTHER에는 보행 유형을 아직 판별하지 못한 유효 통과가 들어간다. `metrics`는 10.4 표 순서, 같은 수치 안에서는 LF·RF·LH·RH 순서다. 분석이 끝났는데 유효 통과가 하나도 없으면 `gaits`는 빈 배열이고 `pass_counts.used`는 0이다. 화면은 빈 표 대신 `exclude_summary`와 다시 촬영 안내를 보여 준다.
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
| `UNKNOWN` | 판단하지 않았다. 값과 `diff`는 있다 | `MODEL_CHANGED`(분석 방식이 바뀜) 또는 `RANGE_NOT_SET`(기준 미정, 또는 두 회차 중 한쪽이라도 그 수치·그 다리의 `n_passes`가 8 미만) |
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
{"scope": "DOG", "target_id": "…", "institution_id": "…", "dry_run": true}

// 응답 200
{"scope": "DOG", "target_id": "…", "dry_run": true,
 "rows": 214, "files": 49, "bytes": 391000000, "analysis_jobs": 12, "purge_log_id": null}
```

- `scope`: `DOG`(반려견 하나, `target_id` 필요) 또는 `INSTITUTION`(기관 전체, `target_id` 생략).
- `institution_id`: 지울 자료가 있는 기관. 생략하면 부른 관리자의 기관이다. 없는 기관이거나 그 기관에 없는 반려견이면 404 `NOT_FOUND`다. 응답은 개수뿐이다.
- `dry_run` 기본값은 true다. 지울 양만 세고 아무것도 지우지 않는다. 실제로 지우려면 false를 보낸다.
- 관리자가 아니면 403 `FORBIDDEN`, 분석 중인 촬영이 있으면 409 `SHOT_IN_PROGRESS`다.
- `analysis_jobs`는 분석 서버에서 지운(또는 지울) 작업 수다. 실제로 지울 때 분석 서버의 사본을 먼저 지우고, 지우지 못하면 팀 서비스 자료는 그대로 둔 채 503 `ANALYSIS_UNAVAILABLE`이다. 다시 부르면 이어서 끝난다.

### 크림오프 관리자 API

크림오프 쪽 화면에서만 쓴다. 조회는 `ADMIN`·`STAFF`, 쓰기는 `ADMIN`만 쓸 수 있고, 아니면 403 `FORBIDDEN`이다. 기관·코드·계정 정보만 다루고 고객 자료는 열지 않는다. 없는 ID는 404 `NOT_FOUND`다. 입력 규칙은 12.6.

- **`GET /admin/institutions`**: 응답 200 `{"items": [InstitutionAdminOut, …]}`. 페이지 없이 전체이고 이름 순서다.
- **`POST /admin/institutions`**: 요청 `{"code": null, "name": "크림 재활센터", "contract_ends_at": "2027-10-30"}`. 응답 201 **InstitutionAdminOut**. 기관 코드가 겹치면 422 `VALIDATION_ERROR`(`fields`에 `code`)다.
- **`PATCH /admin/institutions/{institution_id}`**: 요청 `{"name"?, "contract_ends_at"?}`. 보낸 필드만 바꾸고 `contract_ends_at`의 `null`은 기한 없음이다. 응답 200 **InstitutionAdminOut**.
- **`GET /admin/institutions/{institution_id}/device-codes`**: 응답 200 `{"items": [DeviceCodeOut, …]}`. 회수된 코드도 들어 있고 `revoked_at`으로 구분한다.
- **`POST /admin/institutions/{institution_id}/device-codes`**: 요청 `{"note"?: "2호기"}`. 본문을 비워도 된다. 응답 201 **DeviceCodeOut**. 기관마다 쓸 수 있는 코드는 하나라, 회수하지 않은 코드가 있으면 409 `DEVICE_CODE_EXISTS`다. 새 코드를 주려면 먼저 회수한다.
- **`PATCH /admin/device-codes/{device_code_id}`**: 요청 `{"note"?}`(`null`은 메모 지우기). 응답 200 **DeviceCodeOut**. `max_accounts`는 없어졌고 보내도 무시한다.
- **`POST /admin/device-codes/{device_code_id}/revoke`**: 본문 없음. 이미 회수됐어도 200이다. 기존 계정은 그대로 쓴다(막으려면 계정 중지). 응답 200 **DeviceCodeOut**.
- **`GET /admin/institutions/{institution_id}/staff`**: 응답 200 `{"items": [{id, login_id, name, email, role, is_active, device_code_id, created_at}, …]}`.
- **`PATCH /admin/staff/{staff_id}`**: 요청 `{"is_active": false}`. 응답 200: 위 목록의 항목 하나. 자기 자신에게 false를 보내면 409 `SELF_DISABLE`이다.

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
| `role` | `ADMIN`, `STAFF`(크림오프), `CLIENT`(고객 기관) |
| `effective_role` | `role`의 값 또는 `GUEST`. `role`이 `CLIENT`이고 기관 계약이 끝났으면 `GUEST`다. 화면은 이 값으로 분기한다 |
| `contract_status` | `ACTIVE`, `EXPIRED`. 계약 종료일이 없거나 오늘(한국 날짜) 이후면 `ACTIVE`다 |
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

단위: `deg`(°), `pct`(%), `pct_body`(몸통 길이 대비 %), `body_per_sec`(몸통 길이/초), `count`(회). 거리 수치는 cm가 아니라 몸통 길이 대비 값이다.

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
| `PASSWORD_MISMATCH` | 400 | 현재 비밀번호가 맞지 않습니다. | |
| `RESET_TOKEN_INVALID` | 400 | 재설정 링크가 유효하지 않거나 만료되었습니다. 다시 요청해 주세요. | 재설정 요청 화면으로 |
| `AUTH_REQUIRED` | 401 | 로그인이 필요합니다. | 로그인 화면으로 |
| `AUTH_EXPIRED` | 401 | 로그인 시간이 지났습니다. 다시 로그인해 주세요. | 로그인 화면으로 |
| `LOGIN_FAILED` | 401 | 아이디 또는 비밀번호가 맞지 않습니다. | |
| `ACCOUNT_DISABLED` | 403 | 사용이 중지된 계정입니다. | 로그인 화면으로 |
| `CONTRACT_EXPIRED` | 403 | 기관의 이용 계약이 만료되었습니다. 크림오프에 문의해 주세요. | 만료 안내 화면으로 |
| `FORBIDDEN` | 403 | 이 기능을 사용할 권한이 없습니다. | |
| `FILE_LINK_EXPIRED` | 403 | 링크가 만료되었습니다. 화면을 새로 불러와 주세요. | 조회 API를 다시 불러 새 주소 받기 |
| `NOT_FOUND` | 404 | 요청한 정보를 찾을 수 없습니다. | |
| `DEVICE_CODE_INVALID` | 404 | 유효한 디바이스 코드가 아닙니다. | |
| `SESSION_CLOSED` | 409 | 측정이 끝난 회차입니다. | 회차를 다시 조회 |
| `SESSION_ALREADY_OPEN` | 409 | 이 반려견은 이미 측정 중인 회차가 있습니다. | `detail.session_id` 회차로 이동 |
| `SESSION_EMPTY` | 409 | 촬영이 1건 이상 있어야 측정을 끝낼 수 있습니다. | |
| `SESSION_NOT_DONE` | 409 | 회차 집계가 끝난 뒤에 할 수 있습니다. | |
| `SHOT_IN_PROGRESS` | 409 | 분석 중인 촬영이 있어 지금은 지울 수 없습니다. 분석이 끝난 뒤 다시 시도해 주세요. | |
| `SHOT_NOT_FAILED` | 409 | 실패한 촬영만 다시 분석할 수 있습니다. | |
| `REPORT_IN_PROGRESS` | 409 | 보고서를 만드는 중입니다. 잠시 후 다시 시도해 주세요. | |
| `DEVICE_CODE_EXISTS` | 409 | 이 기관에는 쓸 수 있는 디바이스 코드가 이미 있습니다. 회수한 뒤 새로 발급해 주세요. | 관리자 화면: 회수한 뒤 발급 |
| `LOGIN_ID_TAKEN` | 409 | 이미 사용 중인 아이디입니다. | 아이디 칸 표시 |
| `DOG_MODIFIED` | 409 | 다른 담당자가 먼저 수정했습니다. 화면을 새로 불러온 뒤 다시 시도해 주세요. | 반려견을 다시 조회 |
| `SELF_DISABLE` | 409 | 자기 계정은 중지할 수 없습니다. | |
| `LAST_ACCOUNT` | 409 | 기관의 마지막 계정이라 탈퇴할 수 없습니다. 관리자에게 문의해 주세요. | 계정 화면에 안내 |
| `VIDEO_TOO_LARGE` | 413 | 영상 파일이 너무 큽니다. 최대 {max\_mb} MB까지 올릴 수 있습니다. | |
| `VALIDATION_ERROR` | 422 | 입력값을 확인해 주세요. | `detail.fields`로 입력칸 표시 |
| `INTERNAL_ERROR` | 500 | 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요. | |
| `MAIL_UNAVAILABLE` | 503 | 지금은 메일을 보낼 수 없습니다. 잠시 뒤 다시 시도해 주세요. | |
| `ANALYSIS_UNAVAILABLE` | 503 | 분석 서버의 자료를 지우지 못했습니다. 잠시 뒤 다시 시도해 주세요. | 자료 파기, 반려견 영구 삭제, 측정 취소, 촬영 삭제, 다시 분석 |

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

분석 결과로 나오는 사유다. 촬영은 `validity_reason`, 통과는 `exclude_reason`, 수치는 `unmeasurable_reason`에 온다. 기업의 유효·무효 기준 문서를 받으면 목록이 바뀔 수 있다. 촬영이 일부 유효(`PARTIAL`)인데 `validity_reason`이 null이면 유효 통과는 충분하고 제외된 통과만 있다는 뜻이다. 어느 통과가 왜 빠졌는지는 통과별 `exclude_reason`에 있다.

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
| `NO_DOG` | 촬영·통과 | 반려견이 화면에 없습니다. |
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
| `login_id` | 1~50자 |
| `password` | 화면에서는 빈칸만 막는다 |
| `page` | 1 이상 |
| `size` | 1~100 (기본 20) |
| `q` | 최대 50자 |

### 12.5 디바이스 코드·가입

| 입력 | 규칙 |
| --- | --- |
| `code` | 하이픈·공백을 지우고 대문자로 바꾼 뒤 20자이고 모두 코드 글자(`ABCDEFGHJKMNPQRSTUVWXYZ23456789`, 혼동되는 0·O·1·I·L을 뺀 32종)여야 한다. 아니면 404 `DEVICE_CODE_INVALID`. 화면에는 `XXXXX-XXXXX-XXXXX-XXXXX`로 보여 준다 |
| `login_id` | 4~50자, 영문 소문자·숫자·`.`·`_`·`-`만. 대문자를 넣으면 422 |
| `password` | 8자 이상, UTF-8로 72바이트 이하(한글 한 글자는 3바이트). 비밀번호 확인은 화면만 한다 |
| `name` | 1~50자. 앞뒤 공백은 서버가 지운다 |
| `email` | 필수. 5~254자, `@`가 하나이고 그 뒤에 `.`이 있어야 한다. 소문자로 저장한다 |

### 12.6 관리자

| 입력 | 규칙 |
| --- | --- |
| 기관 `code` | 1~20자, 유일. 비우면 서버가 `INST-` + 6자로 만든다 |
| 기관 `name` | 1~100자 |
| `contract_ends_at` | 날짜 또는 `null`. 과거 날짜도 받는다(즉시 만료시키는 용도). 오늘에서 90일보다 더 지난 날짜는 422다. 오늘 − 90일까지는 받고, 그 날짜를 넣은 기관은 다음 날부터 자동 파기 대상이다 |
| `note` | 최대 100자 |
| `is_active` | true/false. 자기 자신을 false로 하면 409 `SELF_DISABLE` |

### 12.7 비밀번호 변경·내 정보

| 입력 | 규칙 |
| --- | --- |
| `current_password` | 길이를 검사하지 않는다. 틀리면 400 `PASSWORD_MISMATCH` |
| `new_password` | 12.5의 `password` 규칙. 현재 비밀번호와 같으면 422(`fields`에 `new_password`) |
| `name`, `email`(`PATCH /auth/me`) | 12.5와 같다. 보낸 필드만 바꾼다 |

### 12.8 비밀번호 재설정

| 입력 | 규칙 |
| --- | --- |
| `login_id`(request) | 1~50자. 없는 아이디여도 204 |
| `token`(confirm) | 1~100자. 메일 링크의 값이고 30분 뒤 만료된다. 잘못됐거나 만료되면 400 `RESET_TOKEN_INVALID` |
| `new_password`(confirm) | 12.5의 `password` 규칙 |

---

## 13. 화면 흐름 예시

한 마리를 처음 등록해 측정하고 결과를 보는 흐름이다.

1. 가입 또는 로그인: 처음이면 `POST /auth/device-codes/verify`로 코드를 확인하고 `POST /auth/signup`, 아니면 `POST /auth/login` → 토큰 저장. `staff.effective_role`이 `GUEST`면 만료 안내로
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
