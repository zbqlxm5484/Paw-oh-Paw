"""반려견 휴지통: dog.deleted_at (명세 v1.33 12.2, 12.5, 15.5)

Revision ID: 0013
Revises: 0004
Create Date: 2026-11-06

삭제 버튼은 반려견을 휴지통에 넣는다(deleted_at에 시각). NULL이면 휴지통에 없는 반려견이다. 30일이 지나면 워커가
영구 삭제한다. 번호는 작업 목록(웹 전용 기능 서버 구현)이 0005~0011을 다른 일에 주어 0013을 썼다. 순서는
0004 → 0013 → 0010(약관 동의) → 0012(디바이스 코드)다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dog", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("dog", "deleted_at")
