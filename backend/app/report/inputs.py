"""보고서 입력(8절 "입력", 만드는 순서 1번 입력 검사).

팀 서비스는 app/services/report_input.py의 build_report_input이 이 모양의 dict를 만들고, 기업 서버는 같은 모양을 직접
준다. 없는 정보는 그 항목만 빼고(None), 없으면 만들 수 없는 것(판본·반려견 이름·측정일·회차 결과)은 ReportInputError다.

{
  "edition": "OWNER" | "VET",
  "dog": {"name", "breed", "weight_kg", "size_class", "sex", "birth_year"},
  "session": {"id", "measured_on", "weight_kg", "size_class", "model_name", "model_version"},
  "result": GET /sessions/{id}/result 응답(15.7 SessionResultOut)과 같은 dict,
  "previous": 직전 DONE 회차의 같은 dict 또는 null,
  "previous_session": {"round": 직전 회차의 회차 번호, "created_at": 만든 시각(ISO, 한국 시간)} (선택, v1.52),
  "settings": {"tolerance": {수치 코드: 오차 범위}} (선택, 197)
}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.report import ReportInputError

EDITIONS = ("OWNER", "VET")


@dataclass(frozen=True)
class DogInfo:
    name: str
    breed: str | None
    weight_kg: float | None
    size_class: str | None
    sex: str | None
    birth_year: int | None


@dataclass(frozen=True)
class SessionInfo:
    id: str
    measured_on: str
    weight_kg: float | None
    size_class: str | None
    model_name: str | None
    model_version: str | None


@dataclass(frozen=True)
class ReportInput:
    edition: str
    dog: DogInfo
    session: SessionInfo
    result: dict[str, Any]
    previous: dict[str, Any] | None
    tolerance: dict[str, float]
    previous_round: int | None = None  # 직전 회차의 회차 번호(화면과 같은 번호). 없으면 날짜만 적는다
    previous_created_at: str | None = None  # 직전 회차를 만든 시각(ISO). 같은 날 회차를 구분할 때 쓴다

    @property
    def previous_model_changed(self) -> bool:
        """직전 회차의 분석 모델이 다르면 변화를 판단하지 않는다(5절 비교 규칙)."""
        if not self.previous:
            return False
        return self.previous.get("model_version") not in (None, self.session.model_version)


def _optional_text(value: Any) -> str | None:
    return str(value).strip() if isinstance(value, str) and value.strip() else None


def _optional_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    number = _optional_number(value)
    return int(number) if number is not None and number.is_integer() else None


def _required_text(section: dict[str, Any], key: str, where: str) -> str:
    text = _optional_text(section.get(key))
    if text is None:
        raise ReportInputError("MISSING_FIELD", f"{where}.{key}")
    return text


def _section(data: dict[str, Any], key: str, *, required: bool) -> dict[str, Any] | None:
    value = data.get(key)
    if value is None:
        if required:
            raise ReportInputError("MISSING_SECTION", key)
        return None
    if not isinstance(value, dict):
        raise ReportInputError("BAD_SECTION", key)
    return value


def parse_input(data: Any) -> ReportInput:
    """입력 dict → ReportInput.

    만들 수 없으면 ReportInputError(reason: MISSING_SECTION·MISSING_FIELD·BAD_SECTION·BAD_EDITION).
    """
    if not isinstance(data, dict):
        raise ReportInputError("BAD_SECTION", "root")
    edition = _optional_text(data.get("edition"))
    if edition not in EDITIONS:
        raise ReportInputError("BAD_EDITION", str(data.get("edition")))
    dog_raw = _section(data, "dog", required=True)
    session_raw = _section(data, "session", required=True)
    result = _section(data, "result", required=True)
    assert dog_raw is not None and session_raw is not None and result is not None
    if not isinstance(result.get("gaits"), list):
        raise ReportInputError("MISSING_FIELD", "result.gaits")
    previous = _section(data, "previous", required=False)
    previous_session = (_section(data, "previous_session", required=False) or {}) if previous else {}
    settings = _section(data, "settings", required=False) or {}
    tolerance_raw = settings.get("tolerance") or {}
    tolerance = {
        str(code): number
        for code, raw in (tolerance_raw.items() if isinstance(tolerance_raw, dict) else [])
        if (number := _optional_number(raw)) is not None
    }
    return ReportInput(
        edition=edition,
        dog=DogInfo(
            name=_required_text(dog_raw, "name", "dog"),
            breed=_optional_text(dog_raw.get("breed")),
            weight_kg=_optional_number(dog_raw.get("weight_kg")),
            size_class=_optional_text(dog_raw.get("size_class")),
            sex=_optional_text(dog_raw.get("sex")),
            birth_year=_optional_int(dog_raw.get("birth_year")),
        ),
        session=SessionInfo(
            id=_optional_text(session_raw.get("id")) or "",
            measured_on=_required_text(session_raw, "measured_on", "session"),
            weight_kg=_optional_number(session_raw.get("weight_kg")),
            size_class=_optional_text(session_raw.get("size_class")),
            model_name=_optional_text(session_raw.get("model_name")),
            model_version=_optional_text(session_raw.get("model_version")),
        ),
        result=result,
        previous=previous,
        tolerance=tolerance,
        previous_round=_optional_int(previous_session.get("round")),
        previous_created_at=_optional_text(previous_session.get("created_at")),
    )
