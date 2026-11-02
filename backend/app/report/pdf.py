"""PDF 변환(8절 만드는 순서 6): WeasyPrint. 한글 글꼴은 HTML의 font-family에 적힌 시스템 글꼴을 쓴다.

WeasyPrint는 시스템 라이브러리(Pango·Cairo 등. Windows는 GTK 런타임)가 있어야 import된다. 없으면 PdfUnavailableError이고
워커는 REPORT_FAILED로 남긴다. 설치 전제는 실행 가이드(PR-C-07)와 README에 적는다. 모듈을 import할 때가 아니라 PDF를
만들 때 WeasyPrint를 불러, 라이브러리가 없어도 HTML까지는 만들어 볼 수 있게 한다.
"""

from __future__ import annotations

from pathlib import Path

from app.report import ReportError


class PdfUnavailableError(ReportError):
    """WeasyPrint를 쓸 수 없다(패키지나 시스템 라이브러리 없음)."""


def _weasyprint():  # noqa: ANN202 - 타입은 weasyprint 모듈
    try:
        import weasyprint  # noqa: PLC0415 - 시스템 라이브러리가 없을 때를 대비해 늦게 부른다
    except (ImportError, OSError) as error:
        raise PdfUnavailableError(f"WeasyPrint를 쓸 수 없습니다: {type(error).__name__}") from error
    return weasyprint


def pdf_available() -> bool:
    try:
        _weasyprint()
    except PdfUnavailableError:
        return False
    return True


def html_to_pdf(html: str, output: Path) -> int:
    """HTML 문자열 → output에 PDF. 쓴 바이트 수를 돌려준다. 실패는 ReportError."""
    weasyprint = _weasyprint()
    try:
        weasyprint.HTML(string=html, base_url=str(output.parent)).write_pdf(str(output))
    except PdfUnavailableError:
        raise
    except Exception as error:  # WeasyPrint·Pango 오류는 종류가 많아 한 가지로 모은다
        raise ReportError(f"PDF 변환 실패: {type(error).__name__}") from error
    return output.stat().st_size
