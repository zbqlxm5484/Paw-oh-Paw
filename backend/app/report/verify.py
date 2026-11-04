"""수치 대조(명세 8절 만드는 순서 7의 첫 항목, PR-F08-12, 17.4 BE-15, S15P31A404-196).

보고서 모듈이 돌려준 "실린 숫자 목록"(numbers.ListedNumber: 보행 유형·수치 코드·다리 또는 쌍·종류·값)을 기준값과 맞춘다.
기준값은 부르는 쪽이 준다. 팀 서비스는 DB의 session_metric 값과 15.7 다리 비교 계산값으로 만들고
(app/services/report_numbers.py), 기업 서버는 분석 결과에서 같은 모양으로 만들면 된다. 이 모듈은 DB를 모른다(11.3).

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
from typing import Any

from app.report.numbers import ListedNumber

# (보행 유형, 수치 코드, 다리 또는 쌍, 종류). 종류는 metric·left·right·diff·symmetry_index(numbers.ListedNumber.kind)
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


# 15.7 다리 비교 줄의 종류(services/report_numbers.py의 PAIR_KINDS와 같다)
PAIR_KINDS = ("left", "right", "diff", "symmetry_index")


def reference_from_result(result: Mapping[str, Any]) -> dict[NumberKey, float]:
    """회차 결과 dict(15.7 SessionResultOut 모양, 보고서 입력의 result) → 대조 기준값.

    팀 서비스 워커는 DB에서 기준값을 만들지만(services/report_numbers.py), 기업 서버와 견본 스크립트
    (scripts/report_samples.py)는 분석 결과에서 같은 모양으로 만든다(8절 7번). 규칙은 같다: 측정된 수치 값, 쌍의
    왼쪽·오른쪽 값은 비교할 수 없어도, 차이·대칭 지수는 비교할 수 있을 때만.
    """
    reference: dict[NumberKey, float] = {}
    for gait in result.get("gaits") or []:
        gait_type = str(gait.get("gait_type"))
        for row in gait.get("metrics") or []:
            if row.get("value") is not None:
                reference[(gait_type, str(row["metric_code"]), str(row["limb"]), "metric")] = float(row["value"])
        for entry in gait.get("limb_compare") or []:
            comparable = bool(entry.get("comparable"))
            for kind in PAIR_KINDS:
                value = entry.get(kind)
                if value is not None and (comparable or kind in ("left", "right")):
                    reference[(gait_type, str(entry["metric_code"]), str(entry["pair"]), kind)] = float(value)
    return reference
