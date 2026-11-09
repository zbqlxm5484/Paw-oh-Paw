"""HTML 템플릿 채우기(8절 만드는 순서 5): Jinja2, 자동 이스케이프. 템플릿은 templates/report.html.j2 하나다."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.report import TEMPLATE_VERSION
from app.report.numbers import LIMB_LABELS, LIMB_ORDER, NOT_COMPARABLE_LABEL, GaitTable
from app.report.sentences import Sentences

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_NAME = "report.html.j2"


@lru_cache(maxsize=1)
def _environment() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=select_autoescape(["html", "j2"]))


def render_html(
    *,
    edition: str,
    sentences: Sentences,
    tables: list[GaitTable],
    charts: dict[str, str],
    session: dict[str, Any],
) -> str:
    table_limbs = {
        table.gait_type: [limb for limb in LIMB_ORDER if any(limb in row.cells for row in table.rows)]
        for table in tables
    }
    return (
        _environment()
        .get_template(TEMPLATE_NAME)
        .render(
            edition=edition,
            s=sentences,
            tables=tables,
            table_limbs=table_limbs,
            limb_labels=LIMB_LABELS,
            not_comparable=NOT_COMPARABLE_LABEL,
            charts=charts,
            session=session,
            template_version=TEMPLATE_VERSION,
        )
    )
