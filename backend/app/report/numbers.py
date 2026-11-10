"""수치 정리(8절 만드는 순서 2, PR-F08-06·07·14): 회차 결과의 수치를 보행 유형별 표로, 측정 불가는 사유와 함께.

입력은 15.7 SessionResultOut dict의 gaits(수치·다리 비교)다. 값을 다시 계산하지 않고 받은 값을 그대로 싣는다.
실은 수치는 ListedNumber 목록으로도 돌려준다. 8절 7번 수치 대조(verify.py, 워커가 DB 값과 맞춘다. 196)의 재료다.
0은 측정값이 아니므로 value가 None이면 "측정 불가"와 사유를 쓴다(12.5).
직전 회차가 있으면 같은 (보행 유형, 수치, 다리)끼리 짝지어 비교 표(GaitTable.changes)를 따로 만든다(5절 비교 규칙, 272).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.report.judge import CHANGE_LABELS, NOT_COMPARABLE, NOTE_MODEL_CHANGED, judge, usable_tolerance

UNMEASURABLE = "측정 불가"
NO_VALUE = "-"
# 직전 회차 비교 표에서 한쪽 회차에 그 수치 줄이 없을 때의 사유(15.8 NO_DATA와 같은 경우)
NO_PREVIOUS_ROW = "직전 회차에 이 수치가 없습니다."
NO_CURRENT_ROW = "이번 회차에 이 수치가 없습니다."
PREVIOUS_SIDE = "직전 회차"
CURRENT_SIDE = "이번 회차"
NOT_MEASURED = "측정하지 못했습니다."
NOT_COMPARABLE_LABEL = "비교 불가"

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
# 단위의 기준은 표 칸마다 되풀이하지 않고 수치 이름에 한 번만 적는다(metric_label)
UNIT_NOTES: dict[str, str] = {"pct_body": "몸통 길이 기준", "body_per_sec": "몸통 길이/초"}
LIMB_LABELS: dict[str, str] = {
    "LF": "왼쪽 앞다리",
    "RF": "오른쪽 앞다리",
    "LH": "왼쪽 뒷다리",
    "RH": "오른쪽 뒷다리",
    "NONE": "전체",
}
LIMB_ORDER = ("LF", "RF", "LH", "RH", "NONE")
PAIR_LABELS: dict[str, str] = {"FORE": "앞다리", "HIND": "뒷다리"}
PAIR_LIMBS: dict[str, tuple[str, str]] = {"FORE": ("LF", "RF"), "HIND": ("LH", "RH")}
# OTHER 묶음에 든 유효 통과는 분석 API가 보행 유형을 아직 가르지 않은 통과다(gait null, 15.7). 평보·속보가 아닌 걸음은
# GAIT_OTHER로 빠져 수치에 들지 않으므로 '기타'가 아니다. 이름은 화면(웹·앱)과 같게 쓴다
GAIT_LABELS: dict[str, str] = {"WALK": "평보", "TROT": "속보", "PACE": "측대보", "OTHER": "보행 유형 미판별"}


@dataclass(frozen=True)
class Cell:
    value: float | None
    text: str
    reason: str | None = None  # 측정 불가 사유 문장(14절 메시지)


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
class ChangeCell:
    """직전 회차와 이번 회차의 같은 (보행 유형, 수치, 다리) 값 한 쌍(5절 비교 규칙)."""

    previous: str  # 직전 값. 그 줄이 없으면 "-", 측정 불가면 "측정 불가"
    current: str
    diff: str | None = None  # 이번 − 직전(부호를 붙인 글). 비교할 수 없거나 분석 모델이 다르면 None
    change: str | None = None  # judge의 CHANGE_LABELS 키. 기준이 없거나 통과 수가 모자라면 None
    note: str | None = None  # 비교하지 못한 사유 문장

    @property
    def change_label(self) -> str | None:
        return CHANGE_LABELS.get(self.change) if self.change else None


@dataclass(frozen=True)
class ChangeRow:
    code: str
    label: str
    unit: str
    cells: dict[str, ChangeCell] = field(default_factory=dict)  # 다리 코드 → 칸


@dataclass(frozen=True)
class CompareLine:
    pair: str
    pair_label: str
    code: str
    label: str
    left: str
    right: str
    diff: str
    diff_value: float | None  # 비교할 수 있을 때의 원래 값(오차 범위와 견준다)
    min_passes: int | None  # 왼쪽·오른쪽 중 적은 쪽의 유효 통과 수. 한쪽이라도 모르면 None
    symmetry_index: str
    comparable: bool
    reason: str | None


@dataclass(frozen=True)
class GaitTable:
    gait_type: str
    label: str
    rows: list[TableRow]
    compare: list[CompareLine]
    changes: list[ChangeRow] = field(
        default_factory=list
    )  # 직전 회차 비교. 직전 회차에 같은 보행 유형이 없으면 빈 목록

    @property
    def change_limbs(self) -> list[str]:
        return [limb for limb in LIMB_ORDER if any(limb in row.cells for row in self.changes)]

    @property
    def unmeasurable(self) -> int:
        return sum(1 for row in self.rows for cell in row.cells.values() if cell.value is None)

    @property
    def measured(self) -> int:
        return sum(1 for row in self.rows for cell in row.cells.values() if cell.value is not None)


@dataclass(frozen=True)
class ListedNumber:
    """보고서에 실린 숫자 하나(대조용). limb는 다리 또는 쌍(FORE·HIND).

    kind는 metric·left·right·diff·symmetry_index와, 직전 회차 비교 표의 previous(직전 값)·change(이번 − 직전)다.
    """

    gait_type: str
    metric_code: str
    limb: str
    kind: str
    value: float


def metric_label(code: str, unit: str = "") -> str:
    label = METRIC_LABELS.get(code, code)
    note = UNIT_NOTES.get(unit)
    return f"{label}({note})" if note else label


def gait_label(gait_type: str) -> str:
    return GAIT_LABELS.get(gait_type, gait_type)


def format_value(value: float | None, unit: str) -> str:
    """숫자와 단위. 각도·비율은 소수 1자리, 횟수는 정수, 나머지는 소수 2자리. 기준은 수치 이름에 있다."""
    if value is None:
        return UNMEASURABLE
    if unit == "deg":
        return f"{value:.1f}°"
    if unit == "pct":
        return f"{value:.1f}%"
    if unit == "count":
        return f"{value:.0f}회"
    if unit == "pct_body":
        return f"{value:.2f}%"
    if unit in UNIT_NOTES:
        return f"{value:.2f}"
    return f"{value:.2f} {unit}".rstrip()


def format_change(diff: float, unit: str) -> str:
    """이번 − 직전을 부호와 함께. 비율의 차이는 %p로 적는다."""
    sign = "+" if diff > 0 else "-" if diff < 0 else ""
    size = abs(diff)
    if unit in ("pct", "pct_body"):
        places = 1 if unit == "pct" else 2
        return f"{sign}{size:.{places}f}%p"
    return f"{sign}{format_value(size, unit)}"


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


@dataclass(frozen=True)
class _Measured:
    """수치 줄 하나에서 비교에 쓰는 것."""

    value: float | None
    n_passes: float | None
    unit: str
    reason: str | None


def _measured_rows(gait: dict[str, Any]) -> dict[tuple[str, str], _Measured]:
    """보행 유형 하나의 수치 줄 → (수치, 다리) → 값. 받은 순서를 지킨다."""
    rows: dict[tuple[str, str], _Measured] = {}
    for metric in gait.get("metrics") or []:
        value = _number(metric.get("value"))
        rows[(str(metric.get("metric_code", "")), str(metric.get("limb", "NONE")))] = _Measured(
            value=value,
            n_passes=_number(metric.get("n_passes")),
            unit=str(metric.get("unit", "")),
            reason=_reason_text(metric.get("unmeasurable_reason")) if value is None else None,
        )
    return rows


def _change_note(before: _Measured | None, now: _Measured | None) -> str:
    """비교하지 못한 사유. 줄이 없는 쪽, 직전 회차의 측정 불가, 이번 회차의 측정 불가 순서다(15.8 판정 표 1번)."""
    if before is None:
        return NO_PREVIOUS_ROW
    if now is None:
        return NO_CURRENT_ROW
    if before.value is None:
        return f"{PREVIOUS_SIDE}: {before.reason or NOT_MEASURED}"
    return f"{CURRENT_SIDE}: {now.reason or NOT_MEASURED}"


def _change_rows(
    gait_type: str,
    current: dict[tuple[str, str], _Measured],
    prior: dict[tuple[str, str], _Measured],
    tolerance: Mapping[str, float],
    model_changed: bool,
    listed: list[ListedNumber],
) -> list[ChangeRow]:
    """같은 보행 유형의 두 회차 줄 → 비교 표. 어느 한쪽에라도 있는 (수치, 다리)를 모두 낸다(15.8과 같은 합집합).

    순서는 이번 회차의 수치 순서, 그 뒤에 직전 회차에만 있는 수치다. 분석 모델이 다르면 값만 나란히 적는다.
    """
    rows: dict[str, ChangeRow] = {}
    for code, limb in dict.fromkeys([*current, *prior]):
        before, now = prior.get((code, limb)), current.get((code, limb))
        unit = now.unit if now is not None else before.unit if before is not None else ""
        before_value = before.value if before is not None else None
        now_value = now.value if now is not None else None
        allowed = usable_tolerance(
            tolerance.get(code),
            before.n_passes if before is not None else None,
            now.n_passes if now is not None else None,
        )
        verdict = judge(before_value, now_value, allowed, model_changed=model_changed)
        shown_diff = verdict.diff if verdict.note != NOTE_MODEL_CHANGED else None
        row = rows.setdefault(code, ChangeRow(code, metric_label(code, unit), unit))
        row.cells[limb] = ChangeCell(
            previous=format_value(before_value, unit) if before is not None else NO_VALUE,
            current=format_value(now_value, unit) if now is not None else NO_VALUE,
            diff=format_change(shown_diff, unit) if shown_diff is not None else None,
            change=verdict.judgement if verdict.judgement in CHANGE_LABELS else None,
            note=_change_note(before, now) if verdict.judgement == NOT_COMPARABLE else None,
        )
        if before_value is not None:
            listed.append(ListedNumber(gait_type, code, limb, "previous", before_value))
        if shown_diff is not None:
            listed.append(ListedNumber(gait_type, code, limb, "change", shown_diff))
    return list(rows.values())


def _min_passes(passes: dict[tuple[str, str], int], code: str, pair: str) -> int | None:
    counts = [passes[(code, limb)] for limb in PAIR_LIMBS.get(pair, ()) if (code, limb) in passes]
    return min(counts) if len(counts) == 2 else None


def build_tables(
    result: dict[str, Any],
    previous: dict[str, Any] | None = None,
    tolerance: Mapping[str, float] | None = None,
    model_changed: bool = False,
) -> tuple[list[GaitTable], list[ListedNumber]]:
    """gaits[] → 보행 유형별 표와 실린 숫자 목록. 수치 순서는 받은 순서(15.7이 12.3 표 순서로 준다).

    previous에 같은 보행 유형이 있으면 그 유형의 비교 표(changes)를 만든다. tolerance에 그 수치의 오차 범위가 있고
    두 회차의 n_passes가 모두 모자라지 않으면 5절 규칙의 변화(judge)를 함께 적고, model_changed면 값만 적고
    변화는 판단하지 않는다(197). 보행 유형이 다르면 비교하지 않는다(5절).
    """
    tables: list[GaitTable] = []
    listed: list[ListedNumber] = []
    prior = {str(gait.get("gait_type")): _measured_rows(gait) for gait in (previous or {}).get("gaits") or []}
    for gait in result.get("gaits") or []:
        gait_type = str(gait.get("gait_type", "OTHER"))
        rows: dict[str, TableRow] = {}
        passes: dict[tuple[str, str], int] = {}
        for metric in gait.get("metrics") or []:
            code = str(metric.get("metric_code", ""))
            limb = str(metric.get("limb", "NONE"))
            unit = str(metric.get("unit", ""))
            value = _number(metric.get("value"))
            n_passes = _number(metric.get("n_passes"))
            if n_passes is not None:
                passes[(code, limb)] = int(n_passes)
            row = rows.setdefault(code, TableRow(code, metric_label(code, unit), unit))
            row.cells[limb] = Cell(
                value=value,
                text=format_value(value, unit),
                reason=_reason_text(metric.get("unmeasurable_reason")) if value is None else None,
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
                    label=metric_label(code, unit),
                    left=format_value(left, unit),
                    right=format_value(right, unit),
                    diff=format_value(diff, unit) if comparable else NO_VALUE,
                    diff_value=diff if comparable else None,
                    min_passes=_min_passes(passes, code, pair),
                    symmetry_index=f"{symmetry:.1f}%" if comparable and symmetry is not None else NO_VALUE,
                    comparable=comparable,
                    reason=_reason_text(item.get("reason")),
                )
            )
            for kind, number in (("left", left), ("right", right), ("diff", diff), ("symmetry_index", symmetry)):
                if number is not None and (comparable or kind in ("left", "right")):
                    listed.append(ListedNumber(gait_type, code, pair, kind, number))
        changes: list[ChangeRow] = []
        if gait_type in prior:
            changes = _change_rows(
                gait_type, _measured_rows(gait), prior[gait_type], tolerance or {}, model_changed, listed
            )
        tables.append(GaitTable(gait_type, gait_label(gait_type), list(rows.values()), compare, changes))
    return tables, listed
