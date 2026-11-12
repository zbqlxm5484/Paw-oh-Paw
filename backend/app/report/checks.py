"""보고서 검사(명세 8절 만드는 순서 7, PR-F08-11·12, KPI-30·31): 금지 표현, 보호자용 전문 용어, 고정 문구.

PDF로 바꾸기 전에 보고서에 실릴 문장을 모두 모아 검사한다. 하나라도 걸리면 ReportCheckError이고 워커는
REPORT_CHECK_FAILED로 남긴다(12.4). 수치 대조(같은 7번의 첫 항목)는 numbers.py가 실린 숫자 목록을 만들고 verify.py가
기준값과 맞춘다(기준값은 부르는 쪽이 준다, 196).

- 금지 표현: terms.yaml의 forbidden. 판본에 관계없이 0건이어야 한다.
- 전문 용어: 보호자용(OWNER)에 jargon 용어가 나오면 같은 문서 안에 그 explanation 문구가 한 번은 있어야 한다.
  용어 바로 뒤가 아니어도 되므로 맨 끝 용어 설명 칸으로도 된다. 용어는 공백을 빼고 찾는다("가동범위"도 "가동 범위"다).
  수의사용(VET)은 검사하지 않는다.
- 고정 문구: 모든 판본에 "보행 평가 보조 자료"(DISCLAIMER)가 있어야 한다(17.4 BE-15).

목록 파일은 패키지 안에 둔다(11.3: report/는 app과 DB를 모르고 기업에 그대로 넘긴다). 김지윤의 목록을 받으면 그 파일만
바꾼다. Spring에 빗대면 Bean Validation의 Validator 하나이고, 규칙 표는 classpath 리소스다.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.report import ReportCheckError

DISCLAIMER = "보행 평가 보조 자료"
RULES_PATH = Path(__file__).resolve().parent / "terms.yaml"
EDITIONS = ("OWNER", "VET")
# 문제 난 자리를 보여 주는 길이. 문장 전체를 로그에 남기지 않기 위해서다
EXCERPT_CHARS = 40

KIND_FORBIDDEN = "FORBIDDEN"
KIND_JARGON = "JARGON"
KIND_DISCLAIMER = "DISCLAIMER"


@dataclass(frozen=True)
class ForbiddenTerm:
    term: str
    pattern: re.Pattern[str]
    reason: str


@dataclass(frozen=True)
class Jargon:
    term: str
    explanation: str


@dataclass(frozen=True)
class TermRules:
    version: str
    forbidden: tuple[ForbiddenTerm, ...]
    jargon: tuple[Jargon, ...]


@dataclass(frozen=True)
class Finding:
    """걸린 곳 하나. where는 문장 묶음 이름(예: summary), excerpt는 그 자리 앞뒤 몇 글자다."""

    kind: str
    term: str
    where: str
    excerpt: str

    def __str__(self) -> str:
        return f"{self.kind} {self.term!r} in {self.where}: …{self.excerpt}…"


def _text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"terms.yaml: {field}가 비어 있거나 문자열이 아닙니다")
    return value.strip()


def _load_rules(path: Path) -> TermRules:
    try:
        with path.open(encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"검사 목록 파일을 읽을 수 없습니다: {path.name}") from error
    if not isinstance(data, dict):
        raise ValueError("terms.yaml: 최상위가 객체가 아닙니다")
    version = _text(data.get("version"), field="version")
    forbidden: list[ForbiddenTerm] = []
    for position, item in enumerate(data.get("forbidden") or [], start=1):
        if not isinstance(item, dict):
            raise ValueError(f"terms.yaml: forbidden[{position}]가 객체가 아닙니다")
        term = _text(item.get("term"), field=f"forbidden[{position}].term")
        raw_pattern = item.get("pattern")
        source = (
            _text(raw_pattern, field=f"forbidden[{position}].pattern") if raw_pattern is not None else re.escape(term)
        )
        try:
            pattern = re.compile(source, re.IGNORECASE)
        except re.error as error:
            raise ValueError(f"terms.yaml: forbidden[{position}].pattern이 정규식이 아닙니다") from error
        forbidden.append(ForbiddenTerm(term, pattern, _text(item.get("reason"), field=f"forbidden[{position}].reason")))
    jargon: list[Jargon] = []
    for position, item in enumerate(data.get("jargon") or [], start=1):
        if not isinstance(item, dict):
            raise ValueError(f"terms.yaml: jargon[{position}]가 객체가 아닙니다")
        jargon.append(
            Jargon(
                _text(item.get("term"), field=f"jargon[{position}].term"),
                _text(item.get("explanation"), field=f"jargon[{position}].explanation"),
            )
        )
    return TermRules(version, tuple(forbidden), tuple(jargon))


@lru_cache(maxsize=4)
def load_rules(path: Path | None = None) -> TermRules:
    """검사 목록. 바뀌지 않는 파일이라 한 번 읽어 둔다(11.3). 형식이 틀리면 ValueError."""
    return _load_rules(path or RULES_PATH)


def normalize(text: str) -> str:
    """줄바꿈·연속 공백을 공백 하나로. 템플릿 들여쓰기 때문에 표현이 갈라져 보이지 않게 한다."""
    return " ".join(text.split())


def _term_pattern(term: str) -> re.Pattern[str]:
    """전문 용어를 찾는 정규식. 글자 사이의 공백은 있어도 없어도 된다."""
    return re.compile(r"\s*".join(re.escape(letter) for letter in "".join(term.split())))


def contains_term(text: str, term: str) -> bool:
    """글에 전문 용어가 있는지. 공백을 빼고 비교한다."""
    return _term_pattern(term).search(text) is not None


def _excerpt(text: str, start: int, end: int) -> str:
    half = max((EXCERPT_CHARS - (end - start)) // 2, 0)
    return text[max(start - half, 0) : end + half]


def find_forbidden(texts: Mapping[str, str], rules: TermRules) -> list[Finding]:
    """금지 표현. 같은 표현이 여러 번 나와도 묶음마다 처음 한 번만 적는다."""
    findings: list[Finding] = []
    for where, raw in texts.items():
        text = normalize(raw)
        for rule in rules.forbidden:
            match = rule.pattern.search(text)
            if match:
                findings.append(Finding(KIND_FORBIDDEN, rule.term, where, _excerpt(text, match.start(), match.end())))
    return findings


def find_unexplained_jargon(texts: Mapping[str, str], rules: TermRules) -> list[Finding]:
    """보호자용 전문 용어. 용어가 있는데 설명 문구가 문서 어디에도 없으면 걸린다."""
    normalized = {where: normalize(raw) for where, raw in texts.items()}
    whole = " ".join(normalized.values())
    findings: list[Finding] = []
    for rule in rules.jargon:
        if normalize(rule.explanation) in whole:
            continue
        pattern = _term_pattern(rule.term)
        for where, text in normalized.items():
            match = pattern.search(text)
            if match:
                findings.append(Finding(KIND_JARGON, rule.term, where, _excerpt(text, match.start(), match.end())))
                break
    return findings


def find_missing_disclaimer(texts: Mapping[str, str]) -> list[Finding]:
    whole = " ".join(normalize(raw) for raw in texts.values())
    if DISCLAIMER in whole:
        return []
    return [Finding(KIND_DISCLAIMER, DISCLAIMER, "*", "")]


def check_texts(texts: Mapping[str, str], *, edition: str, rules: TermRules | None = None) -> list[Finding]:
    """세 검사를 모두 돌려 걸린 곳을 돌려준다(비어 있으면 통과). edition은 OWNER·VET."""
    if edition not in EDITIONS:
        raise ValueError(f"판본은 {EDITIONS} 중 하나여야 합니다: {edition!r}")
    rules = rules or load_rules()
    findings = find_forbidden(texts, rules)
    if edition == "OWNER":
        findings += find_unexplained_jargon(texts, rules)
    findings += find_missing_disclaimer(texts)
    return findings


def ensure_checked(texts: Mapping[str, str], *, edition: str, rules: TermRules | None = None) -> None:
    """걸린 곳이 하나라도 있으면 ReportCheckError(findings 포함). 워커는 REPORT_CHECK_FAILED로 남긴다."""
    findings = check_texts(texts, edition=edition, rules=rules)
    if findings:
        raise ReportCheckError(findings)


def summarize(findings: Iterable[Finding]) -> str:
    """로그용 한 줄. 종류별 개수와 용어만 적고 문장은 적지 않는다(11.8)."""
    counts: dict[str, list[str]] = {}
    for finding in findings:
        counts.setdefault(finding.kind, []).append(finding.term)
    return "; ".join(f"{kind} {len(terms)}: {', '.join(dict.fromkeys(terms))}" for kind, terms in counts.items())
