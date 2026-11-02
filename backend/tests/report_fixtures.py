"""보고서 모듈 테스트용 입력 견본(8절 입력, 15.7 SessionResultOut 모양). scripts/make_report.py --sample도 쓴다."""

from __future__ import annotations

from typing import Any

SESSION_ID = "a4e9b3c2-1d2e-4f5a-8b6c-7d8e9f0a1b2c"
DOG_ID = "b1c2d3e4-f5a6-4b7c-8d9e-0f1a2b3c4d5e"
MODEL_VERSION = "0.4.0/v1/a4261a10"


def metric(code: str, limb: str, value: float | None, unit: str = "deg", reason: str | None = None, n: int = 2) -> dict:
    return {
        "metric_code": code,
        "limb": limb,
        "value": value,
        "unit": unit,
        "measurable": value is not None,
        "unmeasurable_reason": {"code": reason, "message": f"{reason} 메시지"} if reason else None,
        "n_passes": n,
    }


def compare(
    pair: str, code: str, left: float | None, right: float | None, unit: str = "deg", reason: str | None = None
) -> dict:
    comparable = left is not None and right is not None
    diff = round(left - right, 2) if comparable else None
    mean = (left + right) / 2 if comparable else None
    symmetry = round(abs(diff) / mean * 100, 2) if comparable and mean else None
    return {
        "pair": pair,
        "metric_code": code,
        "unit": unit,
        "left": left,
        "right": right,
        "diff": diff,
        "symmetry_index": symmetry,
        "comparable": comparable,
        "reason": {"code": reason, "message": f"{reason} 메시지"} if reason else None,
    }


def sample_result(**overrides: Any) -> dict:
    """DONE 회차의 결과: 속보 하나, 뒷다리 수치 4종(고관절 오른쪽은 측정 불가), 전체 수치 2종, 다리 비교 2줄."""
    result = {
        "id": SESSION_ID,
        "dog_id": DOG_ID,
        "staff": {"id": "c0ffee00-0000-4000-8000-000000000001", "name": "김담당"},
        "measured_on": "2026-11-02",
        "weight_kg": 12.5,
        "size_class": "MEDIUM",
        "status": "DONE",
        "fail_reason": None,
        "model_name": "fs-v4",
        "model_version": MODEL_VERSION,
        "completed_at": "2026-11-02T03:10:00Z",
        "aggregated_at": "2026-11-02T03:10:20Z",
        "created_at": "2026-11-02T02:50:00Z",
        "updated_at": "2026-11-02T03:10:20Z",
        "pass_counts": {"measured": 6, "used": 5, "excluded": 1},
        "shot_counts": {"total": 4, "failed": 0, "invalid": 1},
        "exclude_summary": [{"code": "NOT_SIDE_VIEW", "message": "옆모습이 찍히지 않았습니다.", "count": 1}],
        "notices": [],
        "gaits": [
            {
                "gait_type": "TROT",
                "metrics": [
                    metric("rom_hip", "LH", 41.9),
                    metric("rom_hip", "RH", None, reason="NOT_ENOUGH_CYCLES"),
                    metric("rom_stifle", "LH", 47.3),
                    metric("rom_stifle", "RH", 43.1),
                    metric("stance_ratio", "LH", 58.2, unit="pct"),
                    metric("stance_ratio", "RH", 61.0, unit="pct"),
                    metric("walk_speed", "NONE", 2.41, unit="body_per_sec"),
                    metric("gait_cycles", "NONE", 9, unit="count", n=5),
                ],
                "limb_compare": [
                    compare("HIND", "rom_stifle", 47.3, 43.1),
                    compare("HIND", "rom_hip", 41.9, None, reason="NO_DATA"),
                ],
            }
        ],
    }
    result.update(overrides)
    return result


def sample_input(edition: str = "OWNER", previous: dict | None = None, **overrides: Any) -> dict:
    data = {
        "edition": edition,
        "dog": {
            "name": "제니",
            "breed": "말티즈",
            "weight_kg": 12.5,
            "size_class": "MEDIUM",
            "sex": "F",
            "birth_year": 2021,
        },
        "session": {
            "id": SESSION_ID,
            "measured_on": "2026-11-02",
            "weight_kg": 12.5,
            "size_class": "MEDIUM",
            "model_name": "fs-v4",
            "model_version": MODEL_VERSION,
        },
        "result": sample_result(),
        "previous": previous,
        "settings": {"tolerance": {"rom_stifle": 4.2, "rom_hip": 3.6}},
    }
    data.update(overrides)
    return data
