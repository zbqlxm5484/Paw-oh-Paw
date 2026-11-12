"""변화 판정(명세 5절 비교 규칙, 15.8 판정 표, 17.5 BE-18, S15P31A404-197).

보고서의 직전 회차 비교(numbers.build_tables)와 회차 비교 API(services/compare.py, 198)가 같이 쓴다.
차이 계산(difference)은 보고서 수치 대조의 기준값(verify.previous_reference)도 쓴다(272). 순서대로 처음
맞는 줄을 따른다.

1. 한쪽 값이 없거나 측정 불가 → NOT_COMPARABLE. note는 행이 없는 쪽이 있으면 NO_DATA, 아니면 base 쪽, 그다음 target 쪽의
   측정 불가 사유. diff는 None
2. 두 회차의 분석 모델이 다름 → UNKNOWN·MODEL_CHANGED
3. 그 수치의 오차 범위가 없음 → UNKNOWN·RANGE_NOT_SET. 통과 수가 모자라면 부르는 쪽이 usable_tolerance로 None을 넘긴다
4. |diff| ≤ 오차 범위 → WITHIN_RANGE
5. 그 밖 → INCREASE(diff > 범위)·DECREASE(diff < −범위)

diff = target − base(원 단위). Decimal로 계산해 30.2 → 33.2에 범위 3.0이 float 오차로 INCREASE가 되지 않는다(BE-18).
"좋아짐·나빠짐" 같은 평가 단어는 내지 않고 방향만 낸다(5절). DB와 app을 모른다(11.3).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

INCREASE = "INCREASE"
DECREASE = "DECREASE"
WITHIN_RANGE = "WITHIN_RANGE"
UNKNOWN = "UNKNOWN"
NOT_COMPARABLE = "NOT_COMPARABLE"

NOTE_NO_DATA = "NO_DATA"
NOTE_MODEL_CHANGED = "MODEL_CHANGED"
NOTE_RANGE_NOT_SET = "RANGE_NOT_SET"

# 보고서 표에 적는 말. 판정이 난 세 경우만 적고(5절: 방향만), UNKNOWN·NOT_COMPARABLE은 값만 적는다
CHANGE_LABELS: dict[str, str] = {INCREASE: "증가", DECREASE: "감소", WITHIN_RANGE: "범위 안"}

# 15.1의 숫자 반올림과 같다(session_results.DIFF_PLACES)
DIFF_PLACES = Decimal("0.0001")


# 오차 범위 값은 통과 8개를 평균한 줄에서 나왔다. 5회면 고관절 약 6°·무릎 약 11°·입각기 약 6%p가 흔들려
# 범위보다 크므로, 회차 비교와 좌우 차이 모두 8회 미만이면 견주지 않는다(박규원 MR 86 답변)
TOLERANCE_MIN_PASSES = 8


class Judgement(NamedTuple):
    judgement: str
    note: str | None  # 14절 사유 코드. 판정이 났으면 None
    diff: float | None  # target − base. 비교할 수 없으면 None


def _difference(base: float, target: float) -> Decimal:
    return (Decimal(str(target)) - Decimal(str(base))).quantize(DIFF_PLACES, rounding=ROUND_HALF_UP)


def difference(base: float, target: float) -> float:
    """target − base(원 단위, 소수 4자리 반올림). 판정과 수치 대조 기준값이 같은 식을 쓰게 한곳에 둔다."""
    return float(_difference(base, target))


def usable_tolerance(tolerance: float | None, *passes: float | None) -> float | None:
    """견줄 수 있는 오차 범위. 견주는 값들의 n_passes가 하나라도 모자라거나 모르면 None이다."""
    if any(count is None or count < TOLERANCE_MIN_PASSES for count in passes):
        return None
    return tolerance


def judge(
    base: float | None,
    target: float | None,
    tolerance: float | None,
    *,
    model_changed: bool = False,
    base_reason: str | None = None,
    target_reason: str | None = None,
) -> Judgement:
    """base → target 변화의 판정. base_reason·target_reason은 그쪽 행이 있는데 측정 불가일 때의 사유 코드다."""
    if base is None or target is None:
        if (base is None and base_reason is None) or (target is None and target_reason is None):
            note = NOTE_NO_DATA
        else:
            note = base_reason if base is None else target_reason
        return Judgement(NOT_COMPARABLE, note, None)
    diff = _difference(base, target)
    if model_changed:
        return Judgement(UNKNOWN, NOTE_MODEL_CHANGED, float(diff))
    if tolerance is None:
        return Judgement(UNKNOWN, NOTE_RANGE_NOT_SET, float(diff))
    limit = Decimal(str(tolerance))
    if abs(diff) <= limit:
        return Judgement(WITHIN_RANGE, None, float(diff))
    return Judgement(INCREASE if diff > limit else DECREASE, None, float(diff))
