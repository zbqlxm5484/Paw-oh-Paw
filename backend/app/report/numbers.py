"""수치 정리(8절 만드는 순서 2, PR-F08-06·07·14): 회차 결과의 수치를 보행 유형별 표로, 측정 불가는 사유와 함께.

입력은 15.7 SessionResultOut dict의 gaits(수치·다리 비교)다. 값을 다시 계산하지 않고 받은 값을 그대로 싣는다.
실은 수치는 ListedNumber 목록으로 함께 돌려주어 8절 7번 수치 대조(numbers 대조, 196)가 원본과 맞춘다.
0은 측정값이 아니므로 value가 None이면 "측정 불가"와 사유를 쓴다(12.5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

UNMEASURABLE = "측정 불가"
NO_VALUE = "-"

# 15.7 수치 코드 → 보고서 이름. 보호자용·수의사용 같은 이름을 쓰고,
# 전문 용어는 보호자용 용어 설명(checks.jargon)이 받친다
METRIC_LABELS: dict[str, str] = {
    "rom_shoulder": "어깨 가동 범위",
    "rom_elbow": "팔꿈치 가동 범위",
    "rom_carpus": "앞발목 가동 범위",
    "rom_hip": "고관절 가동 범위",
    "rom_stifle": "무릎 가동 범위",
    "rom_tarsus": "뒷발목 가동 범위",
    "angle_median_shoulder": "어깨 각도 중앙값",
    "angle_median_elbow": "팔꿈치 각도 중앙값",
    "angle_median_carpus": "앞발목 각도 중앙값",
    "angle_median_hip": "고관절 각도 중앙값",
    "angle_median_stifle": "무릎 각도 중앙값",
    "angle_median_tarsus": "뒷발목 각도 중앙값",
    "stifle_cv": "무릎 움직임 일관성",
    "paw_lift": "발 들림 높이",
    "paw_excursion": "발 움직임 범위",
    "stride_length": "걸음 길이",
    "stance_ratio": "입각기 비율",
    "walk_speed": "보행 속도",
    "gait_cycles": "보행 주기 수",
}
UNIT_LABELS: dict[str, str] = {
    "deg": "°",
    "pct": "%",
    "pct_body": "% (몸통 길이 기준)",
    "body_per_sec": "몸통 길이/초",
    "count": "회",
}
LIMB_LABELS: dict[str, str] = {
    "LF": "왼쪽 앞다리",
    "RF": "오른쪽 앞다리",
    "LH": "왼쪽 뒷다리",
    "RH": "오른쪽 뒷다리",
    "NONE": "전체",
}
LIMB_ORDER = ("LF", "RF", "LH", "RH", "NONE")
PAIR_LABELS: dict[str, str] = {"FORE": "앞다리", "HIND": "뒷다리"}
GAIT_LABELS: dict[str, str] = {"WALK": "평보", "TROT": "속보", "PACE": "측대보", "OTHER": "기타"}


@dataclass(frozen=True)
class Cell:
    value: float | None
    text: str
    reason: str | None = None  # 측정 불가 사유 문장(14절 메시지)
    previous: str | None = None  # 직전 회차의 같은 값


@dataclass(frozen=True)
class TableRow:
    code: str
    label: str
    unit: str
    cells: dict[str, Cell] = field(default_factory=dict)  # 다리 코드 → 칸

    @property
    def limbs(self) -> list[str]:
        return [limb for limb in LIMB_ORDER if limb in self.cells]


@dataclass(frozen=True)
class CompareLine:
    pair: str
    pair_label: str
    code: str
    label: str
    left: str
    right: str
    diff: str
    symmetry_index: str
    comparable: bool
    reason: str | None


@dataclass(frozen=True)
class GaitTable:
    gait_type: str
    label: str
    rows: list[TableRow]
    compare: list[CompareLine]

    @property
    def unmeasurable(self) -> int:
        return sum(1 for row in self.rows for cell in row.cells.values() if cell.value is None)

    @property
    def measured(self) -> int:
        return sum(1 for row in self.rows for cell in row.cells.values() if cell.value is not None)


@dataclass(frozen=True)
class ListedNumber:
    """보고서에 실린 숫자 하나(대조용). kind는 metric·left·right·diff·symmetry_index, limb는 다리 또는 쌍(FORE·HIND)."""

    gait_type: str
    metric_code: str
    limb: str
    kind: str
    value: float


def metric_label(code: str) -> str:
    return METRIC_LABELS.get(code, code)


def unit_label(unit: str) -> str:
    return UNIT_LABELS.get(unit, unit)


def gait_label(gait_type: str) -> str:
    return GAIT_LABELS.get(gait_type, gait_type)


def format_value(value: float | None, unit: str) -> str:
    """숫자와 단위. 각도·비율은 소수 1자리, 횟수는 정수, 나머지는 소수 2자리."""
    if value is None:
        return UNMEASURABLE
    if unit == "deg":
        return f"{value:.1f}°"
    if unit == "pct":
        return f"{value:.1f}%"
    if unit == "count":
        return f"{value:.0f}회"
    return f"{value:.2f} {unit_label(unit)}".rstrip()


def _reason_text(raw: Any) -> str | None:
    if isinstance(raw, dict):
        text = raw.get("message") or raw.get("code")
        return str(text) if text else None
    return str(raw) if raw else None


def _number(raw: Any) -> float | None:
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _previous_values(previous: dict[str, Any] | None) -> dict[tuple[str, str, str], float | None]:
    values: dict[tuple[str, str, str], float | None] = {}
    for gait in (previous or {}).get("gaits") or []:
        for metric in gait.get("metrics") or []:
            values[(str(gait.get("gait_type")), str(metric.get("metric_code")), str(metric.get("limb")))] = _number(
                metric.get("value")
            )
    return values


def build_tables(
    result: dict[str, Any], previous: dict[str, Any] | None = None
) -> tuple[list[GaitTable], list[ListedNumber]]:
    """gaits[] → 보행 유형별 표와 실린 숫자 목록. 수치 순서는 받은 순서(15.7이 12.3 표 순서로 준다)."""
    tables: list[GaitTable] = []
    listed: list[ListedNumber] = []
    prior = _previous_values(previous)
    for gait in result.get("gaits") or []:
        gait_type = str(gait.get("gait_type", "OTHER"))
        rows: dict[str, TableRow] = {}
        for metric in gait.get("metrics") or []:
            code = str(metric.get("metric_code", ""))
            limb = str(metric.get("limb", "NONE"))
            unit = str(metric.get("unit", ""))
            value = _number(metric.get("value"))
            row = rows.setdefault(code, TableRow(code, metric_label(code), unit))
            prev = prior.get((gait_type, code, limb)) if prior else None
            row.cells[limb] = Cell(
                value=value,
                text=format_value(value, unit),
                reason=_reason_text(metric.get("unmeasurable_reason")) if value is None else None,
                previous=format_value(prev, unit) if (gait_type, code, limb) in prior else None,
            )
            if value is not None:
                listed.append(ListedNumber(gait_type, code, limb, "metric", value))
        compare: list[CompareLine] = []
        for item in gait.get("limb_compare") or []:
            code = str(item.get("metric_code", ""))
            pair = str(item.get("pair", ""))
            unit = str(item.get("unit", ""))
            left, right, diff = (_number(item.get(key)) for key in ("left", "right", "diff"))
            symmetry = _number(item.get("symmetry_index"))
            comparable = bool(item.get("comparable")) and diff is not None
            compare.append(
                CompareLine(
                    pair=pair,
                    pair_label=PAIR_LABELS.get(pair, pair),
                    code=code,
                    label=metric_label(code),
                    left=format_value(left, unit),
                    right=format_value(right, unit),
                    diff=format_value(diff, unit) if comparable else NO_VALUE,
                    symmetry_index=f"{symmetry:.1f}%" if comparable and symmetry is not None else NO_VALUE,
                    comparable=comparable,
                    reason=_reason_text(item.get("reason")),
                )
            )
            for kind, number in (("left", left), ("right", right), ("diff", diff), ("symmetry_index", symmetry)):
                if number is not None and (comparable or kind in ("left", "right")):
                    listed.append(ListedNumber(gait_type, code, pair, kind, number))
        tables.append(GaitTable(gait_type, gait_label(gait_type), list(rows.values()), compare))
    return tables, listed
