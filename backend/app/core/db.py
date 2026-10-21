"""엔진, 세션, Base (명세 11.2, 11.7).

- 엔진은 처음 쓸 때 만든다(get_engine). 모델 파일을 import하는 것만으로는 DB에 붙지 않는다.
- 세션은 SessionLocal()로 연다. 처음 열 때 엔진에 연결된다.
- PostgreSQL 오류 종류는 예외 클래스가 아니라 SQLSTATE로 가린다(11.7 오류 종류).
"""

from functools import lru_cache

from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_db_settings

# 기본 키 이름을 PostgreSQL 기본값(<테이블>_pkey)과 맞춘다.
# 나머지 제약·인덱스 이름(uq_·ck_·fk_·ix_)은 각 모델에 12.2 DDL과 같은 이름으로 직접 적는다.
NAMING_CONVENTION = {"pk": "%(table_name)s_pkey"}

# SQLSTATE 코드 (11.7 오류 종류)
UNIQUE_VIOLATION = "23505"
FOREIGN_KEY_VIOLATION = "23503"
CHECK_VIOLATION = "23514"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


@lru_cache
def get_engine() -> Engine:
    url = get_db_settings().DATABASE_URL.get_secret_value()
    # hide_parameters: 오류 메시지에 값(반려견 이름 등)이 찍히지 않게 한다(11.8).
    return create_engine(url, hide_parameters=True, pool_pre_ping=True)


class _LazySessionmaker:
    """sessionmaker에 엔진을 처음 쓸 때 붙인다. 사용법은 sessionmaker와 같다: SessionLocal()"""

    def __init__(self) -> None:
        self._factory = sessionmaker(expire_on_commit=False)
        self._bound = False

    def configure(self, engine: Engine) -> None:
        """테스트처럼 다른 엔진을 쓸 때 부른다."""
        self._factory.configure(bind=engine)
        self._bound = True

    def __call__(self) -> Session:
        if not self._bound:
            self.configure(get_engine())
        return self._factory()


SessionLocal = _LazySessionmaker()


def db_error_code(error: BaseException) -> str | None:
    """DB 오류의 SQLSTATE를 돌려준다. 예: 중복 23505, 외래키 23503, CHECK 23514.

    pg8000은 중복만 IntegrityError로 내고 외래키·CHECK 위반은 ProgrammingError로 낸다.
    그래서 종류를 가릴 때는 예외 클래스가 아니라 이 함수의 값으로 판단한다.
    """
    if not isinstance(error, DBAPIError) or error.orig is None:
        return None
    args = getattr(error.orig, "args", ())
    if args and isinstance(args[0], dict):
        code = args[0].get("C")
        return str(code) if code is not None else None
    return None
