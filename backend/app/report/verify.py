"""수치 대조(명세 8절 만드는 순서 7의 첫 항목, PR-F08-12, 17.4 BE-15, S15P31A404-196).

보고서 모듈이 돌려준 "실린 숫자 목록"(numbers.ListedNumber: 보행 유형·수치 코드·다리 또는 쌍·종류·값)을 기준값과 맞춘다.
기준값은 부르는 쪽이 준다. 팀 서비스는 DB의 session_metric 값과 15.7 다리 비교 계산값으로 만들고
(app/services/report_numbers.py), 기업 서버는 분석 결과에서 같은 모양으로 만들면 된다. 이 모듈은 DB를 모른다(11.3).

- 직전 회차 비교 표의 직전 값(previous)과 차이(change)도 실린 숫자다. 기준값은 직전 회차의 값과, 두 회차 값으로
  다시 계산한 차이(judge.difference)다(272).
- 불일치: 실린 숫자의 값이 기준값과 다르거나(VALUE_DIFFERS), 기준에 없는 숫자가 실렸을 때(NOT_IN_SOURCE).
  하나라도 있으면 워커는 PDF를 저장하지 않고 REPORT_CHECK_FAILED로 남긴다(12.4).
- 기준에는 있는데 싣지 않은 수치(omitted)는 불일치가 아니다(판본에 따라 덜 실을 수 있다). 개수만 로그에 남긴다.
- 값은 절대 오차 1e-6 안이면 같다고 본다. DB의 NUMERIC(10,4)와 JSON의 실수가 같은 수를 가리키면 float로도 같지만,
  계산 경로가 다른 경우에 대비한 여유다.
Spring에 빗대면 원장과 영수증을 맞추는 대사(reconciliation) 검증기다.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.report.judge import difference
from app.report.numbers import PAIR_LIMBS, ListedNumber, _number
from app.report.pairs import pair_numbers

# (보행 유형, 수치 코드, 다리 또는 쌍, 종류). 종류는 metric·left·right·diff·symmetry_index·previous·change
# (numbers.ListedNumber.kind)
NumberKey = tuple[str, str, str, str]
TOLERANCE = 1e-6

KIND_VALUE_DIFFERS = "VALUE_DIFFERS"
KIND_NOT_IN_SOURCE = "NOT_IN_SOURCE"


@dataclass(frozen=True)
class Mismatch:
    """어긋난 숫자 하나. expected는 기준값(기준에 없으면 None)."""

    kind: str
    key: NumberKey
    listed: float
    expected: float | None

    def __str__(self) -> str:
        return f"{self.kind} {'/'.join(self.key)}: listed={self.listed!r} expected={self.expected!r}"


@dataclass(frozen=True)
class Verification:
    """대조 결과. checked는 맞춰 본 숫자 수, omitted는 기준에는 있는데 실리지 않은 키다."""

    checked: int
    mismatches: tuple[Mismatch, ...]
    omitted: tuple[NumberKey, ...]

    @property
    def ok(self) -> bool:
        return not self.mismatches


def key_of(number: ListedNumber) -> NumberKey:
    return (number.gait_type, number.metric_code, number.limb, number.kind)


def same_value(listed: float, expected: float, tolerance: float = TOLERANCE) -> bool:
    return math.isclose(listed, expected, rel_tol=0.0, abs_tol=tolerance)


def compare_numbers(
    listed: Iterable[ListedNumber], reference: Mapping[NumberKey, float], *, tolerance: float = TOLERANCE
) -> Verification:
    """실린 숫자마다 기준값을 찾아 맞춘다. 같은 키가 여러 번 실렸으면 모두 검사한다."""
    numbers = tuple(listed)
    mismatches: list[Mismatch] = []
    seen: set[NumberKey] = set()
    for number in numbers:
        key = key_of(number)
        seen.add(key)
        expected = reference.get(key)
        if expected is None:
            mismatches.append(Mismatch(KIND_NOT_IN_SOURCE, key, number.value, None))
        elif not same_value(number.value, expected, tolerance):
            mismatches.append(Mismatch(KIND_VALUE_DIFFERS, key, number.value, expected))
    omitted = tuple(key for key in reference if key not in seen)
    return Verification(checked=len(numbers), mismatches=tuple(mismatches), omitted=omitted)


def summarize(verification: Verification) -> str:
    """로그용 한 줄: 종류별 개수와 키만 적고 값은 적지 않는다(보고서 내용은 로그에 남기지 않는다, 11.8)."""
    kinds: dict[str, list[str]] = {}
    for mismatch in verification.mismatches:
        kinds.setdefault(mismatch.kind, []).append("/".join(mismatch.key))
    parts = [f"{kind} {len(keys)}: {', '.join(dict.fromkeys(keys))}" for kind, keys in kinds.items()]
    parts.append(f"checked {verification.checked}, omitted {len(verification.omitted)}")
    return "; ".join(parts)


def _finite(raw: Any) -> float | None:
    """numbers._number와 같게 읽되 NaN·무한대는 수로 치지 않는다(Decimal 계산이 깨진다)."""
    number = _number(raw)
    return number if number is not None and math.isfinite(number) else None


def previous_reference(
    current: Mapping[tuple[str, str, str], float | None],
    previous: Mapping[tuple[str, str, str], float | None],
    *,
    model_changed: bool = False,
) -> dict[NumberKey, float]:
    """두 회차의 (보행 유형, 수치, 다리) → 값에서 직전 회차 비교 표의 기준값을 만든다.

    이번 회차에 있는 보행 유형만 본다(5절: 같은 유형끼리만 비교한다). 직전 값이 있으면 previous, 두 값이 다 있으면
    change(이번 − 직전, judge.difference)다. model_changed면 보고서가 차이를 싣지 않으므로 change를 넣지 않는다.
    팀 서비스 워커(services/report_numbers.py)와 reference_from_result가 같이 쓴다.
    """
    reference: dict[NumberKey, float] = {}
    shown = {gait_type for gait_type, _, _ in current}
    for key, before in previous.items():
        if before is None or key[0] not in shown:
            continue
        reference[(*key, "previous")] = before
        now = current.get(key)
        if now is None or model_changed:
            continue
        try:
            reference[(*key, "change")] = difference(before, now)
        except InvalidOperation:  # 반올림할 수 없을 만큼 큰 값. 기준에 넣지 않아 NOT_IN_SOURCE가 된다
            continue
    return reference


def _limb_values(result: Mapping[str, Any]) -> dict[tuple[str, str, str], float | None]:
    return {
        (str(gait.get("gait_type")), str(row.get("metric_code")), str(row.get("limb"))): _finite(row.get("value"))
        for gait in result.get("gaits") or []
        for row in gait.get("metrics") or []
    }


def reference_from_result(
    result: Mapping[str, Any], previous: Mapping[str, Any] | None = None, *, model_changed: bool = False
) -> dict[NumberKey, float]:
    """회차 결과 dict(15.7 SessionResultOut 모양, 보고서 입력의 result) → 대조 기준값.

    previous(보고서 입력의 previous)를 주면 직전 회차 비교 표의 기준값(previous·change)도 넣는다. 두 회차의 분석 모델이
    다르면(inputs.ReportInput.previous_model_changed) model_changed를 넘겨 차이를 기준에서 뺀다.

    팀 서비스 워커는 DB에서 기준값을 만들지만(services/report_numbers.py), 기업 서버와 견본 스크립트
    (scripts/report_samples.py)는 분석 결과에서 같은 모양으로 만든다(8절 7번). 워커처럼 수치 행(metrics)만 읽고
    다리 비교 값은 12.3 식으로 다시 계산한다. 입력의 limb_compare는 읽지 않으므로, 그 값이 틀리면 VALUE_DIFFERS,
    metrics로 만들 수 없는 줄이면 NOT_IN_SOURCE가 된다. 왼쪽·오른쪽 값은 있는 쪽만, 차이는 양쪽이 있을 때만,
    대칭 지수는 합이 0이 아닐 때만 넣는다.

    한계: 보고서를 만든 입력과 같은 dict를 넘기면 수치 값 자체는 같은 곳에서 나오므로 틀려도 잡지 못한다(몸 전체 수치와
    측정된 수치 값). 그 값까지 대조하려면 보고서 입력과 따로 가진 분석 결과를 넘겨야 한다.
    """
    reference: dict[NumberKey, float] = {}
    for gait in result.get("gaits") or []:
        gait_type = str(gait.get("gait_type"))
        values: dict[tuple[str, str], float | None] = {}
        for row in gait.get("metrics") or []:
            code, limb = str(row.get("metric_code")), str(row.get("limb"))
            value = values[(code, limb)] = _finite(row.get("value"))
            if value is not None:
                reference[(gait_type, code, limb, "metric")] = value
        for code in dict.fromkeys(code for code, limb in values if limb != "NONE"):
            for pair, (left_limb, right_limb) in PAIR_LIMBS.items():
                left, right = values.get((code, left_limb)), values.get((code, right_limb))
                if left is not None:
                    reference[(gait_type, code, pair, "left")] = left
                if right is not None:
                    reference[(gait_type, code, pair, "right")] = right
                if left is None or right is None:
                    continue
                try:
                    diff, symmetry = pair_numbers(Decimal(str(left)), Decimal(str(right)))
                except InvalidOperation:  # 반올림할 수 없을 만큼 큰 값. 기준에 넣지 않아 NOT_IN_SOURCE가 된다
                    continue
                reference[(gait_type, code, pair, "diff")] = float(diff)
                if symmetry is not None:
                    reference[(gait_type, code, pair, "symmetry_index")] = float(symmetry)
    if previous:
        reference.update(previous_reference(_limb_values(result), _limb_values(previous), model_changed=model_changed))
    return reference
