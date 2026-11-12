"""반려견 차트 칸: dog.chart_no·owner_name·owner_phone·stage·stage_changed_on (명세 v1.36 12.2, 13.2, 15.5)

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-06

병원이 "동물번호-이름 / 보호자"로 환자를 찾는다. 이미 있는 반려견의 단계는 재활 중(REHAB)으로 둔다. 번호는 작업 목록이
0005~0009를 잡아 두었지만 그 뒤에 0010~0014가 먼저 들어가, 순서의 끝인 0014 다음 번호를 썼다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dog", sa.Column("chart_no", sa.String(length=30), nullable=True))
    op.add_column("dog", sa.Column("owner_name", sa.String(length=50), nullable=True))
    op.add_column("dog", sa.Column("owner_phone", sa.String(length=20), nullable=True))
    op.add_column("dog", sa.Column("stage", sa.String(length=20), server_default="REHAB", nullable=False))
    op.add_column("dog", sa.Column("stage_changed_on", sa.Date(), nullable=True))
    op.create_check_constraint("ck_dog_stage", "dog", "stage IN ('PRE', 'REHAB', 'DONE')")


def downgrade() -> None:
    op.drop_constraint("ck_dog_stage", "dog", type_="check")
    op.drop_column("dog", "stage_changed_on")
    op.drop_column("dog", "stage")
    op.drop_column("dog", "owner_phone")
    op.drop_column("dog", "owner_name")
    op.drop_column("dog", "chart_no")
