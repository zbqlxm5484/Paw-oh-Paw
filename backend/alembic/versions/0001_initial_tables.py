"""테이블 9개 만들기 (명세 v1.3 12.2 PostgreSQL DDL과 같다)

Revision ID: 0001
Revises:
Create Date: 2026-10-21

마이그레이션 파일은 한 번 적용되면 고치지 않는다. 바꿀 일이 생기면 새 파일을 만든다.
그래서 CHECK 값 목록도 app.models.enums를 import하지 않고 이 파일에 그대로 적는다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("now()")


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW)


def _updated_at() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW)


def upgrade() -> None:
    # 기관(병원·재활 센터)
    op.create_table(
        "institution",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="institution_pkey"),
        sa.UniqueConstraint("code", name="uq_institution_code"),
    )

    # 담당자 계정
    op.create_table(
        "staff",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("login_id", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.String(100), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="STAFF"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name="staff_pkey"),
        sa.UniqueConstraint("institution_id", "login_id", name="uq_staff_login"),
        sa.CheckConstraint("role IN ('ADMIN', 'STAFF')", name="ck_staff_role"),
        sa.ForeignKeyConstraint(["institution_id"], ["institution.id"], name="fk_staff_institution"),
    )

    # 반려견 (기준 회차 외래키는 measure_session을 만든 뒤에 붙인다)
    op.create_table(
        "dog",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("breed", sa.String(50), nullable=False),
        sa.Column("weight_kg", sa.Numeric(5, 2), nullable=False),
        sa.Column("size_class", sa.String(20), nullable=False),
        sa.Column("size_class_manual", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("birth_year", sa.SmallInteger(), nullable=True),
        sa.Column("sex", sa.String(20), nullable=True),
        sa.Column("rehab_start_date", sa.Date(), nullable=True),
        sa.Column("focus_limb", sa.String(20), nullable=True),
        sa.Column("baseline_session_id", sa.Uuid(), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name="dog_pkey"),
        sa.CheckConstraint("size_class IN ('SMALL', 'MEDIUM', 'LARGE')", name="ck_dog_size_class"),
        sa.CheckConstraint("sex IN ('MALE', 'FEMALE', 'MALE_NEUTERED', 'FEMALE_SPAYED')", name="ck_dog_sex"),
        sa.CheckConstraint("focus_limb IN ('LF', 'RF', 'LH', 'RH')", name="ck_dog_focus_limb"),
        sa.ForeignKeyConstraint(["institution_id"], ["institution.id"], name="fk_dog_institution"),
    )
    op.create_index("ix_dog_institution_name", "dog", ["institution_id", "name"])

    # 회차
    op.create_table(
        "measure_session",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dog_id", sa.Uuid(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("measured_on", sa.Date(), nullable=False),
        sa.Column("weight_kg", sa.Numeric(5, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="MEASURING"),
        sa.Column("fail_reason", sa.String(50), nullable=True),
        sa.Column("model_name", sa.String(50), nullable=True),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aggregated_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name="measure_session_pkey"),
        sa.CheckConstraint("status IN ('MEASURING', 'AGGREGATING', 'DONE', 'FAILED')", name="ck_session_status"),
        sa.ForeignKeyConstraint(["dog_id"], ["dog.id"], name="fk_session_dog"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], name="fk_session_staff"),
    )
    op.create_index("ix_session_dog_date", "measure_session", ["dog_id", "measured_on"])

    op.create_foreign_key("fk_dog_baseline", "dog", "measure_session", ["baseline_session_id"], ["id"])

    # 촬영
    op.create_table(
        "shot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("seq_no", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="UPLOADED"),
        sa.Column("fail_reason", sa.String(50), nullable=True),
        sa.Column("attempt_count", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("job_id", sa.String(100), nullable=True),
        sa.Column("validity", sa.String(20), nullable=True),
        sa.Column("validity_reason", sa.String(50), nullable=True),
        sa.Column("video_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("original_key", sa.String(255), nullable=False),
        sa.Column("result_key", sa.String(255), nullable=True),
        sa.Column("analysis_key", sa.String(255), nullable=True),
        sa.Column("width", sa.SmallInteger(), nullable=False),
        sa.Column("height", sa.SmallInteger(), nullable=False),
        sa.Column("fps", sa.Numeric(5, 2), nullable=False),
        sa.Column("duration_sec", sa.Numeric(5, 2), nullable=False),
        sa.Column("bitrate_kbps", sa.Integer(), nullable=False),
        sa.Column("codec", sa.String(20), nullable=False),
        sa.Column("below_min_spec", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("model_name", sa.String(50), nullable=True),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("video_ready_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name="shot_pkey"),
        sa.UniqueConstraint("session_id", "seq_no", name="uq_shot_seq"),
        sa.CheckConstraint("status IN ('UPLOADED', 'SUBMITTED', 'ANALYZING', 'DONE', 'FAILED')", name="ck_shot_status"),
        sa.CheckConstraint("validity IN ('VALID', 'PARTIAL', 'INVALID')", name="ck_shot_validity"),
        sa.CheckConstraint("video_status IN ('PENDING', 'READY', 'FAILED')", name="ck_shot_video_status"),
        sa.ForeignKeyConstraint(["session_id"], ["measure_session.id"], name="fk_shot_session"),
    )
    op.create_index("ix_shot_status", "shot", ["status"])
    op.create_index("ix_shot_video", "shot", ["video_status", "status"])

    # 통과
    op.create_table(
        "walk_pass",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("shot_id", sa.Uuid(), nullable=False),
        sa.Column("pass_no", sa.SmallInteger(), nullable=False),
        sa.Column("camera_side", sa.String(20), nullable=False),
        sa.Column("gait_type", sa.String(20), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("exclude_reason", sa.String(50), nullable=True),
        sa.Column("start_frame", sa.Integer(), nullable=False),
        sa.Column("end_frame", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="walk_pass_pkey"),
        sa.UniqueConstraint("shot_id", "pass_no", name="uq_pass_no"),
        sa.CheckConstraint("camera_side IN ('LEFT', 'RIGHT')", name="ck_pass_camera_side"),
        sa.CheckConstraint("gait_type IN ('WALK', 'TROT', 'PACE', 'OTHER')", name="ck_pass_gait_type"),
        sa.ForeignKeyConstraint(["shot_id"], ["shot.id"], name="fk_pass_shot"),
    )

    # 회차 수치
    op.create_table(
        "session_metric",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("gait_type", sa.String(20), nullable=False),
        sa.Column("limb", sa.String(20), nullable=False),
        sa.Column("metric_code", sa.String(50), nullable=False),
        sa.Column("value", sa.Numeric(10, 4), nullable=True),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("measurable", sa.Boolean(), nullable=False),
        sa.Column("unmeasurable_reason", sa.String(50), nullable=True),
        sa.Column("n_passes", sa.SmallInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="session_metric_pkey"),
        sa.UniqueConstraint("session_id", "gait_type", "limb", "metric_code", name="uq_metric"),
        sa.CheckConstraint("gait_type IN ('WALK', 'TROT', 'PACE', 'OTHER')", name="ck_metric_gait_type"),
        sa.CheckConstraint("limb IN ('LF', 'RF', 'LH', 'RH', 'NONE')", name="ck_metric_limb"),
        sa.ForeignKeyConstraint(["session_id"], ["measure_session.id"], name="fk_metric_session"),
    )

    # 보고서
    op.create_table(
        "report",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("edition", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("file_key", sa.String(255), nullable=True),
        sa.Column("fail_reason", sa.String(50), nullable=True),
        sa.Column("generation_ms", sa.Integer(), nullable=True),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("template_version", sa.String(20), nullable=False),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name="report_pkey"),
        sa.UniqueConstraint("session_id", "edition", name="uq_report_edition"),
        sa.CheckConstraint("edition IN ('OWNER', 'VET')", name="ck_report_edition"),
        sa.CheckConstraint("status IN ('PENDING', 'GENERATING', 'DONE', 'FAILED')", name="ck_report_status"),
        sa.ForeignKeyConstraint(["session_id"], ["measure_session.id"], name="fk_report_session"),
    )

    # 파기 기록 (다른 테이블과 외래키로 잇지 않는다)
    op.create_table(
        "purge_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("rows_deleted", sa.Integer(), nullable=False),
        sa.Column("files_deleted", sa.Integer(), nullable=False),
        sa.Column("bytes_deleted", sa.BigInteger(), nullable=False),
        sa.Column("executed_by", sa.Uuid(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.PrimaryKeyConstraint("id", name="purge_log_pkey"),
        sa.CheckConstraint("scope IN ('DOG', 'INSTITUTION', 'ALL')", name="ck_purge_scope"),
    )


def downgrade() -> None:
    op.drop_table("purge_log")
    op.drop_table("report")
    op.drop_table("session_metric")
    op.drop_table("walk_pass")
    op.drop_index("ix_shot_video", table_name="shot")
    op.drop_index("ix_shot_status", table_name="shot")
    op.drop_table("shot")
    op.drop_constraint("fk_dog_baseline", "dog", type_="foreignkey")
    op.drop_index("ix_session_dog_date", table_name="measure_session")
    op.drop_table("measure_session")
    op.drop_index("ix_dog_institution_name", table_name="dog")
    op.drop_table("dog")
    op.drop_table("staff")
    op.drop_table("institution")
