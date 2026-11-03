"""변화 판정(report/judge.py, 명세 5절 비교 규칙·15.8 판정 표·17.5 BE-18, S15P31A404-197). DB 없이 돈다."""

from __future__ import annotations

import pytest

from app.report.judge import (
    CHANGE_LABELS,
    DECREASE,
    INCREASE,
    NOT_COMPARABLE,
    NOTE_MODEL_CHANGED,
    NOTE_NO_DATA,
    NOTE_RANGE_NOT_SET,
    UNKNOWN,
    WITHIN_RANGE,
    judge,
)


def test_a_missing_side_is_not_comparable_with_no_data() -> None:
    assert judge(None, 42.0, 3.0) == (NOT_COMPARABLE, NOTE_NO_DATA, None)
    assert judge(38.2, None, 3.0) == (NOT_COMPARABLE, NOTE_NO_DATA, None)


def test_an_unmeasurable_side_gives_its_reason_base_first() -> None:
    assert judge(None, 42.0, 3.0, base_reason="LOW_CONFIDENCE").note == "LOW_CONFIDENCE"
    assert judge(38.2, None, 3.0, target_reason="NOT_ENOUGH_CYCLES").note == "NOT_ENOUGH_CYCLES"
    both = judge(None, None, 3.0, base_reason="LOW_CONFIDENCE", target_reason="NOT_ENOUGH_CYCLES")
    assert both == (NOT_COMPARABLE, "LOW_CONFIDENCE", None)
    # 한쪽은 행이 없고 다른 쪽은 측정 불가면 NO_DATA가 먼저다
    assert judge(None, None, 3.0, target_reason="LOW_CONFIDENCE").note == NOTE_NO_DATA


def test_a_changed_model_is_unknown_but_still_reports_the_diff() -> None:
    assert judge(38.2, 42.0, 3.0, model_changed=True) == (UNKNOWN, NOTE_MODEL_CHANGED, 3.8)


def test_no_tolerance_is_unknown_with_range_not_set() -> None:
    assert judge(38.2, 42.0, None) == (UNKNOWN, NOTE_RANGE_NOT_SET, 3.8)


@pytest.mark.parametrize(
    ("base", "target", "tolerance", "expected"),
    [
        (30.2, 33.2, 3.0, WITHIN_RANGE),  # BE-18: float 오차로 INCREASE가 되지 않는다
        (33.2, 30.2, 3.0, WITHIN_RANGE),
        (38.2, 42.0, 3.0, INCREASE),
        (42.0, 38.2, 3.0, DECREASE),
        (38.2, 38.2, 0.0, WITHIN_RANGE),
        (38.2, 38.3, 0.0, INCREASE),
    ],
)
def test_within_increase_decrease_follow_the_tolerance(
    base: float, target: float, tolerance: float, expected: str
) -> None:
    verdict = judge(base, target, tolerance)
    assert verdict.judgement == expected and verdict.note is None
    assert verdict.diff == pytest.approx(target - base)


def test_diff_is_target_minus_base_rounded_to_four_places() -> None:
    assert judge(31.0, 38.2, 10.0).diff == 7.2
    assert judge(38.2, 31.0, 10.0).diff == -7.2
    assert judge(1.00004, 1.0, 10.0).diff == 0.0  # 15.1의 네 자리 반올림


def test_labels_exist_only_for_decided_judgements() -> None:
    assert set(CHANGE_LABELS) == {INCREASE, DECREASE, WITHIN_RANGE}
    assert UNKNOWN not in CHANGE_LABELS and NOT_COMPARABLE not in CHANGE_LABELS
    assert not any(word in label for label in CHANGE_LABELS.values() for word in ("좋아", "나빠"))
