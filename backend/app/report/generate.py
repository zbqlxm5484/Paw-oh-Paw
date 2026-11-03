"""보고서 만들기(8절 만드는 순서 전체). 자식 프로세스는 generate_report 하나만 부른다(12.4).

입력 JSON 파일 → parse_input → 수치 표(numbers) → 문장(sentences) → 차트(charts) → HTML(html) → 검사(checks) → PDF(pdf).
출력은 PDF 파일과 ReportResult(실린 숫자 목록·생성 시간·템플릿 판). 검사 실패는 ReportCheckError, 그 밖은 ReportError다.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.report import TEMPLATE_VERSION, ReportError
from app.report.charts import rom_chart
from app.report.checks import ensure_checked
from app.report.html import render_html
from app.report.inputs import ReportInput, parse_input
from app.report.numbers import GaitTable, ListedNumber, build_tables
from app.report.pdf import html_to_pdf
from app.report.sentences import Sentences, compose


@dataclass(frozen=True)
class Rendered:
    """PDF 직전까지 만든 것. 테스트와 미리보기(scripts/make_report.py --html)가 쓴다."""

    html: str
    texts: dict[str, str]
    numbers: tuple[ListedNumber, ...]
    tables: list[GaitTable]
    sentences: Sentences


@dataclass(frozen=True)
class ReportResult:
    pdf_bytes: int
    generation_ms: int
    template_version: str
    numbers: tuple[ListedNumber, ...]
    edition: str


def _table_texts(tables: list[GaitTable]) -> dict[str, str]:
    """표에 찍히는 글(수치 이름, 측정 불가 사유, 비교 사유)도 검사 대상이다."""
    parts: list[str] = []
    for table in tables:
        parts.append(table.label)
        for row in table.rows:
            parts.append(row.label)
            parts.extend(cell.reason for cell in row.cells.values() if cell.reason)
            parts.extend(label for cell in row.cells.values() if (label := cell.change_label))
        for line in table.compare:
            parts.append(f"{line.pair_label} {line.label}")
            if line.reason:
                parts.append(line.reason)
    return {"tables": " ".join(parts)} if parts else {}


def render(data: Any) -> Rendered:
    """입력 dict → HTML과 검사용 문장. 검사는 하지 않는다(generate_report가 한다)."""
    inp: ReportInput = parse_input(data)
    tables, numbers = build_tables(
        inp.result, inp.previous, tolerance=inp.tolerance, model_changed=inp.previous_model_changed
    )
    sentences = compose(inp, tables)
    charts = {table.gait_type: chart for table in tables if (chart := rom_chart(table))}
    html = render_html(
        edition=inp.edition,
        sentences=sentences,
        tables=tables,
        charts=charts,
        session={
            "measured_on": inp.session.measured_on,
            "model_name": inp.session.model_name,
            "model_version": inp.session.model_version,
        },
    )
    texts = {**sentences.texts(), **_table_texts(tables)}
    return Rendered(html=html, texts=texts, numbers=tuple(numbers), tables=tables, sentences=sentences)


def generate_report(input_path: Path, output_path: Path, *, keep_html: bool = False) -> ReportResult:
    """입력 JSON 파일 → output_path에 PDF. keep_html이면 같은 자리에 .html도 남긴다(미리보기용)."""
    started = time.perf_counter()
    try:
        data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ReportError(f"입력 파일을 읽을 수 없습니다: {type(error).__name__}") from error
    rendered = render(data)
    edition = str(data.get("edition"))
    ensure_checked(rendered.texts, edition=edition)
    if keep_html:
        output_path.with_suffix(".html").write_text(rendered.html, encoding="utf-8")
    size = html_to_pdf(rendered.html, output_path)
    return ReportResult(
        pdf_bytes=size,
        generation_ms=int((time.perf_counter() - started) * 1000),
        template_version=TEMPLATE_VERSION,
        numbers=rendered.numbers,
        edition=edition,
    )
