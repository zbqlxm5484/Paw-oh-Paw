"""회원 탈퇴와 알림 설정: staff.withdrawn_at·notif_on (명세 v1.35 12.2, 13.7, 15.4)

Revision ID: 0014
Revises: 0012
Create Date: 2026-11-06

withdrawn_at은 담당자가 스스로 탈퇴한 시각이다(NULL이면 탈퇴하지 않았다). notif_on은 알림을 받을지의 설정값이고
이미 있는 계정은 켜진 것으로 둔다. 순서는 0004 → 0013 → 0010 → 0012 → 0014다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("staff", sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("staff", sa.Column("notif_on", sa.Boolean(), server_default=sa.text("true"), nullable=False))


def downgrade() -> None:
    op.drop_column("staff", "notif_on")
    op.drop_column("staff", "withdrawn_at")
