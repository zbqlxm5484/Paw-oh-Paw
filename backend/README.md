# 크림오프 팀 서비스 백엔드

명세: `크림오프_팀서비스_백엔드_기능명세` v1.13. 지금 들어 있는 것은 작업 단위 1(서버 뼈대), 2(DB 모델·마이그레이션·seed), 3(로그인·기관 분리), 4(반려견 API·체급 분류), 5(회차 시작·조회·취소, 영상 업로드 검사·저장, 파일 저장소), 6(분석 클라이언트, 워커의 분석 제출·상태 조회·결과 저장), 7(촬영 상세·다시 분석·삭제, 결과 영상 렌더 워커·골격 그리기·사람 얼굴 가리기), 8(측정 종료·회차 집계·회차 결과), 12(아이디+비밀번호 로그인, 역할 ADMIN·STAFF·CLIENT와 계산값 GUEST, 기관 계약 종료일, 인증 캐시, 마이그레이션 0003), 13(디바이스 코드 확인·회원가입), 14(크림오프 관리자 API 9개, 비밀번호 변경·내 정보 수정, seed 계약 종료일·이메일), 15(반려견 수정 낙관적 잠금 `version`·409 `DOG_MODIFIED`), 16(이메일 링크 비밀번호 재설정, SMTP 메일)이다. 12~16은 팀장 티켓 S15P31A404-192 "회원가입·로그인 기능 구현"이다.

| 들어 있는 것 | 위치 |
| --- | --- |
| 환경 변수 읽기 (16절) | `app/core/config.py` |
| DB 엔진·세션·오류 코드 (11.7) | `app/core/db.py` |
| 비밀번호 해시·JWT·서명 URL (11.6, 13.4) | `app/core/security.py` |
| 요청 DB 세션, 로그인 담당자 스냅샷·계약 검사·역할 확인(ADMIN, 크림오프) (11.6, 11.7) | `app/api/deps.py` |
| 담당자 스냅샷 캐시 `AuthStaff`(effective_role·contract_status 계산) (11.6 인증 캐시) | `app/core/auth_cache.py` |
| 로그인·내 정보 `POST /auth/login`·`GET /auth/me`, 비밀번호 변경·내 정보 수정 `PATCH /auth/password`·`PATCH /auth/me` (13.4, 13.7, 15.4) | `app/api/routes/auth.py`, `app/services/auth.py`, `app/schemas/auth.py` |
| 디바이스 코드 확인·회원가입 `POST /auth/device-codes/verify`·`POST /auth/signup`(가입 계정은 CLIENT, 코드별 활성 계정 상한) (12.5, 13.5, 15.4) | `app/services/signup.py`, `app/services/device_codes.py` |
| 비밀번호 재설정 `POST /auth/password-reset/request`·`/confirm`(토큰 30분, 해시만 저장)과 SMTP 메일 보내기 (11.6 메일, 13.8, 15.4) | `app/services/password_reset.py`, `app/core/mail.py` |
| 크림오프 관리자 API `/admin/*` 9개: 기관·디바이스 코드·계정 중지(조회는 ADMIN·STAFF, 쓰기는 ADMIN, 기관 필터 없음) (13.6, 15.9) | `app/api/routes/admin.py`, `app/services/admin.py`, `app/schemas/admin.py` |
| 반려견 목록·등록·상세·수정, 수정은 `version` 낙관적 잠금 (12.5, 13.2, 15.5) | `app/api/routes/dogs.py`, `app/services/dogs.py`, `app/schemas/dogs.py` |
| 체급 분류 `classify_size`(체중 기준)와 견종 이름 목록 (12.5) | `app/services/size_class.py`, `config/breeds.yaml` |
| 회차 비교 오차 범위 `config/tolerance.yaml`(통합본 9-3 임시값, 11-05 재측정 값으로 교체)과 읽기(없으면 빈 것, 모양이 틀리면 워커 시작 실패), 변화 판정(5절 비교 규칙·15.8 판정 표, Decimal 계산, 보고서·비교 API 공용) | `app/services/tolerance.py`, `app/report/judge.py` |
| "오늘"의 시간대 (16절 APP_TIMEZONE) | `app/core/dates.py` |
| 회차 시작·상태·진행·촬영 목록·측정 취소, 회차 시점 체급 (12.5, 13.3, 15.6) | `app/api/routes/sessions.py`, `app/services/sessions.py`, `app/schemas/sessions.py` |
| 영상 업로드 검사 9가지·저장 (13.1, 15.6) | `app/services/uploads.py`, `app/video/probe.py`(ffprobe) |
| 촬영 상세(결과 영상 주소는 READY일 때 서명 URL)·다시 분석·삭제·결과 영상 재생(서명 검증, Range 206) (11.6, 13.3, 15.3, 15.6) | `app/api/routes/shots.py`, `app/services/shots.py`, `app/schemas/shots.py`, `app/api/deps.py`의 `check_file_link` |
| 파일 저장소 `StorageService`·`LocalStorage`·파일 키 (7절, 11.11) | `app/storage/` |
| 분석 클라이언트 `MockAnalysisClient`·`HttpAnalysisClient`와 견본 JSON (6절, 16절 `ANALYSIS_API_MODE`) | `app/clients/analysis.py`, `app/clients/fixtures/` |
| 실패한 요청이 만든 파일 정리 (12.4) | `app/api/deps.py`의 `delete_created_files` |
| 워커: UPLOADED 촬영 제출 → SUBMITTED → ANALYZING → DONE(결과 저장), 제출 재시도·시간 초과, 전체·기관별 동시 처리 상한 (3절, 6절, 12.4, 14.2·14.3) | `app/worker/main.py`, `app/services/analysis_results.py` |
| 결과 영상: 렌더 프로세스 풀(spawn, `WORKER_RENDER_CONCURRENCY`), 사람 얼굴 가리기(MediaPipe BlazeFace를 OpenCV DNN으로, 모델 동봉)·관절점으로 골격 그리기(OpenCV)·H.264 인코딩(ffmpeg), READY·FAILED 처리와 작업 폴더 정리 (7절, 12.4, 14.2) | `app/worker/render.py`, `app/video/render.py`, `app/video/models/` |
| 보고서 검사: 금지 표현·보호자용 전문 용어·고정 문구 "보행 평가 보조 자료" (8절 7번, PR-F08-11·12). 목록은 패키지 안 YAML(김지윤 초안, 최종본으로 교체) | `app/report/checks.py`, `app/report/terms.yaml` |
| 보고서 수치 대조(8절 7번 첫 항목, PR-F08-12): 워커가 PDF를 붙이기 전에 자식이 돌려준 실린 숫자 목록을 DB `session_metric` 값·15.7 다리 비교 계산값과 맞춘다. 값이 다르거나 기준에 없으면 PDF 없이 `REPORT_CHECK_FAILED`, 싣지 않은 수치는 불일치 아님 | `app/report/verify.py`(비교), `app/services/report_numbers.py`(기준값), `app/worker/report.py` |
| 보고서 모듈(8절): 입력 dict 검사 → 보행 유형별 수치 표(측정 불가는 사유, 직전 회차 값과 오차 범위 기준 변화 증가·감소·범위 안) → 문장(김지윤 템플릿 전 자리 표시, 보호자용은 용어 설명 자동) → 차트(matplotlib Figure) → HTML(Jinja2) → 검사 → PDF(WeasyPrint). `generate_report(입력 JSON, 출력 PDF)` 하나를 자식 프로세스가 부른다. 미리보기 `python -m scripts.make_report` | `app/report/`(inputs·numbers·sentences·charts·html·pdf·generate, `templates/report.html.j2`) |
| 보고서 워커(12.4): 회차 DONE 때 생긴 OWNER·VET 행을 PENDING → GENERATING → DONE(PDF 저장소)·FAILED(`REPORT_CHECK_FAILED`·`REPORT_FAILED`). 보고서 풀 1개(결과 영상 풀과 별도), 다시 켜면 GENERATING → PENDING | `app/worker/report.py`, `app/services/report_input.py`(입력 dict) |
| 보고서 API: 판본별 상태, 다시 만들기(GENERATING이면 409), PDF 미리보기·내려받기(서명 URL, 한글 파일 이름) (15.7의 19~21) | `app/api/routes/reports.py`, `app/services/reports.py`, `app/schemas/reports.py` |
| 오류 형식·오류 코드·422 변환 (11.5, 14절) | `app/core/errors.py` |
| 화면 문구 (14.5) | `messages/ko.yaml` |
| 앱 생성, CORS, 요청 ID·요청 로그 (11.8, 16절) | `app/main.py` |
| `GET /api/v1/health` (15.9) | `app/api/routes/health.py` |
| 테이블 10개 모델 (12.2) | `app/models/` |
| 마이그레이션 (0001 테이블 9개, 0002 회차 체급, 0003 회원가입·역할·계약: 디바이스 코드 테이블, 계약 종료일, 역할 셋, 아이디 전역 유일) | `alembic/versions/` |
| 기관·계정 만들기 | `scripts/seed.py` |
| 테스트 | `tests/` |

결과 영상 재생(서명 URL 검증)·보고서 등은 다음 작업 단위에서 더한다. 업로드 검사에는 ffprobe, 결과 영상 인코딩에는 ffmpeg가 필요하다: ffmpeg를 설치하고 `.env`의 `FFPROBE_PATH`·`FFMPEG_PATH`에 실행 파일 경로를 적는다(Windows는 `winget install Gyan.FFmpeg` 뒤 전체 경로를 슬래시(`/`)로 적는다). 체급은 등록 체중으로만 나눈다(10 kg 미만 SMALL, 25 kg 미만 MEDIUM, 25 kg 이상 LARGE. 박규원의 체급 기준). 견종 목록(`config/breeds.yaml`)은 화면 자동완성용 초안이고 최종 목록은 박규원과 확정한다. 토큰이 필요한 API는 `Authorization: Bearer <access_token>` 헤더를 붙인다(로그인 응답의 `access_token`). 로그인은 아이디+비밀번호다(기관 코드는 받지 않는다). 기관의 계약 종료일(`institution.contract_ends_at`)이 지나면 그 기관 CLIENT는 `effective_role`이 GUEST가 되어 로그인과 `/auth/me`만 되고 나머지는 403 `CONTRACT_EXPIRED`다. 담당자 스냅샷은 `AUTH_CACHE_TTL_SEC`(기본 60초) 동안 프로세스 메모리에 두므로 계정 중지·계약 만료는 최대 60초 뒤에 반영된다(관리자 API로 바꾼 것은 같은 프로세스에서 즉시). 고객 담당자는 크림오프가 발급한 디바이스 코드(20자, 화면 표시 `XXXXX-XXXXX-XXXXX-XXXXX`)로 `POST /auth/signup`에서 스스로 가입하고(CLIENT, 이메일 필수), 비밀번호를 잊으면 `POST /auth/password-reset/request`가 `{FRONTEND_BASE_URL}/reset-password?token=…` 링크를 메일로 보낸다(`.env`의 `SMTP_HOST`가 비어 있으면 503 `MAIL_UNAVAILABLE`).

## 준비 (처음 한 번)

필요한 것: Python 3.11, PostgreSQL 17(팀 서버와 같은 버전. `docker compose up -d db`로 띄우면 된다). 모든 명령은 `backend` 폴더에서 실행한다.

```bash
python -m venv .venv
# macOS·Linux
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# 한국어 Windows: venv에 딸려 오는 오래된 pip(24.x)는 requirements.txt의 한글 주석을 cp949로 읽다가 멈춘다. 먼저 올린다.
python -m pip install --upgrade pip
pip install -r requirements.txt
```

`.env.example`을 `.env`로 복사하고 `DATABASE_URL`, `TEST_DATABASE_URL`을 내 PostgreSQL에 맞게 고친다.
DB는 두 개 만든다: 개발용(`creamoff`)과 테스트용(`creamoff_test`). 테스트용 DB 이름은 반드시 `_test`로 끝나야 한다.

## 테이블 만들기

```bash
alembic upgrade head
```

Alembic은 Spring의 Flyway와 같은 역할이다. 다른 명령:

| 명령 | 하는 일 |
| --- | --- |
| `alembic upgrade head` | 최신 상태로 테이블 만들기·바꾸기 |
| `alembic downgrade -1` | 한 단계 되돌리기 |
| `alembic revision -m "설명"` | 새 마이그레이션 파일 만들기(`upgrade()`·`downgrade()`는 직접 채운다) |
| `alembic check` | 모델과 DB가 다르면 알려 준다 |

- DB 주소는 `alembic.ini`에 적지 않는다. `alembic/env.py`가 `.env`의 `DATABASE_URL`을 읽는다. 다른 DB에 적용하려면 `alembic -x db_url=postgresql+pg8000://... upgrade head`처럼 준다.
- `alembic.ini`의 주석은 영문(ASCII)만 쓴다. Alembic이 이 파일을 OS 로케일 인코딩(한국어 Windows는 cp949)으로 읽어서, 한글이 한 글자라도 있으면 `alembic` 명령과 pytest가 `UnicodeDecodeError`로 멈춘다. `PYTHONUTF8=1`로도 피할 수 없다.

## 계정 만들기

```bash
python -m scripts.seed --institution-code DEMO --institution-name "데모 병원" --login-id admin --name 관리자 --role ADMIN
```

비밀번호는 화면에서 두 번 묻는다. 8자 이상, UTF-8로 72바이트 이하(한글은 24자까지).
같은 기관에 계정을 더할 때는 `--institution-name`을 빼도 된다. `--role`은 ADMIN·STAFF(크림오프 쪽)·CLIENT(고객 기관 담당자, 기본값)이고, 아이디는 모든 기관에서 유일하다. 고객 담당자는 보통 디바이스 코드로 스스로 가입한다(`POST /auth/signup`). `--contract-ends-at 2027-10-30`은 기관 계약 종료일(당일 포함. 새 기관이면 저장, 있는 기관이면 고친다), `--email`은 재설정 메일을 받을 주소다. 디바이스 코드는 ADMIN 계정으로 `POST /admin/institutions/{id}/device-codes`에서 발급한다.

## 서버 띄우기

```bash
uvicorn app.main:app --no-access-log
```

- `.env`의 `JWT_SECRET`·`FILE_URL_SECRET`(32자 이상, 서로 다른 값)이 비어 있으면 켜지지 않고 어느 값이 문제인지 출력한다(16절). 값 만들기: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- 비밀번호 재설정 메일을 보내려면 `SMTP_HOST`·`SMTP_PORT`·`SMTP_USER`·`SMTP_PASSWORD`·`SMTP_FROM`(STARTTLS)과 링크 앞부분 `FRONTEND_BASE_URL`을 적는다. `SMTP_HOST`가 비어 있으면 메일 없이 돌고 재설정 요청만 503이다. 디바이스 코드 하나의 계정 상한 최댓값은 `DEVICE_CODE_MAX_ACCOUNTS`(기본 10)다.
- 접근 로그는 끈다(11.8). 대신 요청 로그 미들웨어가 메서드, 쿼리를 뺀 경로, 상태 코드, 처리 시간, 요청 ID를 한 줄로 남기고, 응답 헤더 `X-Request-ID`로도 돌려준다.
- `http://localhost:8000/api/v1/health`가 `{"status": "ok", "db": "ok", "version": "1.0.0"}`이면 정상이다. DB에 못 붙으면 503이고 `status`·`db`가 `"error"`다. `storage`는 `STORAGE_ROOT`에 쓸 수 있는지 검사한 결과다.
- 모든 오류 응답은 `{"error": {"code", "message", "detail"}}` 한 모양이다(11.5). `message`는 `messages/ko.yaml`에서 `code`로 찾는다.
- `/docs`(Swagger)·`/redoc`·`/openapi.json`은 `.env`의 `API_DOCS_ENABLED=true`일 때만 열린다(`.env.example`은 true). 배포에서는 끄고, 화면·기업과 맞춘 공식 명세는 `docs/openapi.yaml`이다.

## 워커 띄우기

```bash
python -m app.worker.main
```

- API와 같은 코드를 다른 명령으로 실행하는 별도 프로세스다(3절). `WORKER_POLL_INTERVAL_SEC`(기본 2초)마다 UPLOADED 촬영을 회차 행을 잠근 채 SUBMITTED로 가져온 뒤 분석 API에 보내고, 보낸 것의 상태를 물어 ANALYZING·FAILED로 바꾼다(12.4). 제출에 실패하면 SUBMITTED에 둔 채 다음 바퀴에 다시 보낸다. 제출이 `ANALYSIS_SUBMIT_MAX_ATTEMPTS`번 실패하거나 분석 API가 요청 자체를 거부하면(400·413·415 같은 4xx, 다시 보내지 않음) `ANALYSIS_SUBMIT_FAILED`, 제출 뒤 `ANALYSIS_TIMEOUT_SEC`가 지나면 `ANALYSIS_TIMEOUT`이다. 인증 키가 틀리면(401·403) 촬영을 실패시키지 않고 제출을 멈춘 채 로그만 남기며, 키를 고치면 다음 바퀴에 이어 보낸다.
- 동시에 분석 API에 맡겨 두는 촬영은 전체 `WORKER_MAX_IN_FLIGHT`(기본 16), 기관별 `WORKER_MAX_IN_FLIGHT_PER_INSTITUTION`(기본 4)까지다. 한 기관이 한꺼번에 많이 올려도 그 기관 것은 4건씩만 맡기고, 다른 기관의 새 촬영은 전체 자리가 남아 있으면 바로 가져간다(12.4 기관별 상한). 나머지는 UPLOADED로 기다린다. 둘 다 1 이상이어야 하고, 기관이 하나뿐인 환경에서는 기관별 상한을 전체와 같게 두어도 된다.
- `.env`의 `ANALYSIS_API_MODE=mock`이면 분석 API 없이 견본 결과(`app/clients/fixtures/`)를 `MOCK_ANALYSIS_DELAY_SEC` 뒤에 돌려준다. `http`면 `ANALYSIS_API_BASE_URL`의 분석 API를 부른다. 인증 키 `ANALYSIS_API_KEY`는 `X-API-Key` 헤더로 보내고, 비어 있으면 보내지 않는다.
- 모드를 mock ↔ http로 바꿀 때는 진행 중(SUBMITTED·ANALYZING) 촬영이 없을 때 한다. DB에 남은 작업 ID가 다른 쪽 API에는 없어 상태 조회가 계속 실패하다 `ANALYSIS_TIMEOUT`으로 끝난다.
- **실제 분석 API에 붙이기(S15P31A404-189, 11-02 로컬에서 확인)**: `analysis_api/`를 8010에 띄우고(그 README대로) `.env`에 `ANALYSIS_API_MODE=http`, `ANALYSIS_API_BASE_URL=http://127.0.0.1:8010`, `ANALYSIS_API_KEY`(분석 API의 값과 같게)를 넣은 뒤 API와 워커를 다시 켠다. 확인한 것(분석 API 기본값 `ANALYSIS_POSE_SOURCE=sample`): 촬영 15건이 제출 → `done` → `analysis.json`·통과 행(DONE)까지 8초(기관별 4건씩), 결과 영상은 1건 16~18초(1080p60 8초, 개발 PC). `sample`은 흐름은 실제 API지만 결과는 모든 촬영이 같은 견본(`model.name` `sample-pipeline`, 수치 있음)이다. 엔진 결과를 보려면 `ANALYSIS_POSE_SOURCE=track`인데, 미리 만든 관절점 파일(`ANALYSIS_TRACK_FILE`)에 있는 영상만 찾으므로(SHA-256, 없으면 파일 이름) 새로 찍어 올린 영상은 `POSE_UNAVAILABLE` → 촬영 `ANALYSIS_FAILED`가 된다. 시연에서 엔진 결과를 보이려면 관절점을 만든 원본 영상 파일을 그대로 올린다. `track` 결과는 아직 `metrics` `{}`·`gait` null이라(183·184 뒤에 참) 회차 수치가 비어 나온다. 분석 API는 지금 작업 상태를 메모리에 두므로(그 README 단계 3/4. 182에서 파일 기록으로 바뀜) 분석 API를 다시 켜면 그 전 작업은 404다: 진행 중이던 촬영은 `ANALYSIS_FAILED`, 결과 영상을 아직 안 만든 촬영은 관절점을 못 받아 `VIDEO_RENDER_FAILED`가 된다. 시연 중에는 분석 API를 다시 켜지 않는다. 견본(`app/clients/fixtures/`)은 `analysis_api/samples/`의 결과 JSON v1 사본이고 `tests/test_analysis_api_samples.py`가 같은지 본다(samples를 바꾸는 MR이 사본도 같이 바꾼다, 조유진 11-02).
- 분석이 끝나면 결과 JSON을 촬영 키의 `analysis.json`으로 보관하고 촬영 판정·사유와 통과 행(`walk_pass`)을 넣어 DONE이 된다(6절). 결과 JSON을 읽을 수 없거나 분석 API가 작업이 없다고 답하면(404·410) `ANALYSIS_FAILED`다. 저장 중 오류는 그 촬영만 건너뛰고 다음 바퀴에 다시 한다. 회차 집계·보고서는 다음 작업에서 더한다.
- 결과 영상(12.4 "무거운 일 나누기"): DONE이 된 촬영은 `video_status`가 PENDING이고, 주 반복이 바퀴마다 빈 자리(`WORKER_RENDER_CONCURRENCY`, 기본 1)만큼 `analyzed_at` 순으로 자식 프로세스(spawn 풀)에 맡긴다. 자식은 `app/video/render.py`만 부른다: 원본의 프레임마다 사람 얼굴을 찾아 모자이크로 가리고(MediaPipe BlazeFace를 OpenCV DNN으로, 검출이 끊겨도 0.5초는 그 자리를 계속 가림), 분석 API의 관절점 파일(`get_keypoints`)로 골격을 그린 뒤(OpenCV. 프레임의 `camera_side`에 따라 등 가운데·엉덩이 위와 카메라 쪽 귀·다리만, 반대쪽 귀·다리는 그리지 않는다) ffmpeg로 H.264(yuv420p, faststart, 소리 없음) MP4를 만든다. 작업 폴더는 `UPLOAD_TMP_DIR/worker/{촬영 ID}/`이고 끝나면 지운다. 성공이면 `result.mp4`를 저장소에 넣고 조건을 건 UPDATE로 READY·`result_key`·`video_ready_at`을 붙이며, 그사이 촬영이 지워졌으면 파일을 지운다. 골격 그리기·인코딩 실패, 관절점을 받을 수 없음(작업 없음·거부), 자식 프로세스 종료는 FAILED(`VIDEO_RENDER_FAILED`)이고 판정 결과는 그대로다. 주 반복은 자식을 기다리지 않으므로 결과 영상이 밀려 있어도 분석 제출·조회는 2초 주기대로 돈다. 얼굴 검출 모델(`app/video/models/`, MIT)은 패키지에 들어 있어 설정할 것이 없다.
- 보고서(12.4 "보고서 한 건"): 회차가 DONE이 되는 같은 트랜잭션에서 OWNER·VET 두 행이 PENDING으로 생기고, 주 반복이 보고서 풀(1개)에 맡긴다. 입력은 `services/report_input.py`가 회차 결과(`GET /sessions/{id}/result`와 같은 값)·반려견·직전 DONE 회차로 만들어 `UPLOAD_TMP_DIR/worker/report-{id}/input.json`에 쓰고, 자식은 `app/report/generate.py`만 부른다. 검사(금지 표현·전문 용어·고정 문구)에 걸리면 `REPORT_CHECK_FAILED`, 그 밖의 실패는 `REPORT_FAILED`. 다시 켜면 GENERATING 행을 PENDING으로 돌린다. **WeasyPrint는 시스템 라이브러리가 있어야 PDF를 만든다**(Linux: libpango-1.0-0·libpangoft2-1.0-0, Windows 개발 PC: GTK 런타임. `GTK3-Runtime Win64`를 Program Files나 `%LOCALAPPDATA%\Programs`에 설치하면 `app/report/pdf.py`가 bin 폴더를 찾아 `WEASYPRINT_DLL_DIRECTORIES`로 넣고, 다른 곳이면 그 변수를 직접 둔다). 없으면 보고서는 `REPORT_FAILED`가 되고 HTML 미리보기(`scripts/make_report.py --html`)만 된다. 한글 글꼴은 시스템 글꼴(맑은 고딕·나눔고딕·Noto CJK)을 쓴다.
- 결과 영상 처리 시간: 1080p 60fps 8초 1건이 이 PC에서 약 20초(얼굴 검출 0.05초 간격), 골격만이면 3초다. 측정 방법·표는 `docs/report/renderTiming.md`, 다시 재려면 `python -m scripts.measure_render <영상.mp4>`(관절점 파일이 없으면 합성한다).
- Ctrl+C(SIGINT)나 SIGTERM을 받으면 하던 바퀴를 끝내고 멈춘다. 상태가 DB에 있어 다시 켜면 이어서 한다.

## 테스트

```bash
pytest
```

테스트는 `TEST_DATABASE_URL`의 DB를 지우고 다시 만든다. 개발용 DB는 건드리지 않는다.

## 테이블을 바꿀 때

1. `app/models/`의 모델을 고친다.
2. `alembic revision -m "무엇을 바꾸는지"`로 새 파일을 만들고, `upgrade()`·`downgrade()`를 직접 채운다.
   이미 적용된 마이그레이션 파일은 고치지 않는다.
3. `alembic upgrade head` 후 `pytest`. 모델과 마이그레이션이 어긋나면 `test_models_match_migration`이 실패한다.
4. 명세 12.2 DDL도 같이 고친다.
