"""보고서 만들기(8절 만드는 순서 전체). 자식 프로세스는 generate_report 하나만 부른다(12.4).

입력 JSON 파일 → 수치 표·문장(content.compose_content) → 차트(charts) → HTML(html) → 검사(checks) → PDF(pdf).
출력은 PDF 파일과 ReportResult(실린 숫자 목록·생성 시간·템플릿 판). 검사 실패는 ReportCheckError, 그 밖은 ReportError다.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.report import TEMPLATE_VERSION, ReportError
from app.report.charts import rom_chart
from app.report.checks import ensure_checked
from app.report.content import compose_content
from app.report.html import render_html
from app.report.numbers import GaitTable, ListedNumber
from app.report.pdf import html_to_pdf
from app.report.sentences import Sentences


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


def render(data: Any) -> Rendered:
    """입력 dict → HTML과 검사용 문장. 검사는 하지 않는다(generate_report가 한다)."""
    content = compose_content(data)
    inp, tables, sentences = content.inp, content.tables, content.sentences
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
    return Rendered(html=html, texts=content.texts, numbers=content.numbers, tables=tables, sentences=sentences)


def generate_report(
    input_path: Path,
    output_path: Path,
    *,
    keep_html: bool = False,
    to_pdf: Callable[[str, Path], int] | None = None,
) -> ReportResult:
    """입력 JSON 파일 → output_path에 PDF. keep_html이면 같은 자리에 .html도 남긴다(미리보기용).

    to_pdf는 PDF 단계를 바꿔 끼우는 자리다(8절 6번). 워커가 화면 인쇄(clients/renderer.screen_pdf)를 넣는다.
    글 검사는 그 앞에서 하므로 어느 길로 만들든 검사에 걸린 보고서는 PDF가 되지 않는다.
    """
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
    size = (to_pdf or html_to_pdf)(rendered.html, output_path)
    return ReportResult(
        pdf_bytes=size,
        generation_ms=int((time.perf_counter() - started) * 1000),
        template_version=TEMPLATE_VERSION,
        numbers=rendered.numbers,
        edition=edition,
    )
