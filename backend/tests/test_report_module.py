"""보고서 모듈(8절, S15P31A404-195): 입력 → 수치 표 → 문장 → HTML → 검사 → PDF. DB 없이 돈다."""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import pytest

from app.report import TEMPLATE_VERSION, ReportCheckError, ReportError, ReportInputError
from app.report import pdf as pdf_module
from app.report.checks import DISCLAIMER, check_texts, find_unexplained_jargon, load_rules
from app.report.generate import generate_report, render
from app.report.inputs import parse_input
from app.report.numbers import UNMEASURABLE, build_tables, format_value
from app.report.pdf import PdfUnavailableError, pdf_available
from app.report.sentences import _glossary
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


# ---- 문장·검사(김지윤 문장 템플릿, MR 80 리뷰. 글자 그대로 나오는지 본다) ----

TOP_LINE = (
    "속보에서 왼쪽과 오른쪽의 차이를 비율로 볼 때 가장 큰 항목은 뒷다리 무릎 가동 범위입니다. "
    "왼쪽 47.3°, 오른쪽 43.1°, 차이 4.2°입니다."
)
NO_RANGE = (
    "좌우 차이는 촬영 조건에 따라서도 달라질 수 있어, 이 수치만으로 변화를 판단하지 않습니다. "
    "다음 측정과 같은 조건에서 비교해 보세요."
)
WITHIN_RANGE = "이 차이는 측정 오차 범위 안에 있습니다."
OVER_RANGE = (
    "이 차이는 측정 오차 범위보다 큽니다. 다음 측정에서도 같은 다리에 차이가 이어지는지 담당 수의사와 함께 봐 주세요."
)


@pytest.mark.parametrize("edition", ["OWNER", "VET"])
def test_sentences_pass_the_checks_for_both_editions(edition: str) -> None:
    rendered = render(sample_input(edition=edition))
    assert check_texts(rendered.texts, edition=edition) == []
    assert DISCLAIMER in rendered.sentences.disclaimer
    assert TOP_LINE in rendered.texts["summary"]


def test_summary_names_the_largest_ratio_not_the_largest_absolute_difference() -> None:
    # 비교 줄은 대칭 지수 순서로 온다(15.7). 차이 값은 앞발목(2.0°)이 더 커도 비율은 어깨가 더 크다
    result = sample_result()
    result["gaits"][0]["limb_compare"] = [
        compare("FORE", "rom_shoulder", 39.9, 38.0),
        compare("FORE", "rom_carpus", 73.0, 71.0),
    ]
    summary = render(sample_input(result=result)).texts["summary"]
    assert "왼쪽과 오른쪽의 차이를 비율로 볼 때 가장 큰 항목은 앞다리 어깨 가동 범위입니다" in summary
    assert "차이 1.9°" in summary and "차이가 가장" not in summary


def test_summary_exceptions_follow_the_template_without_a_second_sentence() -> None:
    result = sample_result()
    result["gaits"][0]["limb_compare"] = [compare("HIND", "rom_stifle", 0.0, 0.0)]
    assert render(sample_input(result=result)).sentences.summary == [
        "속보에서 좌우 차이를 비율로 낼 수 있는 항목은 없습니다. "
        "뒷다리 무릎 가동 범위: 왼쪽 0.0°, 오른쪽 0.0°, 차이 0.0°입니다."
    ]
    result["gaits"][0]["limb_compare"] = []
    assert render(sample_input(result=result)).sentences.summary == [
        "왼쪽과 오른쪽을 비교할 수 있는 수치가 없어 차이를 적지 않았습니다."
    ]


def test_intro_follows_the_template_and_drops_only_the_missing_profile_items() -> None:
    assert render(sample_input()).sentences.intro == (
        "2026-11-02에 제니의 걷는 모습을 촬영해 수치를 냈습니다. 체중 12.5 kg, 중형견, 말티즈. "
        "촬영 4건에서 걸음 6회를 보았고, 그중 5회로 수치를 냈습니다(제외 1회)."
    )
    bare = sample_input(dog={"name": "코코"}, session={"id": "x", "measured_on": "2026-11-02"})
    assert render(bare).sentences.intro == (
        "2026-11-02에 코코의 걷는 모습을 촬영해 수치를 냈습니다. "
        "촬영 4건에서 걸음 6회를 보았고, 그중 5회로 수치를 냈습니다(제외 1회)."
    )


@pytest.mark.parametrize(
    ("tolerance", "second"),
    [
        ({}, NO_RANGE),
        ({"rom_hip": 1.0}, NO_RANGE),  # 표에 그 수치가 없으면 오차 범위가 없는 것과 같다
        ({"rom_stifle": 4.2}, WITHIN_RANGE),  # 15.8: |diff| ≤ 오차 범위는 안이다
        ({"rom_stifle": 4.1}, OVER_RANGE),
    ],
)
def test_owner_summary_second_sentence_follows_the_tolerance(tolerance: dict[str, float], second: str) -> None:
    summary = render(sample_input(settings={"tolerance": tolerance})).sentences.summary
    assert summary == [TOP_LINE, second]


def test_tolerance_compares_the_size_of_the_difference_in_decimal() -> None:
    # 오른쪽이 더 커도(diff 음수) 크기로 견주고, 30.2와 33.2의 차이 3.0은 오차 범위 3.0 안이다(15.1, 15.8)
    result = sample_result()
    result["gaits"][0]["limb_compare"] = [compare("HIND", "rom_stifle", 30.2, 33.2)]
    summary = render(sample_input(result=result, settings={"tolerance": {"rom_stifle": 3.0}})).sentences.summary
    assert summary[1] == WITHIN_RANGE


def test_vet_summary_adds_the_symmetry_index_and_no_second_sentence() -> None:
    assert render(sample_input(edition="VET")).sentences.summary == [f"{TOP_LINE} 대칭 지수 9.3%."]


def test_gait_notes_and_no_pass_sentence_follow_the_template() -> None:
    assert render(sample_input()).sentences.gait_notes["TROT"] == [
        "속보: 수치 8개 중 7개를 측정했습니다.",
        "측정하지 못한 1개는 표에 사유를 적었습니다.",
        "좌우 비교를 하지 못한 항목 1개: NO_DATA 메시지",
    ]
    assert render(sample_input(result=sample_result(gaits=[]))).sentences.gait_notes["NONE"] == [
        "수치를 낼 수 있는 걸음이 없었습니다. "
        "매트를 옆으로 곧게 지나가도록, 반대 방향으로도 걷게 해 다시 촬영해 주세요."
    ]


def test_compare_skip_note_lists_each_reason_once() -> None:
    result = sample_result()
    result["gaits"][0]["limb_compare"] = [
        compare("HIND", "rom_stifle", 47.3, None, reason="NO_DATA"),
        compare("HIND", "rom_hip", None, 41.0, reason="NO_DATA"),
        compare("FORE", "rom_elbow", None, None, reason="ONE_SIDE"),
    ]
    assert render(sample_input(result=result)).sentences.gait_notes["TROT"][-1] == (
        "좌우 비교를 하지 못한 항목 3개: NO_DATA 메시지 ONE_SIDE 메시지"
    )


@pytest.mark.parametrize(
    ("edition", "extra"),
    [
        ("OWNER", "걱정되는 변화가 있으면 담당 수의사와 상의해 주세요."),
        ("VET", "이 수치는 영상에서 추정한 값이며, 임상 판단의 보조 자료입니다."),
    ],
)
def test_caution_follows_the_template(edition: str, extra: str) -> None:
    assert render(sample_input(edition=edition)).sentences.caution == [
        "수치는 촬영 조건(바닥, 걷는 속도, 카메라 각도)에 따라 달라질 수 있습니다. "
        "같은 조건에서 다시 잰 값과 비교해 주세요.",
        extra,
    ]


@pytest.mark.parametrize("edition", ["OWNER", "VET"])
def test_every_template_sentence_passes_the_checks(edition: str) -> None:
    no_ratio = sample_result()
    no_ratio["gaits"][0]["limb_compare"] = [compare("HIND", "rom_stifle", 0.0, 0.0)]
    no_lines = sample_result()
    no_lines["gaits"][0]["limb_compare"] = []
    earlier = sample_result(measured_on="2026-10-20")
    other_model = sample_result(measured_on="2026-10-20", model_version="0.3.0/v1/deadbeef")
    for data in (
        sample_input(edition=edition, settings={"tolerance": {}}),
        sample_input(edition=edition),
        sample_input(edition=edition, settings={"tolerance": {"rom_stifle": 1.0}}),
        sample_input(edition=edition, result=no_ratio),
        sample_input(edition=edition, result=no_lines),
        sample_input(edition=edition, result=sample_result(gaits=[])),
        sample_input(edition=edition, previous=earlier),
        sample_input(edition=edition, previous=other_model),
    ):
        rendered = render(data)
        assert check_texts(rendered.texts, edition=edition) == []


def test_owner_glossary_explains_the_tolerance_only_when_a_sentence_uses_it() -> None:
    assert "오차 범위" in dict(render(sample_input()).sentences.glossary)
    assert "오차 범위" not in dict(render(sample_input(settings=None)).sentences.glossary)


def test_glossary_passes_the_check_for_every_listed_term() -> None:
    # 설명 문구가 다른 용어를 쓰는 경우(ROM → 가동 범위)와 붙여 쓴 용어도 검사를 통과해야 한다
    rules = load_rules()
    for rule in rules.jargon:
        for text in (rule.term, "".join(rule.term.split())):
            glossary = _glossary(text, rules)
            assert rule.term in dict(glossary)
            texts = {"body": text, "glossary": " ".join(f"{term}: {note}" for term, note in glossary)}
            assert find_unexplained_jargon(texts, rules) == [], rule.term
    assert "가동 범위" in dict(_glossary("ROM", rules))


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
    assert "수치를 낼 수 있는 걸음이 없었습니다" in empty.texts["gaits"] and empty.tables == []


def test_previous_session_with_another_model_version_is_not_compared() -> None:
    previous = sample_result(measured_on="2026-10-20", model_version="0.3.0/v1/deadbeef")
    rendered = render(sample_input(previous=previous))
    assert rendered.texts["previous"] == (
        "직전 회차(2026-10-20)는 분석 방식이 달라 값만 표에 함께 적고, 변화는 판단하지 않았습니다."
    )


def test_previous_session_with_the_same_model_version_points_at_the_table() -> None:
    rendered = render(sample_input(previous=sample_result(measured_on="2026-10-20")))
    assert rendered.texts["previous"] == (
        "직전 회차(2026-10-20)의 값을 표의 괄호 안에 함께 적었습니다. "
        "값의 차이는 측정 조건에 따라서도 생길 수 있습니다."
    )


# ---- HTML ----


def test_html_has_title_tables_chart_glossary_and_footer() -> None:
    rendered = render(sample_input())
    html = rendered.html
    assert "<title>제니 보행 평가 보고서 (보호자용)</title>" in html
    assert "왼쪽 뒷다리" in html and "측정 불가" in html and "NOT_ENOUGH_CYCLES 메시지" in html
    assert 'src="data:image/png;base64,' in html
    assert "용어 설명" in html and f"템플릿 {TEMPLATE_VERSION}" in html
    assert "<footer>이 보고서는 보행 평가 보조 자료이며 진단을 대신하지 않습니다.</footer>" in html  # 고정 문구 그대로
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
