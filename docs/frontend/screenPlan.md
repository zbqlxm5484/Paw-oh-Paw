# 화면 이식 순서와 API 매핑 계획

작성 박규원 · 10-22 · 초안

디자인 `Paw oh Paw 앱 v5.dc.html`(Claude Design, 412×915 폰 프로토타입, 화면 20개)을 `frontend/`의 React 화면으로 옮기는 순서와, 각 화면이 부를 API를 정리한다. API는 `docs/api-spec.md` v1.0(S15P31A404-64·66·67 브랜치, 10-20)을 기준으로 한다. 구현은 아직 하지 않았고, 이 문서는 순서와 매핑만 정한다.

---

## 1. 전제

| 항목 | 내용 | 근거 |
| --- | --- | --- |
| 스택 | Vite + React + TypeScript. 빌드 결과는 `dist/` | `frontend/Dockerfile`이 `npm run build` → `dist/`를 nginx로 서빙 |
| 라우팅 | React Router(SPA). 새로고침은 `index.html`로 떨어짐 | Dockerfile의 `try_files` |
| API 주소 | `/api/v1` 상대 주소. 개발은 `VITE_API_BASE=http://localhost:8000` | nginx가 `/api/`만 백엔드로, CORS 기본값 `http://localhost:5173` |
| 서버 상태 | 조회·폴링·캐시는 TanStack Query. 화면 상태(촬영 진행, 폼)는 컴포넌트 상태 | 측정 화면이 2~3초 폴링, 보고서 3초 폴링 |
| 스타일 | 디자인 인라인 스타일을 CSS 변수(토큰)로 뽑고 CSS Modules 또는 Tailwind 중 하나 | 디자인 토큰은 3절 |
| 가짜 서버 | `docs/openapi.yaml`로 mock 서버(Prism)를 띄워 백엔드 머지 전에 화면을 만든다 | api-spec 1.8 |
| 앱·웹 | 한 코드로 폰 폭(412)과 넓은 폭을 반응형 처리. PWA(`vite-plugin-pwa`)로 홈 화면 설치. 스토어 앱이 필요해지면 Capacitor | 납품물 D-06은 웹, 명세 4.3은 담당자가 앱으로 촬영 |

폴더 초안:

```
frontend/src/
  api/         클라이언트, 타입(openapi에서 생성), 쿼리 훅
  app/         라우터, 인증 가드, 레이아웃(탭바)
  features/    dogs · sessions · shots · reports · compare · auth
  components/  버튼, 칩, 카드, 시트, 토스트, 아이콘(디자인의 <defs> svg)
  styles/      tokens.css, 전역
```

---

## 2. 이식 순서

시연 최소 범위(백엔드 명세 "등록 → 업로드 → 판별 → 회차 결과 → 다리 비교·재활 비교")가 끝까지 도는 순서로 간다. API가 없는 화면은 뒤로 미룬다. 각 단계는 mock 서버로 먼저 만들고, 백엔드 브랜치가 머지되면 실제 서버에 붙인다.

| 단계 | 화면(디자인 이름) | 명세 화면 | API | 끝났다고 보는 기준 |
| --- | --- | --- | --- | --- |
| 0 | 프로젝트 뼈대, 토큰, 공용 컴포넌트, API 클라이언트, 오류 처리, 탭바 | — | `GET /health`, `GET /auth/me` | mock 서버에 health 호출이 되고 Docker 빌드가 통과 |
| 1 | 로그인(`login`) | 로그인 | `POST /auth/login`, `GET /auth/me` | 토큰 저장, 401·403이면 로그인으로, 새로고침 뒤 `me`로 복구 |
| 2 | 홈·반려견 목록(`home`), 반려견 등록·수정(`petNew`) | S1, S2 | `GET /dogs`, `POST /dogs`, `GET /dogs/{id}`, `PATCH /dogs/{id}` | 검색·등록·수정이 되고 422 필드 오류가 입력칸에 붙음 |
| 3 | 반려견 상세·측정 이력(`dog`) | S2, S7 | `GET /dogs/{id}`, `GET /dogs/{id}/sessions`, `PATCH /dogs/{id}`(기준 회차) | 이력 목록, 기준 회차 지정, 측정 시작 진입 |
| 4 | 반려견 선택·오늘 체중(`capSelect`), 영상 첨부(`capReview`), 분석 중(`analyzing`) | S3 | `POST /dogs/{id}/sessions`, `POST /sessions/{id}/shots`, `GET /sessions/{id}`(폴링), `POST /sessions/{id}/complete`, `DELETE /sessions/{id}`, `POST /shots/{id}/retry`, `DELETE /shots/{id}` | 업로드 → 상태 갱신 → 측정 종료 → DONE이면 회차 결과로 이동 |
| 5 | 촬영 화면(`capGuide`) | S3 | 4단계와 같음(`capture`로 찍은 파일을 같은 업로드 API로) | 폰에서 가로 안내, 촬영 또는 갤러리 선택 뒤 바로 업로드 |
| 6 | 촬영 상세(디자인에 없음, 새로 그림) | S4 | `GET /shots/{id}`, `GET /shots/{id}/angles` | 결과 영상 재생, 통과별 제외 사유, 유효 구간 표시 |
| 7 | 회차 결과(`detail`), 분석 결과 목록(`results`) | S5 | `GET /sessions/{id}/result`, `GET /sessions/{id}`, 목록은 `GET /dogs` + `GET /dogs/{id}/sessions` | 수치 표, 측정 불가 표시, 다리 비교 요약, 통과 집계, 실패 상태 |
| 8 | 보고서(`report`) | S6 | `GET /sessions/{id}/reports`(폴링), `POST /reports/{id}/regenerate`, `file_url`·`download_url` | 보호자용·수의사용 전환, PDF 미리보기와 내려받기, 만료 시 재조회 |
| 9 | 경과 비교(`compare`) | S8 | `GET /dogs/{id}/compare`, `GET /dogs/{id}/trends` | 기준·직전 회차 전환, 증가·감소 표시, 추이 차트 |
| 10 | 스플래시(`splash`), 랜딩(`landing`), 서비스 소개(`story`), 마이페이지(`my`), 기본 정보(`account`), 알림(`notif`), 기관 회원가입(`signupOrg`) | — | 없음(정적 또는 로컬 상태) | 시연 흐름에 필요한 것만. 6절 결정 뒤 범위 확정 |
| 11 | PWA, 넓은 화면 레이아웃(웹 v2 랜딩 참고), Docker·nginx 통합 확인 | — | — | 폰에서 홈 화면 설치, `compose up`으로 nginx 뒤에서 동작 |

- 2~3단계는 백엔드 작업 단위 3(로그인)까지만 있어도 mock으로 진행할 수 있다. 4단계부터는 백엔드 작업 단위 4(회차·업로드·워커)가 필요하므로 그 전까지는 mock에 의존한다.
- 7단계의 "분석 결과 목록"은 디자인에서는 전체 회차를 한 목록으로 보여 주지만 API에는 기관 전체 회차 목록이 없다. 반려견별 이력(`/dogs/{id}/sessions`)을 모으거나 백엔드에 목록 API를 요청한다(6절).

---

## 3. 디자인 토큰

디자인의 인라인 색을 CSS 변수로 둔다. 이름은 디자인 v3의 변수명을 따랐다.

| 변수 | 값 | 쓰임 |
| --- | --- | --- |
| `--bg` | `#FAF9F6` | 화면 배경 (캔버스 배경은 `#E9E6E1`) |
| `--card` / `--line` / `--line2` | `#FFFFFF` / `#ECE8E2` / `#F2EFEA` | 카드, 테두리, 구분선 |
| `--ink` / `--sub` / `--dim` | `#1B2433` / `#5B6472` / `#A0A7B2` | 글자 |
| `--pri` / `--pri-d` / `--pri-l` | `#D2601A` / `#B4501A` / `#FCEEE3` | 주황 포인트, 링크, 선택 상태 |
| `--ok` / `--ok-l` | `#2E8B57` / `#E8F3EC` | 유효(VALID) |
| `--warn` / `--warn-l` | `#9A6A12` / `#FAF1DF` | 일부 유효(PARTIAL) |
| `--bad` / `--bad-l` | `#C2412D` / `#F8E7E3` | 실패·무효(FAILED, INVALID) |
| `--L` / `--R` / `--C` | `#3B6FE0` / `#E5604D` / `#F2B705` | 왼다리, 오른다리, 관절점(그래프·골격) |

폰트 Pretendard Variable(jsdelivr), 글자 간격 `-0.2px`. 버튼 높이 52~56px, 모서리 12~16px, 폰 프레임 모서리 28px.

---

## 4. 화면별 API 매핑

디자인의 상태(`state`)와 `renderVals()` 값이 어느 API 필드에서 나오는지 적는다. "디자인" 열은 `app_v5.html`의 이름, "API" 열은 api-spec의 필드다.

### 4.1 로그인 (`login`)

| 디자인 | API | 비고 |
| --- | --- | --- |
| `li.id`, `li.pw` 두 칸 | `POST /auth/login` 요청 `institution_code`, `login_id`, `password` | **기관 코드 칸을 추가**해야 한다. 디자인은 아이디·비밀번호 두 칸 |
| `loggedIn`, `acct` | 응답 `access_token`, `expires_at`, `staff`(StaffOut) | 토큰과 `expires_at`을 저장. `staff.institution.name`이 홈 상단 기관명 |
| 오류 | 401 `LOGIN_FAILED` | 어느 칸이 틀렸는지 표시하지 않는다(명세) |
| "아이디·비밀번호 찾기", "회원가입" 링크 | 없음 | 6절 |

### 4.2 홈·반려견 목록 (`home`) — S1

| 디자인 | API | 비고 |
| --- | --- | --- |
| `acctKind`, `acctName` | `GET /auth/me` → `institution.name`, `name` | 디자인의 "기관/개인" 구분은 API에 없음. 기관명 + 담당자명으로 |
| `q`, `shown`(검색) | `GET /dogs?q=&page=&size=` | 서버 검색. 디자인은 클라이언트 필터 |
| `homeDogs[].name/desc` | DogOut `name`, `breed`, `birth_year`, `weight_kg` | `desc` = 견종 · N년생 · Nkg |
| `homeDogs[].meta` "마지막 측정 … · N회차" | `last_measured_on`, `session_count` | 없으면 "아직 측정 기록이 없어요" |
| `homeDogs[].live` "측정 중" 배지 | `open_session_id != null` | 누르면 그 회차(S3)로 이어서 측정 |
| `anaOn` 분석 중 배너(`anaName`, `anaStep`, `anaN/5`) | 측정 중 회차의 `GET /sessions/{id}` 촬영 상태 | 5단계 진행은 API에 없음(6절). 촬영별 `status`(UPLOADED·SUBMITTED·ANALYZING·DONE) 집계로 대체 |
| `dogCount` | `total` | |

### 4.3 반려견 등록·수정 (`petNew`) — S2

| 디자인 `pet` 필드 | API DogOut / 요청 | 값 변환 |
| --- | --- | --- |
| `name` | `name` | 그대로 |
| `breed`(자동완성 `BREEDS`) | `breed` | 목록에 없으면 입력한 이름 그대로. 견종표는 서버에도 있으므로 화면 목록은 입력 편의용 |
| `kg` | `weight_kg` | 문자열 → 숫자 |
| `birth` | `birth_year` | 연도 정수 |
| `sex` `m / f / mn / fs` | `sex` `MALE / FEMALE / MALE_NEUTERED / FEMALE_SPAYED` | |
| `size` `S / M / L` + `sizeManual`, `autoSize()` | `size_class` `SMALL / MEDIUM / LARGE`, `size_class_manual` | 등록 때 `size_class`를 빼면 서버가 정한다. 백엔드(develop, S15P31A404-68)는 **체중만으로** 나눈다(10kg 미만 소형 · 25kg 미만 중형). 디자인의 견종 기준 분류는 쓰지 않고, 화면 미리보기도 체중 규칙으로 맞춤. **서버 값이 정본** |
| `rehab` | `rehab_start_date` | `YYYY-MM-DD` |
| `focus` `LF / RF / LH / RH` | `focus_limb` | 같은 값 |
| `memo` | `memo` | |
| "사진 추가" | 없음 | 6절 |
| 삭제(마이페이지 시트 `del`) | 없음 | 반려견 삭제 API가 없다. `POST /admin/purge`는 관리자용(6절) |
| 422 | `detail.fields[].field/type` | 해당 입력칸 아래 문구 |

### 4.4 반려견 상세·측정 이력 (`dog`) — S2·S7

| 디자인 | API | 비고 |
| --- | --- | --- |
| `dd.name/desc/tags` | DogOut (`size_class` + `size_class_manual` → "소형 · 자동 분류/직접 지정", `sex`) | |
| `dd.rows` 재활 시작일·관심 다리·기준 회차·내부 메모 | `rehab_start_date`, `focus_limb`, `baseline_session_id`, `memo` | 기준 회차가 `null`이면 "가장 이른 회차로 자동 지정" |
| `dd.hist[]` "N회차 · 날짜", 체중, 유효 통과, 모델, 보고서 유무, 기준 표시 | `GET /dogs/{id}/sessions` → `measured_on`, `weight_kg`, `valid_passes.LEFT/RIGHT`, `model_version`, `reports.OWNER/VET`, `is_baseline`, `status` | 회차 번호는 서버에 없음. 목록 순서(오래된 것부터 1)로 화면이 매김 |
| `setBase` 기준 회차 지정 | `PATCH /dogs/{id}` `{baseline_session_id}` | DONE 회차만. 400 `BASELINE_INVALID` |
| 실패 회차 "쓸 수 있는 통과 없음" | `status == FAILED` | |
| "경과 비교" (유효 회차 2개 이상) | DONE 회차 2개 이상이면 활성 | |
| "측정 시작" | `open_session_id`가 있으면 그 회차로, 없으면 4.5로 | |

### 4.5 측정 (`capSelect` → `capGuide`/`capReview` → `analyzing`) — S3

디자인은 "4초씩 16개를 모아 분석 시작"이고 명세는 "영상 1건마다 업로드, 서버가 바로 분석"이다. 명세 흐름으로 맞추고 디자인의 화면 요소(진행 16칸, 체크리스트)는 재활용한다.

| 디자인 | API | 비고 |
| --- | --- | --- |
| `capSelect`: 반려견 선택, `sessW` 오늘 체중, "촬영하기/갤러리" | `POST /dogs/{id}/sessions` `{weight_kg}` → SessionOut | 409 `SESSION_ALREADY_OPEN`이면 `detail.session_id`로 이동 |
| `capGuide`: 가로 회전 안내, 녹화 | `<input type="file" accept="video/*" capture="environment">` → `POST /sessions/{id}/shots` (`file`) | 브라우저에서 4초 자동 녹화는 못 한다. 기기 카메라 앱으로 찍어 바로 업로드 |
| `capReview`: `shots/16` 진행, 체크리스트(가로·옆모습·4초) | `GET /sessions/{id}` 2~3초 폴링 → `progress.LEFT/RIGHT.valid_passes / recommended`, `shots[]` | **16칸 대신 방향별 진행 막대(권장 8)**. 체크리스트는 업로드 응답 `warnings`(BELOW_MIN_SPEC, ASPECT_NOT_16_9)와 400 오류(VIDEO_PORTRAIT 등)로 |
| 촬영 1건 상태 | ShotOut `status`, `validity`, `validity_reason.message`, `passes[].exclude_reason.message` | 무효·일부 유효면 사유 문장을 그대로 보여 주고 다시 찍기 안내 |
| `notices` | `RECOMMENDED_MET`("측정을 끝내도 된다"), `ONE_SIDE_ONLY` | 디자인의 `shotHint` 자리 |
| "분석 시작" 버튼 | `POST /sessions/{id}/complete` | 촬영 0건이면 비활성(409 `SESSION_EMPTY`) |
| `analyzing`: `STEPS` 5단계 진행, "홈에서 기다리기" | `GET /sessions/{id}` 폴링, `status` MEASURING → AGGREGATING → DONE/FAILED | 5단계는 API에 없다. AGGREGATING 동안 한 단계 진행 애니메이션으로 단순화하거나 백엔드에 단계 필드를 요청(6절). DONE이면 S5로, FAILED면 `fail_reason.message` |
| 다시 분석, 촬영 삭제, 측정 취소 | `POST /shots/{id}/retry`, `DELETE /shots/{id}`, `DELETE /sessions/{id}` | 버튼 활성 조건은 api-spec 10.2 |

### 4.6 촬영 상세 — S4 (디자인에 없음)

디자인에는 촬영 1건을 여는 화면이 없다. 회차 결과의 "통과 집계" 아래 또는 측정 화면의 촬영 목록에서 들어가는 화면을 새로 그린다.

| 요소 | API |
| --- | --- |
| 결과 영상 | `GET /shots/{id}` → `video_url`을 `<video src>`에. `video_status` PENDING이면 "만드는 중", `url_expires_at` 지나면 재조회 |
| 통과 목록, 유효 구간 | `passes[].pass_no/camera_side/gait_type/is_valid/exclude_reason/start_frame/end_frame`, 초 = 프레임 ÷ `fps` |
| 입력 사양 | `width/height/fps/duration_sec/codec`, `below_min_spec` |
| 각도 곡선(권장) | `GET /shots/{id}/angles` → `passes[].angles.{shoulder,elbow,carpus,hip,stifle,tarsus}`, `null`에서 선 끊기 |

### 4.7 회차 결과 (`detail`) — S5

| 디자인 | API `GET /sessions/{id}/result` | 비고 |
| --- | --- | --- |
| `rd.name/when` "날짜 · N회차 · 체중" | SessionOut `measured_on`, `weight_kg`, 회차 번호는 이력 순서 | |
| `rd.st` 유효·일부 유효·실패 배지 | 회차에는 `validity`가 없다. `status`(DONE/FAILED)와 `shot_counts.invalid`로 | 디자인 `ST` 3색은 촬영 `validity`에 쓰고, 회차는 DONE/FAILED + 무효 촬영 수로 |
| `rd.sym` **대칭 지수**(큰 숫자 1) | `gaits[].limb_compare[0].symmetry_index` | 디자인은 "92%"처럼 높을수록 좋은 값, API는 좌우 차이 비율(%)이라 **낮을수록 대칭**. 의미가 반대이므로 표시 방식을 정해야 한다(6절) |
| `rd.rom` 뒷무릎 가동 | `metrics` 중 `rom_stifle`(LH·RH) | 좌우 둘 다 보여 주거나 평균 |
| `rd.sL/sR` 걸음 길이 왼/오 | `stride_length`(LH·RH 또는 LF·RF), `unit` `pct_body` | 디자인 안내문 "거리 수치는 몸통 길이 대비 %"와 일치 |
| `rd.symD/romD` "직전 대비 +N" | `GET /dogs/{id}/compare?target=…&base=PREVIOUS` 의 `diff` | 회차 결과 API에는 직전 비교가 없다. 비교 API를 한 번 더 부르거나 생략 |
| `rd.topTitle` "뒷다리 무릎 가동 범위에서 좌우 차이가 가장 커요", `rd.rank` | `limb_compare`가 `symmetry_index` 내림차순으로 오므로 `[0]`이 맨 위, 나머지가 순위. `comparable == false`는 "비교 불가 + reason.message" | `pair` FORE/HIND → 앞다리/뒷다리 |
| `gait` 평보·속보 전환(`G`) | `gaits[].gait_type` WALK/TROT. 값이 있는 유형만 | 디자인은 속보값 × 0.86으로 평보를 흉내 냈다. API 값 그대로 |
| `rd.rows` 지표 표(지표 · 왼쪽 · 오른쪽 · 차이, 측정 불가) | `metrics[]`를 `metric_code`별로 묶어 `limb` L/R 짝 맞춤. `measurable == false`면 "측정 불가 · `unmeasurable_reason.message`" | 수치 이름 한글화는 10.4 표. 0으로 그리지 않는다 |
| `rd.pm/pu/px` 통과 집계 측정·사용·제외, `ex[]` 제외 사유 N회 | `pass_counts.measured/used/excluded`, `exclude_summary[].message/count` | |
| 뒷무릎 각도 · 보행 주기 그래프(`knee()`) | `GET /shots/{id}/angles`의 `stifle` 배열 | 회차 단위 그래프는 API에 없으니 대표 촬영 1건의 유효 통과로 그리거나 뒤로 미룸 |
| `rd.model` "분석 모델 v1" | `model_name`, `model_version` | |
| 실패 상태 `rd.fail` | `status == FAILED` → `fail_reason.message` | 디자인 문구 "쓸 수 있는 통과가 없었어요…"는 사유 문장으로 대체 |
| `partMsg`, `notices` | `notices` `ONE_SIDE_ONLY` | |
| 409 `SESSION_NOT_DONE` | 집계 중이면 분석 중 화면으로 | |

### 4.8 분석 결과 목록 (`results`)

| 디자인 | API | 비고 |
| --- | --- | --- |
| 전체 회차 목록 + 필터 `filt`(전체·유효·일부·실패) + `r.sym` | 기관 전체 회차 목록 API가 **없다** | 1안: 홈(S1)에 합치고 반려견 → 이력으로 들어가게. 2안: `GET /dogs` 뒤 반려견별 `GET /dogs/{id}/sessions`를 모아 클라이언트에서 정렬(반려견 수가 적은 시연에서는 가능). 3안: 백엔드에 `GET /sessions` 요청. 6절 |

### 4.9 보고서 (`report`) — S6

| 디자인 | API | 비고 |
| --- | --- | --- |
| `repType` g(보호자)/v(수의사) 전환 | `GET /sessions/{id}/reports` → `reports[]` `edition` OWNER/VET | 순서 OWNER, VET |
| `repStatus` | `status` PENDING/GENERATING/DONE/FAILED, `fail_reason.message` | 3초 폴링. `session_status` DONE이고 PENDING·GENERATING이 없으면 멈춤 |
| 보고서 본문(`rp.title/summary/items/rows`)을 HTML로 그림 | **PDF만 온다.** `file_url`을 `<iframe>` 또는 새 탭 | 디자인처럼 HTML 보고서를 직접 그리면 "화면 수치 = 보고서 수치"(PR-F09-05) 검증 부담이 생긴다. PDF 미리보기로 간다 |
| "PDF 내려받기" | `download_url` 링크 | 파일 이름은 서버가 정함 |
| "다시 만들기" | `POST /reports/{id}/regenerate` | GENERATING이면 비활성(409 `REPORT_IN_PROGRESS`) |
| 만료 | 403 `FILE_LINK_EXPIRED` → `reports` 재조회 | `url_expires_at` 지나기 전 미리 재조회해도 된다 |

### 4.10 경과 비교 (`compare`) — S8

| 디자인 | API | 비고 |
| --- | --- | --- |
| `cmp` base(기준 회차)/prev(직전) 전환, `cp.baseLabel/baseDate/tDate` | `GET /dogs/{id}/compare?base=BASELINE\|PREVIOUS&target=…` → `base.measured_on/kind`, `target.measured_on` | |
| `gait` 속보 고정 안내 "같은 보행 유형, 같은 다리끼리만" | `gait_type=TROT` 쿼리 | 평보 탭을 둘지는 데이터 보고 결정 |
| `cp.modelChanged`, "새 모델로 재분석" | `model_changed`, `note.code == MODEL_CHANGED` | 재분석 API는 없다. 버튼은 빼거나 안내만 |
| `m.n/limb/vals/j` 수치별 기준→최근 값과 증감 | `items[]` `metric_code`, `limb`, `base_value`, `target_value`, `diff`, `judgement` | `INCREASE/DECREASE/WITHIN_RANGE/UNKNOWN/NOT_COMPARABLE`. 지금은 전부 `UNKNOWN`+`RANGE_NOT_SET`으로 오므로 `diff`만 보여 주고 증감 화살표는 판정이 올 때만 |
| 안내문 "증가·감소는 오차 범위(±1)를 넘을 때만" | `note.message` | ±1은 디자인 가정. 서버 문구를 쓴다 |
| `cp.focusNote` 관심 다리 | `items`가 관심 다리 먼저 정렬돼 옴. DogOut `focus_limb` | |
| 회차별 추이 차트(`tk` rom/… 전환, 왼쪽·오른쪽) | `GET /dogs/{id}/trends?metric_code=&gait_type=TROT` → `series[].limb/points[]`, `lr_diff` | 측정 불가 점은 `value null`로 끊어 그림. `model_version`이 바뀌는 지점 표시 |
| 빈 상태 "유효한 회차가 2개 이상 필요" | 400 `COMPARE_INVALID` `detail.reason` NO_DONE_SESSION/SAME_SESSION/NO_PREVIOUS/NOT_DONE | 사유별 문구 |

### 4.11 API 없이 두는 화면 (`splash`, `landing`, `story`, `my`, `account`, `notif`, `signupOrg`)

| 화면 | 처리 |
| --- | --- |
| 스플래시, 랜딩(영상), 서비스 소개 | 정적. 로그인 전 진입 화면. 시연·발표용으로 그대로 옮긴다. `landing.mp4`는 용량 확인 뒤 `public/`에 |
| 마이페이지 | `GET /auth/me`로 기관·담당자 표시. "측정 기기", "분석 완료 알림" 토글, "고객센터"는 API 없음. 로그아웃은 토큰 삭제 |
| 기본 정보, 회원 탈퇴 | StaffOut 표시만. 수정·탈퇴 API 없음 |
| 알림 | API 없음. 측정 중 회차의 상태 변화를 클라이언트에서 토스트로 대신 |
| 기관 회원가입 | API 없음(계정은 관리자 seed). 시연에서 보여 줄지 6절 |

---

## 5. 공통 처리

| 항목 | 규칙 | 근거 |
| --- | --- | --- |
| 인증 | 모든 요청에 `Authorization: Bearer`. `expires_at` 지남 또는 401 `AUTH_REQUIRED/AUTH_EXPIRED`, 403 `ACCOUNT_DISABLED`면 토큰 지우고 로그인으로 | api-spec 1.2, 1.4 |
| 오류 모양 | 응답은 항상 `{error: {code, message, detail}}`. 화면은 `message`를 그대로 보여 주고 `code`로만 분기 | 1.3 |
| 서명 주소 | `video_url`, `file_url`, `download_url`은 토큰 없이 `src/href`에. `/api/v1`로 시작하면 서버 주소만 붙이고 `http`로 시작하면 그대로 | 1.6 |
| 폴링 | 회차 2~3초, 보고서 3초. 화면을 떠나면 멈춤. 홈 배너용 폴링은 측정 중 회차가 있을 때만 | 1.7 |
| 시각 | UTC `Z` → 한국 시간으로 화면이 변환. `measured_on`은 이미 한국 날짜 | 1.1 |
| 값 한글화 | `sex`, `size_class`, `limb`, `gait_type`, `validity`, 각종 `status`, `metric_code`(10.4 표) 사전을 `api/labels.ts` 한 곳에 | 10절 |
| 금지 표현 | "아프다", "좋아졌다", 진단성 단어를 화면 문구에 쓰지 않는다. 디자인의 "진단이 아닌 좌우 차이 비교예요", "보행 평가 보조 자료이며 진단을 대신하지 않습니다"는 유지 | 명세 PG-05, PR-F08-03 |
| 숫자 | 자릿수는 화면이 정한다. 각도 소수 1자리, 비율 정수, 대칭 지수 소수 1자리로 통일 | 1.1 |

---

## 6. 디자인과 명세가 다른 점 · 결정할 것

구현 전에 정하거나 백엔드에 물어볼 것이다. 담당은 추정이다.

| # | 내용 | 안 | 누구와 |
| --- | --- | --- | --- |
| 1 | 로그인에 기관 코드 칸이 없다 | 칸 추가(명세 따름) | 디자인만 바꾸면 됨 |
| 2 | 촬영 흐름: 디자인 "4초 × 16개 모아서 분석" vs 명세 "1건씩 업로드, 방향별 유효 통과 권장 8" | **적용함(10-23)**: 명세 흐름으로, 진행 UI는 방향별 막대 | 조영운(권장 수 설정값은 박규원 D-14) |
| 3 | "대칭 지수" 의미: 디자인은 높을수록 좋음(92%), API `symmetry_index`는 좌우 차이 비율(낮을수록 대칭) | **적용함(10-23)**: 화면은 "좌우 차이 지수 N% · 낮을수록 대칭"으로 표기. 뒤집지 않음 | 조유진·조영운에게 지수 정의 확인 |
| 4 | 분석 중 5단계(`STEPS`)가 API에 없다 | **적용함(10-23)**: 집계 중 화면은 "영상 N건 분석 중 / 회차 수치 계산 중" 두 상태만 | 조영운 |
| 5 | 기관 전체 "분석 결과" 목록 API가 없다 | **적용함(10-23)**: 2안. 반려견별 이력을 모아 클라이언트에서 정렬(`useAllSessions`). 반려견이 많아지면 `GET /sessions` 요청 | 조영운 |
| 6 | 회차 결과의 "직전 대비" 증감이 결과 API에 없다 | compare `base=PREVIOUS`를 추가 호출하거나 1차에서는 생략 | — |
| 7 | 보고서를 HTML로 그릴지 PDF만 보여 줄지 | **적용함(10-23)**: 서버 PDF 를 받아 iframe 미리보기 + 내려받기. 403 만료면 재조회 | 조영운·김지윤 |
| 8 | 반려견 삭제, 회원가입, 회원 탈퇴, 알림, 측정 기기, 아이디 찾기 API가 없다 | **적용함(10-23)**: 모두 뺐다. 랜딩에 회원가입 버튼 없음, 마이페이지는 계정 표시와 로그아웃만 | 팀 |
| 9 | 회차 단위 보행 주기 그래프(`knee()`)에 쓸 데이터가 없다 | **적용함(10-23)**: 촬영 상세(S4)에서 `GET /shots/{id}/angles` 로 관절별 곡선. 회차 결과에는 없음 | 조유진(angles 합의 중) |
| 10 | 회차 번호("N회차")를 서버가 주지 않는다 | 이력 순서로 화면이 매김. 삭제 회차가 생기면 번호가 밀리므로 날짜를 주 표시로 | — |
| 11 | 디자인 목업의 수치(무릎·고관절·팔꿈치, 걸음 길이, 입각기, 발 높이)와 10.4 수치 코드 매핑 | `rom_stifle`, `rom_hip`, `rom_elbow`, `stride_length`, `stance_ratio`, `paw_lift`. 나머지 코드(`rom_shoulder`, `rom_carpus`, `rom_tarsus`, `stifle_cv`, `paw_excursion`, `walk_speed`, `gait_cycles`)는 표에 더 넣을지 | 김지윤(보고서 문장과 맞춤) |
| 12 | 웹 v2 디자인(데스크톱)을 같이 구현할지 | **적용함(10-23)**: 같은 코드에서 1024px 이상이면 웹 v2(상단 내비, 넓은 표·2단 레이아웃), 아래면 앱 v5. 주소는 같고 `Responsive` 가 화면을 고른다. 폰 화면을 그대로 쓰는 곳(로그인·반려견 등록·보고서·촬영 상세)은 가운데 카드로 | 팀 |

---

## 7. 진행 기록

| 날짜 | 내용 |
| --- | --- |
| 10-22 | 0~3단계 구현(뼈대·토큰·로그인·반려견 화면), MSW 가짜 서버 |
| 10-23 | Capacitor 안드로이드 포장(`frontend/android/`, `capacitor.config.ts`, `npm run build:android`·`android:apk`). 서비스 워커는 빼고 `VITE_API_BASE` 로 서버 주소를 넣는다. 카메라·영상 권한, 세로 고정, 로고 아이콘·스플래시. 이 PC 에 Android SDK 가 없어 APK 빌드는 SDK 설치 뒤에 |
| 10-23 | 웹 v2 데스크톱 레이아웃(`src/features/web/`, `app/WebShell.tsx`, `app/useIsDesktop.ts`): 랜딩(영상 히어로·Main Service 세 블록·서비스 소개 스크롤 스테이지·푸터), 홈(반려견 띠·요약 카드·최근 회차 KPI·이력 표·최근 분석), 영상 올리기(드래그앤드롭), 분석 결과 표, 회차 결과, 경과 비교 2단, 마이페이지·기본 정보. 디자인 자산은 내보내기 HTML 묶음에서 풀어 넣고 사진은 WebP(17MB→5MB), 글꼴은 자체 호스팅. 폰 프레임은 412×915 |
| 10-23 | 6~11단계 구현: 촬영 상세(영상·유효 구간·각도 곡선), 회차 결과, 보고서(PDF 미리보기·재생성), 경과 비교·추이, 분석 결과 목록, 랜딩·스플래시·서비스 소개, PWA(manifest·서비스 워커, `/api` 는 캐시 안 함). 디자인 자산(logo·story PNG, landing.mp4)은 Claude Design 에서 256KB 넘는 파일을 못 받아 글자 로고·SVG 로 대신했다. PNG 를 넣을 때는 `frontend/public/` 에 두면 된다(.gitignore 예외 추가) |
| 10-23 | 4~5단계 구현(회차 시작·영상 업로드·측정 종료·집계 중). 백엔드 브랜치 S15P31A404-70(작업 단위 5)을 Docker로 띄워 실제 연결 확인: 로그인, 반려견 등록, 회차 시작, 영상 업로드(201), 세로 영상 거부(400 VIDEO_PORTRAIT) 통과. 그 브랜치에 아직 없는 API: `GET /dogs/{id}/sessions`(405), `POST /sessions/{id}/complete`(404), `DELETE /shots/{id}`(404), `POST /shots/{id}/retry`, 촬영 분석 워커(촬영이 UPLOADED 에 머묾). 화면은 서버 오류 문구를 그대로 보여 주고 다음 작업 단위에서 붙는다 |

## 8. 디자인 원본 참고

- Claude Design 프로젝트 `4f38ddd5-4eef-463a-852a-4db9339b5e6b`. 파일 `Paw oh Paw 앱 v5.dc.html`(구현 대상), `Paw oh Paw 웹 v2.dc.html`(데스크톱), `support.js`(디자인 런타임, 구현에는 쓰지 않음).
- 앱 v5가 쓰는 자산 7개: `logo-plain.png`, `logo-joint.png`, `paw-print.png`, `story-1~3.png`, `landing.mp4`. 레포에는 `.gitignore`가 `*.png`를 막고 있으므로 `frontend/public/` 예외를 추가해야 한다.
- 화면 로직은 `renderVals()` 한 함수(약 400줄)에 들어 있다. 옮길 때 화면별 훅으로 쪼개고, 목업 데이터(`DOGS`, `RES`)는 mock 서버 응답으로 바꾼다.
