"""보고서 내용(8절 만드는 순서의 수치 표·문장까지): 입력 dict → 수치 표, 문장, 실린 숫자 목록, 검사에 넘길 글.

PDF를 만드는 generate.render와 보고서 내용 API(15.7의 62번, services/report_content.py)가 같이 쓴다. 두 곳이 같은
함수로 만들기 때문에 화면 인쇄용 내용과 PDF의 글·숫자가 어긋나지 않는다. HTML·차트·PDF는 여기서 만들지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.report.inputs import ReportInput, parse_input
from app.report.numbers import NOT_COMPARABLE_LABEL, PAIR_LIMBS, GaitTable, ListedNumber, build_tables
from app.report.sentences import Sentences, compose

# 다리 쌍 요약이 보는 수치(쌍 → 수치 코드, 이 순서). 대칭 점수(12.3, services/symmetry.SCORE_PAIRS)와 같은 수치다
LEG_CODES: dict[str, tuple[str, ...]] = {
    "FORE": ("rom_elbow",),
    "HIND": ("rom_stifle", "rom_hip", "stride_length", "stance_ratio"),
}
# 보행 유형 하나만 본다. 이 순서로, 대상 수치를 비교할 수 있는 첫 유형이다(12.3 대칭 점수와 같은 순서)
LEG_GAITS = ("TROT", "WALK", "OTHER")
# 차이 단계: 대칭 지수(%)가 5 미만, 10 미만, 그 이상(화면의 몸 그림 색과 같은 경계, 박규원 11-10)
LEVEL_SIMILAR, LEVEL_SLIGHT, LEVEL_LARGE = "SIMILAR", "SLIGHT", "LARGE"
LEVEL_BOUNDS = (5.0, 10.0)


def difference_level(index: float) -> str:
    """대칭 지수(또는 100 − 대칭 점수) → 차이 단계. 화면에 찍히는 값(소수 첫째 자리)으로 가른다."""
    if index < LEVEL_BOUNDS[0]:
        return LEVEL_SIMILAR
    return LEVEL_SLIGHT if index < LEVEL_BOUNDS[1] else LEVEL_LARGE


@dataclass(frozen=True)
class LegSummary:
    """다리 한 쌍(앞·뒤)에서 좌우 차이가 가장 큰 수치. weak_limb는 값이 작은 쪽 다리이고 단계가 SIMILAR면 None이다."""

    pair: str
    gait_type: str
    metric_code: str
    label: str
    symmetry_index: str
    symmetry_value: float
    weak_limb: str | None
    level: str


def leg_summaries(tables: list[GaitTable]) -> list[LegSummary]:
    """보행 유형 하나에서 다리 쌍마다 대칭 지수가 가장 큰 수치를 고른다. 비교할 수 있는 대상 수치가 없는 쌍은 뺀다.

    값은 모두 좌우 비교 줄(GaitTable.compare)의 것이라 수치 대조(8절 7번)를 지난 숫자다. 같은 값이면 LEG_CODES의
    앞 수치를 고른다.
    """
    by_gait = {table.gait_type: table for table in tables}
    for gait in LEG_GAITS:
        table = by_gait.get(gait)
        if table is None:
            continue
        found: list[LegSummary] = []
        for pair, codes in LEG_CODES.items():
            lines = [
                line
                for code in codes
                for line in table.compare
                if line.pair == pair and line.code == code and line.comparable and line.symmetry_value is not None
            ]
            if not lines:
                continue
            worst = max(lines, key=lambda line: line.symmetry_value)  # 같으면 앞의 것(max는 처음 만난 최댓값을 준다)
            level = difference_level(worst.symmetry_value)
            weak = None
            if level != LEVEL_SIMILAR and worst.left_value is not None and worst.right_value is not None:
                left_limb, right_limb = PAIR_LIMBS[pair]
                weak = left_limb if worst.left_value < worst.right_value else right_limb
            found.append(
                LegSummary(
                    pair=pair,
                    gait_type=gait,
                    metric_code=worst.code,
                    label=worst.label,
                    symmetry_index=worst.symmetry_index,
                    symmetry_value=worst.symmetry_value,
                    weak_limb=weak,
                    level=level,
                )
            )
        if found:
            return found
    return []


@dataclass(frozen=True)
class ReportContent:
    """검사 전의 보고서 내용. texts는 금지 표현·용어·고정 문구 검사(checks.ensure_checked)에 넘기는 글이다."""

    inp: ReportInput
    tables: list[GaitTable]
    numbers: tuple[ListedNumber, ...]
    sentences: Sentences
    texts: dict[str, str]


def table_texts(tables: list[GaitTable]) -> dict[str, str]:
    """표에 찍히는 글(수치 이름, 측정 불가 사유, 비교 사유, 직전 회차 비교의 변화·사유)도 검사 대상이다."""
    parts: list[str] = []
    for table in tables:
        parts.append(table.label)
        for row in table.rows:
            parts.append(row.label)
            parts.extend(cell.reason for cell in row.cells.values() if cell.reason)
        for line in table.compare:
            parts.append(f"{line.pair_label} {line.label}")
            if line.reason:
                parts.append(line.reason)
        for change in table.changes:
            parts.append(change.label)
            for pair in change.cells.values():
                if pair.change_label:
                    parts.append(pair.change_label)
                if pair.note:
                    parts.append(f"{NOT_COMPARABLE_LABEL}. {pair.note}")
    return {"tables": " ".join(parts)} if parts else {}


def compose_content(data: Any) -> ReportContent:
    """입력 dict → 수치 표와 문장. 검사는 하지 않는다(부르는 쪽이 ensure_checked와 수치 대조를 한다)."""
    inp: ReportInput = parse_input(data)
    tables, numbers = build_tables(
        inp.result, inp.previous, tolerance=inp.tolerance, model_changed=inp.previous_model_changed
    )
    sentences = compose(inp, tables)
    texts = {**sentences.texts(), **table_texts(tables)}
    return ReportContent(inp=inp, tables=tables, numbers=tuple(numbers), sentences=sentences, texts=texts)
