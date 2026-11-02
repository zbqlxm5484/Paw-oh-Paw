"""보고서 모듈(명세 8절, 11.3). app과 DB를 모르고 입력 dict·파일 경로만 받는다. 기업에 그대로 넘기는 패키지다.

- TEMPLATE_VERSION: 보고서 행의 template_version(12.4)
- ReportCheckError: 8절 7번 검사(수치 대조·금지 표현·전문 용어·고정 문구)에 걸렸을 때.
  워커는 REPORT_CHECK_FAILED로 남긴다
PDF 만들기는 작업 단위 9에서 더한다.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

TEMPLATE_VERSION = "0.1"


class ReportCheckError(Exception):
    """검사에 걸려 PDF를 내보내지 않는다(PR-F08-11·12). findings는 checks.Finding 목록이다.

    메시지에는 종류와 용어만 담고 보고서 문장은 담지 않는다(11.8 로그 규칙).
    """

    def __init__(self, findings: Iterable[Any]) -> None:
        self.findings = tuple(findings)
        kinds: dict[str, list[str]] = {}
        for finding in self.findings:
            kinds.setdefault(str(getattr(finding, "kind", "?")), []).append(str(getattr(finding, "term", "?")))
        summary = "; ".join(f"{kind} {len(terms)}: {', '.join(dict.fromkeys(terms))}" for kind, terms in kinds.items())
        super().__init__(f"보고서 검사 실패: {summary or '내용 없음'}")
