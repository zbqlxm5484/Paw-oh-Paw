"""바이탈: dog_vital (명세 v1.36 12.2, 12.5, 13.9, 15.11)

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-06

반려견마다 하루 한 줄이다(uq_dog_vital_day). 회차를 시작하며 함께 보낸 값이면 session_id에 그 회차를 적는다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dog_vital",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dog_id", sa.Uuid(), nullable=False),
        sa.Column("measured_on", sa.Date(), nullable=False),
        sa.Column("weight_kg", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("temp_c", sa.Numeric(precision=4, scale=1), nullable=False),
        sa.Column("heart_rate", sa.SmallInteger(), nullable=False),
        sa.Column("sbp", sa.SmallInteger(), nullable=False),
        sa.Column("dbp", sa.SmallInteger(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dog_id", "measured_on", name="uq_dog_vital_day"),
        sa.ForeignKeyConstraint(["dog_id"], ["dog.id"], name="fk_dog_vital_dog"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], name="fk_dog_vital_staff"),
        sa.ForeignKeyConstraint(["session_id"], ["measure_session.id"], name="fk_dog_vital_session"),
    )


def downgrade() -> None:
    op.drop_table("dog_vital")
