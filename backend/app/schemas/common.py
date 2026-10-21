"""응답 모델 공통(11.4, 11.5).

- 시각은 UTC ISO 8601, 초까지, Z로 끝낸다. DB에서 읽은 시각은 연결의 시간대가 붙어 오므로 astimezone(UTC)으로 바꾼다.
- ID(uuid.UUID)는 pydantic이 JSON에서 문자열로 내보낸다.
- 값이 없는 필드도 키를 빼지 않고 null로 보낸다(11.5). Optional 필드에 기본값 None을 두면 된다.
"""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer


def to_utc_z(value: datetime) -> str:
    """2026-10-19T00:30:00Z 모양. 시간대 없는 시각은 11.4 위반이라 내보내지 않는다."""
    if value.tzinfo is None:
        raise ValueError("시간대 없는 시각은 내보낼 수 없습니다(11.4)")
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


UtcDateTime = Annotated[datetime, PlainSerializer(to_utc_z, return_type=str, when_used="json")]


class OutModel(BaseModel):
    """DB 모델(ORM 객체)의 속성에서 바로 만들 수 있는 응답 모델. Spring의 엔티티 → DTO 변환에 해당한다."""

    model_config = ConfigDict(from_attributes=True)
