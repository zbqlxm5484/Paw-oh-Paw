# Paw oh Paw 웹 프로토타입

디자인 시안 `PawOhPaw_web.html`의 화면 18개를 FastAPI + Jinja2로 옮긴 사이트다. 색·글꼴(Pretendard)·간격·문구는 시안 그대로이고, 시안에서 화면 상태로만 있던 것을 실제 주소와 폼으로 바꿨다.

- 데이터는 메모리에 있다. 서버를 다시 켜면 예시 데이터(한빛동물병원, 반려견 4마리, 회차 8개)로 돌아간다.
- 분석은 시뮬레이션이다. 올린 영상은 `uploads/`에 저장되지만 실제로 분석하지 않고, 약 7초 뒤 직전 회차를 바탕으로 결과를 만든다 (시안의 동작과 같다).
- `backend/`·`frontend/`와 연결되지 않는다. 시연과 화면 흐름 확인용이다.

## 실행

`prototype` 폴더에서 실행한다. backend(8000)와 겹치지 않게 8001 포트를 쓴다.

```bash
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS·Linux
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn proto_app.main:app --reload --port 8001
```

브라우저에서 http://localhost:8001 을 연다.

- 로그인: 아이디 2자 이상, 비밀번호 4자 이상이면 데모 기관(한빛동물병원)으로 들어간다. 회원가입한 계정은 그 아이디·비밀번호로 들어간다.
- 왼쪽 아래 "화면 바로가기"로 시안의 화면 18개를 바로 열 수 있다 (시안에 있던 검토용 메뉴).

## 화면

| 시안 화면 | 주소 |
| --- | --- |
| 랜딩 | `/` |
| 서비스 소개 (스크롤 애니메이션) | `/about` |
| 로그인 · 기관 회원가입 | `/login`, `/signup` |
| 홈 · 반려견 · 측정 이력 | `/home?dog={id}` |
| 반려견 등록 · 수정 (모달) | 홈·업로드·마이페이지의 "등록", "정보 수정" |
| 영상 업로드 | `/upload?dog={id}` |
| 분석 중 | `/analyzing/{작업 id}` |
| 분석 결과 목록 | `/results?dog={id}` |
| 회차 결과 (유효 · 일부 유효 · 실패) | `/results/{회차 id}?gait=walk|trot` |
| 보고서 (보호자용 · 수의사용) | `/results/{회차 id}/report?type=g|v` |
| 경과 비교 | `/compare/{반려견 id}?cmp=base|prev&tk=rom|stride|stance|sym` |
| 마이페이지 · 기본 정보 | `/my`, `/account` |

"PDF 내려받기"는 브라우저 인쇄 창을 연다. 대상에서 "PDF로 저장"을 고르면 보고서 종이 부분만 저장된다.

## 파일

| 파일 | 하는 일 |
| --- | --- |
| `proto_app/main.py` | 주소(라우트), 로그인 쿠키, 폼 처리, 알림 메시지 |
| `proto_app/views.py` | 화면 값 계산: 좌우 차이 순위, 대칭 지수 변화, 경과 비교, 추이 그래프 좌표 (시안의 계산을 그대로 옮김) |
| `proto_app/analysis.py` | 분석 작업 흉내: 진행률, 끝나면 회차 결과 만들기 |
| `proto_app/store.py` | 메모리 저장소 (기관 · 반려견 · 회차 결과 · 분석 작업) |
| `proto_app/seed.py` | 데모 기관 예시 데이터 |
| `proto_app/config.py` | 상태 색, 견종 목록, 체급 자동 분류, 분석 시간 |
| `proto_app/templates/` | 화면 HTML. 시안의 마크업과 인라인 스타일을 그대로 옮겼다 |
| `proto_app/static/app.css` | 글꼴, hover · focus, 인쇄 |
| `proto_app/static/*.js` | 공통(알림 · 모달), 서비스 소개 스크롤, 업로드, 반려견 모달 |
| `proto_app/static/assets/` | 시안의 이미지 · 영상 · 로고 (용량을 줄여 다시 저장) |
| `proto_app/static/fonts/` | Pretendard Variable (SIL OFL) |

저장소 루트 `.gitignore`가 `*.png`·`*.jpg`·`*.mp4`를 막아서, `prototype/.gitignore`에서 `static/assets/`만 다시 허용했다.

## 테스트

```bash
pip install -r requirements-dev.txt
pytest
```
