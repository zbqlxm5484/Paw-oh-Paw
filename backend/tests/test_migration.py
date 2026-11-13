"""마이그레이션이 명세 12.2와 같은 테이블을 만드는지, 모델과 어긋나지 않는지 확인한다."""

import uuid

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, Engine, text

from app.core.dates import today_local
from app.core.db import Base
from tests.conftest import ROOT, TABLES, alembic_config

# 명세 12.2 DDL의 제약 이름. 오류 처리에서 이 이름으로 어느 규칙을 어겼는지 가린다.
EXPECTED_CONSTRAINTS = {
    "institution": {"institution_pkey", "uq_institution_code"},
    "device_code": {"device_code_pkey", "uq_device_code", "fk_device_code_institution"},
    "staff": {"staff_pkey", "uq_staff_login", "ck_staff_role", "fk_staff_institution", "fk_staff_device_code"},
    "dog": {
        "dog_pkey",
        "ck_dog_size_class",
        "ck_dog_sex",
        "ck_dog_focus_limb",
        "ck_dog_stage",
        "fk_dog_institution",
        "fk_dog_baseline",
    },
    "dog_vital": {
        "dog_vital_pkey",
        "uq_dog_vital_day",
        "ck_dog_vital_any_value",
        "ck_dog_vital_bp_pair",
        "fk_dog_vital_dog",
        "fk_dog_vital_staff",
        "fk_dog_vital_session",
    },
    "dog_history": {
        "dog_history_pkey",
        "ck_dog_history_kind",
        "ck_dog_history_site",
        "fk_dog_history_dog",
        "fk_dog_history_staff",
    },
    "dog_note": {
        "dog_note_pkey",
        "ck_dog_note_category",
        "fk_dog_note_dog",
        "fk_dog_note_session",
        "fk_dog_note_staff",
    },
    "dog_image": {
        "dog_image_pkey",
        "ck_dog_image_kind",
        "fk_dog_image_dog",
        "fk_dog_image_staff",
    },
    "dog_note_revision": {
        "dog_note_revision_pkey",
        "ck_dog_note_revision_category",
        "fk_dog_note_revision_note",
        "fk_dog_note_revision_staff",
    },
    "measure_session": {
        "measure_session_pkey",
        "ck_session_status",
        "ck_session_size_class",
        "fk_session_dog",
        "fk_session_staff",
    },
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
EXPECTED_INDEXES = {
    "ix_dog_institution_name",
    "ix_dog_history_dog_date",
    "ix_dog_image_dog_taken",
    "ix_dog_note_dog_created",
    "ix_dog_note_dog_visited",
    "ix_dog_note_revision_note",
    "ix_session_dog_date",
    "ix_session_queued_at",
    "ix_shot_status",
    "ix_shot_video",
    "uq_device_code_active",
}


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


def _has_column(conn: Connection, table: str, column: str) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM information_schema.columns WHERE table_name = :t AND column_name = :c"),
        {"t": table, "c": column},
    ).first()
    return row is not None


def test_0003_turns_old_staff_into_client_and_rejects_duplicate_login_ids(engine: Engine, clean_tables: None) -> None:
    """0003(v1.12): STAFF였던 기관 담당자는 CLIENT가 되고, 기관이 달라도 같은 아이디가 있으면 올라가지 않는다."""
    config = alembic_config()
    inst_a, inst_b = uuid.uuid4(), uuid.uuid4()
    command.downgrade(config, "0002")
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO institution (id, code, name) VALUES (:a, 'A', '병원 A'), (:b, 'B', '병원 B')"),
                {"a": inst_a, "b": inst_b},
            )
            conn.execute(
                text(
                    "INSERT INTO staff (id, institution_id, login_id, password_hash, name, role) VALUES "
                    "(:s1, :a, 'dup', 'x', '갑', 'STAFF'), (:s2, :b, 'dup', 'x', '을', 'STAFF'), "
                    "(:s3, :a, 'boss', 'x', '병', 'ADMIN')"
                ),
                {"s1": uuid.uuid4(), "s2": uuid.uuid4(), "s3": uuid.uuid4(), "a": inst_a, "b": inst_b},
            )
        with pytest.raises(RuntimeError, match="같은 아이디가 1개"):
            command.upgrade(config, "head")
        with engine.begin() as conn:  # 실패한 올리기는 아무것도 바꾸지 않았다. 중복을 치우면 올라간다
            assert not _has_column(conn, "institution", "contract_ends_at")
            conn.execute(text("DELETE FROM staff WHERE institution_id = :b"), {"b": inst_b})
        command.upgrade(config, "head")
        with engine.connect() as conn:
            roles = dict(conn.execute(text("SELECT login_id, role FROM staff")).all())
            assert roles == {"dup": "CLIENT", "boss": "ADMIN"}
            ends_at = conn.execute(text("SELECT contract_ends_at FROM institution WHERE id = :a"), {"a": inst_a})
            assert ends_at.scalar_one() is None
    finally:
        command.upgrade(config, "head")


def test_0012_keeps_one_usable_code_per_institution(engine: Engine, clean_tables: None) -> None:
    """0012(v1.32): 기관마다 가입에 쓰인 코드를 먼저, 없으면 가장 최근 코드를 하나 남기고 나머지를 회수한다."""
    config = alembic_config()
    inst_a, inst_b = uuid.uuid4(), uuid.uuid4()
    ids = {name: uuid.uuid4() for name in ("used", "old", "new", "gone", "b_old", "b_new", "account")}
    command.downgrade(config, "0010")
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO institution (id, code, name) VALUES (:a, 'A', '병원 A'), (:b, 'B', '병원 B')"),
                {"a": inst_a, "b": inst_b},
            )
            conn.execute(
                text(
                    "INSERT INTO device_code (id, institution_id, code, max_accounts, revoked_at, created_at) VALUES "
                    "(:used, :a, 'USED', 3, NULL, '2026-10-01'), (:old, :a, 'OLD', 3, NULL, '2026-09-01'), "
                    "(:new, :a, 'NEW', 3, NULL, '2026-11-01'), (:gone, :a, 'GONE', 3, '2026-10-02', '2026-08-01'), "
                    "(:b_old, :b, 'B1', 3, NULL, '2026-09-01'), (:b_new, :b, 'B2', 3, NULL, '2026-10-01')"
                ),
                {**ids, "a": inst_a, "b": inst_b},
            )
            # 중지한 계정이어도 그 코드는 가입에 쓰인 코드다
            conn.execute(
                text(
                    "INSERT INTO staff (id, institution_id, login_id, password_hash, name, role, device_code_id, "
                    "is_active) VALUES (:account, :a, 'kim01', 'x', '갑', 'CLIENT', :used, FALSE)"
                ),
                {"account": ids["account"], "a": inst_a, "used": ids["used"]},
            )
        command.upgrade(config, "head")
        with engine.connect() as conn:
            usable = {str(row[0]) for row in conn.execute(text("SELECT id FROM device_code WHERE revoked_at IS NULL"))}
            assert usable == {str(ids["used"]), str(ids["b_new"])}
            assert not _has_column(conn, "device_code", "max_accounts")
            # 원래 회수돼 있던 코드의 회수 시각은 건드리지 않는다
            gone = conn.execute(text("SELECT revoked_at FROM device_code WHERE id = :id"), {"id": ids["gone"]})
            assert gone.scalar_one().date().isoformat() == "2026-10-02"
            # 회수한 코드와 관계없이 계정은 그대로다
            account = conn.execute(
                text("SELECT device_code_id, is_active FROM staff WHERE id = :id"), {"id": ids["account"]}
            ).one()
            assert (str(account[0]), account[1]) == (str(ids["used"]), False)
            total = conn.execute(text("SELECT count(*) FROM device_code")).scalar_one()
            assert total == 6
    finally:
        command.upgrade(config, "head")


def test_0022_adds_login_lock_columns_and_leaves_accounts_as_they_were(engine: Engine, clean_tables: None) -> None:
    """0022(v1.48): 있던 계정은 틀린 수 0이고 잠금 시각·비밀번호를 바꾼 시각은 NULL이다. 내리면 세 칸만 없어진다.

    이 칸을 모르는 앞 판 앱의 INSERT(배포 중에 잠깐 같은 DB에 가입 계정을 넣는다)도 들어간다.
    """
    config = alembic_config()
    columns = ("login_fail_count", "login_locked_until", "password_changed_at")
    ids = {name: uuid.uuid4() for name in ("inst", "old", "late")}
    insert_staff = (
        "INSERT INTO staff (id, institution_id, login_id, password_hash, name, role) "
        "VALUES (:id, :inst, :login_id, 'x', '갑', 'CLIENT')"
    )
    command.downgrade(config, "0021")
    try:
        with engine.begin() as conn:
            assert not any(_has_column(conn, "staff", column) for column in columns)
            conn.execute(text("INSERT INTO institution (id, code, name) VALUES (:inst, 'A', '병원 A')"), ids)
            conn.execute(text(insert_staff), {"id": ids["old"], "inst": ids["inst"], "login_id": "kim01"})
        command.upgrade(config, "head")
        with engine.begin() as conn:
            conn.execute(text(insert_staff), {"id": ids["late"], "inst": ids["inst"], "login_id": "kim02"})
            rows = conn.execute(
                text(
                    "SELECT login_id, login_fail_count, login_locked_until, password_changed_at "
                    "FROM staff ORDER BY login_id"
                )
            ).all()
            assert [tuple(row) for row in rows] == [("kim01", 0, None, None), ("kim02", 0, None, None)]
        command.downgrade(config, "0021")
        with engine.connect() as conn:
            assert not any(_has_column(conn, "staff", column) for column in columns)
            assert conn.execute(text("SELECT count(*) FROM staff")).scalar_one() == 2
    finally:
        command.upgrade(config, "head")


def test_0023_adds_the_queue_time_and_leaves_sessions_as_they_were(engine: Engine, clean_tables: None) -> None:
    """0023(v1.59): 있던 회차의 queued_at은 NULL이다(새 워커가 다음 바퀴에 줄에 세운다). 내리면 그 칸만 없어진다."""
    config = alembic_config()
    ids = {name: uuid.uuid4() for name in ("inst", "staff", "dog", "session")}
    command.downgrade(config, "0022")
    try:
        with engine.begin() as conn:
            assert not _has_column(conn, "measure_session", "queued_at")
            conn.execute(text("INSERT INTO institution (id, code, name) VALUES (:inst, 'A', '병원 A')"), ids)
            conn.execute(
                text(
                    "INSERT INTO staff (id, institution_id, login_id, password_hash, name, role) "
                    "VALUES (:staff, :inst, 'kim01', 'x', '갑', 'CLIENT')"
                ),
                ids,
            )
            conn.execute(
                text(
                    "INSERT INTO dog (id, institution_id, name, breed, weight_kg, size_class) "
                    "VALUES (:dog, :inst, '보리', '믹스', 10, 'MEDIUM')"
                ),
                ids,
            )
            conn.execute(
                text(
                    "INSERT INTO measure_session (id, dog_id, staff_id, measured_on, size_class) "
                    "VALUES (:session, :dog, :staff, '2026-11-12', 'MEDIUM')"
                ),
                ids,
            )
        command.upgrade(config, "head")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT queued_at FROM measure_session")).scalar_one() is None
        command.downgrade(config, "0022")
        with engine.connect() as conn:
            assert not _has_column(conn, "measure_session", "queued_at")
            assert conn.execute(text("SELECT count(*) FROM measure_session")).scalar_one() == 1
    finally:
        command.upgrade(config, "head")


def test_0021_fills_the_visit_date_from_the_written_day(engine: Engine, clean_tables: None) -> None:
    """0021(v1.46): 있던 메모의 방문일은 쓴 날(한국 날짜)이다. UTC로는 전날 밤이어도 한국 날짜로 채운다.

    API 서버의 비밀값(JWT_SECRET 등) 없이 DB 주소만으로 돈다(설정을 읽지 않는다).
    """
    source = (ROOT / "alembic" / "versions" / "0021_dog_note_visited_on.py").read_text(encoding="utf-8")
    assert "get_settings" not in source
    config = alembic_config()
    ids = {name: uuid.uuid4() for name in ("inst", "staff", "dog", "night", "noon")}
    command.downgrade(config, "0020")
    try:
        with engine.begin() as conn:
            assert not _has_column(conn, "dog_note", "visited_on")
            conn.execute(text("INSERT INTO institution (id, code, name) VALUES (:inst, 'A', '병원 A')"), ids)
            conn.execute(
                text(
                    "INSERT INTO staff (id, institution_id, login_id, password_hash, name, role) "
                    "VALUES (:staff, :inst, 'kim01', 'x', '갑', 'CLIENT')"
                ),
                ids,
            )
            conn.execute(
                text(
                    "INSERT INTO dog (id, institution_id, name, breed, weight_kg, size_class) "
                    "VALUES (:dog, :inst, '보리', '믹스', 10, 'MEDIUM')"
                ),
                ids,
            )
            conn.execute(
                text(
                    "INSERT INTO dog_note (id, dog_id, category, body, staff_id, created_at, updated_at) VALUES "
                    "(:night, :dog, 'S', '가', :staff, '2026-11-05T16:30:00+00', '2026-11-05T16:30:00+00'), "
                    "(:noon, :dog, 'O', '나', :staff, '2026-11-05T03:00:00+00', '2026-11-05T03:00:00+00')"
                ),
                ids,
            )
        command.upgrade(config, "head")
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT id, visited_on FROM dog_note")).all()
            days = {str(note_id): day.isoformat() for note_id, day in rows}
            assert days == {str(ids["night"]): "2026-11-06", str(ids["noon"]): "2026-11-05"}
        # 이 칸을 모르는 앞 판 앱의 INSERT(배포 중에 잠깐 같은 DB에 쓴다)도 오늘의 한국 날짜로 들어간다
        with engine.begin() as conn:
            late = conn.execute(
                text(
                    "INSERT INTO dog_note (id, dog_id, category, body, staff_id) "
                    "VALUES (:late, :dog, 'S', '다', :staff) RETURNING visited_on"
                ),
                {**ids, "late": uuid.uuid4()},
            ).scalar_one()
            assert late == today_local()
    finally:
        command.upgrade(config, "head")
