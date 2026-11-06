"""'오늘'을 정하는 시간대(16절 APP_TIMEZONE). measured_on 기본값과 날짜 검사(13.2, 15.6)가 쓴다.

DB와 API는 UTC를 쓰지만(11.4), "오늘"이라는 날짜는 담당자가 있는 곳(기본 Asia/Seoul)의 날짜다.
"""

from datetime import date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.models.enums import ContractStatus


@lru_cache
def _zone(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def local_zone() -> ZoneInfo:
    return _zone(get_settings().APP_TIMEZONE)


# 계약이 끝나고 이 날수가 지나면 워커가 그 기관의 측정 자료와 가입 계정을 지운다(12.5)
CONTRACT_RETENTION_DAYS = 90


def today_local() -> date:
    """APP_TIMEZONE 기준 오늘 날짜."""
    return datetime.now(local_zone()).date()


def contract_status(ends_at: date | None) -> str:
    """기관 계약 상태(11.6). 종료일이 없거나 오늘(APP_TIMEZONE) 이후면 ACTIVE. 당일은 통과한다."""
    if ends_at is None or ends_at >= today_local():
        return ContractStatus.ACTIVE
    return ContractStatus.EXPIRED
