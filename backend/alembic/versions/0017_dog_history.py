"""진단 이력: dog_history (명세 v1.36 12.2, 12.5, 13.9, 15.11)

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-06

진단·수술·재활을 날짜와 함께 한 줄씩 남긴다. 부위는 네 다리 또는 척추(SP)다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dog_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dog_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("site", sa.String(length=20), nullable=True),
        sa.Column("clinician", sa.String(length=50), nullable=True),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("kind IN ('DIAGNOSIS', 'SURGERY', 'REHAB')", name="ck_dog_history_kind"),
        sa.CheckConstraint("site IN ('LF', 'RF', 'LH', 'RH', 'SP')", name="ck_dog_history_site"),
        sa.ForeignKeyConstraint(["dog_id"], ["dog.id"], name="fk_dog_history_dog"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], name="fk_dog_history_staff"),
    )
    op.create_index("ix_dog_history_dog_date", "dog_history", ["dog_id", "occurred_on"])


def downgrade() -> None:
    op.drop_index("ix_dog_history_dog_date", table_name="dog_history")
    op.drop_table("dog_history")
