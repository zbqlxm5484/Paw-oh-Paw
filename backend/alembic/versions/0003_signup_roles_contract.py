"""회원가입·역할·계약 (명세 v1.12 12.2): institution·device_code·staff·dog 변경

institution.contract_ends_at, device_code 테이블, staff 역할 CHECK·아이디 전역 유일·device_code_id·email·재설정 두 칸,
dog.version.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-30

- 지금까지의 STAFF(기관 담당자)는 CLIENT가 된다. STAFF는 이제 크림오프 임시 스태프다(11.6). role의 기본값도 CLIENT.
- 아이디가 전역 유일이 된다(uq_staff_login이 (institution_id, login_id) → (login_id)). 서로 다른 기관에 같은 아이디가
  있으면 올리기 전에 멈추고 개수를 알려 준다. 손으로 정리한 뒤 다시 돌린다(아이디는 로그에 남기지 않는다, 11.8).
- 내리면 CLIENT는 STAFF로 돌아가고 새 칸·테이블은 지워진다(가입 계정의 코드·이메일·재설정 정보는 사라진다).
- CHECK 값 목록은 0001과 같은 이유로 여기 그대로 적는다(마이그레이션은 혼자 돌아야 한다).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DUPLICATE_LOGIN_IDS = "SELECT count(*) FROM (SELECT login_id FROM staff GROUP BY login_id HAVING count(*) > 1) AS d"


def upgrade() -> None:
    duplicates = op.get_bind().execute(sa.text(DUPLICATE_LOGIN_IDS)).scalar_one()
    if duplicates:
        raise RuntimeError(
            f"서로 다른 기관에 같은 아이디가 {duplicates}개 있어 uq_staff_login(login_id)을 만들 수 없습니다. "
            "아이디를 정리한 뒤 다시 올리세요(명세 12.2 v1.12)"
        )

    # 기관: 계약 종료일(당일 포함, NULL = 기한 없음)
    op.add_column("institution", sa.Column("contract_ends_at", sa.Date(), nullable=True))

    # 디바이스 코드
    op.create_table(
        "device_code",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("max_accounts", sa.SmallInteger(), nullable=False, server_default=sa.text("3")),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="device_code_pkey"),
        sa.UniqueConstraint("code", name="uq_device_code"),
        sa.CheckConstraint("max_accounts >= 1", name="ck_device_code_max"),
        sa.ForeignKeyConstraint(["institution_id"], ["institution.id"], name="fk_device_code_institution"),
    )

    # 담당자: 역할 셋, 아이디 전역 유일, 가입 코드, 이메일, 재설정 토큰
    op.drop_constraint("ck_staff_role", "staff", type_="check")  # 옛 CHECK(ADMIN·STAFF)가 CLIENT를 막으므로 먼저 푼다
    op.execute("UPDATE staff SET role = 'CLIENT' WHERE role = 'STAFF'")
    op.create_check_constraint("ck_staff_role", "staff", "role IN ('ADMIN', 'STAFF', 'CLIENT')")
    op.alter_column("staff", "role", server_default="CLIENT")
    op.drop_constraint("uq_staff_login", "staff", type_="unique")
    op.create_unique_constraint("uq_staff_login", "staff", ["login_id"])
    op.add_column("staff", sa.Column("device_code_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_staff_device_code", "staff", "device_code", ["device_code_id"], ["id"])
    op.add_column("staff", sa.Column("email", sa.String(254), nullable=True))
    op.add_column("staff", sa.Column("password_reset_hash", sa.CHAR(64), nullable=True))
    op.add_column("staff", sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True))

    # 반려견: 낙관적 잠금
    op.add_column("dog", sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")))


def downgrade() -> None:
    op.drop_column("dog", "version")

    op.drop_column("staff", "password_reset_expires_at")
    op.drop_column("staff", "password_reset_hash")
    op.drop_column("staff", "email")
    op.drop_constraint("fk_staff_device_code", "staff", type_="foreignkey")
    op.drop_column("staff", "device_code_id")
    op.drop_constraint("uq_staff_login", "staff", type_="unique")
    op.create_unique_constraint("uq_staff_login", "staff", ["institution_id", "login_id"])
    op.drop_constraint("ck_staff_role", "staff", type_="check")
    op.execute("UPDATE staff SET role = 'STAFF' WHERE role = 'CLIENT'")
    op.alter_column("staff", "role", server_default="STAFF")
    op.create_check_constraint("ck_staff_role", "staff", "role IN ('ADMIN', 'STAFF')")

    op.drop_table("device_code")
    op.drop_column("institution", "contract_ends_at")
