"""모델 기본값, 관계, DB 제약 위반 코드(11.7)를 실제 PostgreSQL에서 확인한다."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.core.db import CHECK_VIOLATION, FOREIGN_KEY_VIOLATION, UNIQUE_VIOLATION, db_error_code
from app.models import Dog, Institution, MeasureSession, Shot, Staff
from app.models.enums import ShotStatus, StaffRole, VideoStatus


def _institution(db: Session, code: str = "T01") -> Institution:
    institution = Institution(code=code, name="테스트 병원")
    db.add(institution)
    db.flush()
    return institution


def _staff(db: Session, institution: Institution, login_id: str = "staff1") -> Staff:
    staff = Staff(institution_id=institution.id, login_id=login_id, password_hash="x" * 60, name="담당자")
    db.add(staff)
    db.flush()
    return staff


def _dog(db: Session, institution: Institution) -> Dog:
    dog = Dog(institution_id=institution.id, name="초코", breed="말티즈", weight_kg=Decimal("3.25"), size_class="SMALL")
    db.add(dog)
    db.flush()
    return dog


def _session(db: Session, dog: Dog, staff: Staff) -> MeasureSession:
    measure = MeasureSession(
        dog_id=dog.id, staff_id=staff.id, measured_on=date(2026, 10, 21), size_class=dog.size_class
    )
    db.add(measure)
    db.flush()
    return measure


def _shot(db: Session, measure: MeasureSession, seq_no: int) -> Shot:
    shot = Shot(
        session_id=measure.id,
        seq_no=seq_no,
        original_key=f"originals/{uuid.uuid4()}.mp4",
        width=1920,
        height=1080,
        fps=Decimal("30"),
        duration_sec=Decimal("12.5"),
        bitrate_kbps=8000,
        codec="h264",
        uploaded_at=datetime.now(UTC),
    )
    db.add(shot)
    db.flush()
    return shot


def _error_code(db: Session, statement: str, params: dict) -> tuple[type[BaseException], str | None]:
    """SQL을 실행해 난 오류의 종류와 SQLSTATE를 돌려준다. 오류 뒤에도 세션을 계속 쓸 수 있게 savepoint 안에서 한다."""
    with pytest.raises(DBAPIError) as caught:
        with db.begin_nested():
            db.execute(text(statement), params)
    return type(caught.value), db_error_code(caught.value)


def test_server_defaults(db: Session) -> None:
    institution = _institution(db)
    staff = _staff(db, institution)
    dog = _dog(db, institution)
    shot = _shot(db, _session(db, dog, staff), seq_no=1)
    for row in (staff, dog, shot):
        db.refresh(row)

    assert staff.role == StaffRole.CLIENT
    assert staff.is_active is True
    assert dog.size_class_manual is False
    assert dog.weight_kg == Decimal("3.25")
    assert shot.status == ShotStatus.UPLOADED
    assert shot.video_status == VideoStatus.PENDING
    assert shot.attempt_count == 0
    assert shot.below_min_spec is False
    # TIMESTAMPTZ는 시간대가 붙은 값으로 돌아온다(11.4)
    assert staff.created_at.tzinfo is not None
    assert shot.uploaded_at.tzinfo is not None


def test_server_defaults_without_orm(db: Session) -> None:
    """ORM을 거치지 않고 넣어도 DB 기본값이 채워진다(마이그레이션의 server_default 확인)."""
    institution = _institution(db)
    row = db.execute(
        text(
            "INSERT INTO staff (id, institution_id, login_id, password_hash, name) "
            "VALUES (:id, :institution_id, 'raw', 'x', '담당자') RETURNING role, is_active, created_at, updated_at"
        ),
        {"id": uuid.uuid4(), "institution_id": institution.id},
    ).one()
    assert row.role == "CLIENT"
    assert row.is_active is True
    assert row.created_at is not None and row.updated_at is not None


def test_updated_at_changes_on_update(db: Session) -> None:
    institution = _institution(db)
    staff = _staff(db, institution)
    past = datetime(2000, 1, 1, tzinfo=UTC)
    db.execute(update(Staff).where(Staff.id == staff.id).values(updated_at=past))
    db.refresh(staff)
    assert staff.updated_at == past

    staff.name = "이름 변경"
    db.flush()
    db.refresh(staff)
    assert staff.updated_at > past


def test_unique_violation_is_23505(db: Session) -> None:
    _institution(db, code="DUP")
    kind, code = _error_code(
        db, "INSERT INTO institution (id, code, name) VALUES (:id, 'DUP', '다른 병원')", {"id": uuid.uuid4()}
    )
    assert code == UNIQUE_VIOLATION
    assert issubclass(kind, IntegrityError)


def test_foreign_key_violation_is_23503(db: Session) -> None:
    kind, code = _error_code(
        db,
        "INSERT INTO staff (id, institution_id, login_id, password_hash, name) VALUES (:id, :missing, 'a', 'x', 'b')",
        {"id": uuid.uuid4(), "missing": uuid.uuid4()},
    )
    assert code == FOREIGN_KEY_VIOLATION
    # pg8000은 외래키 위반을 IntegrityError가 아닌 다른 종류로 낸다. 그래서 코드로 가린다(11.7).
    assert not issubclass(kind, IntegrityError)


def test_check_violation_is_23514(db: Session) -> None:
    institution = _institution(db)
    kind, code = _error_code(
        db,
        "INSERT INTO staff (id, institution_id, login_id, password_hash, name, role) "
        "VALUES (:id, :institution_id, 'a', 'x', 'b', 'BOSS')",
        {"id": uuid.uuid4(), "institution_id": institution.id},
    )
    assert code == CHECK_VIOLATION
    assert not issubclass(kind, IntegrityError)


def test_session_usable_after_error_in_savepoint(db: Session) -> None:
    """오류가 난 뒤에도 savepoint만 되돌리면 같은 트랜잭션을 계속 쓸 수 있다(11.7)."""
    _institution(db, code="A1")
    _error_code(db, "INSERT INTO institution (id, code, name) VALUES (:id, 'A1', 'x')", {"id": uuid.uuid4()})
    _institution(db, code="A2")
    codes = db.scalars(select(Institution.code).order_by(Institution.code)).all()
    assert codes == ["A1", "A2"]


def test_dog_baseline_session_cycle(db: Session) -> None:
    """dog ↔ measure_session이 서로를 가리켜도 저장된다(fk_dog_baseline, post_update)."""
    institution = _institution(db)
    staff = _staff(db, institution)
    dog = _dog(db, institution)
    measure = _session(db, dog, staff)

    dog.baseline_session = measure
    db.flush()
    db.expire_all()

    saved = db.get(Dog, dog.id)
    assert saved is not None
    assert saved.baseline_session_id == measure.id
    assert [s.id for s in saved.sessions] == [measure.id]

    kind, code = _error_code(
        db, "UPDATE dog SET baseline_session_id = :missing WHERE id = :id", {"missing": uuid.uuid4(), "id": dog.id}
    )
    assert code == FOREIGN_KEY_VIOLATION


def test_shots_are_ordered_by_seq_no(db: Session) -> None:
    institution = _institution(db)
    measure = _session(db, _dog(db, institution), _staff(db, institution))
    for seq_no in (3, 1, 2):
        _shot(db, measure, seq_no)
    db.expire_all()
    assert [shot.seq_no for shot in db.get(MeasureSession, measure.id).shots] == [1, 2, 3]

    kind, code = _error_code(
        db,
        "INSERT INTO shot (id, session_id, seq_no, original_key, width, height, fps, duration_sec, bitrate_kbps, "
        "codec, uploaded_at) VALUES (:id, :sid, 1, 'k', 1, 1, 30, 1, 1, 'h264', now())",
        {"id": uuid.uuid4(), "sid": measure.id},
    )
    assert code == UNIQUE_VIOLATION
