"""보고서 모듈(8절, S15P31A404-195): 입력 → 수치 표 → 문장 → HTML → 검사 → PDF. DB 없이 돈다."""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import pytest

from app.report import TEMPLATE_VERSION, ReportCheckError, ReportError, ReportInputError
from app.report import pdf as pdf_module
from app.report.checks import DISCLAIMER, check_texts
from app.report.generate import generate_report, render
from app.report.inputs import parse_input
from app.report.numbers import UNMEASURABLE, build_tables, format_value
from app.report.pdf import PdfUnavailableError, pdf_available
from tests.report_fixtures import compare, metric, sample_input, sample_result

# ---- 입력 ----


def test_parse_input_reads_every_section() -> None:
    inp = parse_input(sample_input())
    assert inp.edition == "OWNER" and inp.dog.name == "제니" and inp.dog.birth_year == 2021
    assert inp.session.measured_on == "2026-11-02" and inp.session.model_version.startswith("0.4.0")
    assert inp.previous is None and inp.tolerance == {"rom_stifle": 4.2, "rom_hip": 3.6}


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        ([], "BAD_SECTION"),
        (sample_input(edition="GUEST"), "BAD_EDITION"),
        (sample_input(dog=None), "MISSING_SECTION"),
        (sample_input(dog={"name": " "}), "MISSING_FIELD"),
        (sample_input(session={"id": "x"}), "MISSING_FIELD"),
        (sample_input(result={"gaits": "no"}), "MISSING_FIELD"),
        (sample_input(previous="x"), "BAD_SECTION"),
    ],
)
def test_input_that_cannot_make_a_report_is_rejected_with_a_reason(data: object, reason: str) -> None:
    with pytest.raises(ReportInputError) as caught:
        parse_input(data)
    assert caught.value.reason == reason


def test_optional_sections_may_be_missing() -> None:
    inp = parse_input(sample_input(dog={"name": "코코"}, settings=None))
    assert inp.dog.breed is None and inp.dog.weight_kg is None and inp.tolerance == {}


# ---- 수치 표 ----


def test_tables_group_metrics_by_limb_and_mark_unmeasurable_with_reason() -> None:
    tables, numbers = build_tables(sample_result())
    assert [t.gait_type for t in tables] == ["TROT"] and tables[0].label == "속보"
    rows = {row.code: row for row in tables[0].rows}
    assert rows["rom_hip"].limbs == ["LH", "RH"]
    assert rows["rom_hip"].cells["LH"].text == "41.9°"
    assert (
        rows["rom_hip"].cells["RH"].text == UNMEASURABLE and "NOT_ENOUGH_CYCLES" in rows["rom_hip"].cells["RH"].reason
    )
    assert rows["stance_ratio"].cells["LH"].text == "58.2%" and rows["gait_cycles"].cells["NONE"].text == "9회"
    assert rows["walk_speed"].cells["NONE"].text.startswith("2.41")
    assert tables[0].measured == 7 and tables[0].unmeasurable == 1
    # 실린 숫자: 측정값 7개 + 비교 줄(왼쪽·오른쪽·차이·대칭 지수 4 + 비교 불가 줄의 왼쪽 1)
    kinds = [(n.metric_code, n.limb, n.kind) for n in numbers]
    assert kinds.count(("rom_hip", "RH", "metric")) == 0
    assert ("rom_stifle", "HIND", "diff") in kinds and ("rom_hip", "HIND", "left") in kinds
    assert ("rom_hip", "HIND", "diff") not in kinds
    assert len(numbers) == 12


def test_compare_lines_keep_reasons_and_previous_values_go_into_cells() -> None:
    previous = sample_result(measured_on="2026-10-20")
    previous["gaits"][0]["metrics"] = [metric("rom_stifle", "LH", 45.0), metric("rom_stifle", "RH", 44.0)]
    tables, _ = build_tables(sample_result(), previous)
    line = tables[0].compare[1]
    assert not line.comparable and line.diff == "-" and "NO_DATA" in line.reason
    row = next(row for row in tables[0].rows if row.code == "rom_stifle")
    assert row.cells["LH"].previous == "45.0°" and row.cells["RH"].previous == "44.0°"
    assert next(row for row in tables[0].rows if row.code == "rom_hip").cells["LH"].previous is None


def test_format_value_never_prints_zero_for_missing() -> None:
    assert format_value(None, "deg") == UNMEASURABLE
    assert format_value(0.0, "deg") == "0.0°"  # 진짜 0은 0으로 적는다(값이 있을 때만)
    assert format_value(12.345, "pct_body") == "12.35%"
    assert format_value(2.41, "body_per_sec") == "2.41"


def test_unit_basis_is_in_the_metric_name_not_in_every_cell() -> None:
    result = sample_result()
    result["gaits"][0]["metrics"] = [
        metric("stride_length", "LF", 122.7, unit="pct_body"),
        metric("walk_speed", "NONE", 2.42, unit="body_per_sec"),
    ]
    result["gaits"][0]["limb_compare"] = [compare("FORE", "stride_length", 122.7, 120.7, unit="pct_body")]
    tables, _ = build_tables(result)
    rows = {row.code: row for row in tables[0].rows}
    assert rows["stride_length"].label == "걸음 길이(몸통 길이 기준)"
    assert rows["stride_length"].cells["LF"].text == "122.70%"
    assert rows["walk_speed"].label == "보행 속도(몸통 길이/초)" and rows["walk_speed"].cells["NONE"].text == "2.42"
    line = tables[0].compare[0]
    assert line.label == "걸음 길이(몸통 길이 기준)" and (line.left, line.diff) == ("122.70%", "2.00%")


# ---- 문장·검사 ----


@pytest.mark.parametrize("edition", ["OWNER", "VET"])
def test_sentences_pass_the_checks_for_both_editions(edition: str) -> None:
    rendered = render(sample_input(edition=edition))
    assert check_texts(rendered.texts, edition=edition) == []
    assert DISCLAIMER in rendered.sentences.disclaimer
    assert "속보 기준, 좌우 차이를 비율로 볼 때 가장 큰 항목은 뒷다리 무릎 가동 범위입니다" in rendered.texts["summary"]


def test_summary_names_the_largest_ratio_not_the_largest_absolute_difference() -> None:
    # 비교 줄은 대칭 지수 순서로 온다(15.7). 차이 값은 앞발목(2.0°)이 더 커도 비율은 어깨가 더 크다
    result = sample_result()
    result["gaits"][0]["limb_compare"] = [
        compare("FORE", "rom_shoulder", 39.9, 38.0),
        compare("FORE", "rom_carpus", 73.0, 71.0),
    ]
    summary = render(sample_input(result=result)).texts["summary"]
    assert "좌우 차이를 비율로 볼 때 가장 큰 항목은 앞다리 어깨 가동 범위입니다" in summary
    assert "차이 1.9°" in summary and "차이가 가장" not in summary


def test_summary_without_any_ratio_does_not_claim_a_largest_difference() -> None:
    result = sample_result()
    result["gaits"][0]["limb_compare"] = [compare("HIND", "rom_stifle", 0.0, 0.0)]
    summary = render(sample_input(result=result)).texts["summary"]
    assert "비율로 낼 수 있는 항목이 없습니다" in summary and "뒷다리 무릎 가동 범위" in summary
    assert "가장 큰 항목" not in summary and "덜 쓰고" not in summary


def test_owner_edition_explains_the_jargon_it_uses_and_vet_adds_symmetry() -> None:
    owner = render(sample_input(edition="OWNER"))
    terms = dict(owner.sentences.glossary)
    assert "가동 범위" in terms and "입각기" in terms and "보행 주기" in terms
    assert "대칭 지수" not in owner.texts["summary"]
    vet = render(sample_input(edition="VET"))
    assert vet.sentences.glossary == [] and "대칭 지수" in vet.texts["summary"]


def test_one_side_only_notice_and_no_numbers_are_sentences_not_failures() -> None:
    result = sample_result(notices=[{"code": "ONE_SIDE_ONLY", "message": "한쪽만 찍혀 비교할 수 없습니다."}])
    result["gaits"][0]["limb_compare"] = [compare("HIND", "rom_stifle", 47.3, None, reason="NO_DATA")]
    rendered = render(sample_input(result=result))
    assert "한쪽만 찍혀" in rendered.texts["summary"] and "가장 큰 항목" not in rendered.texts["summary"]
    empty = render(sample_input(result=sample_result(gaits=[])))
    assert "유효한 걸음이 없어" in empty.texts["gaits"] and empty.tables == []


def test_previous_session_with_another_model_version_is_not_compared() -> None:
    previous = sample_result(measured_on="2026-10-20", model_version="0.3.0/v1/deadbeef")
    rendered = render(sample_input(previous=previous))
    assert "분석 방식이 달라" in rendered.texts["previous"]


# ---- HTML ----


def test_html_has_title_tables_chart_glossary_and_footer() -> None:
    rendered = render(sample_input())
    html = rendered.html
    assert "<title>제니 보행 평가 보고서 (보호자용)</title>" in html
    assert "왼쪽 뒷다리" in html and "측정 불가" in html and "NOT_ENOUGH_CYCLES 메시지" in html
    assert 'src="data:image/png;base64,' in html
    assert "용어 설명" in html and DISCLAIMER in html and f"템플릿 {TEMPLATE_VERSION}" in html
    assert "tr { break-inside: avoid; }" in html  # 표 한 줄이 쪽 경계에서 갈라지지 않게
    assert "<script" not in html


def test_html_escapes_input_text() -> None:
    rendered = render(sample_input(dog={"name": "<b>제니</b>"}))
    assert "&lt;b&gt;제니&lt;/b&gt;" in rendered.html and "<b>제니</b>" not in rendered.html


# ---- 전체 ----


def _write_input(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_generate_report_writes_the_pdf_and_reports_time_and_numbers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_pdf(html: str, output: Path) -> int:
        output.write_bytes(b"%PDF-fake " + html[:20].encode("utf-8"))
        return output.stat().st_size

    monkeypatch.setattr("app.report.generate.html_to_pdf", fake_pdf)
    output = tmp_path / "report.pdf"
    result = generate_report(_write_input(tmp_path, sample_input()), output, keep_html=True)
    assert output.read_bytes().startswith(b"%PDF-fake") and result.pdf_bytes == output.stat().st_size
    assert result.generation_ms >= 0 and result.template_version == TEMPLATE_VERSION and result.edition == "OWNER"
    assert len(result.numbers) == 12 and (tmp_path / "report.html").is_file()


def test_forbidden_text_in_the_input_fails_the_check_before_the_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = []
    monkeypatch.setattr("app.report.generate.html_to_pdf", lambda html, output: called.append(output))
    data = sample_input(dog={"name": "확진이"})
    with pytest.raises(ReportCheckError) as caught:
        generate_report(_write_input(tmp_path, data), tmp_path / "report.pdf")
    assert called == [] and {f.kind for f in caught.value.findings} == {"FORBIDDEN"}
    copied = pickle.loads(pickle.dumps(caught.value))  # 자식 프로세스에서 건너온다
    assert isinstance(copied, ReportCheckError) and copied.findings == caught.value.findings


def test_unreadable_input_and_missing_pdf_library_are_report_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ReportError):
        generate_report(tmp_path / "none.json", tmp_path / "x.pdf")

    def unavailable(html: str, output: Path) -> int:
        raise PdfUnavailableError("없음")

    monkeypatch.setattr("app.report.generate.html_to_pdf", unavailable)
    with pytest.raises(ReportError):
        generate_report(_write_input(tmp_path, sample_input()), tmp_path / "x.pdf")
    assert isinstance(pickle.loads(pickle.dumps(ReportInputError("MISSING_FIELD", "dog.name"))), ReportInputError)


@pytest.mark.skipif(not pdf_available(), reason="WeasyPrint 시스템 라이브러리(GTK/Pango)가 없다")
def test_real_weasyprint_makes_a_pdf(tmp_path: Path) -> None:
    output = tmp_path / "report.pdf"
    result = generate_report(_write_input(tmp_path, sample_input(edition="VET")), output)
    assert output.read_bytes().startswith(b"%PDF") and result.pdf_bytes > 1000


# ---- Windows GTK 경로 ----


def test_windows_gtk_bin_is_put_into_the_dll_env_only_when_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pdf_module.sys, "platform", "win32")
    monkeypatch.delenv(pdf_module.DLL_DIRS_ENV, raising=False)
    bin_dir = tmp_path / "GTK3-Runtime Win64" / "bin"
    monkeypatch.setattr(pdf_module, "gtk_candidates", lambda: [bin_dir])
    assert pdf_module.prepare_windows_dlls() is None and pdf_module.DLL_DIRS_ENV not in pdf_module.os.environ

    bin_dir.mkdir(parents=True)
    (bin_dir / pdf_module.GTK_MARKER_DLL).write_bytes(b"")
    assert pdf_module.prepare_windows_dlls() == bin_dir
    assert pdf_module.os.environ[pdf_module.DLL_DIRS_ENV] == str(bin_dir)
    # 이미 있으면 건드리지 않는다
    monkeypatch.setenv(pdf_module.DLL_DIRS_ENV, "elsewhere")
    assert pdf_module.prepare_windows_dlls() is None and pdf_module.os.environ[pdf_module.DLL_DIRS_ENV] == "elsewhere"


def test_non_windows_never_touches_the_dll_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf_module.sys, "platform", "linux")
    monkeypatch.delenv(pdf_module.DLL_DIRS_ENV, raising=False)
    assert pdf_module.prepare_windows_dlls() is None and pdf_module.DLL_DIRS_ENV not in pdf_module.os.environ
