"""좌우 차이·대칭 지수(engine/symmetry.py) 테스트. 값은 팀 서비스 테스트(backend/tests/test_session_results.py)와 같다."""
from decimal import Decimal

from engine.symmetry import limb_difference


def test_spec_example():
    # 백엔드 명세 15.7 예시: 무릎 가동 범위 왼쪽 31.0, 오른쪽 38.2 (test_compare_example_from_the_spec)
    assert limb_difference(31.0, 38.2) == {"diff": -7.2, "symmetry_index": 20.81, "comparable": True}


def test_diff_is_decimal_not_float():
    assert 42.0 - 38.2 != 3.8                                # float 그대로면 3.7999…
    assert limb_difference(42.0, 38.2)["diff"] == 3.8         # test_diff_is_computed_in_decimal_not_float


def test_round_half_up_not_bankers():
    # |100.0625 − 99.9375| ÷ 100 × 100 = 0.125 → 0.13 (은행원 반올림이면 0.12) (test_symmetry_index_rounds_half_up)
    r = limb_difference(100.0625, 99.9375)
    assert r["symmetry_index"] == 0.13 and r["diff"] == 0.125


def test_zero_sum_has_diff_but_no_symmetry():
    assert limb_difference(0.0, 0.0) == {"diff": 0.0, "symmetry_index": None, "comparable": True}


def test_missing_side_is_not_comparable():
    for left, right in ((None, 12.4), (12.4, None), (None, None)):
        assert limb_difference(left, right) == {"diff": None, "symmetry_index": None, "comparable": False}


def test_sign_and_symmetry_are_left_minus_right():
    a, b = limb_difference(50.0, 40.0), limb_difference(40.0, 50.0)
    assert a["diff"] == 10.0 and b["diff"] == -10.0
    assert a["symmetry_index"] == b["symmetry_index"] == 22.22      # 10 ÷ 45 × 100


def test_accepts_decimal_from_db():
    assert limb_difference(Decimal("31.0000"), Decimal("38.2000"))["symmetry_index"] == 20.81
