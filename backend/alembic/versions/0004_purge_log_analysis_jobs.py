"""자료 파기: purge_log.analysis_jobs_deleted (명세 v1.22 12.2, 15.9)

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-05

파기 때 분석 API에서 지운 작업 수를 함께 남긴다. 이 칸이 생기기 전의 기록은 분석 API를 부르지 않았으므로 0이다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "purge_log", sa.Column("analysis_jobs_deleted", sa.Integer(), server_default=sa.text("0"), nullable=False)
    )


def downgrade() -> None:
    op.drop_column("purge_log", "analysis_jobs_deleted")
