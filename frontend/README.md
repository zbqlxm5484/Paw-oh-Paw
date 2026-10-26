# 크림오프 팀 서비스 앱 (frontend)

Paw oh Paw **앱 v5** 디자인을 그대로 쓰는 React 앱. 폰 브라우저·PWA·Capacitor 안드로이드로 같은 코드가 돈다. 웹(데스크톱) 화면은 팀원이 따로 만든다.
계획과 API 매핑은 `docs/frontend/screenPlan.md`.

| 항목 | 값 |
| --- | --- |
| 스택 | Vite 8 · React 19 · TypeScript · React Router 7 · TanStack Query 5 · MSW 2 · Capacitor 8 |
| 개발 서버 | `http://localhost:5173` (백엔드 `CORS_ORIGINS` 기본값) |
| API | `/api/v1`. 개발은 vite proxy, 배포는 nginx가 백엔드로 넘긴다 |
| 빌드 | `npm run build` → `dist/` → `frontend/Dockerfile` 이 nginx 로 서빙 |

## 처음 한 번

```bash
cd frontend
npm ci
cp .env.example .env.local
```

## 개발 서버

가짜 서버(MSW)로 띄우기. 백엔드 없이 화면을 볼 때 쓴다. `.env.local` 의 `VITE_MOCK=1`.

```bash
npm run dev
```

- 로그인: 기관 코드·아이디는 아무 값, 비밀번호는 `wrong`(로그인 실패)·`disabled`(중지 계정)만 빼고 아무 값.
- 데이터는 메모리에만 있어서 새로고침하면 초기값으로 돌아간다. 초기값은 `src/mocks/db.ts`.
- 데스크톱 브라우저에서는 디자인 기기 크기(412×915)로 가운데에 뜬다. 폰 폭에서는 꽉 찬다. 개발자 도구 기기 모드(Galaxy S24, 412px)로 보면 디자인과 같다.

백엔드에 붙이기: `.env.local` 에서 `VITE_MOCK=` 로 비우고 `VITE_DEV_PROXY_TARGET` 을 uvicorn 주소로 둔다. 로그인 계정은 `backend/scripts/seed.py` 로 만든다.

## 화면은 디자인 원본에서 생성한다

화면 마크업은 손으로 그리지 않는다. Claude Design 에서 내보낸 `PawOhPaw_app.html` 을 풀어서 템플릿을 JSX 로 1:1 변환한다. 그래서 간격·색·문구가 디자인과 같다.

```bash
# 1) 내보내기 HTML 에서 템플릿(template.html)·로직(source.jsx)·자산을 꺼낸다
python -I scripts/dc_extract.py ~/Downloads/PawOhPaw_app.html /tmp/dc/app
# 2) 템플릿 → src/design/app/AppView.tsx (+ app-view.css: hover/focus)
python -I scripts/dc2jsx.py /tmp/dc/app/template.html src/design/app/AppView.tsx AppView scripts/assets.app.json src/design/app/app-view.css --root-override --select=frame
```

- `src/design/app/AppView.tsx` 는 **생성 파일**이다. 고치지 않는다. 디자인이 바뀌면 다시 생성한다.
- `scripts/assets.app.json` 은 디자인 자산 id → `public/assets/d/` 파일 경로. 새 자산이 생기면 여기에 더한다(PNG 는 무손실 WebP 로 바꿔 넣었다).
- 변환 규칙: 인라인 `style` → style 객체, `sc-if` → 조건, `sc-for` → map, `{{ x }}` → `v.x`, `sc-camel-on-click` → onClick, `style-hover/focus` → `!important` 클래스. 로그인 화면에는 아이디 칸 앞에 같은 모양의 **기관 코드** 칸을 하나 더 넣는다(API 가 `institution_code` 를 요구).
- 로직은 `src/design/app/AppProto.tsx`. 원본 프로토타입의 `renderVals()` 값 이름을 그대로 두고, 목업 대신 API 데이터(`src/design/adapter.ts`·`useDesignData.ts`)를 넣는다. 화면 이동은 주소로 한다(`src/design/DesignRoot.tsx` 의 `parseRoute`).

## 폴더

```
src/
  api/        client.ts(요청·오류·토큰), types.ts(API 타입), labels.ts(값→문구), auth.ts, dogs.ts, sessions.ts, results.ts(쿼리 훅)
  app/        auth.tsx(로그인 상태), router.tsx
  design/     DesignRoot.tsx(주소→화면, 로그인 가드, 파일 입력), adapter.ts(API→디자인 값), shared.ts, useDesignData.ts, DCLogic.tsx
    app/      AppView.tsx(생성), app-view.css(생성), AppProto.tsx(로직)
  mocks/      MSW 핸들러와 메모리 DB
  styles/     global.css(글꼴·body), tokens.css
scripts/      dc_extract.py, dc2jsx.py, assets.app.json
public/assets/ d/(디자인 이미지 WebP), landing.mp4
```

## 주소와 화면

| 주소 | 화면 |
| --- | --- |
| `/welcome` | 스플래시 → 랜딩 |
| `/intro` | 서비스 소개 |
| `/login`, `/signup` | 로그인, 기관 회원가입(안내만) |
| `/` | 홈(반려견 목록·분석 중) |
| `/dogs/:id`, `/dogs/new`, `/dogs/:id/edit` | 반려견 상세·측정 이력, 등록, 수정 |
| `/notifications` | 알림(회차 상태로 만든다) |
| `/capture` | 촬영 · 반려견 선택 |
| `/sessions/:id` | 영상 첨부(16칸) |
| `/sessions/:id/record` | 촬영 화면(촬영 버튼 → 기기 카메라) |
| `/sessions/:id/analyzing` | 분석 중(회차가 끝나면 결과로) |
| `/results` | 분석 결과 목록 |
| `/sessions/:id/result`, `/sessions/:id/report` | 회차 결과, 보고서 |
| `/dogs/:id/compare` | 경과 비교 |
| `/my`, `/account` | 마이페이지, 기본 정보 |

API 가 없는 것(회원가입, 반려견 삭제, 계정 수정, 알림 설정, 새 모델 재분석)은 화면은 디자인대로 두고 누르면 안내 토스트를 띄운다.

## 안드로이드 앱 (Capacitor)

같은 React 빌드를 WebView 에 넣은 앱이다. 코틀린 코드는 Capacitor 가 만든 껍데기(`android/`)뿐이다.

```bash
cp .env.android.example .env.android   # VITE_API_BASE 에 서버 주소
npm run build:android                  # 서비스 워커 없이 빌드 → android/ 로 복사
npm run android:apk                    # android/gradlew assembleDebug → android/app/build/outputs/apk/debug/app-debug.apk
npm run android:open                   # Android Studio 로 열기
```

- APK 를 만들려면 **JDK 21**(Capacitor 8 요구)과 Android SDK(platform 36, build-tools 36)가 필요하다. 없으면 Android Studio 를 깔거나 command-line tools 로 `sdkmanager "platform-tools" "platforms;android-36" "build-tools;36.0.0"` 를 받는다. `JAVA_HOME` 이 JDK 17 이면 `compileDebugJavaWithJavac` 에서 실패한다.
- 이 PC(10-23)에서는 `C:/Users/SSAFY/AppData/Local/Android/Sdk` 에 command-line tools 로 설치했다. Gradle 에 알리는 `android/local.properties` 의 `sdk.dir` 은 **슬래시(/)** 로 적는다. 역슬래시는 속성 파일의 이스케이프라 경로가 깨져 `IOException: 파일 이름… 구문이 잘못되었습니다` 로 실패한다.
- 빌드 예(PowerShell): `$env:JAVA_HOME="C:/Program Files/Java/jdk-21.0.11"; $env:ANDROID_HOME="C:/Users/SSAFY/AppData/Local/Android/Sdk"; npm run android:apk`.
- 앱 안의 origin 은 `https://localhost` 라 백엔드 `CORS_ORIGINS` 에 `https://localhost` 를 더해야 한다. 에뮬레이터에서 호스트 PC 의 백엔드는 `http://10.0.2.2:8000`.
- 촬영하기는 촬영 화면의 촬영 버튼이 기기 카메라(파일 입력 `capture`)를 여는 방식이다(`CAMERA` 권한 포함). 갤러리는 `READ_MEDIA_VIDEO`.
- 세로 고정이고, 런처 아이콘·스플래시는 디자인 로고로 만들어 두었다(`android/app/src/main/res`).

## 확인

```bash
npm run build     # tsc + vite build
npm run lint
```

Docker 로 전체 스택 확인은 저장소 루트에서 `docker compose up --build` (nginx 80 → frontend·api).

## 백엔드와 맞춰 본 것 (10-23, 브랜치 S15P31A404-70)

로그인 · 반려견 등록 · 회차 시작 · 영상 업로드(201) · 세로 영상 거부(400) · 측정 취소(204) 통과. 측정 이력·측정 종료·촬영 삭제·결과·보고서·비교 API 는 아직 없어 화면이 서버 오류 문구를 그대로 보여 준다(가짜 서버에서는 전부 돈다). 실제 연결은 S15P31A404-103 에서 이어간다.
