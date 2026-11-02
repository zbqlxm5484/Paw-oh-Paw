# 웹 시제품 → React 옮기기 규칙 (작업자 공통)

목표: `prototype/proto_app`(FastAPI + Jinja2) 웹을 `web/`(Vite + React 19 + TypeScript + react-router-dom 7)으로 **픽셀 단위로 똑같이** 옮긴다.
같은 시연 데이터(`web/src/mocks/fixture.json`, 시제품 seed 를 그대로 내보낸 것)로 두 화면을 스크린샷 비교한다.

## 레포·브랜치
- 레포 `C:\Users\SSAFY\Desktop\PJT\S15P31A404`, 브랜치 `S15P31A404-103-web-react`. **커밋·브랜치 변경 금지. `backend/`·`prototype/`·`frontend/` 수정 금지**(읽기만).
- 원본: `prototype/proto_app/` 의 `main.py`(주소·화면 준비·폼 처리), `views.py`·`real.py`·`analysis.py`·`seed.py`·`config.py`, `templates/*.html`, `static/*.js`, `static/app.css`.

## 이미 있는 것 (web/src)
- `config.ts`: config.py 그대로(같은 이름).
- `store/types.ts`: store.py dataclass 를 같은 필드 이름의 interface 로(Dog, Result, Note, Vital, History, Image, Job, Staff, DeviceCode, Account, RealSession).
- `store/db.ts`: `db`(= Store: accounts·staff·codes·sessions(= real.sessions())). 도우미 `dogOf(acct,id)`·`resultOf`·`jobOf`·`activeJobs(acct)`·`contractStatus(acct)`·`jobProgress(job)`·`getAccount(id)`·`byLogin`·`staffOf`·`codesOf`·`byCode`·`activeCount`·`effectiveRole(staff)`·`norm_code`·`show_code`·`new_id(prefix)`·`kdate(iso?)`·`isoToday()`·`changed()`(바꾼 뒤 부르면 화면 다시 그림)·`useDb()`·`freshAccount(id)`.
- `store/demo.ts`: `DEMO_ID`, `DEMO_STAFF`, `DEMO_CODE`, `FULL_CODE`, `EXPIRED_CODE`, `STAFF`, `resetDemo()`(seed.demo_account).
- `app/session.ts`: `currentStaff()`, `current()`(기관, 계약 만료면 `ContractExpired` 를 던짐), `setLogin(staffId|null)`(쿠키 pp_acct 대신), `setToast`·`takeToast`, `finished_notices(acct, skipJob)`, `redirect(to, toast)`·`need_login()` → `Go {to, toast}`, `hasActive(acct)`.
- `app/page.tsx`: `usePage({login?, jobId?})` → `{acct, me, toast, query, go}` (로그인 필요 화면은 `login: true`; 안 됐으면 알아서 /login 으로 보냄. 이때 화면은 acct 없이 한 번 그려질 수 있으니 `if (!acct) return null`). `PostForm`(= `<form method="post" action="...">`, 주소 그대로 store/actions 로 보냄), `GetForm`, `submitGet`, `staticUrl(path)`(= url_for('static', path=...) → `/static/...`), `useTitle`.
- `app/Base.tsx`: base.html. `<Base acct me nav q toast jobId topbar modals>{본문}</Base>`. `topbar={false}` = 상단 바 없음, `topbar={<AuthBar/>}` = 다른 상단 바. 모달은 `modals` 로. data-open/data-close/data-lightbox/data-toast/data-href 클릭, 화면 안 `<a href>` 클릭(새로 불러오지 않고 이동), `input.author-inp` 기본값 채우기, 분석 완료 알림은 Base 가 한다.
- `app/css.ts`: `css('display:flex;gap:8px')` → style 객체. **인라인 style 은 반드시 이걸로 문자열 그대로 옮긴다**(손으로 camelCase 바꾸지 말 것). Jinja 값이 들어가면 템플릿 문자열: ``css(`background:${x.bg};color:${x.c}`)``.
- `store/actions.ts`: `on('/dogs/:dog_id/notes', (p, fd) => Go)` 로 POST 주소 등록, `f(fd, 'name')` = Form(""). 등록은 `store/actions_impl.ts` 에서.
- `App.tsx`: 주소 → 화면 표(시제품과 같은 주소). 화면 파일은 `pages/<이름>.tsx` 의 default export.
- 정적 파일: `web/public/static/` = 시제품 `static/`(app.css·fonts·assets). 주소 `/static/...` 그대로.

## 이름 약속 (병렬 작업이라 꼭 지킨다)
- 파이썬 함수·dict 키 이름을 **그대로**(snake_case) TS 로 옮긴다. 예) `views.patient_row(acct, d, live)` → `patient_row(acct, d, live: Set<string>)` 같은 키의 객체. 다른 작업자는 이 이름을 믿고 부른다.
- `web/src/views/views.ts`(views.py), `views/real.ts`(real.py), `views/analysis.ts`(analysis.py: `start_job`, `finish_due_jobs`; seed 의 `J` 도 여기서 export), `views/pyfmt.ts`(파이썬 round·f-string 숫자 서식 흉내).
- 공통 조각: `pages/parts/Modals.tsx`(`_modals.html` 의 매크로 → `OpenModal`·`CloseModal`·`PetModal({next_url})`·`GuideModal`·`LogoutModal`·`DeleteModal`, pet.js 동작 포함), `pages/parts/DogPanel.tsx`(`_dogpanel.html` → `MemoCard`·`MemoForm`·`DogPanel`), `pages/parts/Vital.tsx`(`_vital.html` → `VV({value, f, size})`), `pages/parts/AuthBar.tsx`(`_authbar.html`).

## 템플릿 → JSX 규칙
1. 태그·속성·순서·글자를 그대로. `class` → `className`, `for` → `htmlFor`, SVG 속성은 camelCase(stroke-width → strokeWidth 등). 주석 `{# #}` 은 JSX 주석으로.
2. **공백**: 플렉스·그리드가 아닌 부모 안에서 인라인 요소 사이의 줄바꿈·공백은 화면에 공백 한 칸으로 보인다. JSX 는 줄바꿈 공백을 지우므로, 그런 자리에는 `{' '}` 를 넣는다. 같은 줄의 공백은 JSX 도 남긴다. 템플릿의 `{%- -%}` 등으로 공백이 지워지는 곳도 맞춘다.
3. 숫자·문자 서식은 파이썬과 같게(`{:.1f}`, round, `|tojson`, `|length` 등). 파이썬 round 는 반올림이 아니라 짝수 반올림이다(views/pyfmt.ts).
4. 폼: `method="post"` → `<PostForm action="같은 주소">`. 입력은 비제어(`defaultValue`·`defaultChecked`), hidden 은 `value`. `onchange="this.form.submit()"` → `onChange={e => e.currentTarget.form?.requestSubmit()}`. GET 폼 → `<GetForm action=...>`.
5. 페이지 JS(static/*.js, `<script>`)는 useEffect·상태로 옮기되 같은 결과가 보이게.
6. 각 화면은 main.py 의 해당 `@app.get` 함수의 준비 로직(리다이렉트 포함)을 그대로 옮긴다. 리다이렉트는 `go(redirect(...))` 를 useEffect 에서, 또는 `<Navigate>`.
7. 제목 `{% block title %}` → `useTitle(...)`.

## 끝나면
- `cd web && npx tsc -p tsconfig.app.json --noEmit` 로 자기 파일 오류가 없게(다른 작업자 파일이 아직 없어 생기는 import 오류는 괜찮다).
- 무엇을 만들었는지, 옮기면서 시제품과 다르게 할 수밖에 없었던 곳을 짧게 보고.
