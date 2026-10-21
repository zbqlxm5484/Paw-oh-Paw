"""GET /health 응답(15.9). 저장소 검사(storage)는 작업 단위 5에서 더한다."""

from typing import Literal

from pydantic import BaseModel

Check = Literal["ok", "error"]


class HealthOut(BaseModel):
    # 503이면 "error"(명세 v1.4에 반영 예정)
    status: Check
    db: Check
    version: str
