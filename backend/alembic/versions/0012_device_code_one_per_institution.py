"""디바이스 코드: 계정 상한 삭제, 기관마다 쓸 수 있는 코드 하나 (명세 v1.32 12.2, 12.5, 15.9)

Revision ID: 0012
Revises: 0010
Create Date: 2026-11-06

- max_accounts 칸과 ck_device_code_max를 지운다. 코드 하나로 만들 수 있는 계정 수에 상한이 없다.
- 회수하지 않은 코드는 기관마다 하나다(부분 유일 인덱스 uq_device_code_active).
- 이미 쓸 수 있는 코드가 여러 개인 기관은 하나만 남기고 나머지를 회수한다. 가입에 쓰인 코드를 먼저 남기고,
  그런 코드가 여럿이거나 없으면 가장 최근에 발급한 것을 남긴다. 회수한 코드로 가입한 계정은 그대로 둔다.
- 번호는 작업 목록(웹 전용 기능 서버 구현)이 0011을 알림 설정에 주어 0012를 썼다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVOKE_EXTRA_CODES = """
UPDATE device_code
SET revoked_at = now(), updated_at = now()
WHERE id IN (
    SELECT id
    FROM (
        SELECT
            dc.id,
            row_number() OVER (
                PARTITION BY dc.institution_id
                ORDER BY
                    (EXISTS (SELECT 1 FROM staff s WHERE s.device_code_id = dc.id)) DESC,
                    dc.created_at DESC,
                    dc.id DESC
            ) AS rn
        FROM device_code dc
        WHERE dc.revoked_at IS NULL
    ) ranked
    WHERE rn > 1
)
"""


def upgrade() -> None:
    op.execute(REVOKE_EXTRA_CODES)
    op.drop_constraint("ck_device_code_max", "device_code", type_="check")
    op.drop_column("device_code", "max_accounts")
    op.create_index(
        "uq_device_code_active",
        "device_code",
        ["institution_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    """칸과 제약만 되돌린다. 올릴 때 회수한 코드는 회수된 채로 둔다(어느 것이 그때 회수됐는지 남기지 않았다)."""
    op.drop_index("uq_device_code_active", table_name="device_code")
    op.add_column(
        "device_code", sa.Column("max_accounts", sa.SmallInteger(), server_default=sa.text("3"), nullable=False)
    )
    op.create_check_constraint("ck_device_code_max", "device_code", "max_accounts >= 1")
