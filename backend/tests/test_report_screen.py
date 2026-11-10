"""보고서 PDF를 웹 인쇄 화면으로 만들기(명세 8절 6번, 12.4, S15P31A404-276).

렌더러(Gotenberg)는 가짜 HTTP 서버로 바꿔 끼운다. 보는 것: 렌더러에 보내는 요청, 렌더러가 안 될 때 기본 템플릿으로
넘어가는 것, 주소(인쇄 토큰)가 로그에 남지 않는 것, 워커가 그 회차의 토큰을 붙인 주소를 자식에 넘기는 것.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy.orm import Session

from app.clients import renderer
from app.clients.renderer import RendererError, ScreenPrint, print_page, screen_pdf
from app.core.security import decode_print_token
from app.report import ReportCheckError, samples
from app.report import generate as generate_module
from app.report.generate import generate_report
from app.storage.base import get_storage
from app.worker.report import ReportGenerator
from tests.report_fixtures import FakeExecutor
from tests.test_report_worker import _done_session, _reports, _run, _settings, fake_generate

TOKEN = "print-token-value"
JOB = ScreenPrint(
    renderer_url="http://renderer.test:3000/",
    page_url=f"http://web.test/web/print/reports/abc?edition=OWNER&token={TOKEN}",
    timeout_sec=5,
)
PDF = b"%PDF-1.7 screen"


def _transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


# ---- 렌더러 요청 ----


def test_print_page_posts_the_page_address_and_writes_the_pdf(tmp_path: Path) -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["type"] = request.headers["content-type"]
        seen["body"] = request.content.decode("utf-8")
        return httpx.Response(200, content=PDF)

    output = tmp_path / "report.pdf"
    size = print_page(JOB, output, transport=_transport(handler))

    assert seen["url"] == "http://renderer.test:3000/forms/chromium/convert/url"
    assert seen["type"].startswith("multipart/form-data")
    for value in (JOB.page_url, "window.__REPORT_READY__ === true", "preferCssPageSize", "printBackground"):
        assert value in seen["body"]
    assert output.read_bytes() == PDF and size == len(PDF)


@pytest.mark.parametrize(
    "response",
    [httpx.Response(503, text="timeout"), httpx.Response(200, text="<html>오류</html>"), httpx.ConnectError("refused")],
)
def test_renderer_failures_raise_without_the_address(tmp_path: Path, response: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(response, Exception):
            raise response
        return response

    output = tmp_path / "report.pdf"
    with pytest.raises(RendererError) as caught:
        print_page(JOB, output, transport=_transport(handler))
    assert TOKEN not in str(caught.value) and "web.test" not in str(caught.value)
    assert not output.exists()


# ---- 안 되면 기본 템플릿 ----


def test_screen_pdf_falls_back_to_the_built_in_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def refuse(job: ScreenPrint, output: Path, **kwargs: Any) -> int:
        raise RendererError("renderer answered 503")

    def built_in(html: str, output: Path) -> int:
        Path(output).write_bytes(b"%PDF-built-in " + html.encode("utf-8"))
        return 99

    monkeypatch.setattr(renderer, "print_page", refuse)
    monkeypatch.setattr("app.report.pdf.html_to_pdf", built_in)
    output = tmp_path / "report.pdf"
    with caplog.at_level(logging.WARNING, logger="app.clients.renderer"):
        size = screen_pdf(JOB, "<p>본문</p>", output)

    assert size == 99 and output.read_bytes().startswith(b"%PDF-built-in")
    assert "screen print failed" in caplog.text
    assert TOKEN not in caplog.text and "web.test" not in caplog.text  # 주소(토큰)는 로그에 남기지 않는다(11.8)


def test_screen_pdf_uses_the_renderer_when_it_answers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def answer(job: ScreenPrint, output: Path, **kwargs: Any) -> int:
        Path(output).write_bytes(PDF)
        return len(PDF)

    def built_in(html: str, output: Path) -> int:
        raise AssertionError("기본 템플릿을 부르면 안 된다")

    monkeypatch.setattr(renderer, "print_page", answer)
    monkeypatch.setattr("app.report.pdf.html_to_pdf", built_in)
    output = tmp_path / "report.pdf"
    assert screen_pdf(JOB, "<p>본문</p>", output) == len(PDF)
    assert output.read_bytes() == PDF


# ---- generate_report의 PDF 단계 자리 ----


def _input_file(tmp_path: Path) -> Path:
    path = tmp_path / "input.json"
    path.write_text(json.dumps(samples.sample_input("follow_up", "OWNER"), ensure_ascii=False), encoding="utf-8")
    return path


def test_generate_report_hands_the_pdf_step_to_to_pdf(tmp_path: Path) -> None:
    called: dict[str, Any] = {}

    def to_pdf(html: str, output: Path) -> int:
        called["html"] = html
        Path(output).write_bytes(PDF)
        return len(PDF)

    output = tmp_path / "report.pdf"
    result = generate_report(_input_file(tmp_path), output, to_pdf=to_pdf)

    assert "<html" in called["html"] and output.read_bytes() == PDF
    assert result.pdf_bytes == len(PDF) and result.numbers  # 실린 숫자 목록은 그대로 돌려준다(워커가 대조한다)


def test_text_check_runs_before_the_pdf_step(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """검사에 걸린 보고서는 화면 인쇄로도 PDF가 되지 않는다."""

    def refuse(texts: Any, *, edition: str, rules: Any = None) -> None:
        raise ReportCheckError("forbidden=1")

    def to_pdf(html: str, output: Path) -> int:
        raise AssertionError("검사에 걸렸는데 PDF 단계를 불렀다")

    monkeypatch.setattr(generate_module, "ensure_checked", refuse)
    with pytest.raises(ReportCheckError):
        generate_report(_input_file(tmp_path), tmp_path / "report.pdf", to_pdf=to_pdf)


# ---- 워커 ----


def test_worker_passes_a_page_address_with_the_print_token_of_that_session(
    db: Session, dog, staff, tmp_path: Path
) -> None:
    session = _done_session(db, dog, staff)
    settings = _settings(
        REPORT_RENDERER_URL="http://renderer.test:3000",
        REPORT_PRINT_URL="http://web.test/web/",
        UPLOAD_TMP_DIR=str(tmp_path),
    )
    executor = FakeExecutor()
    captured: list[dict[str, Any]] = []

    def generate(input_path: Path, output: Path, **kwargs: Any):
        captured.append(kwargs)
        return fake_generate(input_path, output)

    reporter = ReportGenerator(settings, get_storage(), executor_factory=lambda: executor, generate=generate)
    for _ in range(3):
        _run(db, reporter, settings)

    assert {row.status for row in _reports(db, session).values()} == {"DONE"}
    editions = []
    for kwargs in captured:
        to_pdf = kwargs["to_pdf"]
        assert to_pdf.func is screen_pdf
        (job,) = to_pdf.args
        assert job.renderer_url == "http://renderer.test:3000"
        assert job.timeout_sec == settings.REPORT_RENDER_TIMEOUT_SEC
        head, _, token = job.page_url.partition("&token=")
        prefix = f"http://web.test/web/print/reports/{session.id}?edition="
        assert head.startswith(prefix)
        editions.append(head.removeprefix(prefix))
        claims = decode_print_token(token)
        assert (claims.session_id, claims.institution_id) == (session.id, dog.institution_id)
    assert editions == ["OWNER", "VET"]


def test_worker_uses_the_built_in_template_without_the_settings(db: Session, dog, staff, tmp_path: Path) -> None:
    _done_session(db, dog, staff)
    settings = _settings(UPLOAD_TMP_DIR=str(tmp_path))
    executor = FakeExecutor()
    reporter = ReportGenerator(settings, get_storage(), executor_factory=lambda: executor, generate=fake_generate)
    _run(db, reporter, settings)

    assert [kwargs for _, _, kwargs in executor.calls] == [{}]


@pytest.mark.parametrize(
    "overrides",
    [{"REPORT_RENDERER_URL": "http://renderer.test:3000"}, {"REPORT_PRINT_URL": "http://web.test/web"}],
)
def test_only_one_of_the_two_addresses_stops_the_worker(overrides: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        ReportGenerator(_settings(**overrides), get_storage())
