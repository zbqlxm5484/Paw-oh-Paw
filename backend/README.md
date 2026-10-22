# 크림오프 팀 서비스 백엔드

명세: `크림오프_팀서비스_백엔드_기능명세` v1.3. 지금 들어 있는 것은 작업 단위 1(서버 뼈대), 2(DB 모델·마이그레이션·seed), 3(로그인·기관 분리)이다.

| 들어 있는 것 | 위치 |
| --- | --- |
| 환경 변수 읽기 (16절) | `app/core/config.py` |
| DB 엔진·세션·오류 코드 (11.7) | `app/core/db.py` |
| 비밀번호 해시·JWT·서명 URL (11.6, 13.4) | `app/core/security.py` |
| 요청 DB 세션, 로그인 담당자·관리자 확인 (11.6, 11.7) | `app/api/deps.py` |
| `POST /api/v1/auth/login`, `GET /api/v1/auth/me` (15.4) | `app/api/routes/auth.py`, `app/services/auth.py` |
| 오류 형식·오류 코드·422 변환 (11.5, 14절) | `app/core/errors.py` |
| 화면 문구 (14.5) | `messages/ko.yaml` |
| 앱 생성, CORS, 요청 ID·요청 로그 (11.8, 16절) | `app/main.py` |
| `GET /api/v1/health` (15.9) | `app/api/routes/health.py` |
| 테이블 9개 모델 (12.2) | `app/models/` |
| 첫 마이그레이션 | `alembic/versions/0001_initial_tables.py` |
| 기관·계정 만들기 | `scripts/seed.py` |
| 테스트 | `tests/` |

반려견·회차 API, 업로드, 워커, 보고서 등은 다음 작업 단위에서 더한다. 토큰이 필요한 API는 `Authorization: Bearer <access_token>` 헤더를 붙인다(로그인 응답의 `access_token`).

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
같은 기관에 계정을 더할 때는 `--institution-name`을 빼도 된다.

## 서버 띄우기

```bash
uvicorn app.main:app --no-access-log
```

- `.env`의 `JWT_SECRET`·`FILE_URL_SECRET`(32자 이상, 서로 다른 값)이 비어 있으면 켜지지 않고 어느 값이 문제인지 출력한다(16절). 값 만들기: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- 접근 로그는 끈다(11.8). 대신 요청 로그 미들웨어가 메서드, 쿼리를 뺀 경로, 상태 코드, 처리 시간, 요청 ID를 한 줄로 남기고, 응답 헤더 `X-Request-ID`로도 돌려준다.
- `http://localhost:8000/api/v1/health`가 `{"status": "ok", "db": "ok", "version": "1.0.0"}`이면 정상이다. DB에 못 붙으면 503이고 `status`·`db`가 `"error"`다. 저장소 검사(`storage`)는 작업 단위 5에서 더한다.
- 모든 오류 응답은 `{"error": {"code", "message", "detail"}}` 한 모양이다(11.5). `message`는 `messages/ko.yaml`에서 `code`로 찾는다.
- `/docs`(Swagger)·`/redoc`·`/openapi.json`은 `.env`의 `API_DOCS_ENABLED=true`일 때만 열린다(`.env.example`은 true). 배포에서는 끄고, 화면·기업과 맞춘 공식 명세는 `docs/openapi.yaml`이다.

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
