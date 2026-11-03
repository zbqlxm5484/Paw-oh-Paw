"""보고서 모듈(명세 8절, 11.3). app과 DB를 모르고 입력 dict·파일 경로만 받는다. 기업에 그대로 넘기는 패키지다.

- TEMPLATE_VERSION: 보고서 행의 template_version(12.4)
- ReportError: 보고서를 만들지 못함(REPORT_FAILED). ReportInputError는 입력으로는 만들 수 없는 경우(8절 1번)
- ReportCheckError: 8절 7번 검사(수치 대조·금지 표현·전문 용어·고정 문구)에 걸렸을 때(REPORT_CHECK_FAILED)
만드는 흐름은 generate.py(입력 → 수치 정리 → 문장 → 차트 → HTML → 검사 → PDF). 자식 프로세스는 그것만 부른다.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

TEMPLATE_VERSION = "0.4"


class ReportError(Exception):
    """보고서를 만들지 못했다. 워커는 REPORT_FAILED로 남긴다."""


class ReportInputError(ReportError):
    """입력으로는 보고서를 만들 수 없다(8절 1번 "만들 수 없으면 사유를 낸다"). reason은 짧은 영문 코드다."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        super().__init__(f"{reason}: {detail}" if detail else reason)

    def __reduce__(self) -> tuple[Any, tuple[Any, ...]]:
        return (ReportInputError, (self.reason, ""))


class ReportCheckError(ReportError):
    """검사에 걸려 PDF를 내보내지 않는다(PR-F08-11·12). findings는 checks.Finding 목록이다.

    메시지에는 종류와 용어만 담고 보고서 문장은 담지 않는다(11.8 로그 규칙). 자식 프로세스에서 부모로 건너오므로
    pickle이 되게 __reduce__를 둔다.
    """

    def __init__(self, findings: Iterable[Any]) -> None:
        self.findings = tuple(findings)
        kinds: dict[str, list[str]] = {}
        for finding in self.findings:
            kinds.setdefault(str(getattr(finding, "kind", "?")), []).append(str(getattr(finding, "term", "?")))
        summary = "; ".join(f"{kind} {len(terms)}: {', '.join(dict.fromkeys(terms))}" for kind, terms in kinds.items())
        super().__init__(f"보고서 검사 실패: {summary or '내용 없음'}")

    def __reduce__(self) -> tuple[Any, tuple[Any, ...]]:
        return (ReportCheckError, (self.findings,))
