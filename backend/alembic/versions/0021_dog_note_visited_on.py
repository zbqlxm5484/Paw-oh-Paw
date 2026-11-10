"""메모·진료 기록의 방문일: dog_note.visited_on (명세 v1.46 12.2, 12.5, 13.9, 15.11)

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-10

지난 날짜의 진료 기록을 쓸 수 있게 방문일을 둔다. 있던 줄은 쓴 날(APP_TIMEZONE의 날짜)을 방문일로 채운다.
목록 순서와 그날 기록이 쓰는 색인(dog_id, visited_on)을 함께 만든다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.config import get_settings

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dog_note", sa.Column("visited_on", sa.Date(), nullable=True))
    op.execute(
        sa.text("UPDATE dog_note SET visited_on = (created_at AT TIME ZONE :zone)::date").bindparams(
            zone=get_settings().APP_TIMEZONE
        )
    )
    op.alter_column("dog_note", "visited_on", existing_type=sa.Date(), nullable=False)
    op.create_index("ix_dog_note_dog_visited", "dog_note", ["dog_id", "visited_on"])


def downgrade() -> None:
    op.drop_index("ix_dog_note_dog_visited", table_name="dog_note")
    op.drop_column("dog_note", "visited_on")
