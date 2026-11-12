"""견본 보고서 입력(D-08, 명세 8절 입력, S15P31A404-200). 경우별 입력 dict를 만든다. DB와 app을 모른다(11.3).

경우 목록은 조영운 제안이고 기업 승인 전이다(계획 문서 "경우 목록은 기업 승인"). scripts/report_samples.py가 이 목록으로
판본별 PDF를 만들고 생성 시간(KPI-29, 20초)을 잰다. 수치는 지어낸 값이되 15.7 다리 비교 값(diff·symmetry_index)은
12.3 식(Decimal, 넷째·둘째 자리)으로 맞춰 두어, 실린 숫자 대조(report/verify.py)를 그대로 통과한다. 다리 비교 줄의
순서도 결과 조회와 같다(compare_rank. 요약 문장이 "비율로 가장 큰 항목"을 첫 줄에서 고르므로 순서가 내용이다).

경우(이름 → 뜻):
- first: 첫 회차. 평보·속보 모두 왼쪽·오른쪽 통과가 8회씩이다. 직전 회차 없음
- follow_up: 직전 회차가 있고 오차 범위가 있다. 증가·감소·범위 안·기준 없는 수치(값만)·통과 부족(값만)이 섞인다
- model_changed: 직전 회차의 분석 모델이 다르다. 값만 적고 변화를 판단하지 않는다
- unmeasurable: 측정 불가 수치(NOT_ENOUGH_CYCLES·LOW_CONFIDENCE)와 좌우 비교 불가 줄이 있다. 통과가 좌우 5회씩이라
  좌우 차이를 오차 범위와 견주지 않는다
- one_side: 한쪽 방향만 찍혔다(ONE_SIDE_ONLY). 오른쪽 다리는 전부 NO_PASS_FOR_LIMB, 좌우 비교 불가
- no_passes: 유효 통과가 0건인 DONE 회차. 수치 표 없이 다시 촬영 안내만 있다

통과 수도 집계 규칙(services/aggregation.py)에 맞춘다. 왼쪽 통과는 LF·LH, 오른쪽 통과는 RF·RH의 값만 내므로 다리의
n_passes는 그 쪽 통과 수를 넘지 못하고, 몸 전체 수치(NONE)는 양쪽의 합까지다. 증가·감소·범위 안은 두 회차 모두 8회
이상이어야 붙으므로(judge.usable_tolerance), 판정을 보여 주는 경우는 좌우 8회씩 둔다.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.report.pairs import pair_numbers

SESSION_ID = "a4e9b3c2-1d2e-4f5a-8b6c-7d8e9f0a1b2c"
PREVIOUS_SESSION_ID = "9b8a7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d"
DOG_ID = "b1c2d3e4-f5a6-4b7c-8d9e-0f1a2b3c4d5e"
MODEL_VERSION = "0.4.0/v1/a4261a10"
OLD_MODEL_VERSION = "0.3.0/v1/7c1d2e3f"
MEASURED_ON = "2026-11-04"
PREVIOUS_MEASURED_ON = "2026-10-14"
EDITIONS = ("OWNER", "VET")

# config/tolerance.yaml의 값과 같다(15.8, 11-11 권장 촬영 횟수 분석 값). 스크립트는 실제 파일 값을 넣어 준다
PROVISIONAL_TOLERANCE: dict[str, float] = {
    "rom_shoulder": 5.0,
    "rom_carpus": 11.8,
    "rom_hip": 5.0,
    "rom_stifle": 8.0,
    "rom_tarsus": 5.9,
    "stance_ratio": 5.8,
}

# 14.3·14.4 사유 문구(messages/ko.yaml과 같은 글). 패키지는 문구 파일을 읽지 않으므로 입력에 넣어 준다
MESSAGES = {
    "NOT_ENOUGH_CYCLES": "보행 주기가 부족해 계산하지 못했습니다.",
    "LOW_CONFIDENCE": "관절점 인식이 불안정해 계산하지 못했습니다.",
    "NO_PASS_FOR_LIMB": "이 다리를 잴 유효 통과가 없습니다. 반대 방향으로도 걷게 해 주세요.",
    "NO_DATA": "이 회차에는 이 수치가 없습니다.",
    "STOPPED": "중간에 멈췄습니다.",
    "TOWARD_CAMERA": "카메라 쪽으로 걸었습니다. 옆으로 일직선으로 걷게 해 주세요.",
    "NOT_SIDE_VIEW": "옆모습이 찍히지 않았습니다.",
    "ONE_SIDE_ONLY": "좌우 비교: 측정 조건상 비교할 수 없습니다. 반대 방향으로도 걷게 해 주세요.",
}
UNITS = {
    "rom_shoulder": "deg",
    "rom_elbow": "deg",
    "rom_carpus": "deg",
    "rom_hip": "deg",
    "rom_stifle": "deg",
    "rom_tarsus": "deg",
    "stifle_cv": "pct",
    "paw_lift": "pct_body",
    "stride_length": "pct_body",
    "stance_ratio": "pct",
    "walk_speed": "body_per_sec",
    "gait_cycles": "count",
}
FORE = ("LF", "RF")
HIND = ("LH", "RH")


def reason(code: str | None) -> dict | None:
    return None if code is None else {"code": code, "message": MESSAGES.get(code, code)}


def metric(code: str, limb: str, value: float | None, *, n: int, reason_code: str | None = None) -> dict:
    return {
        "metric_code": code,
        "limb": limb,
        "value": value,
        "unit": UNITS[code],
        "measurable": value is not None,
        "unmeasurable_reason": reason(reason_code),
        "n_passes": n,
    }


def compare(pair: str, code: str, left: float | None, right: float | None, *, reason_code: str | None = None) -> dict:
    """15.7 다리 비교 한 줄. diff = 왼쪽 − 오른쪽(넷째 자리), 대칭 지수는 12.3 식(둘째 자리)."""
    comparable = left is not None and right is not None
    diff = symmetry = None
    if comparable:
        diff_d, symmetry_d = pair_numbers(Decimal(str(left)), Decimal(str(right)))
        diff = float(diff_d)
        symmetry = None if symmetry_d is None else float(symmetry_d)
    return {
        "pair": pair,
        "metric_code": code,
        "unit": UNITS[code],
        "left": left,
        "right": right,
        "diff": diff,
        "symmetry_index": symmetry,
        "comparable": comparable,
        "reason": None if comparable else reason(reason_code or "NO_DATA"),
    }


def compare_rank(line: Mapping[str, Any]) -> tuple[int, float]:
    """15.7 다리 비교 줄 순서: 대칭 지수가 있는 줄을 큰 순서로 → 지수만 없는 비교 가능 줄 → 비교할 수 없는 줄.

    결과 조회(services/session_results.py의 _compare_rank)와 같은 규칙이다. 이 패키지는 app.services를 모르므로(11.3)
    규칙을 여기 둔다. 같은 값끼리는 만든 순서(12.3 표, 앞다리 쌍 → 뒷다리 쌍)를 지킨다(sorted는 안정 정렬).
    """
    symmetry = line.get("symmetry_index")
    if symmetry is not None:
        return (0, -float(symmetry))
    return (1, 0.0) if line.get("comparable") else (2, 0.0)


def _pairs(rows: list[dict]) -> list[dict]:
    """수치 행에서 15.7 다리 비교 줄을 만들고 compare_rank 순서로 정렬한다(같은 값은 12.3 표, 앞다리 쌍 → 뒷다리 쌍)."""
    by_key = {(row["metric_code"], row["limb"]): row for row in rows}
    lines: list[dict] = []
    for code in dict.fromkeys(row["metric_code"] for row in rows if row["limb"] != "NONE"):
        for pair, (left_limb, right_limb) in (("FORE", FORE), ("HIND", HIND)):
            left, right = by_key.get((code, left_limb)), by_key.get((code, right_limb))
            if left is None and right is None:
                continue
            missing = next((row for row in (left, right) if row is not None and row["value"] is None), None)
            lines.append(
                compare(
                    pair,
                    code,
                    None if left is None else left["value"],
                    None if right is None else right["value"],
                    reason_code=(missing["unmeasurable_reason"] or {}).get("code") if missing else None,
                )
            )
    return sorted(lines, key=compare_rank)


def gait(gait_type: str, rows: list[dict]) -> dict:
    return {"gait_type": gait_type, "metrics": rows, "limb_compare": _pairs(rows)}


def result(
    gaits: list[dict],
    *,
    passes: tuple[int, int, int],
    shots: tuple[int, int, int],
    session_id: str = SESSION_ID,
    measured_on: str = MEASURED_ON,
    model_version: str | None = MODEL_VERSION,
    exclude_summary: list[dict] | None = None,
    notices: list[dict] | None = None,
) -> dict:
    """15.7 SessionResultOut 모양의 회차 결과."""
    measured, used, excluded = passes
    total, failed, invalid = shots
    return {
        "id": session_id,
        "dog_id": DOG_ID,
        "staff": {"id": "c0ffee00-0000-4000-8000-000000000001", "name": "김담당"},
        "measured_on": measured_on,
        "weight_kg": 12.5,
        "size_class": "MEDIUM",
        "status": "DONE",
        "fail_reason": None,
        "model_name": "fs-v4",
        "model_version": model_version,
        "completed_at": f"{measured_on}T03:10:00Z",
        "aggregated_at": f"{measured_on}T03:10:20Z",
        "created_at": f"{measured_on}T02:50:00Z",
        "updated_at": f"{measured_on}T03:10:20Z",
        "pass_counts": {"measured": measured, "used": used, "excluded": excluded},
        "shot_counts": {"total": total, "failed": failed, "invalid": invalid},
        "exclude_summary": exclude_summary
        if exclude_summary is not None
        else [{**reason("NOT_SIDE_VIEW"), "count": excluded}]
        if excluded
        else [],
        "notices": notices or [],
        "gaits": gaits,
    }


def _trot_rows(left: int, right: int, **overrides: tuple[float | None, float | None]) -> list[dict]:
    """속보 수치 전부. left·right는 왼쪽·오른쪽 유효 통과 수, overrides는 수치 코드 → (왼쪽, 오른쪽) 값."""
    values: dict[str, tuple[float | None, float | None]] = {
        "rom_shoulder": (28.5, 27.9),
        "rom_elbow": (55.1, 52.0),
        "rom_carpus": (60.4, 58.8),
        "rom_hip": (41.9, 40.2),
        "rom_stifle": (47.3, 43.1),
        "rom_tarsus": (35.0, 36.4),
        "stifle_cv": (6.2, 7.5),
    }
    values.update(overrides)
    rows: list[dict] = []
    for code, (left_value, right_value) in values.items():
        left_limb, right_limb = FORE if code in ("rom_shoulder", "rom_elbow", "rom_carpus") else HIND
        rows.append(metric(code, left_limb, left_value, n=left))
        rows.append(metric(code, right_limb, right_value, n=right))
    rows += [
        metric("paw_lift", "LF", 12.4, n=left),
        metric("paw_lift", "RF", 12.1, n=right),
        metric("paw_lift", "LH", 10.8, n=left),
        metric("paw_lift", "RH", 10.2, n=right),
        metric("stride_length", "LF", 142.0, n=left),
        metric("stride_length", "RF", 140.5, n=right),
        metric("stride_length", "LH", 138.2, n=left),
        metric("stride_length", "RH", 133.4, n=right),
        metric("stance_ratio", "LF", 58.2, n=left),
        metric("stance_ratio", "RF", 59.1, n=right),
        metric("stance_ratio", "LH", 61.0, n=left),
        metric("stance_ratio", "RH", 62.3, n=right),
        metric("walk_speed", "NONE", 2.41, n=left + right),
        metric("gait_cycles", "NONE", left + right, n=left + right),
    ]
    return rows


def _walk_rows(left: int, right: int) -> list[dict]:
    return [
        metric("rom_hip", "LH", 33.4, n=left),
        metric("rom_hip", "RH", 32.8, n=right),
        metric("rom_stifle", "LH", 38.6, n=left),
        metric("rom_stifle", "RH", 36.9, n=right),
        metric("stance_ratio", "LH", 64.5, n=left),
        metric("stance_ratio", "RH", 65.2, n=right),
        metric("walk_speed", "NONE", 1.62, n=left + right),
        metric("gait_cycles", "NONE", left + right, n=left + right),
    ]


def _previous_result(model_version: str = MODEL_VERSION) -> dict:
    """직전 회차(2026-10-14). 속보만. follow_up 경우에 증가·감소·범위 안·값만이 섞이도록 값을 둔다."""
    rows = _trot_rows(
        8,
        8,
        rom_stifle=(38.0, 44.0),  # LH +9.3 > 8.0 증가, RH −0.9 범위 안
        rom_hip=(48.5, 40.6),  # LH −6.6 < −5.0 감소, RH는 통과 부족(아래)으로 값만
        rom_tarsus=(30.5, 36.0),  # LH +4.5 > 4.0 증가, RH +0.4 범위 안
        rom_elbow=(50.0, 50.0),  # 오차 범위 없음 → 값만
    )
    previous_values = {
        ("stance_ratio", "LH"): 57.0,  # +4.0 ≤ 5.0 범위 안
        ("stifle_cv", "LH"): 7.0,  # 오차 범위 없음 → 값만
        ("stifle_cv", "RH"): 8.1,
        ("paw_lift", "LF"): 11.9,
        ("paw_lift", "RF"): 12.3,
        ("paw_lift", "LH"): 10.1,
        ("paw_lift", "RH"): 10.6,
        ("stride_length", "LF"): 139.5,
        ("stride_length", "RF"): 138.0,
        ("stride_length", "LH"): 134.0,
        ("stride_length", "RH"): 131.2,
        ("walk_speed", "NONE"): 2.25,
    }
    for row in rows:
        if row["metric_code"] == "rom_hip" and row["limb"] == "RH":
            row["n_passes"] = 5  # 통과 부족 → 값만
        value = previous_values.get((row["metric_code"], row["limb"]))
        if value is not None:
            row["value"] = value
    return result(
        [gait("TROT", rows)],
        session_id=PREVIOUS_SESSION_ID,
        measured_on=PREVIOUS_MEASURED_ON,
        model_version=model_version,
        passes=(18, 16, 2),
        shots=(16, 0, 1),
    )


def _first() -> tuple[dict, dict | None]:
    gaits = [gait("WALK", _walk_rows(8, 8)), gait("TROT", _trot_rows(8, 8))]
    return result(gaits, passes=(34, 32, 2), shots=(16, 0, 1)), None


def _follow_up() -> tuple[dict, dict | None]:
    gaits = [gait("WALK", _walk_rows(3, 3)), gait("TROT", _trot_rows(8, 8))]
    return result(gaits, passes=(24, 22, 2), shots=(16, 0, 1)), _previous_result()


def _model_changed() -> tuple[dict, dict | None]:
    current = result([gait("TROT", _trot_rows(8, 8))], passes=(18, 16, 2), shots=(16, 0, 1))
    return current, _previous_result(model_version=OLD_MODEL_VERSION)


def _unmeasurable() -> tuple[dict, dict | None]:
    rows = _trot_rows(5, 5, rom_hip=(41.9, None), rom_carpus=(None, 58.8), stifle_cv=(None, 7.5))
    for row in rows:
        if row["value"] is None:
            row["unmeasurable_reason"] = reason(
                "LOW_CONFIDENCE" if row["metric_code"] == "rom_carpus" else "NOT_ENOUGH_CYCLES"
            )
    return result([gait("TROT", rows)], passes=(12, 10, 2), shots=(8, 0, 2)), None


def _one_side() -> tuple[dict, dict | None]:
    rows = _trot_rows(6, 0)
    for row in rows:
        if row["limb"] in ("RF", "RH"):
            row.update(value=None, measurable=False, unmeasurable_reason=reason("NO_PASS_FOR_LIMB"), n_passes=0)
    return (
        result([gait("TROT", rows)], passes=(6, 6, 0), shots=(3, 0, 0), notices=[reason("ONE_SIDE_ONLY")]),
        None,
    )


def _no_passes() -> tuple[dict, dict | None]:
    summary = [{**reason("STOPPED"), "count": 3}, {**reason("TOWARD_CAMERA"), "count": 2}]
    return result([], passes=(5, 0, 5), shots=(3, 0, 3), exclude_summary=summary), None


@dataclass(frozen=True)
class SampleCase:
    name: str
    title: str
    summary: str
    build: Callable[[], tuple[dict, dict | None]]  # (회차 결과, 직전 회차 결과 또는 None)


CASES: tuple[SampleCase, ...] = (
    SampleCase("first", "첫 회차", "양방향 통과 충분, 평보·속보 둘 다, 직전 회차 없음", _first),
    SampleCase(
        "follow_up", "재측정(직전 회차 있음)", "오차 범위 판정: 증가·감소·범위 안·값만(기준 없음·통과 부족)", _follow_up
    ),
    SampleCase(
        "model_changed", "분석 모델 바뀜", "직전 회차와 모델이 달라 값만 적고 변화를 판단하지 않음", _model_changed
    ),
    SampleCase(
        "unmeasurable",
        "측정 불가 수치 포함",
        "NOT_ENOUGH_CYCLES·LOW_CONFIDENCE, 좌우 비교 불가 줄, 통과 부족",
        _unmeasurable,
    ),
    SampleCase(
        "one_side", "한쪽 방향만 촬영", "ONE_SIDE_ONLY, 오른쪽 다리 NO_PASS_FOR_LIMB, 좌우 비교 불가", _one_side
    ),
    SampleCase("no_passes", "유효 통과 0건", "수치 표 없이 다시 촬영 안내만", _no_passes),
)
CASE_BY_NAME = {case.name: case for case in CASES}


def case_names() -> list[str]:
    return [case.name for case in CASES]


def sample_input(case: str, edition: str = "OWNER", *, tolerance: Mapping[str, float] | None = None) -> dict[str, Any]:
    """경우 이름과 판본 → 보고서 입력 dict(app/report/inputs.py 머리말 모양)."""
    if case not in CASE_BY_NAME:
        raise KeyError(f"모르는 견본 경우입니다: {case!r} (있는 것: {', '.join(case_names())})")
    if edition not in EDITIONS:
        raise KeyError(f"모르는 판본입니다: {edition!r}")
    current, previous = CASE_BY_NAME[case].build()
    return {
        "edition": edition,
        "dog": {
            "name": "보리",
            "breed": "웰시코기",
            "weight_kg": 12.5,
            "size_class": "MEDIUM",
            "sex": "FEMALE_SPAYED",
            "birth_year": 2021,
        },
        "session": {
            "id": current["id"],
            "measured_on": current["measured_on"],
            "weight_kg": current["weight_kg"],
            "size_class": current["size_class"],
            "model_name": current["model_name"],
            "model_version": current["model_version"],
        },
        "result": current,
        "previous": previous,
        "settings": {"tolerance": dict(tolerance if tolerance is not None else PROVISIONAL_TOLERANCE)},
    }
