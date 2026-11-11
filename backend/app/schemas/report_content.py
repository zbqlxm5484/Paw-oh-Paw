"""보고서 내용 응답(15.7의 62번 ReportContentOut). 웹의 보고서 인쇄 화면이 이 글과 표를 그대로 그린다.

글자는 모두 서버가 만든 것이다(8절 문장 템플릿, 금지 표현·용어 검사와 수치 대조를 지난 뒤에만 나간다).
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class ContentSession(BaseModel):
    measured_on: str
    round: int  # 같은 반려견의 끝난 회차(DONE·FAILED)를 (측정일, 만든 시각) 순으로 센 번호, 1부터
    model_name: str | None
    model_version: str | None
    weight_kg: float | None
    size_class: str | None
    symmetry_score: int | None  # 12.3 대칭 점수. 계산할 쌍이 없으면 null
    symmetry_level: str | None  # 100 − 대칭 점수의 차이 단계(SIMILAR·SLIGHT·LARGE). 점수가 없으면 null


class ContentDog(BaseModel):
    name: str
    breed: str | None
    sex: str | None
    birth_year: int | None
    focus_limb: str | None  # 관심 다리(12.2 dog.focus_limb)


class ContentPrevious(BaseModel):
    """직전 DONE 회차. model_changed면 값만 나란히 적고 차이·변화를 판단하지 않는다(5절)."""

    session_id: uuid.UUID
    measured_on: str
    round: int
    label: str  # "2회차, 2026년 11월 10일". 이번 회차와 같은 날이면 만든 시각이 붙는다(문장의 괄호 안과 같은 글)
    model_changed: bool


class ContentBaseline(BaseModel):
    """기준 회차(12.5: 지정한 회차, 없으면 가장 이른 DONE 회차)."""

    session_id: uuid.UUID
    measured_on: str
    round: int
    symmetry_score: int | None
    diff: int | None  # 이 회차의 대칭 점수 − 기준 회차의 대칭 점수. 한쪽이라도 없으면 null


class ContentHistoryItem(BaseModel):
    """이 회차까지 끝난 회차 하나. FAILED 회차는 symmetry_score가 null이다."""

    measured_on: str
    round: int
    symmetry_score: int | None


class GlossaryItem(BaseModel):
    term: str
    explanation: str


class ContentSentences(BaseModel):
    title: str
    edition_label: str
    intro: str
    summary: list[str]
    previous_note: str | None
    previous_gaps: list[str]
    caution: list[str]
    glossary: list[GlossaryItem]
    disclaimer: str


class ContentCell(BaseModel):
    """수치 표의 한 칸. 측정하지 못했으면 value가 null이고 reason에 사유 문장이 있다."""

    value: float | None
    text: str
    reason: str | None


class ContentRow(BaseModel):
    metric_code: str
    label: str
    unit: str
    cells: dict[str, ContentCell]  # 다리 코드 → 칸


class ContentCompare(BaseModel):
    """좌우 비교 한 줄(15.7 다리 비교와 같은 값)."""

    pair: str
    pair_label: str
    metric_code: str
    label: str
    left: str
    right: str
    diff: str
    symmetry_index: str
    diff_value: float | None  # diff·symmetry_index의 숫자 값. 비교할 수 없으면 null
    symmetry_value: float | None
    comparable: bool
    reason: str | None


class ContentLeg(BaseModel):
    """다리 한 쌍에서 좌우 차이가 가장 큰 수치(몸 그림용). weak_limb는 값이 작은 쪽이고 SIMILAR면 null이다."""

    pair: str
    gait_type: str
    metric_code: str
    label: str
    symmetry_index: str
    symmetry_value: float
    weak_limb: str | None
    level: str


class ContentChangeCell(BaseModel):
    """직전 회차 비교의 한 칸. diff는 이번 − 직전, change는 INCREASE·DECREASE·WITHIN_RANGE 또는 null."""

    previous: str
    current: str
    diff: str | None
    change: str | None
    change_label: str | None
    note: str | None


class ContentChangeRow(BaseModel):
    metric_code: str
    label: str
    unit: str
    cells: dict[str, ContentChangeCell]


class ContentGait(BaseModel):
    gait_type: str
    label: str
    notes: list[str]
    rows: list[ContentRow]
    compare: list[ContentCompare]
    changes: list[ContentChangeRow]


class ReportContentOut(BaseModel):
    """GET /sessions/{id}/report-content. 판본 하나의 글·표·숫자."""

    session_id: uuid.UUID
    edition: str
    template_version: str
    session: ContentSession
    dog: ContentDog
    previous: ContentPrevious | None
    baseline: ContentBaseline | None
    history: list[ContentHistoryItem]
    legs: list[ContentLeg]
    sentences: ContentSentences
    gaits: list[ContentGait]
