"""measure_session.size_class 추가 (명세 v1.5 12.2·12.5: 회차 시점 체급)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22

회차를 시작할 때의 체급을 회차에 따로 저장한다(팀 회의 10-22).
반려견 체중·체급이 뒤에 바뀌어도 지난 회차의 체급은 그대로다.
이미 있는 회차는 그날 체중(없으면 등록 체중)으로 채우고, 담당자가 직접 지정한 반려견은 그 체급을 쓴다.
경계값(10·25 kg)은 설정값이지만 마이그레이션은 혼자 돌아야 하므로 여기 그대로 적는다.
(0001이 CHECK 값 목록을 그대로 적는 것과 같은 이유다.)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKFILL = """
UPDATE measure_session s
SET size_class = CASE
    WHEN d.size_class_manual THEN d.size_class
    WHEN coalesce(s.weight_kg, d.weight_kg) < 10 THEN 'SMALL'
    WHEN coalesce(s.weight_kg, d.weight_kg) < 25 THEN 'MEDIUM'
    ELSE 'LARGE'
END
FROM dog d
WHERE d.id = s.dog_id
"""


def upgrade() -> None:
    op.add_column("measure_session", sa.Column("size_class", sa.String(20), nullable=True))
    op.execute(BACKFILL)
    op.alter_column("measure_session", "size_class", nullable=False)
    op.create_check_constraint("ck_session_size_class", "measure_session", "size_class IN ('SMALL', 'MEDIUM', 'LARGE')")


def downgrade() -> None:
    op.drop_constraint("ck_session_size_class", "measure_session", type_="check")
    op.drop_column("measure_session", "size_class")
