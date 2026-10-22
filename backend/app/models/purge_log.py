"""파기 기록. 파기 확인서(D-13)의 근거. 명세 12.2 purge_log.

파기 대상을 지울 때 기록까지 같이 지워지면 안 되므로 다른 테이블과 외래키로 잇지 않는다(12.1).
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import PurgeScope, check_in


class PurgeLog(Base):
    __tablename__ = "purge_log"
    __table_args__ = (check_in("scope", PurgeScope, name="ck_purge_scope"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(String(20))
    # scope가 ALL이면 NULL
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    rows_deleted: Mapped[int] = mapped_column(Integer)
    files_deleted: Mapped[int] = mapped_column(Integer)
    bytes_deleted: Mapped[int] = mapped_column(BigInteger)
    # 실행한 담당자 ID. 외래키 없음
    executed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
