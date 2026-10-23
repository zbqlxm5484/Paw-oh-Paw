# 크림오프 팀 서비스 화면 (frontend)

Paw oh Paw 앱 v5 디자인을 옮긴 React 화면. 계획과 API 매핑은 `docs/frontend/screenPlan.md`.

| 항목 | 값 |
| --- | --- |
| 스택 | Vite 8 · React 19 · TypeScript · React Router 7 · TanStack Query 5 · MSW 2 |
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

가짜 서버(MSW)로 띄우기. 백엔드 없이 화면을 만들 때 쓴다. `.env.local` 의 `VITE_MOCK=1`.

```bash
npm run dev
```

- 로그인: 기관 코드·아이디는 아무 값, 비밀번호는 `wrong`(로그인 실패)·`disabled`(중지 계정)만 빼고 아무 값.
- 데이터는 메모리에만 있어서 새로고침하면 초기값으로 돌아간다. 초기값은 `src/mocks/db.ts`.

백엔드에 붙이기: `.env.local` 에서 `VITE_MOCK=` 로 비우고 `VITE_DEV_PROXY_TARGET` 을 uvicorn 주소로 둔다. 로그인 계정은 `backend/scripts/seed.py` 로 만든다.

## 폴더

```
src/
  api/        client.ts(요청·오류·토큰), types.ts(API 타입), labels.ts(값→문구), auth.ts, dogs.ts, sessions.ts, results.ts(쿼리 훅)
  app/        auth.tsx(로그인 상태), router.tsx, Layout.tsx(틀·탭바), toast.tsx
  components/ Icon.tsx(디자인 아이콘 스프라이트), ui.tsx(버튼·입력·카드·시트)
  features/   intro/ · auth/ · dogs/ · sessions/(측정) · results/(결과·보고서·비교) · placeholders(마이페이지)
  mocks/      MSW 핸들러와 메모리 DB
  styles/     tokens.css(디자인 토큰), global.css
```

## 확인

```bash
npm run build     # tsc + vite build
npm run lint
```

Docker 로 전체 스택 확인은 저장소 루트에서 `docker compose up --build` (nginx 80 → frontend·api).

## 지금 들어 있는 것 (이식 0~11단계)

- 진입: 스플래시 · 랜딩 · 서비스 소개
- 로그인, 홈·반려견 목록·검색, 반려견 등록·수정, 반려견 상세·측정 이력·기준 회차 지정
- 측정: 회차 시작(반려견·오늘 체중) · 영상 업로드(갤러리·촬영) · 방향별 유효 통과 · 촬영 재분석·삭제 · 측정 종료·취소 · 집계 중
- 결과: 회차 결과(지표 표, 다리 비교 요약, 통과 집계) · 촬영별 결과 · 촬영 상세(결과 영상, 유효 구간, 관절 각도 곡선) · 보고서(보호자용·수의사용 PDF 미리보기·내려받기·다시 만들기) · 경과 비교·추이 · 분석 결과 목록
- 마이페이지(계정 표시·로그아웃), PWA 설치(manifest, 서비스 워커. `/api` 는 캐시하지 않는다)

없는 것: 회원가입·반려견 삭제·알림·계정 수정(API 없음). 디자인의 로고 PNG·배경 영상은 아직 없어 글자 로고와 SVG 로 대신한다. 넣을 때는 `public/` 에 두면 된다.

## 백엔드와 맞춰 본 것 (10-23, 브랜치 S15P31A404-70)

로그인 · 반려견 등록 · 회차 시작 · 영상 업로드(201) · 세로 영상 거부(400) · 측정 취소(204) 통과. 측정 이력·측정 종료·촬영 삭제·결과·보고서·비교 API 는 그 브랜치에 아직 없어 화면이 서버 오류 문구를 그대로 보여 준다.
