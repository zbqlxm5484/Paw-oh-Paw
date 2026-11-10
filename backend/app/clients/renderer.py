"""화면 인쇄 렌더러 클라이언트(8절 6번, 12.4 "보고서 한 건"). 워커의 보고서 자식 프로세스가 쓴다.

렌더러는 headless Chromium을 HTTP로 감싼 Gotenberg다. 웹의 보고서 인쇄 화면 주소를 넘기면 그 화면을 열어, 화면이
다 그렸다고 알릴 때(window.__REPORT_READY__)까지 기다린 뒤 PDF로 돌려준다.

- 인쇄 화면 주소에는 인쇄 토큰(11.6)이 들어 있다. 그래서 주소는 로그에 남기지 않는다(11.8).
- 렌더러가 답하지 않거나 PDF가 아닌 것을 주면 RendererError다. screen_pdf는 그때 기본 템플릿(WeasyPrint)으로 만든다.
  글 검사와 수치 대조는 어느 길로 만들든 그 앞뒤에서 똑같이 한다(generate_report, 워커의 _verify_and_attach).

Spring에 빗대면 외부 PDF 서비스를 부르는 RestClient와, 실패하면 로컬 구현으로 넘어가는 fallback이다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

CONVERT_PATH = "/forms/chromium/convert/url"
# 인쇄 화면이 데이터를 다 그린 뒤 켜는 값(웹 pages/ReportPrint.tsx). 이 식이 참이 될 때까지 렌더러가 기다린다
READY_EXPRESSION = "window.__REPORT_READY__ === true"
PDF_MAGIC = b"%PDF"


class RendererError(Exception):
    """렌더러가 PDF를 주지 못했다. 메시지에 인쇄 화면 주소를 넣지 않는다(토큰이 들어 있다)."""


@dataclass(frozen=True)
class ScreenPrint:
    """자식 프로세스에 넘기는 화면 인쇄 한 건. page_url은 인쇄 토큰이 붙은 인쇄 화면 주소다."""

    renderer_url: str
    page_url: str
    timeout_sec: float


def print_page(job: ScreenPrint, output: Path, *, transport: httpx.BaseTransport | None = None) -> int:
    """인쇄 화면을 PDF로 받아 output에 쓰고 크기를 돌려준다. transport는 테스트가 가짜 서버를 끼우는 자리다."""
    fields = {
        "url": job.page_url,
        "waitForExpression": READY_EXPRESSION,
        "preferCssPageSize": "true",  # 쪽 크기·여백은 화면의 @page를 따른다
        "printBackground": "true",
    }
    try:
        with httpx.Client(timeout=job.timeout_sec, transport=transport) as client:
            response = client.post(
                job.renderer_url.rstrip("/") + CONVERT_PATH,
                files={name: (None, value) for name, value in fields.items()},  # 파일이 없어도 multipart로 보낸다
            )
    except httpx.HTTPError as error:  # 연결 실패, 시간 초과
        raise RendererError(f"renderer unreachable: {type(error).__name__}") from None
    if response.status_code != 200:
        raise RendererError(f"renderer answered {response.status_code}")
    body = response.content
    if not body.startswith(PDF_MAGIC):
        raise RendererError("renderer did not return a PDF")
    Path(output).write_bytes(body)
    return len(body)


def screen_pdf(job: ScreenPrint, html: str, output: Path) -> int:
    """generate_report의 PDF 단계 자리에 끼우는 함수. 화면 인쇄가 안 되면 같은 내용의 기본 템플릿으로 만든다."""
    try:
        return print_page(job, output)
    except RendererError as error:
        logger.warning("screen print failed; using the built-in template instead: %s", error)
    from app.report.pdf import html_to_pdf

    return html_to_pdf(html, output)
