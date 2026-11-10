"""기관의 그날 기록(BE-35, 12.5 그날 기록, 15.11 GET /daily-records, v1.46).

하루치 바이탈·메모·진료 기록·회차를 모아 준다. 저장하지 않고 조회할 때 읽는다. 홈의 '오늘' 목록이 반려견마다
차트를 따로 읽지 않게 하려는 것이라, 반려견 수와 상관없이 정해진 수의 쿼리로 끝낸다(15.1).
Spring에 빗대면 세 서비스의 조회 메서드를 묶어 DTO 하나로 돌려주는 퍼사드다.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.schemas.daily_records import DailyRecordsOut
from app.services.notes import notes_on
from app.services.sessions import sessions_on
from app.services.vitals import vitals_on


def daily_records(db: Session, institution_id: uuid.UUID, day: date) -> DailyRecordsOut:
    """그날의 바이탈(measured_on)·메모와 진료 기록(visited_on)·회차(measured_on). 휴지통의 반려견은 뺀다."""
    return DailyRecordsOut(
        date=day,
        vitals=vitals_on(db, institution_id, day),
        notes=notes_on(db, institution_id, day),
        sessions=sessions_on(db, institution_id, day),
    )
