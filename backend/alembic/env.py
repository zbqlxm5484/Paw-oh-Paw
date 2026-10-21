"""Alembic 실행 환경.

DB 주소는 .env의 DATABASE_URL을 쓴다. 다른 DB에 적용하려면 -x db_url=...을 붙인다.
    alembic -x db_url=postgresql+pg8000://.../creamoff_test upgrade head
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  모든 테이블을 Base.metadata에 올린다
from app.core.config import get_db_settings
from app.core.db import Base

config = context.config
if config.config_file_name is not None:
    # disable_existing_loggers=False: 테스트에서 불러도 다른 로거를 끄지 않게 한다.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _db_url() -> str:
    url = context.get_x_argument(as_dictionary=True).get("db_url")
    return url or get_db_settings().DATABASE_URL.get_secret_value()


def run_migrations_offline() -> None:
    """DB에 붙지 않고 SQL만 출력한다: alembic upgrade head --sql"""
    context.configure(
        url=_db_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_db_url(), poolclass=pool.NullPool, hide_parameters=True)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
