"""DB 오류의 글에 행 값이 남지 않는다(11.8 로그로 새지 않게, core/db.py scrub_db_error, v1.46).

PostgreSQL은 제약을 어긴 행 전체('Failing row contains (…)'), 겹친 키의 값('Key (…)=(…)'), 형식이 틀린 값을 오류에
붙여 보낸다. 그것이 예외의 글이 되면 logger.exception으로 로그에 간다.
"""

import logging
import traceback
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.core.db import CHECK_VIOLATION, UNIQUE_VIOLATION, db_error_code
from app.models import Institution

SECRET_BODY = "약 알레르기 있음 010-1234-5678"
NOT_A_UUID = "홍길동-010-1234-5678"  # 부르는 줄에 직접 적으면 traceback의 소스 줄에 찍힌다
BAD_NOTE = text(
    "INSERT INTO dog_note (id, dog_id, category, body, staff_id) VALUES (:id, :dog, 'X', :body, :staff)"
)  # 분류 'X'는 ck_dog_note_category에 걸린다


def _everything(error: BaseException) -> str:
    """예외에서 로그로 나갈 수 있는 글 전부: str, 원래 예외, 연결된 예외까지 그린 traceback."""
    parts = [str(error), repr(error), "".join(traceback.format_exception(error))]
    original = getattr(error, "orig", None)
    if original is not None:
        parts += [str(original), repr(original)]
    return "\n".join(parts)


def test_check_violation_keeps_names_and_drops_the_row(db: Session, dog, staff) -> None:
    with pytest.raises(DBAPIError) as caught, db.begin_nested():
        db.execute(BAD_NOTE, {"id": uuid.uuid4(), "dog": dog.id, "body": SECRET_BODY, "staff": staff.id})
    error = caught.value
    shown = _everything(error)
    for secret in ("알레르기", "010-1234-5678", "Failing row"):
        assert secret not in shown
    # 어느 규칙을 어겼는지는 남는다: SQLSTATE와 테이블·제약 이름
    assert db_error_code(error) == CHECK_VIOLATION
    assert "ck_dog_note_category" in shown and "dog_note" in shown
    assert error.orig.args[0]["n"] == "ck_dog_note_category"
    assert "D" not in error.orig.args[0]


def test_unique_violation_drops_the_key_value_and_stays_an_integrity_error(db: Session, staff) -> None:
    """겹친 값('Key (code)=(T01) already exists')은 빠지고, 서비스가 보는 예외 종류와 SQLSTATE는 그대로다."""
    with pytest.raises(IntegrityError) as caught, db.begin_nested():
        db.add(Institution(code="T01", name="홍길동 동물병원"))  # staff fixture의 기관과 같은 코드
        db.flush()
    error = caught.value
    shown = _everything(error)
    assert "(T01)" not in shown and "already exists" not in shown and "홍길동" not in shown
    assert db_error_code(error) == UNIQUE_VIOLATION
    assert "uq_institution_code" in shown


def test_data_error_drops_the_message_that_quotes_the_value(db: Session) -> None:
    """자료 오류(22)의 메시지는 받은 값을 그대로 싣는다('invalid input syntax for type uuid: "…"'). 메시지째 뺀다."""
    with pytest.raises(DBAPIError) as caught, db.begin_nested():
        db.execute(text("SELECT CAST(:value AS uuid)"), {"value": NOT_A_UUID})
    error = caught.value
    shown = _everything(error)
    assert "홍길동" not in shown and "010-1234-5678" not in shown
    assert db_error_code(error) == "22P02" and "M" not in error.orig.args[0]


def test_unhandled_db_error_is_logged_without_the_row(client: TestClient, db: Session, dog, staff, caplog) -> None:
    """500이 될 때 남는 예외 로그(logger.exception)에도 값이 없다."""
    logger = logging.getLogger("app.test_db_error_scrub")
    with caplog.at_level(logging.ERROR, logger=logger.name):
        try:
            with db.begin_nested():
                db.execute(BAD_NOTE, {"id": uuid.uuid4(), "dog": dog.id, "body": SECRET_BODY, "staff": staff.id})
        except DBAPIError:
            logger.exception("unhandled error")
    assert caplog.text.count("unhandled error") == 1
    assert "ck_dog_note_category" in caplog.text
    for secret in ("알레르기", "010-1234-5678", "Failing row"):
        assert secret not in caplog.text
