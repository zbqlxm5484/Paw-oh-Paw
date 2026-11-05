"""측정 이력·회차 비교·수치 추이 응답 모델(명세 15.8, BE-17·18, S15P31A404-198).

값은 15.1대로 JSON 숫자(float)로 내보내고, 서버가 계산한 diff·symmetry_index는 Decimal로 계산한 뒤 바꾼다.
"""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.common import ReasonOut

# base 쿼리(15.8): BASELINE, PREVIOUS, 또는 회차 ID(UUID). 그 밖은 422 VALIDATION_ERROR(fields의 field는 base)
BASE_QUERY_PATTERN = (
    r"^(BASELINE|PREVIOUS|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$"
)


class ValidPassesOut(BaseModel):
    """camera_side별 유효 통과 수(15.6·15.7과 같은 기준: DONE 촬영의 유효 통과)."""

    LEFT: int
    RIGHT: int


class ReportStatusesOut(BaseModel):
    """판본별 보고서 status. 행이 없으면 null."""

    OWNER: str | None
    VET: str | None


class SessionHistoryItem(BaseModel):
    """측정 이력 한 줄(15.8 SessionHistoryItem). is_baseline은 12.5 규칙의 기준 회차 하나만 TRUE다."""

    id: uuid.UUID
    measured_on: date
    weight_kg: float | None
    status: str
    is_baseline: bool
    valid_passes: ValidPassesOut
    model_version: str | None
    reports: ReportStatusesOut


class SessionHistoryOut(BaseModel):
    """페이지 목록(11.5): items, total, page, size. 이 모양은 반려견 목록과 측정 이력 두 곳만 쓴다(15.1)."""

    items: list[SessionHistoryItem]
    total: int
    page: int
    size: int


class CompareBaseOut(BaseModel):
    """비교의 기준 회차. kind는 BASELINE·PREVIOUS·SESSION(회차 ID로 지정)."""

    session_id: uuid.UUID
    measured_on: date
    model_version: str | None
    kind: str


class CompareTargetOut(BaseModel):
    session_id: uuid.UUID
    measured_on: date
    model_version: str | None


class CompareItemOut(BaseModel):
    """비교 항목 하나(5절 예시, 15.8). diff = target_value − base_value. judgement는 report/judge.py의 다섯 값."""

    metric_code: str
    limb: str
    gait_type: str
    unit: str
    base_value: float | None
    target_value: float | None
    diff: float | None
    judgement: str
    note: ReasonOut | None


class CompareOut(BaseModel):
    dog_id: uuid.UUID
    base: CompareBaseOut
    target: CompareTargetOut
    model_changed: bool
    items: list[CompareItemOut]


class TrendPointOut(BaseModel):
    """추이의 점 하나. 측정 불가면 value가 null이고 사유가 있다. 행이 없는 회차는 점을 넣지 않는다."""

    session_id: uuid.UUID
    measured_on: date
    value: float | None
    measurable: bool
    unmeasurable_reason: ReasonOut | None
    model_version: str | None


class TrendSeriesOut(BaseModel):
    limb: str
    points: list[TrendPointOut]


class LrDiffPointOut(BaseModel):
    """좌우 차이 추이의 점(양쪽이 모두 측정된 회차만). diff는 왼쪽 − 오른쪽, symmetry_index는 12.3 식."""

    session_id: uuid.UUID
    measured_on: date
    diff: float
    symmetry_index: float | None


class LrDiffSeriesOut(BaseModel):
    pair: str
    points: list[LrDiffPointOut]


class TrendsOut(BaseModel):
    dog_id: uuid.UUID
    metric_code: str
    unit: str
    gait_type: str
    series: list[TrendSeriesOut]
    lr_diff: list[LrDiffSeriesOut]
