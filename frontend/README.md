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
  api/        client.ts(요청·오류·토큰), types.ts(API 타입), labels.ts(값→문구), auth.ts, dogs.ts(쿼리 훅)
  app/        auth.tsx(로그인 상태), router.tsx, Layout.tsx(틀·탭바), toast.tsx
  components/ Icon.tsx(디자인 아이콘 스프라이트), ui.tsx(버튼·입력·카드·시트)
  features/   auth/LoginPage · dogs/HomePage · dogs/PetFormPage · dogs/DogDetailPage · placeholders
  mocks/      MSW 핸들러와 메모리 DB
  styles/     tokens.css(디자인 토큰), global.css
```

## 확인

```bash
npm run build     # tsc + vite build
npm run lint
```

Docker 로 전체 스택 확인은 저장소 루트에서 `docker compose up --build` (nginx 80 → frontend·api).

## 지금 들어 있는 것 (이식 0~3단계)

로그인, 홈·반려견 목록·검색, 반려견 등록·수정, 반려견 상세·측정 이력·기준 회차 지정, 마이페이지(로그아웃). 측정·결과·보고서·비교 화면은 자리만 있다.
