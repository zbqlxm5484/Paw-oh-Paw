"""바이탈 부분 입력: dog_vital의 다섯 값을 비울 수 있게 (명세 v1.41 12.2, 12.5, 13.9)

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-09

잰 값만 적을 수 있게 다섯 값의 NOT NULL을 푼다. 대신 값이 하나는 있어야 하고(ck_dog_vital_any_value),
혈압은 수축기·이완기가 함께 있거나 함께 없다(ck_dog_vital_bp_pair). 있던 줄은 다섯 값이 다 있어 그대로 통과한다.
내릴 때는 빈 값이 있는 줄을 지운다(NOT NULL로 되돌릴 수 없어서다).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = (
    ("weight_kg", sa.Numeric(precision=5, scale=2)),
    ("temp_c", sa.Numeric(precision=4, scale=1)),
    ("heart_rate", sa.SmallInteger()),
    ("sbp", sa.SmallInteger()),
    ("dbp", sa.SmallInteger()),
)


def upgrade() -> None:
    for name, kind in COLUMNS:
        op.alter_column("dog_vital", name, existing_type=kind, nullable=True)
    op.create_check_constraint(
        "ck_dog_vital_any_value",
        "dog_vital",
        "weight_kg IS NOT NULL OR temp_c IS NOT NULL OR heart_rate IS NOT NULL OR sbp IS NOT NULL",
    )
    op.create_check_constraint("ck_dog_vital_bp_pair", "dog_vital", "(sbp IS NULL) = (dbp IS NULL)")


def downgrade() -> None:
    op.drop_constraint("ck_dog_vital_bp_pair", "dog_vital", type_="check")
    op.drop_constraint("ck_dog_vital_any_value", "dog_vital", type_="check")
    op.execute(
        "DELETE FROM dog_vital WHERE weight_kg IS NULL OR temp_c IS NULL OR heart_rate IS NULL "
        "OR sbp IS NULL OR dbp IS NULL"
    )
    for name, kind in COLUMNS:
        op.alter_column("dog_vital", name, existing_type=kind, nullable=False)
