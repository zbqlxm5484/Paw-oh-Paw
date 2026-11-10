"""그날 기록 응답 모델(15.11 GET /daily-records, v1.46).

schemas/chart.py는 schemas/sessions.py를 import하지 않으므로(회차 시작이 VitalIn을 쓴다) 둘을 묶는 모델은 여기 둔다.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.schemas.chart import NoteOut, VitalOut
from app.schemas.sessions import SessionListItem


class DailyRecordsOut(BaseModel):
    """기관의 하루치 기록. 어느 반려견의 것인지는 VitalOut.dog_id·NoteOut.dog_id·SessionListItem.dog로 안다."""

    date: date
    vitals: list[VitalOut]
    notes: list[NoteOut]
    sessions: list[SessionListItem]
