"""보고서 내용(8절 만드는 순서의 수치 표·문장까지): 입력 dict → 수치 표, 문장, 실린 숫자 목록, 검사에 넘길 글.

PDF를 만드는 generate.render와 보고서 내용 API(15.7의 62번, services/report_content.py)가 같이 쓴다. 두 곳이 같은
함수로 만들기 때문에 화면 인쇄용 내용과 PDF의 글·숫자가 어긋나지 않는다. HTML·차트·PDF는 여기서 만들지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.report.inputs import ReportInput, parse_input
from app.report.numbers import NOT_COMPARABLE_LABEL, GaitTable, ListedNumber, build_tables
from app.report.sentences import Sentences, compose


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
