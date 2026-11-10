"""회차 요청·응답 모델(13.3, 15.3 SessionOut, 15.6)."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, field_validator

from app.core.dates import today_local
from app.schemas.chart import VitalIn
from app.schemas.common import OutModel, ReasonOut, StaffBriefOut, UtcDateTime, Weight
from app.schemas.shots import ShotOut


class SessionCreate(BaseModel):
    """POST /dogs/{dog_id}/sessions 요청. 모두 선택이다. measured_on 기본값은 오늘(한국 날짜), 미래 날짜 불가(13.3).

    vital을 보내면 그날 바이탈로 함께 저장한다(15.6, v1.36).
    """

    measured_on: date | None = None
    weight_kg: Weight | None = None
    vital: VitalIn | None = None

    @field_validator("measured_on")
    @classmethod
    def not_future(cls, value: date | None) -> date | None:
        if value is not None and value > today_local():
            raise ValueError("미래 날짜는 쓸 수 없습니다")
        return value


class DogBriefOut(OutModel):
    id: uuid.UUID
    name: str
    breed: str
    weight_kg: float
    size_class: str


class SideProgressOut(BaseModel):
    valid_passes: int
    recommended: int


class ProgressOut(BaseModel):
    """camera_side별 유효 통과 수와 권장 수(15.6)."""

    LEFT: SideProgressOut
    RIGHT: SideProgressOut


class SessionOut(BaseModel):
    """회차(15.3)."""

    id: uuid.UUID
    dog_id: uuid.UUID
    staff: StaffBriefOut
    measured_on: date
    weight_kg: float | None
    # 회차 시점 체급(12.5). 반려견의 지금 체급(DogOut.size_class)과 다를 수 있다
    size_class: str
    status: str
    fail_reason: ReasonOut | None
    model_name: str | None
    model_version: str | None
    completed_at: UtcDateTime | None
    aggregated_at: UtcDateTime | None
    created_at: UtcDateTime


class DogNameOut(OutModel):
    """반려견의 ID와 이름만(기관 회차 목록)."""

    id: uuid.UUID
    name: str


class SessionListItem(BaseModel):
    """기관 회차 목록의 한 줄(15.6 GET /sessions). symmetry_score는 12.3의 대칭 점수다."""

    id: uuid.UUID
    measured_on: date
    status: str
    fail_reason: ReasonOut | None
    dog: DogNameOut
    staff: StaffBriefOut
    weight_kg: float | None
    model_version: str | None
    symmetry_score: int | None
    completed_at: UtcDateTime | None
    created_at: UtcDateTime


class SessionListOut(BaseModel):
    """페이지 목록(11.5): items, total, page, size."""

    items: list[SessionListItem]
    total: int
    page: int
    size: int


class SessionDetailOut(SessionOut):
    """GET /sessions/{id}: SessionOut + 반려견 요약, 진행, 안내, 촬영 목록(seq_no 내림차순)."""

    dog: DogBriefOut
    progress: ProgressOut
    notices: list[ReasonOut]
    shots: list[ShotOut]


class PassCountsOut(BaseModel):
    measured: int
    used: int
    excluded: int


class ShotCountsOut(BaseModel):
    total: int
    failed: int
    invalid: int


class ExcludeSummaryOut(ReasonOut):
    """제외 사유 하나와 그 사유로 제외된 통과 수."""

    count: int


class MetricOut(BaseModel):
    """회차 수치 한 줄(12.3). 측정 불가면 value는 null이고 사유가 있다. 0을 보내지 않는다(12.5)."""

    metric_code: str
    limb: str
    value: float | None
    unit: str
    measurable: bool
    unmeasurable_reason: ReasonOut | None
    n_passes: int


class LimbCompareOut(BaseModel):
    """다리 비교 요약 한 줄(BE-21). diff는 왼쪽 − 오른쪽이다(12.3)."""

    pair: str
    metric_code: str
    unit: str
    left: float | None
    right: float | None
    diff: float | None
    symmetry_index: float | None
    comparable: bool
    reason: ReasonOut | None


class GaitResultOut(BaseModel):
    gait_type: str
    metrics: list[MetricOut]
    limb_compare: list[LimbCompareOut]


class SessionResultOut(SessionOut):
    """GET /sessions/{id}/result(15.7): SessionOut + 통과·촬영 수, 제외 사유, 안내, 보행 유형별 수치.

    symmetry_score는 12.3의 대칭 점수(0~100, 100에 가까울수록 좌우가 비슷함)이고 계산할 쌍이 없으면 null이다.
    """

    pass_counts: PassCountsOut
    shot_counts: ShotCountsOut
    exclude_summary: list[ExcludeSummaryOut]
    notices: list[ReasonOut]
    symmetry_score: int | None = None
    gaits: list[GaitResultOut]
