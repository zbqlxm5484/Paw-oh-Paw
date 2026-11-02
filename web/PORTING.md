# React 웹(web/)

`prototype/proto_app`(FastAPI + Jinja2) 웹을 Vite + React 19 + TypeScript + react-router-dom 7 로 옮긴 것이다.
화면·문구·동작은 시제품과 같게 유지하고, 같은 시연 데이터로 두 화면을 스크린샷 비교해 확인한다.

## 실행

```bash
cd web
npm install
npm run dev -- --mode mock   # 시연 데이터(src/mocks/fixture.json)만으로. 백엔드 없이 모든 화면
npm run dev                  # 백엔드 API 사용(vite.config.ts 가 /api 를 localhost:8000 으로 넘긴다)
npm run build                # tsc -b + vite build
npm test                     # vitest
```

## 구조

| 위치 | 내용 |
|---|---|
| `src/App.tsx` | 주소 → 화면(시제품과 같은 주소) |
| `src/pages/*.tsx` | 화면. 시제품 `templates/*.html` 과 1:1. 공통 조각은 `pages/parts/` |
| `src/views/` | 화면 값 계산. `views.py`·`real.py`·`analysis.py` 를 같은 함수 이름(snake_case)으로 옮김. `pyfmt.ts` 는 파이썬 round·숫자 서식 |
| `src/store/` | `db.ts`(브라우저 저장소, 시연 데이터 불러오기), `actions.ts`(폼 POST 주소 → 처리 함수), `actions_impl.ts`(시제품 `main.py` 의 POST 처리), `actions_backend.ts`·`backend.ts`·`sessions_backend.ts`(백엔드 API) |
| `src/api/client.ts` | 백엔드 API 호출·토큰 |
| `src/app/` | `Base.tsx`(base.html), `page.tsx`(`usePage`·`PostForm`·`GetForm`), `session.ts`(로그인·토스트), `css.ts` |
| `public/static/` | 시제품 `static/`(app.css·글꼴·그림) |

## 백엔드 모드와 시연 모드

- 폼은 `<PostForm action="/주소">` 로 보내고 `store/actions.ts` 의 `dispatch` 가 처리 함수를 고른다.
- 백엔드에 있는 기능(로그인·가입·비밀번호, 반려견 등록·수정, 측정·업로드, 내 정보, 관리)은 `actions_backend.ts` 가 `BACKEND` 우선순위로 등록한다.
  - **import 순서와 무관하게 언제나 먼저** 불린다.
  - 처리 함수가 `{ to: '__local__' }` 를 돌려주면(시연 기관) 다음 처리 함수(`actions_impl.ts`)로 넘어간다.
- 백엔드에 없는 기능(메모·바이탈·진단 이력·기준 회차 등)은 `actions_impl.ts` 만 받아 브라우저 저장소에 둔다.
- 측정 결과는 `/sessions/{id}/result` 를 `sessions_backend.ts` 가 화면 결과로 바꾼다.
  - 반려견별 회차 목록 API 가 없어 이 브라우저에서 연 회차와 측정 중 회차만 따라간다.

## 시제품과 맞추기

- 시연 데이터: `python prototype/tools/export_web_fixture.py` → `src/mocks/fixture.json`. 크림오프 제공 데이터는 넣지 않는다.
- 화면 비교: `python web/scripts/proto_for_compare.py`(시제품을 8002 로, 회사 데이터 없이) + `npm run dev -- --mode mock` 뒤 `python web/scripts/pixel_compare.py`. Git Bash 에서는 `MSYS_NO_PATHCONV=1` 을 붙인다.
- 값 비교: `python web/scripts/dump_views.py` → `src/views/__parity__/expected.json`(git 밖, 약 15MB) 뒤 `npm test`.
  - 파일이 없으면 그 비교는 건너뛴다.
  - 시험은 기대값을 뜬 날로 시계를 고정한다.

## 옮길 때 규칙

1. 태그·속성·순서·글자를 그대로. 인라인 style 은 `css('...')` 로 문자열 그대로 옮긴다.
2. 플렉스·그리드가 아닌 부모 안의 인라인 요소 사이 줄바꿈은 화면에 공백 한 칸이다. JSX 는 지우므로 `{' '}` 를 넣는다.
3. 숫자 서식은 파이썬과 같게(`views/pyfmt.ts`). 파이썬 round 는 짝수 반올림이다.
4. 입력은 비제어(`defaultValue`·`defaultChecked`). `onchange="this.form.submit()"` → `onChange={(e) => e.currentTarget.form?.requestSubmit()}`.
5. 시제품 화면을 고치면 같은 변경을 이쪽에도 넣고 화면 비교를 다시 돌린다.
