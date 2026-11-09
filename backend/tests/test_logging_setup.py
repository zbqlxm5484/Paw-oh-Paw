"""로그 설정(11.8): 바깥 라이브러리의 INFO가 서버·워커 로그에 섞이지 않는다(S15P31A404-273)."""

from __future__ import annotations

import logging

import pytest

from app.main import QUIET_LOGGERS, configure_logging


@pytest.mark.parametrize("name", ["httpx", "weasyprint", "weasyprint.progress", "fontTools", "fontTools.subset"])
def test_outside_libraries_log_warnings_only(name: str) -> None:
    """보고서 PDF를 만들 때 fontTools가 INFO로 찍는 글리프 목록은 보고서에 쓰인 글자를 드러낸다."""
    configure_logging("INFO")
    logger = logging.getLogger(name)
    assert logger.getEffectiveLevel() == logging.WARNING
    assert not logger.isEnabledFor(logging.INFO) and logger.isEnabledFor(logging.WARNING)


def test_the_app_keeps_logging_at_the_configured_level() -> None:
    configure_logging("INFO")
    assert logging.getLogger("app.worker").isEnabledFor(logging.INFO)
    assert set(QUIET_LOGGERS) == {"httpx", "weasyprint", "fontTools"}
