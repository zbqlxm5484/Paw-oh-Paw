"""회차 비교 오차 범위 파일 읽기(services/tolerance.py, 명세 15.8·16절 TOLERANCE_FILE, S15P31A404-197)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.services.aggregation import METRICS
from app.services.tolerance import ToleranceFileError, get_tolerance, load_tolerance

ROOT = Path(__file__).resolve().parents[1]


def test_the_shipped_file_has_the_provisional_values_from_the_handover_doc() -> None:
    tolerance = load_tolerance(ROOT / get_settings().TOLERANCE_FILE)
    assert tolerance == {
        "rom_shoulder": 2.5,
        "rom_elbow": 4.4,
        "rom_carpus": 7.6,
        "rom_hip": 3.6,
        "rom_stifle": 4.2,
        "rom_tarsus": 4.0,
        "stance_ratio": 5.0,
    }
    assert set(tolerance) <= {metric.code for metric in METRICS}


def test_an_empty_file_means_no_tolerance_at_all(tmp_path: Path) -> None:
    file = tmp_path / "tolerance.yaml"
    file.write_text("# 아직 값이 없다\n", encoding="utf-8")
    assert load_tolerance(file) == {}


def test_a_missing_file_is_empty_with_a_warning_and_no_path_in_the_log(tmp_path: Path, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="app.services.tolerance"):
        assert load_tolerance(tmp_path / "none.yaml") == {}
    assert any("tolerance file not found" in message for message in caplog.messages)
    assert not any(str(tmp_path) in message for message in caplog.messages)


@pytest.mark.parametrize(
    ("content", "fragment"),
    [
        ("- rom_stifle\n", "매핑"),
        ("rom_knee: 3.0\n", "모르는 수치 코드"),
        ("rom_stifle: -1\n", "0 이상의 숫자"),
        ("rom_stifle: '3.0'\n", "0 이상의 숫자"),
        ("rom_stifle: true\n", "0 이상의 숫자"),
    ],
)
def test_bad_shapes_are_rejected_with_a_reason(tmp_path: Path, content: str, fragment: str) -> None:
    file = tmp_path / "tolerance.yaml"
    file.write_text(content, encoding="utf-8")
    with pytest.raises(ToleranceFileError, match=fragment):
        load_tolerance(file)


def test_get_tolerance_reads_once_per_path_and_returns_a_copy(tmp_path: Path) -> None:
    file = tmp_path / "tolerance.yaml"
    file.write_text("rom_stifle: 3\n", encoding="utf-8")
    first = get_tolerance(str(file))
    assert first == {"rom_stifle": 3.0}
    first["rom_stifle"] = 99.0
    file.write_text("rom_stifle: 4\n", encoding="utf-8")
    assert get_tolerance(str(file)) == {"rom_stifle": 3.0}  # 캐시된 값, 복사본
