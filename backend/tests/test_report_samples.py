"""견본 보고서 경우 목록(app/report/samples.py)과 견본 스크립트(scripts/report_samples.py), D-08·KPI-29(S15P31A404-200).

경우마다 두 판본이 입력 검사·금지 표현·용어 검사를 통과하고, 실린 숫자가 입력의 결과 값과 맞는지 본다. PDF 변환 자체는
WeasyPrint가 있을 때만 한 경우로 확인한다(test_report_module의 실제 PDF 테스트와 같은 조건).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.report.checks import ensure_checked
from app.report.generate import render
from app.report.pdf import pdf_available
from app.report.samples import CASES, EDITIONS, MESSAGES, case_names, sample_input
from app.report.verify import compare_numbers, reference_from_result
from scripts import report_samples

PAIRS = [(case.name, edition) for case in CASES for edition in EDITIONS]


def _html(case: str, edition: str) -> str:
    return render(sample_input(case, edition)).html


@pytest.mark.parametrize(("case", "edition"), PAIRS)
def test_every_case_renders_passes_the_checks_and_matches_its_own_numbers(case: str, edition: str) -> None:
    data = sample_input(case, edition)
    rendered = render(data)
    ensure_checked(rendered.texts, edition=edition)  # 금지 표현 0건, 보호자용 용어 설명, 고정 문구
    verification = compare_numbers(rendered.numbers, reference_from_result(data["result"]))
    assert verification.ok, verification.mismatches
    assert "보행 평가 보조 자료" in rendered.html


def test_catalog_has_six_distinct_cases_with_titles() -> None:
    assert len(CASES) == 6 and len(set(case_names())) == 6
    assert case_names() == ["first", "follow_up", "model_changed", "unmeasurable", "one_side", "no_passes"]
    assert all(case.title and case.summary for case in CASES)
    with pytest.raises(KeyError):
        sample_input("nope")
    with pytest.raises(KeyError):
        sample_input("first", "PDF")


def test_first_session_has_no_previous_note_but_both_gaits() -> None:
    html = _html("first", "VET")
    assert "직전 회차" not in html
    assert "평보" in html and "속보" in html


def test_follow_up_shows_all_three_change_labels() -> None:
    for edition in EDITIONS:
        html = _html("follow_up", edition)
        assert ", 증가)" in html and ", 감소)" in html and ", 범위 안)" in html
        assert "2026-10-14" in html  # 직전 회차 날짜


def test_model_change_keeps_values_but_no_change_labels() -> None:
    html = _html("model_changed", "VET")
    assert "분석 방식이 달라" in html
    assert ", 증가)" not in html and ", 감소)" not in html and ", 범위 안)" not in html


def test_unmeasurable_and_one_side_cases_carry_the_reason_texts() -> None:
    html = _html("unmeasurable", "VET")
    assert MESSAGES["NOT_ENOUGH_CYCLES"] in html and MESSAGES["LOW_CONFIDENCE"] in html
    html = _html("one_side", "OWNER")
    assert MESSAGES["NO_PASS_FOR_LIMB"] in html


def test_no_passes_case_asks_to_shoot_again() -> None:
    html = _html("no_passes", "OWNER")
    assert "수치를 낼 수 있는 걸음이 없었습니다" in html


def test_reference_from_result_follows_the_worker_rules() -> None:
    result = sample_input("unmeasurable", "VET")["result"]
    reference = reference_from_result(result)
    (gait,) = result["gaits"]
    measured = [row for row in gait["metrics"] if row["value"] is not None]
    assert all(("TROT", row["metric_code"], row["limb"], "metric") in reference for row in measured)
    assert not any(
        ("TROT", row["metric_code"], row["limb"], "metric") in reference
        for row in gait["metrics"]
        if row["value"] is None
    )
    # 고관절 쌍은 오른쪽이 측정 불가 → 왼쪽 값만 기준에 있고 차이·대칭 지수는 없다
    assert ("TROT", "rom_hip", "HIND", "left") in reference
    assert ("TROT", "rom_hip", "HIND", "right") not in reference
    assert ("TROT", "rom_hip", "HIND", "diff") not in reference
    # 무릎 쌍은 양쪽이 있어 네 값이 다 있고 12.3 식과 맞는다(47.3·43.1 → 4.2, 9.29)
    assert reference[("TROT", "rom_stifle", "HIND", "diff")] == pytest.approx(4.2)
    assert reference[("TROT", "rom_stifle", "HIND", "symmetry_index")] == pytest.approx(9.29)


def test_script_html_mode_writes_every_case_and_edition(tmp_path: Path) -> None:
    assert report_samples.main([str(tmp_path), "--html"]) == 0
    assert sorted(p.name for p in tmp_path.glob("*.json")) == sorted(
        f"{c}_{e}.json" for c in case_names() for e in EDITIONS
    )
    assert len(list(tmp_path.glob("*.html"))) == 12
    data = json.loads((tmp_path / "follow_up_VET.json").read_text(encoding="utf-8"))
    assert data["settings"]["tolerance"]["rom_stifle"] == 8.0  # config/tolerance.yaml의 값이 들어간다


def test_script_case_filter_and_repeat_rule(tmp_path: Path) -> None:
    assert report_samples.main([str(tmp_path), "--html", "--case", "no_passes"]) == 0
    assert sorted(p.name for p in tmp_path.glob("*.html")) == ["no_passes_OWNER.html", "no_passes_VET.html"]
    with pytest.raises(SystemExit):
        report_samples.main([str(tmp_path), "--repeat", "0"])


@pytest.mark.skipif(not pdf_available(), reason="WeasyPrint 시스템 라이브러리(GTK/Pango)가 없다")
def test_script_makes_real_pdfs_for_one_case(tmp_path: Path, capsys) -> None:
    assert report_samples.main([str(tmp_path), "--case", "follow_up"]) == 0
    for edition in EDITIONS:
        pdf = tmp_path / f"follow_up_{edition}.pdf"
        assert pdf.read_bytes().startswith(b"%PDF")
    assert "KPI-29 20초" in capsys.readouterr().out
