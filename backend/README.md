# 크림오프 팀 서비스 백엔드

명세: `크림오프_팀서비스_백엔드_기능명세` v1.3. 지금 들어 있는 것은 작업 단위 2(S15P31A404-66)까지다.

| 들어 있는 것 | 위치 |
| --- | --- |
| 환경 변수 읽기 (16절) | `app/core/config.py` |
| DB 엔진·세션·오류 코드 (11.7) | `app/core/db.py` |
| 비밀번호 해시 (13.4) | `app/core/security.py` |
| 테이블 9개 모델 (12.2) | `app/models/` |
| 첫 마이그레이션 | `alembic/versions/0001_initial_tables.py` |
| 기관·계정 만들기 | `scripts/seed.py` |
| 테스트 | `tests/` |

FastAPI 서버, 워커, 보고서 등은 다음 작업 단위에서 더한다.

## 준비 (처음 한 번)

필요한 것: Python 3.11, PostgreSQL 18. 모든 명령은 `backend` 폴더에서 실행한다.

```bash
python -m venv .venv
# macOS·Linux
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

`.env.example`을 `.env`로 복사하고 `DATABASE_URL`, `TEST_DATABASE_URL`을 내 PostgreSQL에 맞게 고친다.
DB는 두 개 만든다: 개발용(`creamoff`)과 테스트용(`creamoff_test`). 테스트용 DB 이름은 반드시 `_test`로 끝나야 한다.

## 테이블 만들기

```bash
alembic upgrade head
```

## 계정 만들기

```bash
python -m scripts.seed --institution-code DEMO --institution-name "데모 병원" --login-id admin --name 관리자 --role ADMIN
```

비밀번호는 화면에서 두 번 묻는다. 8자 이상, UTF-8로 72바이트 이하(한글은 24자까지).
같은 기관에 계정을 더할 때는 `--institution-name`을 빼도 된다.

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
