"""반려견 사진: dog_image (명세 v1.40 12.2, 12.5, 13.9, 15.11)

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-06

수술 전·후 사진, 방사선 사진, 그 밖의 사진을 날짜·종류와 함께 둔다. 파일은 얼굴을 가린 것만 저장한다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dog_image",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dog_id", sa.Uuid(), nullable=False),
        sa.Column("taken_on", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("caption", sa.String(length=100), nullable=True),
        sa.Column("file_key", sa.String(length=255), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("masked_faces", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("kind IN ('PRE_OP', 'POST_OP', 'XRAY', 'PHOTO')", name="ck_dog_image_kind"),
        sa.ForeignKeyConstraint(["dog_id"], ["dog.id"], name="fk_dog_image_dog"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], name="fk_dog_image_staff"),
    )
    op.create_index("ix_dog_image_dog_taken", "dog_image", ["dog_id", "taken_on"])


def downgrade() -> None:
    op.drop_index("ix_dog_image_dog_taken", table_name="dog_image")
    op.drop_table("dog_image")
