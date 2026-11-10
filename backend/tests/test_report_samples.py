"""견본 보고서 경우 목록(app/report/samples.py)과 견본 스크립트(scripts/report_samples.py), D-08·KPI-29(S15P31A404-200).

경우마다 두 판본이 입력 검사·금지 표현·용어 검사를 통과하고, 실린 숫자가 입력의 결과 값과 맞는지 본다. PDF 변환 자체는
WeasyPrint가 있을 때만 한 경우로 확인한다(test_report_module의 실제 PDF 테스트와 같은 조건).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.models import SessionMetric
from app.report import ReportError
from app.report.checks import ensure_checked
from app.report.generate import render
from app.report.pairs import pair_numbers
from app.report.pdf import pdf_available
from app.report.samples import CASES, EDITIONS, MESSAGES, case_names, compare_rank, metric, sample_input
from app.report.verify import KIND_NOT_IN_SOURCE, KIND_VALUE_DIFFERS, compare_numbers, reference_from_result
from app.services.session_results import limb_compare
from scripts import report_samples

PAIRS = [(case.name, edition) for case in CASES for edition in EDITIONS]


def _html(case: str, edition: str) -> str:
    return render(sample_input(case, edition)).html


@pytest.mark.parametrize(("case", "edition"), PAIRS)
def test_every_case_renders_passes_the_checks_and_matches_its_own_numbers(case: str, edition: str) -> None:
    data = sample_input(case, edition)
    rendered = render(data)
    ensure_checked(rendered.texts, edition=edition)  # 금지 표현 0건, 보호자용 용어 설명, 고정 문구
    reference = reference_from_result(data["result"], data["previous"], model_changed=case == "model_changed")
    verification = compare_numbers(rendered.numbers, reference)
    assert verification.ok, verification.mismatches
    assert verification.omitted == ()
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
        assert " 증가</span>" in html and " 감소</span>" in html and " 범위 안</span>" in html
        assert "<h2>직전 회차와 비교</h2>" in html
        assert "2026-10-14" in html  # 직전 회차 날짜


def test_model_change_keeps_values_but_no_change_labels() -> None:
    html = _html("model_changed", "VET")
    assert "분석 방식이 달라" in html
    assert " 증가</span>" not in html and " 감소</span>" not in html and " 범위 안</span>" not in html
    assert 'class="delta"' not in html and 'class="pair"' in html  # 값은 나란히, 차이와 변화는 없다


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


def _as_rows(gait: dict) -> list[SessionMetric]:
    """견본의 수치 행을 결과 조회가 받는 session_metric 행 모양으로(DB 없이 객체만)."""
    return [
        SessionMetric(
            gait_type=gait["gait_type"],
            limb=row["limb"],
            metric_code=row["metric_code"],
            value=None if row["value"] is None else Decimal(str(row["value"])),
            unit=row["unit"],
            measurable=row["measurable"],
            unmeasurable_reason=(row["unmeasurable_reason"] or {}).get("code"),
            n_passes=row["n_passes"],
        )
        for row in gait["metrics"]
    ]


@pytest.mark.parametrize("case", case_names())
def test_limb_compare_lines_follow_the_result_api_order(case: str) -> None:
    """견본의 다리 비교 줄은 결과 조회(services/session_results.limb_compare)와 같은 순서·값이다(15.7)."""
    for gait in sample_input(case, "VET")["result"]["gaits"]:
        keys = ("pair", "metric_code", "left", "right", "diff", "symmetry_index", "comparable")
        expected = [tuple(getattr(entry, key) for key in keys) for entry in limb_compare(_as_rows(gait))]
        actual = [tuple(line[key] for key in keys) for line in gait["limb_compare"]]
        assert actual == expected, gait["gait_type"]
        assert gait["limb_compare"] == sorted(gait["limb_compare"], key=compare_rank)


def test_follow_up_summary_names_the_largest_ratio_item() -> None:
    """평보는 무릎 4.50% > 고관절 1.81% > 입각기 1.08%라 요약의 "가장 큰 항목"은 무릎이다(정렬 전엔 첫 행 고관절)."""
    (walk, _trot) = sample_input("follow_up", "OWNER")["result"]["gaits"]
    assert [line["metric_code"] for line in walk["limb_compare"]] == ["rom_stifle", "rom_hip", "stance_ratio"]
    assert [line["symmetry_index"] for line in walk["limb_compare"]] == [4.5, 1.81, 1.08]
    html = _html("follow_up", "OWNER")
    assert "평보에서 왼쪽과 오른쪽의 차이를 비율로 볼 때 가장 큰 항목은 뒷다리 무릎 가동 범위입니다." in html
    assert "가장 큰 항목은 뒷다리 고관절" not in html


# ---- 통과 수: 집계 규칙(services/aggregation.py)에서 나올 수 있는 값 ----


@pytest.mark.parametrize("case", case_names())
def test_pass_counts_fit_the_aggregation_rule(case: str) -> None:
    """왼쪽 통과는 왼쪽 다리, 오른쪽 통과는 오른쪽 다리 값만 낸다. 몸 전체 수치는 양쪽 합까지다(!93 리뷰)."""
    data = sample_input(case, "VET")
    for session in filter(None, (data["result"], data["previous"])):
        counts = session["pass_counts"]
        assert counts["measured"] == counts["used"] + counts["excluded"]
        assert sum(item["count"] for item in session["exclude_summary"]) == counts["excluded"]
        needed = 0
        for gait in session["gaits"]:
            rows = gait["metrics"]
            left = max((row["n_passes"] for row in rows if row["limb"] in ("LF", "LH")), default=0)
            right = max((row["n_passes"] for row in rows if row["limb"] in ("RF", "RH")), default=0)
            whole = max((row["n_passes"] for row in rows if row["limb"] == "NONE"), default=0)
            assert whole <= left + right
            needed += left + right
            for row in rows:
                no_pass = (row["unmeasurable_reason"] or {}).get("code") == "NO_PASS_FOR_LIMB"
                assert no_pass == (row["n_passes"] == 0), row
        assert needed == counts["used"]


def test_follow_up_keeps_labels_and_both_value_only_kinds() -> None:
    """정직한 통과 수로도 증가·감소·범위 안이 남고, 기준 없음·통과 부족은 값만 나온다."""
    (walk, trot) = render(sample_input("follow_up", "VET")).tables
    rows = {row.code: row for row in trot.changes}
    labels = {rows["rom_stifle"].cells["LH"].change, rows["rom_hip"].cells["LH"].change}
    labels.add(rows["rom_stifle"].cells["RH"].change)
    assert labels == {"INCREASE", "DECREASE", "WITHIN_RANGE"}
    too_few, no_range = rows["rom_hip"].cells["RH"], rows["rom_elbow"].cells["LF"]
    assert too_few.diff and too_few.change is None
    assert no_range.diff and no_range.change is None
    # 직전 회차에 평보가 없어 평보는 비교 표가 없다
    assert walk.changes == []


def test_unmeasurable_top_item_is_not_held_against_the_tolerance() -> None:
    """가장 큰 항목(무릎)은 오차 범위가 있어도 통과가 5회씩이라 견주지 않는다."""
    summary = render(sample_input("unmeasurable", "OWNER")).sentences.summary
    assert any("가장 큰 항목은 뒷다리 무릎 가동 범위입니다" in line for line in summary)
    assert any("판단하지 않습니다" in line for line in summary)
    assert not any("측정 오차 범위 안에 있습니다" in line for line in summary)


# ---- 대조 기준값: limb_compare를 믿지 않고 metrics에서 다시 계산한다 ----


def _verified(data: dict):
    return compare_numbers(render(data).numbers, reference_from_result(data["result"], data.get("previous")))


def _top_trot_line(data: dict) -> dict:
    return next(gait for gait in data["result"]["gaits"] if gait["gait_type"] == "TROT")["limb_compare"][0]


@pytest.mark.parametrize(
    ("field", "kind"), [("diff", "diff"), ("symmetry_index", "symmetry_index"), ("left", "left"), ("right", "right")]
)
def test_a_wrong_limb_compare_value_is_caught(field: str, kind: str) -> None:
    data = sample_input("follow_up", "VET")
    line = _top_trot_line(data)
    honest = line[field]
    line[field] = 77.0
    (mismatch,) = _verified(data).mismatches
    assert (mismatch.kind, mismatch.key, mismatch.listed) == (
        KIND_VALUE_DIFFERS,
        ("TROT", line["metric_code"], line["pair"], kind),
        77.0,
    )
    assert mismatch.expected == pytest.approx(honest)


def test_a_changed_metric_with_the_old_line_is_caught() -> None:
    data = sample_input("follow_up", "VET")
    trot = next(gait for gait in data["result"]["gaits"] if gait["gait_type"] == "TROT")
    row = next(row for row in trot["metrics"] if (row["metric_code"], row["limb"]) == ("rom_stifle", "LH"))
    row["value"] = 40.0
    kinds = {mismatch.key[3] for mismatch in _verified(data).mismatches}
    assert kinds == {"left", "diff", "symmetry_index"}


def test_a_line_metrics_cannot_make_is_not_in_source() -> None:
    data = sample_input("follow_up", "VET")
    walk = data["result"]["gaits"][0]
    walk["limb_compare"].append({**walk["limb_compare"][0], "metric_code": "rom_shoulder", "pair": "FORE"})
    kinds = {mismatch.kind for mismatch in _verified(data).mismatches}
    assert kinds == {KIND_NOT_IN_SOURCE}


def _result_of(rows: list[dict]) -> dict:
    return {"gaits": [{"gait_type": "TROT", "metrics": rows, "limb_compare": []}]}


def _row(limb: str, value: float | None) -> dict:
    return {"metric_code": "rom_hip", "limb": limb, "value": value}


def test_reference_keeps_only_what_the_values_allow() -> None:
    zero = reference_from_result(_result_of([_row("LH", 0.0), _row("RH", 0.0)]))
    assert zero[("TROT", "rom_hip", "HIND", "diff")] == 0.0
    assert ("TROT", "rom_hip", "HIND", "symmetry_index") not in zero
    one_side = reference_from_result(_result_of([_row("LH", 40.0), _row("RH", None)]))
    assert one_side[("TROT", "rom_hip", "HIND", "left")] == 40.0
    assert ("TROT", "rom_hip", "HIND", "right") not in one_side
    assert ("TROT", "rom_hip", "HIND", "diff") not in one_side


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 1e30])
def test_reference_survives_values_it_cannot_calculate(bad: float) -> None:
    reference = reference_from_result(_result_of([_row("LH", bad), _row("RH", 40.0)]))
    assert ("TROT", "rom_hip", "HIND", "diff") not in reference
    assert reference[("TROT", "rom_hip", "HIND", "right")] == 40.0


def test_reference_cannot_prove_a_value_that_comes_from_the_same_input() -> None:
    """한계: 몸 전체 수치는 보고서와 기준이 같은 입력에서 나와 틀려도 통과한다(독립된 결과를 넘겨야 잡힌다)."""
    data = sample_input("follow_up", "VET")
    trot = next(gait for gait in data["result"]["gaits"] if gait["gait_type"] == "TROT")
    next(row for row in trot["metrics"] if row["metric_code"] == "walk_speed")["value"] = 99.0
    assert _verified(data).ok


@pytest.mark.parametrize(
    ("left", "right", "diff", "symmetry"),
    [
        ("31.0", "38.2", "-7.2000", "20.81"),
        ("42.0", "38.2", "3.8000", "9.48"),
        ("100.0625", "99.9375", "0.1250", "0.13"),
        ("47.3", "43.1", "4.2000", "9.29"),
        ("0", "0", "0.0000", None),
    ],
)
def test_pair_numbers_match_the_result_api(left: str, right: str, diff: str, symmetry: str | None) -> None:
    """식은 결과 조회(session_results._compare_one)에도 있으니 둘이 같은 값을 내는지 본다."""
    got_diff, got_symmetry = pair_numbers(Decimal(left), Decimal(right))
    assert got_diff == Decimal(diff)
    assert got_symmetry == (None if symmetry is None else Decimal(symmetry))
    gait = {
        "gait_type": "TROT",
        "metrics": [
            {**metric("rom_hip", "LH", float(left), n=8)},
            {**metric("rom_hip", "RH", float(right), n=8)},
        ],
    }
    (line,) = limb_compare(_as_rows(gait))
    assert (line.diff, line.symmetry_index) == (float(got_diff), None if got_symmetry is None else float(got_symmetry))


@pytest.mark.parametrize("case", case_names())
def test_reference_equals_what_the_result_api_calculates(case: str) -> None:
    for gait in sample_input(case, "VET")["result"]["gaits"]:
        reference = reference_from_result({"gaits": [gait]})
        for line in limb_compare(_as_rows(gait)):
            if line.comparable:
                assert reference[(gait["gait_type"], line.metric_code, line.pair, "diff")] == line.diff


def test_script_fails_when_a_listed_number_went_missing(tmp_path: Path) -> None:
    """기준에 있는 숫자가 실리지 않으면(값이 null로 빠진 줄) 스크립트 대조가 실패한다."""
    data = sample_input("follow_up", "VET")
    _top_trot_line(data)["left"] = None
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ReportError):
        report_samples._verify(path, render(data).numbers)


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
