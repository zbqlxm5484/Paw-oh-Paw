"""엔진, 세션, Base (명세 11.2, 11.7).

- 엔진은 처음 쓸 때 만든다(get_engine). 모델 파일을 import하는 것만으로는 DB에 붙지 않는다.
- 세션은 SessionLocal()로 연다. 처음 열 때 엔진에 연결된다.
- PostgreSQL 오류 종류는 예외 클래스가 아니라 SQLSTATE로 가린다(11.7 오류 종류).
- DB 오류의 글에서 행 값을 뺀다(scrub_db_error, 11.8). 로그와 str(error) 어디에도 값이 남지 않는다.
"""

from functools import lru_cache

from sqlalchemy import Engine, MetaData, create_engine, event
from sqlalchemy.engine import ExceptionContext
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


# PostgreSQL이 오류에 붙여 보내는 칸 중 남기는 것: 심각도(S·V), SQLSTATE(C), 스키마·테이블·칸·자료형·제약 이름
# (s·t·c·d·n), 서버 소스 위치(F·L·R). 값이 실리는 칸은 뺀다: 자세한 내용(D, 'Failing row contains (…)'·'Key (…)=(…)'),
# 힌트(H), 문맥(W), 쿼리와 위치(q·p·P). 메시지(M)는 아래 종류에서만 남긴다
_SAFE_PG_FIELDS = ("S", "V", "C", "s", "t", "c", "d", "n", "F", "L", "R")
# 메시지에 값이 들어가지 않는 SQLSTATE 종류(앞 두 글자): 연결 08, 제약 23, 교착·직렬화 40, 문법·이름 42, 자원 53·55·57.
# 22(자료 오류)는 'invalid input syntax for type uuid: "…"'처럼 받은 값을 그대로 싣는다
_MESSAGE_SAFE_CLASSES = frozenset({"08", "23", "40", "42", "53", "55", "57"})


@event.listens_for(Engine, "handle_error")
def scrub_db_error(context: ExceptionContext) -> None:
    """DB 오류의 글에서 행 값을 뺀다(11.8). 모든 엔진에 걸린다(API, 워커, 스크립트, 시험).

    hide_parameters는 SQLAlchemy가 붙이는 바인드 값만 가린다. PostgreSQL이 보내는 글에는 제약을 어긴 행 전체나
    겹친 키의 값이 들어 있고, 그것이 예외의 글이 되어 logger.exception으로 로그에 간다(메모 본문, 연락처 등).
    드라이버 예외(pg8000, args[0]이 칸 dict)와 그것을 감싼 SQLAlchemy 예외의 글을 함께 바꾼다. pg8000은 오류를
    받아 다시 던지기도 해서, 드라이버 예외에 이어진 예외(__cause__·__context__)도 모두 바꾼다(traceback에 함께
    찍힌다). 예외의 종류와 SQLSTATE는 그대로라 db_error_code와 except IntegrityError는 전과 같이 동작한다.
    """
    original = context.original_exception
    seen: set[int] = set()
    pending: list[BaseException | None] = [original]
    while pending:
        error = pending.pop()
        if error is None or id(error) in seen:
            continue
        seen.add(id(error))
        _scrub_pg_fields(error)
        pending += [error.__cause__, error.__context__]
    wrapped = context.sqlalchemy_exception
    if wrapped is not None and wrapped.args:
        kind = type(original)
        wrapped.args = (f"({kind.__module__}.{kind.__name__}) {original}", *wrapped.args[1:])


def _scrub_pg_fields(error: BaseException) -> None:
    """PostgreSQL이 보낸 오류(args[0]이 칸 dict)면 남길 칸만 남긴다. 아니면(연결 실패 등) 그대로 둔다."""
    args = error.args
    if not args or not isinstance(args[0], dict):
        return
    fields = args[0]
    safe = {name: fields[name] for name in _SAFE_PG_FIELDS if name in fields}
    if str(fields.get("C", ""))[:2] in _MESSAGE_SAFE_CLASSES and "M" in fields:
        safe["M"] = fields["M"]
    error.args = (safe, *args[1:])


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


@lru_cache
def get_engine() -> Engine:
    url = get_db_settings().DATABASE_URL.get_secret_value()
    # hide_parameters: 오류 메시지에 바인드 값(반려견 이름 등)이 찍히지 않게 한다(11.8). PostgreSQL이 보내는 글의
    # 값은 scrub_db_error가 뺀다.
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
