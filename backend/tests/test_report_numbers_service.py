"""보고서 수치 대조의 기준값(services/report_numbers.py, 8절 7번 첫 항목, S15P31A404-196).

DB의 session_metric 행에서 수치 값과 15.7 다리 비교 계산값(반올림 포함)을 report.verify의 키로 뽑는다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.dates import today_local
from app.models import MeasureSession, SessionMetric
from app.services.report_numbers import reference_numbers

Row = tuple[str, str, str, str | None, str]  # gait_type, metric_code, limb, value, unit


def _session(db: Session, dog, staff, rows: list[Row]) -> MeasureSession:
    now = datetime.now(UTC)
    session = MeasureSession(
        dog_id=dog.id,
        staff_id=staff.id,
        measured_on=today_local(),
        size_class="MEDIUM",
        status="DONE",
        model_name="fs-v4",
        model_version="0.4.0/v1/a4261a10",
        completed_at=now,
        aggregated_at=now,
    )
    db.add(session)
    db.flush()
    for gait_type, code, limb, value, unit in rows:
        db.add(
            SessionMetric(
                session_id=session.id,
                gait_type=gait_type,
                limb=limb,
                metric_code=code,
                value=None if value is None else Decimal(value),
                unit=unit,
                measurable=value is not None,
                unmeasurable_reason=None if value is not None else "NOT_ENOUGH_CYCLES",
                n_passes=2,
            )
        )
    db.flush()
    return session


def test_reference_has_metric_values_and_pair_numbers_rounded_as_in_the_result_api(db: Session, dog, staff) -> None:
    session = _session(
        db,
        dog,
        staff,
        [
            ("TROT", "rom_stifle", "LH", "31.0", "deg"),
            ("TROT", "rom_stifle", "RH", "38.2", "deg"),
            ("TROT", "walk_speed", "NONE", "2.41", "body_per_sec"),
        ],
    )
    reference = reference_numbers(db, session.id)
    assert reference == {
        ("TROT", "rom_stifle", "LH", "metric"): 31.0,
        ("TROT", "rom_stifle", "RH", "metric"): 38.2,
        ("TROT", "walk_speed", "NONE", "metric"): 2.41,
        ("TROT", "rom_stifle", "HIND", "left"): 31.0,
        ("TROT", "rom_stifle", "HIND", "right"): 38.2,
        ("TROT", "rom_stifle", "HIND", "diff"): -7.2,  # BE-21의 예
        ("TROT", "rom_stifle", "HIND", "symmetry_index"): 20.81,
    }


def test_unmeasurable_rows_give_no_numbers_but_the_other_side_is_still_a_number(db: Session, dog, staff) -> None:
    session = _session(
        db, dog, staff, [("TROT", "rom_hip", "LH", "41.9", "deg"), ("TROT", "rom_hip", "RH", None, "deg")]
    )
    reference = reference_numbers(db, session.id)
    assert reference == {("TROT", "rom_hip", "LH", "metric"): 41.9, ("TROT", "rom_hip", "HIND", "left"): 41.9}


def test_gaits_are_kept_apart_and_fore_pairs_use_the_front_limbs(db: Session, dog, staff) -> None:
    session = _session(
        db,
        dog,
        staff,
        [
            ("WALK", "paw_lift", "LF", "10.5", "pct_body"),
            ("WALK", "paw_lift", "RF", "10.5", "pct_body"),
            ("TROT", "paw_lift", "LF", "12.25", "pct_body"),
        ],
    )
    reference = reference_numbers(db, session.id)
    assert reference[("WALK", "paw_lift", "FORE", "diff")] == 0.0
    assert reference[("WALK", "paw_lift", "FORE", "symmetry_index")] == 0.0
    assert reference[("TROT", "paw_lift", "LF", "metric")] == 12.25
    assert ("TROT", "paw_lift", "FORE", "right") not in reference and (
        "TROT",
        "paw_lift",
        "FORE",
        "diff",
    ) not in reference


def test_unknown_session_has_no_reference_numbers(db: Session) -> None:
    assert reference_numbers(db, uuid.uuid4()) == {}


def test_reference_is_read_fresh_from_the_database(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff, [("TROT", "rom_stifle", "LH", "47.3", "deg")])
    assert reference_numbers(db, session.id)[("TROT", "rom_stifle", "LH", "metric")] == 47.3
    row = db.query(SessionMetric).filter(SessionMetric.session_id == session.id).one()
    row.value = Decimal("40.0")
    db.flush()
    assert reference_numbers(db, session.id)[("TROT", "rom_stifle", "LH", "metric")] == 40.0
