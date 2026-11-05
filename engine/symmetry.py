"""좌우 차이·대칭 지수 검증용 함수 (F-02, S15P31A404-186)

계산의 원본은 팀 서비스다(backend/app/services/session_results.py `_compare_one`, 백엔드 명세 12.3·15.1, 10절 Q6).
이 함수는 같은 식·같은 반올림을 엔진 쪽에 둔 것이다. 쓰는 곳:
- 엔진 수치를 바꿀 때, 회차 비교 결과가 어떻게 달라지는지 팀 서비스 없이 미리 보기
- 기업 서버처럼 팀 서비스 없이 분석 결과만 받는 쪽이 같은 값을 내기
- 팀 서비스 계산이 바뀌었을 때 테스트로 어긋남을 알아채기(tests/test_symmetry.py의 값은 백엔드 테스트와 같다)

규칙(팀 서비스와 같음)
- 좌우 차이 diff = 왼쪽 − 오른쪽(원 단위). 부호가 있다: 음수면 오른쪽이 크다
- 대칭 지수 = |왼쪽 − 오른쪽| ÷ ((왼쪽 + 오른쪽) ÷ 2) × 100 (%)
- float가 아니라 Decimal로 계산한다. float로 빼면 42.0 − 38.2가 3.7999…가 된다. float 입력은 str을 거쳐 Decimal로 바꾼다
  (팀 서비스가 분석 결과의 숫자를 저장할 때와 같다)
- 반올림은 ROUND_HALF_UP: diff 소수 넷째 자리, 대칭 지수 소수 둘째 자리
- 한쪽이라도 값이 없으면(측정 불가) 비교할 수 없다: comparable false, diff·대칭 지수 None
- 왼쪽 + 오른쪽이 0이면 comparable true, diff는 내고 대칭 지수만 None
- 판단 단어(좋아짐·나빠짐)는 내지 않는다
"""
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional, Union

SYMMETRY_VERSION = "v1"
DIFF_PLACES = Decimal("0.0001")
SYMMETRY_PLACES = Decimal("0.01")

Number = Union[int, float, Decimal]


def _decimal(value: Optional[Number]) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def limb_difference(left: Optional[Number], right: Optional[Number]) -> dict:
    """왼쪽·오른쪽 회차 값 → {"diff", "symmetry_index", "comparable"}. 값은 float 또는 None (팀 서비스 15.7과 같은 모양)"""
    a, b = _decimal(left), _decimal(right)
    if a is None or b is None:
        return {"diff": None, "symmetry_index": None, "comparable": False}
    diff = (a - b).quantize(DIFF_PLACES, rounding=ROUND_HALF_UP)
    total = a + b
    symmetry = None
    if total != 0:
        symmetry = (abs(a - b) / (total / 2) * 100).quantize(SYMMETRY_PLACES, rounding=ROUND_HALF_UP)
    return {"diff": float(diff), "symmetry_index": None if symmetry is None else float(symmetry), "comparable": True}
