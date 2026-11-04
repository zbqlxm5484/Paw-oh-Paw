"""회차 비교 오차 범위 읽기(명세 5절 비교 규칙, 15.8 판정 표, 16절 TOLERANCE_FILE, S15P31A404-197).

config/tolerance.yaml은 수치 코드(12.3) → 원 단위 오차 범위의 평평한 매핑이다. 보고서 입력의 settings.tolerance(8절)와
비교 API(15.8, services/compare.py)가 같은 값을 쓴다. 판정 자체는 report/judge.py가 한다.

- 파일이 없으면 비어 있는 것과 같다(기업 값을 받기 전 상태, 15.8). 경고 로그를 남긴다.
- 파일 모양이 틀리면(매핑이 아님, 모르는 수치 코드, 숫자가 아니거나 음수) ToleranceFileError. 워커는 시작할 때 읽으므로
  바로 멈춰 보인다(16절의 WORKER_* 검사와 같은 뜻).
- 설정 파일은 바뀌지 않으므로 경로별로 한 번만 읽는다(11.3, breeds와 같다). 로그에는 경로를 적지 않는다(11.8).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import yaml

from app.services.aggregation import METRICS

logger = logging.getLogger("app.services.tolerance")

METRIC_CODES = frozenset(metric.code for metric in METRICS)


class ToleranceFileError(ValueError):
    """오차 범위 파일의 모양이 잘못되었을 때."""


def load_tolerance(path: str | Path) -> dict[str, float]:
    """오차 범위 파일 → {수치 코드: 오차 범위}. 없으면 빈 dict, 모양이 틀리면 ToleranceFileError."""
    file = Path(path)
    if not file.exists():
        logger.warning("tolerance file not found; every change judgement will be UNKNOWN (RANGE_NOT_SET)")
        return {}
    with file.open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ToleranceFileError(f"{file.name}: 수치 코드 → 오차 범위 매핑이어야 합니다")
    tolerance: dict[str, float] = {}
    for code, raw in data.items():
        if code not in METRIC_CODES:
            raise ToleranceFileError(f"{file.name}: 모르는 수치 코드입니다(12.3 표): {code!r}")
        if isinstance(raw, bool) or not isinstance(raw, int | float) or raw < 0:
            raise ToleranceFileError(f"{file.name}: {code}의 오차 범위는 0 이상의 숫자여야 합니다: {raw!r}")
        tolerance[str(code)] = float(raw)
    return tolerance


@lru_cache
def _cached(path: str) -> tuple[tuple[str, float], ...]:
    return tuple(load_tolerance(path).items())


def get_tolerance(path: str) -> dict[str, float]:
    """오차 범위를 처음 쓸 때 한 번 읽는다. 돌려주는 dict는 복사본이라 고쳐도 캐시는 그대로다."""
    return dict(_cached(path))
