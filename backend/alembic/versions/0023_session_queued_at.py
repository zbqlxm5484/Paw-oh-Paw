"""분석 줄에 선 시각: measure_session에 queued_at (명세 v1.59 12.2, 12.4 분석 줄)

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-12

워커가 회차를 분석 줄에 세운 시각이다. 기관마다 줄에 서 있는 회차 수와 1시간에 줄에 세운 회차 수를 이 칸으로 세고,
이 순서대로 촬영을 분석 API에 맡긴다. 줄에 선 순서로 읽으므로 인덱스를 둔다.

있던 회차는 NULL이다. 분석을 기다리는 촬영(UPLOADED)이 남은 회차는 새 판 워커가 다음 바퀴에 줄에 세운다. 이 칸을 모르는
앞 판 앱과 워커는 그대로 돈다(NULL 허용. 배포 중에는 새 판을 띄우기 전에 마이그레이션이 먼저 돈다).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("measure_session", sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_session_queued_at", "measure_session", ["queued_at"])


def downgrade() -> None:
    op.drop_index("ix_session_queued_at", table_name="measure_session")
    op.drop_column("measure_session", "queued_at")
