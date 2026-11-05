# 좌우 차이·대칭 지수 (F-02)

작성 조유진 · v1 11-05 (S15P31A404-186) · 코드 `engine/symmetry.py` · 테스트 `tests/test_symmetry.py`

좌우 차이와 대칭 지수의 **계산 원본은 팀 서비스**다(`backend/app/services/session_results.py`, 백엔드 명세 12.3·15.1·15.7). 회차 값(통과들의 중앙값)이 팀 서비스에서 나오므로 계산도 한곳에 둔다(백엔드 명세 10절 Q6, MR !65 리뷰). 엔진에는 **같은 식·같은 반올림의 검증용 함수**만 둔다.

## 1. 쓰는 곳

- 엔진 수치를 바꿀 때 회차 비교 결과가 어떻게 달라지는지 팀 서비스 없이 미리 보기
- 기업 서버처럼 팀 서비스 없이 분석 결과만 받는 쪽이 같은 값 내기
- 팀 서비스 계산이 바뀌면 테스트로 어긋남 알아채기 (테스트 값은 백엔드 테스트와 같다)

## 2. 규칙

| 항목 | 규칙 |
| --- | --- |
| 좌우 차이 `diff` | 왼쪽 − 오른쪽(원 단위). 음수면 오른쪽이 크다 |
| 대칭 지수 `symmetry_index` | \|왼쪽 − 오른쪽\| ÷ ((왼쪽 + 오른쪽) ÷ 2) × 100 (%) |
| 계산 | `Decimal`. float 입력은 `str`을 거쳐 바꾼다(42.0 − 38.2 = 3.8, float면 3.7999…) |
| 반올림 | `ROUND_HALF_UP`. `diff` 소수 넷째 자리, 대칭 지수 소수 둘째 자리 (0.125 → 0.13) |
| 한쪽 값 없음 | 비교 불가: `comparable` false, 둘 다 null |
| 왼쪽 + 오른쪽 = 0 | `comparable` true, `diff`는 내고 대칭 지수만 null |

판단 단어(좋아짐·나빠짐)는 내지 않는다(백엔드 명세 5절).

## 3. 사용 예

```python
from engine.symmetry import limb_difference

limb_difference(31.0, 38.2)
# {"diff": -7.2, "symmetry_index": 20.81, "comparable": True}   (백엔드 명세 15.7 예시와 같음)
```

## 4. 확인한 값 (백엔드 테스트와 같음)

| 왼쪽 | 오른쪽 | `diff` | 대칭 지수 | 백엔드 테스트 |
| --- | --- | --- | --- | --- |
| 31.0 | 38.2 | −7.2 | 20.81 | `test_compare_example_from_the_spec` |
| 42.0 | 38.2 | 3.8 | | `test_diff_is_computed_in_decimal_not_float` |
| 100.0625 | 99.9375 | 0.125 | 0.13 | `test_symmetry_index_rounds_half_up` |
| 0.0 | 0.0 | 0.0 | null | `test_zero_sum_is_comparable_without_a_symmetry_index` |
