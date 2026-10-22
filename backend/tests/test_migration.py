"""마이그레이션이 명세 12.2와 같은 테이블을 만드는지, 모델과 어긋나지 않는지 확인한다."""

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, Engine, text

from app.core.db import Base
from tests.conftest import TABLES, alembic_config

# 명세 12.2 DDL의 제약 이름. 오류 처리에서 이 이름으로 어느 규칙을 어겼는지 가린다.
EXPECTED_CONSTRAINTS = {
    "institution": {"institution_pkey", "uq_institution_code"},
    "staff": {"staff_pkey", "uq_staff_login", "ck_staff_role", "fk_staff_institution"},
    "dog": {
        "dog_pkey",
        "ck_dog_size_class",
        "ck_dog_sex",
        "ck_dog_focus_limb",
        "fk_dog_institution",
        "fk_dog_baseline",
    },
    "measure_session": {"measure_session_pkey", "ck_session_status", "fk_session_dog", "fk_session_staff"},
    "shot": {
        "shot_pkey",
        "uq_shot_seq",
        "ck_shot_status",
        "ck_shot_validity",
        "ck_shot_video_status",
        "fk_shot_session",
    },
    "walk_pass": {"walk_pass_pkey", "uq_pass_no", "ck_pass_camera_side", "ck_pass_gait_type", "fk_pass_shot"},
    "session_metric": {
        "session_metric_pkey",
        "uq_metric",
        "ck_metric_gait_type",
        "ck_metric_limb",
        "fk_metric_session",
    },
    "report": {"report_pkey", "uq_report_edition", "ck_report_edition", "ck_report_status", "fk_report_session"},
    "purge_log": {"purge_log_pkey", "ck_purge_scope"},
}
EXPECTED_INDEXES = {"ix_dog_institution_name", "ix_session_dog_date", "ix_shot_status", "ix_shot_video"}


def _tables(conn: Connection) -> set[str]:
    rows = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
    return {row[0] for row in rows}


def _catalog(conn: Connection, schema: str) -> dict[str, set[tuple]]:
    """한 스키마의 컬럼·제약·인덱스 정의를 비교하기 쉬운 모양으로 뽑는다."""
    conn.execute(text(f"SET LOCAL search_path TO {schema}"))
    columns = conn.execute(
        text(
            """
            SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull,
                   coalesce(pg_get_expr(d.adbin, d.adrelid), '')
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
            WHERE n.nspname = :schema AND c.relkind = 'r' AND a.attnum > 0 AND NOT a.attisdropped
              AND c.relname <> 'alembic_version'
            """
        ),
        {"schema": schema},
    )
    constraints = conn.execute(
        text(
            """
            SELECT c.relname, k.conname, pg_get_constraintdef(k.oid)
            FROM pg_constraint k
            JOIN pg_class c ON c.oid = k.conrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = :schema AND k.contype <> 'n' AND c.relname <> 'alembic_version'
            """
        ),
        {"schema": schema},
    )
    indexes = conn.execute(
        text(
            "SELECT tablename, indexname, replace(indexdef, :prefix, '') FROM pg_indexes "
            "WHERE schemaname = :schema AND tablename <> 'alembic_version'"
        ),
        {"schema": schema, "prefix": f"{schema}."},
    )
    return {
        "columns": {tuple(row) for row in columns},
        "constraints": {tuple(row) for row in constraints},
        "indexes": {tuple(row) for row in indexes},
    }


def test_all_tables_exist(engine: Engine) -> None:
    with engine.connect() as conn:
        assert _tables(conn) == set(TABLES) | {"alembic_version"}


def test_constraint_and_index_names_match_spec(engine: Engine) -> None:
    with engine.connect() as conn:
        found = _catalog(conn, "public")
    constraints: dict[str, set[str]] = {}
    for table, name, _definition in found["constraints"]:
        constraints.setdefault(table, set()).add(name)
    assert constraints == EXPECTED_CONSTRAINTS
    index_names = {name for _table, name, _definition in found["indexes"]}
    assert EXPECTED_INDEXES <= index_names


def test_models_match_migration(engine: Engine) -> None:
    """모델(app/models)로 만든 테이블과 마이그레이션으로 만든 테이블이 컬럼·제약·인덱스까지 같다."""
    with engine.connect() as conn, conn.begin() as trans:
        conn.execute(text("CREATE SCHEMA model_check"))
        conn.execute(text("SET LOCAL search_path TO model_check"))
        Base.metadata.create_all(conn)
        from_models = _catalog(conn, "model_check")
        from_migration = _catalog(conn, "public")
        trans.rollback()
    for key in ("columns", "constraints", "indexes"):
        assert from_models[key] == from_migration[key], key


def test_alembic_check_finds_nothing(engine: Engine) -> None:
    """alembic check와 같다: 모델을 바꾸고 마이그레이션을 안 만들었으면 실패한다."""
    with engine.connect() as conn:
        context = MigrationContext.configure(conn, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []


def test_downgrade_then_upgrade(engine: Engine) -> None:
    config = alembic_config()
    command.downgrade(config, "base")
    with engine.connect() as conn:
        assert _tables(conn) == {"alembic_version"}
    command.upgrade(config, "head")
    with engine.connect() as conn:
        assert _tables(conn) == set(TABLES) | {"alembic_version"}
