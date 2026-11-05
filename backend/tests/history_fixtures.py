"""측정 이력·회차 비교·추이 테스트의 공용 준비 함수(S15P31A404-198). DB 행을 바로 넣는다."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Dog, MeasureSession, Report, SessionMetric, Shot, WalkPass
from app.services.aggregation import METRICS

UNITS = {metric.code: metric.unit for metric in METRICS}
EPOCH = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)


def make_session(
    db: Session,
    dog,
    staff,
    measured_on: date,
    *,
    status: str = "DONE",
    model_version: str | None = "v1",
    seq: int = 0,
    weight: Decimal | None = None,
) -> MeasureSession:
    """회차 한 행. created_at은 측정일 + seq분이라 같은 날 회차의 순서를 seq로 정한다(12.5)."""
    created = EPOCH + timedelta(days=(measured_on - EPOCH.date()).days, minutes=seq)
    done = status == "DONE"
    session = MeasureSession(
        dog_id=dog.id,
        staff_id=staff.id,
        measured_on=measured_on,
        weight_kg=weight,
        size_class="LARGE",
        status=status,
        model_name=None if model_version is None else "fs-v4",
        model_version=model_version,
        created_at=created,
        completed_at=created if done else None,
        aggregated_at=created if done else None,
    )
    db.add(session)
    db.flush()
    return session


def add_metric(
    db: Session,
    session: MeasureSession,
    code: str,
    limb: str,
    value: float | None,
    *,
    gait: str = "TROT",
    n_passes: int = 8,
    reason: str | None = None,
) -> SessionMetric:
    """수치 한 행. value가 None이면 측정 불가(12.5: 0을 넣지 않는다)."""
    row = SessionMetric(
        session_id=session.id,
        gait_type=gait,
        limb=limb,
        metric_code=code,
        value=None if value is None else Decimal(str(value)),
        unit=UNITS[code],
        measurable=value is not None,
        unmeasurable_reason=reason,
        n_passes=n_passes,
    )
    db.add(row)
    db.flush()
    return row


def add_shot(
    db: Session, session: MeasureSession, seq_no: int, *, status: str = "DONE", passes: dict[str, tuple[int, int]]
) -> Shot:
    """촬영 한 건과 통과들. passes는 {camera_side: (유효 수, 제외 수)}."""
    shot = Shot(
        session_id=session.id,
        seq_no=seq_no,
        status=status,
        original_key=f"{uuid.uuid4()}/original.mp4",
        width=1920,
        height=1080,
        fps=Decimal("30"),
        duration_sec=Decimal("4.5"),
        bitrate_kbps=8000,
        codec="h264",
        uploaded_at=datetime.now(UTC),
    )
    db.add(shot)
    db.flush()
    pass_no = 1
    for side, (valid, excluded) in passes.items():
        for index in range(valid + excluded):
            is_valid = index < valid
            db.add(
                WalkPass(
                    shot_id=shot.id,
                    pass_no=pass_no,
                    camera_side=side,
                    gait_type="TROT" if is_valid else "OTHER",
                    is_valid=is_valid,
                    exclude_reason=None if is_valid else "STOPPED",
                    start_frame=pass_no * 100,
                    end_frame=pass_no * 100 + 50,
                )
            )
            pass_no += 1
    db.flush()
    return shot


def add_report(db: Session, session: MeasureSession, edition: str, status: str) -> Report:
    report = Report(session_id=session.id, edition=edition, status=status, template_version="0.4")
    db.add(report)
    db.flush()
    return report


def another_dog(db: Session, institution_id: uuid.UUID, name: str = "콩이") -> Dog:
    """같은 기관의 다른 반려견."""
    dog = Dog(institution_id=institution_id, name=name, breed="푸들", weight_kg=Decimal("6.20"), size_class="SMALL")
    db.add(dog)
    db.flush()
    return dog
