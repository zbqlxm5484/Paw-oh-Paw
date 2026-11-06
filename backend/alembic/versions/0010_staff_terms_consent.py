"""가입 약관 동의 기록: staff.terms_version·terms_agreed_at·marketing_agreed (명세 v1.31 12.2, 13.5, 15.4)

Revision ID: 0010
Revises: 0013
Create Date: 2026-11-06

가입 때 동의한 약관 버전과 시각, 선택 항목(마케팅 수신)을 남긴다. 이 칸이 생기기 전에 만든 계정과 seed.py 계정은
기록이 없어 NULL·FALSE다. 번호는 작업 목록(웹 전용 기능 서버 구현)에서 받은 0010이고 0005~0009는 차트 자료가 쓴다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("staff", sa.Column("terms_version", sa.String(length=20), nullable=True))
    op.add_column("staff", sa.Column("terms_agreed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("staff", sa.Column("marketing_agreed", sa.Boolean(), server_default=sa.text("false"), nullable=False))


def downgrade() -> None:
    op.drop_column("staff", "marketing_agreed")
    op.drop_column("staff", "terms_agreed_at")
    op.drop_column("staff", "terms_version")
