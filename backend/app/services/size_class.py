"""체급 분류(명세 12.5). DB·설정을 읽지 않는 순수 함수라 박규원의 D-14 코드도 그대로 쓴다.

규칙(박규원의 체급 기준 자료, 2026-10-22): 등록 체중만으로 나눈다. 견종은 보지 않는다.
  small_max_kg 미만 SMALL, medium_max_kg 미만 MEDIUM, 그 이상 LARGE.
  기준값은 설정(16절 SIZE_SMALL_MAX_KG=10, SIZE_MEDIUM_MAX_KG=25)이고 부르는 쪽이 넘긴다.
  10.00 kg은 MEDIUM, 25.00 kg은 LARGE다(경계값은 위 구간에 들어간다).

견종 목록(config/breeds.yaml)은 화면의 견종 자동완성용 이름 목록일 뿐 체급 분류에는 쓰지 않는다.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

from app.models.enums import SizeClass

DEFAULT_SMALL_MAX_KG = Decimal("10")
DEFAULT_MEDIUM_MAX_KG = Decimal("25")


class BreedListError(ValueError):
    """견종 목록 파일의 모양이 잘못되었을 때."""


def load_breeds(path: str | Path) -> list[str]:
    """견종 목록을 읽는다. 설정 파일이라 open()으로 읽고 인코딩을 꼭 적는다. 이름은 앞뒤 공백을 지우고 중복은 뺀다."""
    with Path(path).open(encoding="utf-8") as file:
        rows = yaml.safe_load(file) or []
    if not isinstance(rows, list):
        raise BreedListError(f"{path}: 견종 이름 목록(- 이름)이어야 합니다")
    names: list[str] = []
    for row in rows:
        if not isinstance(row, str) or not row.strip():
            raise BreedListError(f"{path}: 각 줄은 비어 있지 않은 견종 이름이어야 합니다: {row!r}")
        name = row.strip()
        if name not in names:
            names.append(name)
    return names


@lru_cache
def _cached_breeds(path: str) -> tuple[str, ...]:
    return tuple(load_breeds(path))


def get_breeds(path: str) -> tuple[str, ...]:
    """견종 목록을 처음 쓸 때 한 번 읽는다(바뀌지 않는 값은 읽어 두어도 된다, 11.3)."""
    return _cached_breeds(path)


def classify_size(
    weight_kg: Decimal,
    *,
    small_max_kg: Decimal = DEFAULT_SMALL_MAX_KG,
    medium_max_kg: Decimal = DEFAULT_MEDIUM_MAX_KG,
) -> str:
    """SMALL · MEDIUM · LARGE 중 하나. 9.99 kg은 SMALL, 10.00·24.99 kg은 MEDIUM, 25.00 kg은 LARGE(17.2)."""
    weight = Decimal(weight_kg)
    if weight < small_max_kg:
        return SizeClass.SMALL.value
    if weight < medium_max_kg:
        return SizeClass.MEDIUM.value
    return SizeClass.LARGE.value
