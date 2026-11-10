"""메모·진료 기록의 방문일: dog_note.visited_on (명세 v1.46 12.2, 12.5, 13.9, 15.11)

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-10

지난 날짜의 진료 기록을 쓸 수 있게 방문일을 둔다. 있던 줄은 쓴 날(한국 날짜)을 방문일로 채운다.
목록 순서와 그날 기록이 쓰는 색인(dog_id, visited_on)을 함께 만든다.

칸에 서버 기본값(오늘의 한국 날짜)을 둔다. 새 앱은 늘 값을 보내지만, 배포 중에는 이 칸을 모르는 앞 판 앱이
잠깐 같은 DB에 쓴다(새 판을 띄우기 전에 마이그레이션이 먼저 돈다). 기본값이 없으면 그동안 메모 쓰기가 500이다.
시간대는 설정에서 읽지 않고 여기 적는다. 마이그레이션은 DB 주소만 있으면 돌아야 한다(alembic/env.py).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 명세의 날짜는 한국 날짜다(12.5). APP_TIMEZONE의 기본값과 같다
ZONE = "Asia/Seoul"
TODAY = f"(now() AT TIME ZONE '{ZONE}')::date"


def upgrade() -> None:
    op.add_column("dog_note", sa.Column("visited_on", sa.Date(), server_default=sa.text(TODAY), nullable=False))
    op.execute(sa.text("UPDATE dog_note SET visited_on = (created_at AT TIME ZONE :zone)::date").bindparams(zone=ZONE))
    op.create_index("ix_dog_note_dog_visited", "dog_note", ["dog_id", "visited_on"])


def downgrade() -> None:
    op.drop_index("ix_dog_note_dog_visited", table_name="dog_note")
    op.drop_column("dog_note", "visited_on")
