"""보고서 검사(8절 7번, S15P31A404-194): 금지 표현·보호자용 전문 용어·고정 문구. DB 없이 돈다."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.report import ReportCheckError
from app.report.checks import (
    DISCLAIMER,
    KIND_DISCLAIMER,
    KIND_FORBIDDEN,
    KIND_JARGON,
    RULES_PATH,
    check_texts,
    ensure_checked,
    find_forbidden,
    find_unexplained_jargon,
    load_rules,
    normalize,
    summarize,
)

OK_OWNER = {
    "title": "제니 보행 평가",
    "summary": "오른쪽 뒷다리의 가동 범위(관절이 움직인 각도의 폭)가 왼쪽보다 4.2° 작습니다.",
    "footer": f"{DISCLAIMER}이며 진단을 대신하지 않습니다.",
}


def _rules(tmp_path: Path, text: str):
    path = tmp_path / "terms.yaml"
    path.write_text(text, encoding="utf-8")
    return load_rules(path)


# ---- 목록 파일 ----


def test_shipped_rules_load_and_have_entries() -> None:
    rules = load_rules()
    assert rules.version and rules.forbidden and rules.jargon
    assert RULES_PATH.name == "terms.yaml"


def test_shipped_rules_do_not_flag_the_disclaimer_sentence() -> None:
    # "진단을 대신하지 않습니다"는 금지 표현(진단합니다 등)에 걸리면 안 된다
    assert find_forbidden({"footer": OK_OWNER["footer"]}, load_rules()) == []


@pytest.mark.parametrize(
    "text",
    [
        "- just a list",
        "version: ''\nforbidden: []\n",
        "version: '1'\nforbidden:\n  - term: 확진\n",  # reason 없음
        "version: '1'\nforbidden:\n  - term: a\n    pattern: '('\n    reason: r\n",  # 정규식 오류
        "version: '1'\njargon:\n  - term: 입각기\n",  # explanation 없음
    ],
)
def test_bad_rule_files_are_rejected(tmp_path: Path, text: str) -> None:
    with pytest.raises(ValueError):
        _rules(tmp_path, text)


def test_missing_rule_file_is_a_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_rules(tmp_path / "none.yaml")


# ---- 금지 표현 ----


def test_forbidden_term_is_found_with_inflection_and_case(tmp_path: Path) -> None:
    rules = _rules(
        tmp_path,
        "version: '1'\nforbidden:\n  - term: 진단합니다\n    pattern: 진단(합니다|됩니다)\n    reason: r\n"
        "  - term: ROM OK\n    reason: r\n",
    )
    findings = find_forbidden({"body": "관절염으로 진단됩니다. rom ok"}, rules)
    assert [(f.kind, f.term, f.where) for f in findings] == [
        (KIND_FORBIDDEN, "진단합니다", "body"),
        (KIND_FORBIDDEN, "ROM OK", "body"),
    ]
    assert "진단됩니다" in findings[0].excerpt and "\n" not in findings[0].excerpt


def test_forbidden_is_reported_once_per_block_and_across_line_breaks(tmp_path: Path) -> None:
    rules = _rules(tmp_path, "version: '1'\nforbidden:\n  - term: 반드시\n    reason: r\n")
    texts = {"a": "반드시 걷게\n하세요. 반드시.", "b": "괜찮습니다"}
    findings = find_forbidden(texts, rules)
    assert len(findings) == 1 and findings[0].where == "a"
    assert normalize("반드\n시") == "반드 시"  # 줄바꿈은 공백이 된다(단어 안을 잇지는 않는다)


# ---- 전문 용어 ----


def test_owner_jargon_needs_its_explanation_somewhere_in_the_document() -> None:
    rules = load_rules()
    bare = {"summary": "입각기 비율이 왼쪽 58%, 오른쪽 61%입니다."}
    findings = find_unexplained_jargon(bare, rules)
    assert [(f.kind, f.term, f.where) for f in findings] == [(KIND_JARGON, "입각기", "summary")]

    explained_elsewhere = {**bare, "glossary": "입각기: 발이 바닥에 닿아 있는 구간"}
    assert find_unexplained_jargon(explained_elsewhere, rules) == []
    inline = {"summary": "입각기(발이 바닥에 닿아 있는 구간) 비율이 왼쪽 58%입니다."}
    assert find_unexplained_jargon(inline, rules) == []


def test_vet_edition_skips_the_jargon_check() -> None:
    texts = {"summary": "입각기 비율 58%.", "footer": DISCLAIMER}
    assert check_texts(texts, edition="VET") == []
    assert [f.kind for f in check_texts(texts, edition="OWNER")] == [KIND_JARGON]


# ---- 고정 문구·전체 ----


def test_missing_disclaimer_is_a_finding() -> None:
    texts = {k: v for k, v in OK_OWNER.items() if k != "footer"}
    assert [f.kind for f in check_texts(texts, edition="OWNER")] == [KIND_DISCLAIMER]


def test_clean_owner_report_passes_and_ensure_checked_is_silent() -> None:
    assert check_texts(OK_OWNER, edition="OWNER") == []
    ensure_checked(OK_OWNER, edition="OWNER")


def test_ensure_checked_raises_with_findings_and_a_summary_without_sentences() -> None:
    texts = {**OK_OWNER, "summary": "관절염입니다. 반드시 수술이 필요합니다. 입각기 비율은 58%입니다."}
    with pytest.raises(ReportCheckError) as caught:
        ensure_checked(texts, edition="OWNER")
    kinds = {f.kind for f in caught.value.findings}
    assert kinds == {KIND_FORBIDDEN, KIND_JARGON}
    message = str(caught.value)
    assert "FORBIDDEN" in message and "JARGON" in message
    assert "58%" not in message  # 문장은 메시지에 담지 않는다
    assert summarize(caught.value.findings).startswith("FORBIDDEN ")


def test_unknown_edition_is_rejected() -> None:
    with pytest.raises(ValueError):
        check_texts(OK_OWNER, edition="GUEST")
