"""보고서 수치 대조의 비교 함수(8절 7번 첫 항목, PR-F08-12, S15P31A404-196). DB 없이 돈다."""

from __future__ import annotations

from app.report.numbers import ListedNumber, build_tables
from app.report.verify import (
    KIND_NOT_IN_SOURCE,
    KIND_VALUE_DIFFERS,
    NumberKey,
    compare_numbers,
    key_of,
    summarize,
)
from tests.report_fixtures import sample_result


def _listed() -> list[ListedNumber]:
    return build_tables(sample_result())[1]


def _reference() -> dict[NumberKey, float]:
    return {key_of(number): number.value for number in _listed()}


def _replace(numbers: list[ListedNumber], key: NumberKey, value: float) -> list[ListedNumber]:
    return [ListedNumber(n.gait_type, n.metric_code, n.limb, n.kind, value) if key_of(n) == key else n for n in numbers]


def test_numbers_that_match_the_reference_pass() -> None:
    reference = _reference()
    verification = compare_numbers(_listed(), reference)
    assert verification.ok
    assert verification.checked == len(reference) > 0 and verification.omitted == ()
    assert summarize(verification) == f"checked {len(reference)}, omitted 0"


def test_a_changed_value_is_a_mismatch_that_names_both_values() -> None:
    key = ("TROT", "rom_stifle", "LH", "metric")
    verification = compare_numbers(_replace(_listed(), key, 47.8), _reference())
    assert not verification.ok
    (mismatch,) = verification.mismatches
    assert (mismatch.kind, mismatch.key, mismatch.listed, mismatch.expected) == (KIND_VALUE_DIFFERS, key, 47.8, 47.3)
    assert str(mismatch) == "VALUE_DIFFERS TROT/rom_stifle/LH/metric: listed=47.8 expected=47.3"


def test_a_number_without_a_source_is_a_mismatch() -> None:
    extra = ListedNumber("TROT", "rom_hip", "RH", "metric", 40.0)  # 기준에서는 측정 불가라 값이 없다
    verification = compare_numbers([*_listed(), extra], _reference())
    (mismatch,) = verification.mismatches
    assert (mismatch.kind, mismatch.key, mismatch.expected) == (KIND_NOT_IN_SOURCE, key_of(extra), None)


def test_reference_numbers_that_are_not_listed_are_omitted_not_mismatches() -> None:
    listed = [n for n in _listed() if n.kind != "symmetry_index"]  # 보호자용은 대칭 지수를 표에 찍지 않는다
    verification = compare_numbers(listed, _reference())
    assert verification.ok and verification.checked == len(listed)
    assert verification.omitted == (("TROT", "rom_stifle", "HIND", "symmetry_index"),)


def test_nothing_listed_passes_with_everything_omitted() -> None:
    verification = compare_numbers([], _reference())
    assert verification.ok and verification.checked == 0 and len(verification.omitted) == len(_reference())


def test_float_noise_within_the_tolerance_is_the_same_number() -> None:
    key = ("TROT", "walk_speed", "NONE", "metric")
    assert compare_numbers(_replace(_listed(), key, 2.41 + 1e-9), _reference()).ok
    assert not compare_numbers(_replace(_listed(), key, 2.42), _reference()).ok


def test_pair_numbers_are_checked_by_pair_and_kind() -> None:
    key = ("TROT", "rom_stifle", "HIND", "diff")
    verification = compare_numbers(_replace(_listed(), key, 4.3), _reference())
    (mismatch,) = verification.mismatches
    assert mismatch.key == key and mismatch.expected == 4.2


def test_summary_counts_by_kind_and_lists_keys_but_no_values() -> None:
    extra = ListedNumber("WALK", "rom_hip", "LH", "metric", 40.0)
    listed = _replace([*_listed(), extra], ("TROT", "rom_stifle", "LH", "metric"), 1.0)
    text = summarize(compare_numbers(listed, _reference()))
    assert text.startswith("VALUE_DIFFERS 1: TROT/rom_stifle/LH/metric; NOT_IN_SOURCE 1: WALK/rom_hip/LH/metric")
    assert text.endswith(f"checked {len(_listed()) + 1}, omitted 0") and "40.0" not in text and "1.0" not in text
