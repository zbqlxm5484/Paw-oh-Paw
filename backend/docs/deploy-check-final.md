# 팀 서버 배포 최종 점검 (티켓 279)

티켓 S15P31A404-279(백엔드 배포 최종 점검)의 기록이다. 백엔드 담당(조영운)이 적는다. 중간 점검은 `deploy-check-2026-11-04.md`(티켓 199)에 있다. 서버와 배포 파일은 손대지 않는다. 배포·인프라는 허정원 담당이다.

## 이 문서의 상태

- 2026-11-12: **1\~3절을 채웠다.** develop `af8a7de`의 배포 파일과 백엔드 설정을 읽은 것이다.
- 2026-11-12 13:51: 운영 주소에 4.1의 호출 여섯을 미리 돌렸다(4.0). 서버에서 본 것은 이것뿐이다.
- 2026-11-13: develop `8ee66c1`을 다시 읽었다. 보고서 렌더러(Gotenberg)가 compose에 들어가(티켓 310) 2절의 보고서 PDF 줄, 3절 5번의 설정 줄, 4.2의 5번, 4.4의 1번과 4번을 고쳤다. 같은 날 로컬에서 같은 이미지로 보고서를 찍어 본 것을 2절 아래에 적었다.
- 4.1\~4.4의 결과 칸은 운영 배포가 끝난 뒤에 채운다. 지금은 비어 있다.

## 1. 배포가 나가는 길 (저장소에서 본 것)

| 환경 | 브랜치 | compose 프로젝트 | 호스트 포트 | 배포 | 서버 `.env`가 오는 곳 | 분석 API |
| --- | --- | --- | --- | --- | --- | --- |
| 운영 | master | `creamoff` | 8080 | 수동(`deploy_prod`) | CI 변수 `ENV_FILE` | GPU 서버 |
| 개발 | develop | `creamoff-dev` | 8082 | 머지하면 자동(`deploy_dev`) | CI 변수 `ENV_FILE_DEV` | mock(`.gitlab-ci.yml`의 주석) |

- 두 환경은 같은 EC2 한 대에서 돌고, DB와 업로드 볼륨은 따로다.
- 환경이 둘로 나뉜 것은 11-11 11:07의 머지(티켓 307)부터다. 그 전에는 develop이 `creamoff`(8080)로 자동 배포됐다.
- `origin/master`의 끝은 10-12의 문서 커밋이다. develop이 master로 머지된 적이 없다.
- 그래서 **CI로 운영에 마지막으로 나간 것은 11-11 09:54의 develop(`b28f0d4`)이다.** 그 뒤에 develop에 들어간 것은 개발 환경에만 나갔다. 서버에서 손으로 배포했는지는 저장소로 알 수 없다.
- 11-12 13:51에 운영 주소를 불러 보니 가입에 약관 동의가 필수가 아니었다(4.0의 6번). 278이 운영에 없다는 것은 서버에서도 확인됐다.
- 운영에 아직 없는 백엔드 변경(저장소 기준): 274 동시 처리 보강, 275 보안 보강(마이그레이션 0022), 287 허용 범위, 277 시연 자료와 보고서 문구, 278 `/metrics`·인쇄 토큰 범위·약관 동의 필수. 같은 기간의 웹·앱 변경도 운영에는 없다.
- master에 머지하면 분석 API(GPU 서버)도 같이 배포된다(`deploy_gpu`). CI 변수 `GPU_DEPLOY_FREEZE`가 1이면 건너뛴다. 환경이 나뉜 뒤로는 develop 머지로 분석 API가 나가지 않는다.
- 배포 순서(`infra/ci/deploy.sh`): 쉬는 색 빌드 → `alembic upgrade head` → 새 색 기동(health 통과까지 대기) → nginx 전환 → 서버 안 주소로 `/api/v1/health`와 `/` 확인(실패하면 이전 색으로 되돌림) → worker 재생성 → 이전 색 정지.

## 2. 사전 점검 (저장소 기준)

| 항목 | 결과 | 본 곳 |
| --- | --- | --- |
| 마이그레이션 head | 하나다(`0023`. develop은 `0022`이고 이 브랜치가 분석 줄의 `0023`을 더한다) | `alembic heads` |
| 0022가 옛 코드와 같이 돌아도 되는가 | 된다. `staff`에 칸 셋을 더하기만 하고, NOT NULL인 `login_fail_count`에는 서버 기본값 0이 있다. 배포는 마이그레이션을 먼저 돌리고 색을 바꾸므로 잠깐 옛 코드가 새 스키마를 쓴다 | `0022_staff_login_lock.py`, `deploy.sh` |
| 0023이 옛 코드와 같이 돌아도 되는가 | 된다. `measure_session`에 NULL을 허용하는 칸 하나(`queued_at`)와 인덱스를 더하기만 한다. 옛 워커는 이 칸을 모르고 그대로 돈다 | `0023_session_queued_at.py` |
| 이미지의 OS 패키지 | ffmpeg, Pango 둘, `fonts-nanum`이 있다(11-04에 넘긴 2번이 반영됨) | `backend/Dockerfile` |
| 시간대 | `tzdata`가 고정돼 있고 `APP_TIMEZONE` 기본값이 `Asia/Seoul`이다 | `requirements.txt`, `app/core/config.py` |
| worker | 한 대다. api와 같은 이미지·`.env`·업로드 볼륨을 쓴다. 배포 때 api 전환 뒤에 다시 만들고, 기동 직후 죽어 있으면 배포 실패로 본다(11-04에 넘긴 1번이 반영됨) | `compose.yaml`, `deploy.sh` |
| 업로드 볼륨 | api 두 색과 worker가 `api-data:/data/files`를 같이 본다. `STORAGE_ROOT` 기본값과 같다 | `compose.yaml`, `config.py` |
| 업로드 한도 | `UPLOAD_MAX_MB` 기본 100과 컨테이너 nginx의 `client_max_body_size 100m`이 같다. 호스트 nginx와 GPU 서버의 값은 저장소에 없다 | `infra/docker/nginx.conf`, `config.py` |
| 밖에서 열리는 경로 | `/api/`만 백엔드로 간다. `/metrics`·`/docs`·`/openapi.json`은 루트라서 화면 컨테이너로 가고 밖에서 보이지 않는다 | `nginx.conf`, `app/main.py` |
| 기동을 막는 설정 | `DATABASE_URL`, `JWT_SECRET`, `FILE_URL_SECRET`(32자 이상, 서로 다른 값)이 없거나 틀리면 뜨지 않는다. `ANALYSIS_API_MODE=http`인데 주소가 없어도 뜨지 않는다 | `config.py` |
| 보고서 PDF | compose에 렌더러 `gotenberg`(headless Chromium, 밖으로 여는 포트 없음)가 있고, worker에만 `REPORT_RENDERER_URL=http://gotenberg:3000`과 `REPORT_PRINT_URL=http://nginx/web`이 들어간다(11-13, 티켓 310). 보고서 PDF는 웹의 인쇄 화면을 찍어 만들고, 렌더러가 답하지 않거나 `REPORT_RENDER_TIMEOUT_SEC`(기본 60초)을 넘기면 기본 템플릿(WeasyPrint)으로 만든다. 배포 스크립트가 postgres·redis와 함께 gotenberg를 먼저 띄운다 | `compose.yaml`, `infra/ci/deploy.sh`, `config.py`, `app/worker/report.py` |
| `/metrics` | 기본이 꺼짐이다. Prometheus는 api 컨테이너 넷의 `/metrics`를 읽게 돼 있어, `METRICS_ENABLED=true`를 넣기 전에는 `ApiDown` 경보가 켜진 채다 | `config.py`, `infra/monitoring/prometheus/` |
| Redis | compose에는 있지만 백엔드는 쓰지 않는다(설정에 `REDIS_URL`이 없다). 작업 큐는 DB다 | `compose.yaml`, `config.py` |
| CI | check → build → smoke(배포 스크립트를 두 번 돌려 첫 배포와 색 전환을 본다) → deploy | `.gitlab-ci.yml` |
| 첫 관리자와 시연 자료 | 배포 스크립트에 seed 단계가 없다. 운영과 개발의 DB가 따로라 각각 넣어야 한다 | `deploy.sh`, `backend/README.md` |

보고서 PDF의 화면 인쇄는 11-13에 로컬에서 미리 돌려 봤다. develop 코드의 API와 웹, compose와 같은 이미지(`gotenberg/gotenberg:8`), 시연 자료로 워커와 같은 함수(인쇄 토큰 → 인쇄 화면 주소 → 렌더러)를 불렀다. 수의사용은 4쪽에 약 4초, 보호자용은 3쪽에 약 2초였다. 수의사용에는 '무릎을 가장 굽힌 순간·가장 편 순간' 칸(결과 영상의 프레임 넷)과 변화 프로필의 추이선이 나왔고, 세 번 찍어 세 번 모두 같았다. 로컬은 웹 개발 서버였으므로, 빌드된 웹과 nginx를 거치는 길은 서버에서 본다(4.2의 5번, 4.4의 4번).

## 3. 저장소로는 알 수 없는 것 (허정원에게 확인)

1. 운영 배포(develop → master 머지, `deploy_prod` 수동 실행)를 언제 누가 하는가.
2. 지금 운영(8080)에 올라가 있는 커밋이 무엇인가. 278 전의 코드라는 것까지만 확인했다(4.0).
3. 바깥 주소는 최신 develop이 아니었다(4.0). 운영(8080)을 보는 것이 맞는가. 개발 환경(8082)에도 바깥 주소가 있는가.
4. 호스트 nginx의 `client_max_body_size`가 100m 이상인가(기본값은 1m이다).
5. 운영 `.env`(`ENV_FILE`)의 아래 값. 기본값이 서버와 맞지 않는 것들이다.

   | 값 | 기본값 | 서버에서 필요한 것 |
   | --- | --- | --- |
   | `ANALYSIS_API_MODE` | `mock` | 운영은 `http`. `ANALYSIS_API_BASE_URL`과 `ANALYSIS_API_KEY`(GPU 서버와 같은 값)도 같이 |
   | `CORS_ORIGINS` | `http://localhost:5173` | 앱(Capacitor Android)의 `https://localhost`가 들어 있어야 한다(`frontend/capacitor.config.ts`의 주석). 없으면 앱에서 로그인부터 막힌다. 11-12에 운영 주소에서 허용되는 것을 확인했다(4.0의 5번) |
   | `FRONTEND_BASE_URL` | `http://localhost:5173` | 비밀번호 재설정 메일의 링크 앞부분이다. 웹이 `/web/` 아래에 있으므로 `https://<주소>/web` |
   | `SMTP_HOST` 등 | 비어 있음 | 비어 있으면 재설정 요청이 503 `MAIL_UNAVAILABLE`이다. 시연에서 재설정을 보일 때만 필요하다 |
   | `METRICS_ENABLED` | `false` | Prometheus가 읽게 하려면 `true` |
   | `REPORT_RENDERER_URL`, `REPORT_PRINT_URL` | 비어 있음 | `.env`에 넣지 않는다. compose가 worker에 직접 넣는다(`http://gotenberg:3000`, `http://nginx/web`). `.env`에 다른 값이 있어도 worker는 compose의 값을 쓴다 |
   | `API_DOCS_ENABLED` | `false` | 운영은 비워 두거나 `false` |
   | `JWT_SECRET`, `FILE_URL_SECRET` | 없음 | 운영과 개발이 서로 다른 값이어야 한다 |
   | `WORKER_QUEUE_PER_INSTITUTION`, `WORKER_HOURLY_PER_INSTITUTION` | `4`, `10` | 분석 줄의 새 설정이다(명세 12.4). 기본값을 쓰면 넣지 않아도 된다. 옛 이름 `WORKER_MAX_IN_FLIGHT_PER_INSTITUTION`은 남아 있어도 무시되고, 지워도 된다 |

6. 개발 환경의 DB(11-11에 새로 생김)에 관리자 계정과 시연 자료가 있는가.
7. 11-04에 넘긴 3번(과제 종료 때 돌릴 전체 파기 명령)이 정해졌는가.

## 4. 배포 뒤 점검 (운영 배포가 끝난 뒤에 채운다)

### 4.0 배포 전에 미리 돌린 결과 (2026-11-12 13:51, 운영 주소)

4.1의 여섯을 운영 배포 전에 한 번 돌렸다. 조영운의 허락을 받고 불렀다.

| 번호 | 결과 | 뜻 |
| --- | --- | --- |
| 1 | 200, `{"status":"ok","db":"ok","storage":"ok","version":"1.0.0"}` | 서버와 DB, 저장소가 정상이다. HTTPS로 붙는다(11-04에는 안 됐다) |
| 2 | `/` 200, `/web/` 200 | 화면이 뜬다 |
| 3 | 401 `AUTH_REQUIRED` | 토큰 없이는 막힌다 |
| 4 | `/metrics`·`/docs`·`/openapi.json` 모두 화면의 HTML | 운영용 경로가 밖에 열려 있지 않다 |
| 5 | 200, `access-control-allow-origin: https://localhost` | 운영 `.env`의 `CORS_ORIGINS`에 앱의 주소가 들어 있다 |
| 6 | 422 `VALIDATION_ERROR`, `detail.fields`는 `code`·`login_id`·`password`·`name`·`email`. **`terms`가 없다** | 운영의 백엔드는 약관 동의 필수(278, 명세 v1.58) 전의 코드다 |

1\~5는 기대와 같다. 6은 1절에서 저장소로 본 것(운영에 278이 없다)과 맞는다. 운영 배포 뒤에 4.1을 다시 돌리면 6번에 `terms`가 나와야 한다.

### 4.1 밖에서 부르는 점검 (로그인 없음, 아무것도 만들지 않는다)

Git Bash 기준이다. 주소는 앱의 App Links 호스트(`frontend/android/app/src/main/AndroidManifest.xml`)다.

```bash
BASE=https://k15a404.p.ssafy.io
```

| 번호 | 무엇을 | 명령 | 기대하는 결과 | 결과 |
| --- | --- | --- | --- | --- |
| 1 | 서버 상태 | `curl -sS -w '\n%{http_code}\n' $BASE/api/v1/health` | 200, `status`·`db`·`storage`가 모두 `ok` | |
| 2 | 화면 | `curl -sS -o /dev/null -w '%{http_code}\n' $BASE/` 와 `$BASE/web/` | 둘 다 200 | |
| 3 | 토큰 없이 API | `curl -sS -w '\n%{http_code}\n' $BASE/api/v1/dogs` | 401, `error.code`가 `AUTH_REQUIRED` | |
| 4 | 운영용 경로 | `curl -sS $BASE/metrics \| head -c 200` (`/docs`, `/openapi.json`도) | 화면의 HTML이 온다. `# HELP`나 `"openapi"`가 보이면 안 된다 | |
| 5 | 앱의 CORS | `curl -sS -i -X OPTIONS $BASE/api/v1/auth/login -H 'Origin: https://localhost' -H 'Access-Control-Request-Method: POST' \| grep -i '^access-control-allow-origin'` | `access-control-allow-origin: https://localhost`. 허용 목록에 없으면 400 `Disallowed CORS origin`이고 이 헤더가 없다 | |
| 6 | 올라간 코드가 최신인가 | `curl -sS -X POST $BASE/api/v1/auth/signup -H 'Content-Type: application/json' -d '{}'` | 422 `VALIDATION_ERROR`이고 `detail.fields`에 `terms`가 있다(명세 v1.58). 없으면 278 전의 코드다 | |

6번은 POST지만 입력 검사에서 끝나므로 계정이 만들어지지 않는다. 기대하는 결과는 11-12에 시험 클라이언트로 같은 요청을 보내 확인했다.

여섯을 한 번에 돌리는 묶음이다.

```bash
BASE=https://k15a404.p.ssafy.io
echo "1 서버 상태";   curl -sS -w '\n%{http_code}\n' $BASE/api/v1/health
echo "2 화면";        curl -sS -o /dev/null -w 'app %{http_code}\n' $BASE/; curl -sS -o /dev/null -w 'web %{http_code}\n' $BASE/web/
echo "3 토큰 없이";   curl -sS -w '\n%{http_code}\n' $BASE/api/v1/dogs
echo "4 운영용 경로"; for p in metrics docs openapi.json; do printf '/%s: ' $p; curl -sS $BASE/$p | head -c 60 | tr '\n' ' '; echo; done
echo "5 앱의 CORS";   curl -sS -i -X OPTIONS $BASE/api/v1/auth/login -H 'Origin: https://localhost' -H 'Access-Control-Request-Method: POST' | grep -i '^access-control-allow-origin' || echo "(헤더 없음)"
echo "6 약관 필수";   curl -sS -w '\n%{http_code}\n' -X POST $BASE/api/v1/auth/signup -H 'Content-Type: application/json' -d '{}'
```

### 4.2 로그인해서 눈으로 보는 점검 (조영운이 직접 로그인한다)

| 번호 | 무엇을 | 기대하는 결과 | 결과 |
| --- | --- | --- | --- |
| 1 | 웹(`/web/`) 로그인, 반려견 목록 | 목록이 보인다 | |
| 2 | 회차 결과 화면 | 수치와 판정이 나온다 | |
| 3 | 결과 영상 | 재생된다. 사람 얼굴이 가려져 있다 | |
| 4 | 비교, 추이 | 그려진다 | |
| 5 | 서버가 만든 보고서 PDF 두 판본(보고서 화면의 미리보기·내려받기) | 열린다. 한글이 깨지지 않는다. 화면 인쇄로 만든 것이면 웹의 보고서 화면과 같은 모양이고, 결과 영상이 있는 회차의 수의사용에는 '무릎을 가장 굽힌 순간·가장 편 순간' 칸과 변화 프로필의 추이선이 있다 | |
| 6 | 관리자 계정으로 기관·기기 코드 목록 | 보인다 | |
| 7 | 앱(APK) 로그인, 목록, 결과 | 된다. 앱이 운영 주소를 보고 있다 | |

### 4.3 만드는 점검 (할지는 조영운이 정한다)

시험용 반려견 하나로 한 바퀴를 돈다. 업로드 한도, worker, 분석 API 연결, 결과 영상, 보고서를 한 번에 본다. 운영의 분석 API는 GPU 서버라서 이 점검은 운영에서만 뜻이 있다.

| 번호 | 무엇을 | 기대하는 결과 | 결과 |
| --- | --- | --- | --- |
| 1 | 회차 시작, 실제 크기의 영상 하나 올리기 | 201. 413이 나면 nginx 한도 문제다 | |
| 2 | 분석 | 끝난다(`DONE`). `ANALYSIS_SUBMIT_FAILED`면 분석 API 연결이나 한도 문제다 | |
| 3 | 측정 종료 | 결과와 결과 영상, 보고서 두 판본이 만들어진다 | |
| 4 | 뒷정리 | 그 반려견을 휴지통에 넣고 영구 삭제한다 | |

### 4.4 서버 안에서 보는 것 (허정원)

| 번호 | 무엇을 | 기대하는 결과 | 결과 |
| --- | --- | --- | --- |
| 1 | `docker compose -p creamoff ps` | nginx, api 한 색, web 한 색, worker 하나, gotenberg, postgres, redis가 떠 있다. worker는 둘이면 안 된다 | |
| 2 | `docker compose -p creamoff run --rm --no-deps api-<색> alembic current` | `0023 (head)`(이 브랜치가 머지되기 전의 배포라면 `0022`) | |
| 3 | 3절 5번의 `.env` 값 | 표와 같다 | |
| 4 | worker 로그 | 기동 줄(`worker started`)에 `queue_per_institution=4 hourly_per_institution=10`이 찍힌다. 기동 뒤 오류가 없다. 보고서 완료 로그(`report ready`)에 `made_by=screen`이 찍힌다. `made_by=template`이면 화면 인쇄가 안 돼 기본 템플릿으로 만든 것이고, 그 앞에 `screen print failed` 경고가 있다 | |
| 5 | Prometheus의 `api` 대상 | `METRICS_ENABLED=true` 뒤에 up이고 `ApiDown`이 꺼진다 | |
| 6 | 운영 배포 전의 DB 백업 | 있다(배포 때 0022와 0023이 돈다) | |
| 7 | 시연 자료(`python -m scripts.seed_demo`) | 시연 날 운영 DB에 넣는다. `demo_seed` 폴더에 `face_masks.json`이 있어야 한다 | |
