"""다리 비교 계산(명세 12.3 식, 15.1 반올림). 표준 라이브러리만 쓴다(11.3).

견본 입력(samples.py)과 대조 기준값(verify.reference_from_result)이 같이 쓴다. 팀 서비스의 결과 조회는
services/session_results.py의 _compare_one이 같은 식으로 계산한다. 둘이 같은 값을 내는지는
tests/test_report_samples.py가 본다.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

DIFF_PLACES = Decimal("0.0001")
SYMMETRY_PLACES = Decimal("0.01")


def pair_numbers(left: Decimal, right: Decimal) -> tuple[Decimal, Decimal | None]:
    """(차이 = 왼쪽 − 오른쪽, 대칭 지수). 왼쪽과 오른쪽의 합이 0이면 대칭 지수는 None이다."""
    gap = left - right
    total = left + right
    symmetry = None
    if total != 0:
        symmetry = (abs(gap) / (total / 2) * 100).quantize(SYMMETRY_PLACES, rounding=ROUND_HALF_UP)
    return gap.quantize(DIFF_PLACES, rounding=ROUND_HALF_UP), symmetry
