"""'오늘'을 정하는 시간대(16절 APP_TIMEZONE). measured_on 기본값과 날짜 검사(13.2, 15.6)가 쓴다.

DB와 API는 UTC를 쓰지만(11.4), "오늘"이라는 날짜는 담당자가 있는 곳(기본 Asia/Seoul)의 날짜다.
"""

from datetime import date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from app.core.config import get_settings


@lru_cache
def _zone(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def local_zone() -> ZoneInfo:
    return _zone(get_settings().APP_TIMEZONE)


def today_local() -> date:
    """APP_TIMEZONE 기준 오늘 날짜."""
    return datetime.now(local_zone()).date()
