"""메모·진료 기록과 수정 이력: dog_note, dog_note_revision (명세 v1.36 12.2, 12.5, 13.9, 15.11)

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-06

메모(CAUTION·GUARDIAN·BOOKING·OTHER)와 진료 기록(S·O·A·P)을 한 테이블에 둔다. 지우지 않고, 고칠 때마다 고치기 전
내용을 dog_note_revision에 한 줄 남긴다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CATEGORIES = "category IN ('S', 'O', 'A', 'P', 'CAUTION', 'GUARDIAN', 'BOOKING', 'OTHER')"


def upgrade() -> None:
    op.create_table(
        "dog_note",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dog_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("important", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(_CATEGORIES, name="ck_dog_note_category"),
        sa.ForeignKeyConstraint(["dog_id"], ["dog.id"], name="fk_dog_note_dog"),
        sa.ForeignKeyConstraint(["session_id"], ["measure_session.id"], name="fk_dog_note_session"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], name="fk_dog_note_staff"),
    )
    op.create_index("ix_dog_note_dog_created", "dog_note", ["dog_id", "created_at"])
    op.create_table(
        "dog_note_revision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("note_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("important", sa.Boolean(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("revised_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(_CATEGORIES, name="ck_dog_note_revision_category"),
        sa.ForeignKeyConstraint(["note_id"], ["dog_note.id"], name="fk_dog_note_revision_note"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], name="fk_dog_note_revision_staff"),
    )
    op.create_index("ix_dog_note_revision_note", "dog_note_revision", ["note_id", "revised_at"])


def downgrade() -> None:
    op.drop_index("ix_dog_note_revision_note", table_name="dog_note_revision")
    op.drop_table("dog_note_revision")
    op.drop_index("ix_dog_note_dog_created", table_name="dog_note")
    op.drop_table("dog_note")
