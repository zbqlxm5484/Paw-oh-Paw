"""로그인 잠금과 비밀번호를 바꾼 시각: staff에 칸 셋 (명세 v1.48 12.2, 12.5)

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-11

칸은 login_fail_count, login_locked_until, password_changed_at이다.
비밀번호를 5회 틀리면 30분 동안 잠그려고 이어서 틀린 수와 잠금이 풀리는 시각을 둔다. 비밀번호를 바꾸면 그전에 받은
토큰을 끊으려고 바꾼 시각을 둔다(토큰의 iat와 견준다, 11.6).

있던 계정은 틀린 수 0, 두 시각은 NULL이다(잠기지 않았고, 이미 받은 토큰은 그대로 쓴다). 틀린 수에 서버 기본값을
둔다: 배포 중에는 이 칸을 모르는 앞 판 앱이 잠깐 같은 DB에 가입 계정을 넣는다(새 판을 띄우기 전에 마이그레이션이
먼저 돈다).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("staff", sa.Column("login_fail_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("staff", sa.Column("login_locked_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("staff", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("staff", "password_changed_at")
    op.drop_column("staff", "login_locked_until")
    op.drop_column("staff", "login_fail_count")
