"""로그인 잠금(12.5 로그인 잠금, 11.7 실패해도 commit하는 곳, 13.4, 15.4, 17.2 BE-01 v1.48)과 보안 로그(11.8)."""

import logging
import threading
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, event, update
from sqlalchemy.orm import Session

from app.core.errors import AppError, message_for
from app.models import Institution, Staff
from app.services import auth as auth_service
from app.services.auth import LOGIN_LOCK_MINUTES, LOGIN_MAX_FAILURES, LoginRejected, authenticate
from tests.conftest import GOOD_PASSWORD, bearer, password_hash_for

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
PASSWORD = "/api/v1/auth/password"
WRONG = "wrong-pass-0000"


def _login(client: TestClient, login_id: str = "staff1", password: str = GOOD_PASSWORD):
    return client.post(LOGIN, json={"login_id": login_id, "password": password})


def _unknown_body(client: TestClient) -> dict:
    """없는 아이디로 로그인했을 때의 응답 본문. 잠긴 계정의 본문이 이것과 같아야 한다(13.4)."""
    response = _login(client, login_id="nobody-here")
    assert response.status_code == 401
    return response.json()


def _lock(db: Session, staff: Staff, *, minutes_left: float) -> None:
    """다섯 번 틀린 뒤의 상태를 바로 만든다(bcrypt를 다섯 번 돌지 않으려고)."""
    staff.login_fail_count = LOGIN_MAX_FAILURES
    staff.login_locked_until = datetime.now(UTC) + timedelta(minutes=minutes_left)
    db.flush()


# ---- 잠김 (BE-01) ----


def test_fifth_wrong_password_locks_and_then_the_right_password_is_refused(
    client: TestClient, db: Session, staff
) -> None:
    unknown = _unknown_body(client)
    for failures in range(1, LOGIN_MAX_FAILURES):
        wrong = _login(client, password=WRONG)
        assert (wrong.status_code, wrong.json()) == (401, unknown)
        assert (staff.login_fail_count, staff.login_locked_until) == (failures, None)

    before = datetime.now(UTC)
    fifth = _login(client, password=WRONG)
    assert (fifth.status_code, fifth.json()) == (401, unknown)
    assert staff.login_fail_count == LOGIN_MAX_FAILURES
    lock_for = timedelta(minutes=LOGIN_LOCK_MINUTES)
    assert before + lock_for <= staff.login_locked_until <= datetime.now(UTC) + lock_for

    # 잠긴 동안에는 맞는 비밀번호도 같은 401이고, 본문으로는 잠겼는지 알 수 없다(13.4)
    locked_until = staff.login_locked_until
    right = _login(client)
    assert (right.status_code, right.json()) == (401, unknown)
    assert right.json()["error"]["code"] == "LOGIN_FAILED"
    # 잠긴 동안의 시도는 횟수도 잠금 시각도 바꾸지 않는다(틀릴 때마다 길어지지 않는다)
    assert _login(client, password=WRONG).status_code == 401
    assert (staff.login_fail_count, staff.login_locked_until) == (LOGIN_MAX_FAILURES, locked_until)


def test_success_resets_the_count(client: TestClient, db: Session, staff) -> None:
    for _ in range(LOGIN_MAX_FAILURES - 1):
        assert _login(client, password=WRONG).status_code == 401
    assert _login(client).status_code == 200
    assert (staff.login_fail_count, staff.login_locked_until) == (0, None)
    # 0에서 다시 센다: 한 번 더 틀려도 잠기지 않는다
    assert _login(client, password=WRONG).status_code == 401
    assert (staff.login_fail_count, staff.login_locked_until) == (1, None)
    assert _login(client).status_code == 200


def test_lock_is_released_when_the_time_has_passed(client: TestClient, db: Session, staff) -> None:
    _lock(db, staff, minutes_left=1)
    assert _login(client).status_code == 401  # 아직 1분 남았다

    _lock(db, staff, minutes_left=-0.01)  # 잠금 시각이 방금 지났다
    assert _login(client).status_code == 200
    assert (staff.login_fail_count, staff.login_locked_until) == (0, None)


def test_count_starts_over_after_the_lock_has_passed(client: TestClient, db: Session, staff) -> None:
    """잠금이 풀린 뒤 한 번 틀리면 1이다. 다시 바로 잠기지 않는다."""
    _lock(db, staff, minutes_left=-0.01)
    assert _login(client, password=WRONG).status_code == 401
    assert (staff.login_fail_count, staff.login_locked_until) == (1, None)
    assert _login(client).status_code == 200


def test_unknown_login_id_is_not_counted(client: TestClient, db: Session, staff, other_staff) -> None:
    for _ in range(LOGIN_MAX_FAILURES + 1):
        assert _login(client, login_id="nobody-here", password=WRONG).status_code == 401
    db.expire_all()
    assert (staff.login_fail_count, staff.login_locked_until) == (0, None)
    assert (other_staff.login_fail_count, other_staff.login_locked_until) == (0, None)
    assert _login(client).status_code == 200


def test_lock_is_per_account(client: TestClient, db: Session, staff, other_staff) -> None:
    _lock(db, staff, minutes_left=10)
    assert _login(client).status_code == 401
    assert _login(client, login_id="staff2").status_code == 200


def test_wrong_password_on_a_disabled_account_is_counted(client: TestClient, db: Session, staff) -> None:
    staff.is_active = False
    db.flush()
    assert _login(client, password=WRONG).status_code == 401
    assert staff.login_fail_count == 1
    # 비밀번호가 맞으면 지금처럼 403이고 횟수는 그대로다(로그인에 성공한 것이 아니다)
    assert _login(client).status_code == 403
    db.expire_all()
    assert staff.login_fail_count == 1


def test_token_already_issued_keeps_working_while_locked(client: TestClient, db: Session, staff) -> None:
    """잠금은 새 로그인만 막는다. 이미 받은 토큰은 쓸 수 있다(12.5 알고 둘 것)."""
    headers = bearer(staff)
    _lock(db, staff, minutes_left=10)
    assert client.get(ME, headers=headers).status_code == 200


def test_message_names_the_same_numbers_as_the_code() -> None:
    """문구에 적힌 5회·30분이 코드 상수와 같다(12.5 상수)."""
    message = message_for("LOGIN_FAILED")
    assert f"{LOGIN_MAX_FAILURES}회" in message
    assert f"{LOGIN_LOCK_MINUTES}분" in message


# ---- 풀리는 길 (BE-26·27) ----


def test_password_change_unlocks(client: TestClient, db: Session, staff) -> None:
    """잠긴 채 비밀번호를 바꾼 사람이 새 비밀번호로 바로 로그인할 수 있다."""
    headers = bearer(staff)
    _lock(db, staff, minutes_left=10)
    changed = client.patch(
        PASSWORD, json={"current_password": GOOD_PASSWORD, "new_password": "new-pass-5678"}, headers=headers
    )
    assert changed.status_code == 200
    assert (staff.login_fail_count, staff.login_locked_until) == (0, None)
    assert _login(client, password="new-pass-5678").status_code == 200


# ---- 잠근 뒤의 값으로 판단한다 (12.5 동시 요청) ----


@contextmanager
def _statements(engine: Engine) -> Iterator[list[str]]:
    seen: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany) -> None:  # noqa: ANN001
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", record)


def test_the_staff_row_is_locked_without_a_join(client: TestClient, db: Session, engine: Engine, staff) -> None:
    """11.7 잠금 조회: FOR UPDATE에는 조인을 붙이지 않는다. 틀려도 맞아도 행을 잠근 뒤에 판단한다."""
    for password in (WRONG, GOOD_PASSWORD):
        with _statements(engine) as seen:
            _login(client, password=password)
        locks = [statement for statement in seen if "FOR UPDATE" in statement]
        assert len(locks) == 1, seen
        assert "FROM staff" in locks[0] and "JOIN" not in locks[0]
    # 없는 아이디도 같은 모양의 조회를 한 번 한다(응답 시간, 15.4)
    with _statements(engine) as seen:
        _login(client, login_id="nobody-here")
    assert len([statement for statement in seen if "FOR UPDATE" in statement and "FROM staff" in statement]) == 1


def test_password_changed_during_the_check_is_checked_again(
    client: TestClient, db: Session, staff, monkeypatch: pytest.MonkeyPatch
) -> None:
    """bcrypt로 견주는 사이에 비밀번호가 바뀌었으면 새 해시로 다시 본다. 옛 비밀번호로는 들어오지 못한다."""
    real_verify = auth_service.verify_password
    new_hash = password_hash_for("brand-new-pass-1")
    calls: list[str] = []

    def verify_then_change(password: str, password_hash: str) -> bool:
        calls.append(password_hash)
        if len(calls) == 1:  # 첫 비교가 도는 동안 다른 요청이 비밀번호를 바꿨다
            db.execute(update(Staff).where(Staff.id == staff.id).values(password_hash=new_hash))
        return real_verify(password, password_hash)

    monkeypatch.setattr(auth_service, "verify_password", verify_then_change)
    old = _login(client)
    assert old.status_code == 401
    assert calls[1] == new_hash and len(calls) == 2
    assert staff.login_fail_count == 1
    assert _login(client, password="brand-new-pass-1").status_code == 200


def test_account_deleted_during_the_check_is_a_plain_login_failure(
    client: TestClient, db: Session, staff, monkeypatch: pytest.MonkeyPatch
) -> None:
    """견주는 사이에 계정이 지워졌으면(계약 종료 뒤 자동 파기) 없는 아이디와 같은 401이다. 500이 아니다."""
    real_verify = auth_service.verify_password
    unknown = _unknown_body(client)

    def verify_then_delete(password: str, password_hash: str) -> bool:
        db.execute(delete(Staff).where(Staff.id == staff.id))
        return real_verify(password, password_hash)

    monkeypatch.setattr(auth_service, "verify_password", verify_then_delete)
    gone = _login(client)
    assert (gone.status_code, gone.json()) == (401, unknown)


# ---- 실제 commit과 동시 요청 (11.7, 12.5) ----


def _committed_staff(engine: Engine, login_id: str = "lock01") -> uuid.UUID:
    """다른 연결에서도 보이게 정말로 commit한 기관과 담당자. 끝나면 clean_tables가 지운다."""
    with Session(engine) as session:
        institution = Institution(code="LOCK", name="잠금 시험 병원")
        session.add(institution)
        session.flush()
        row = Staff(
            institution_id=institution.id,
            login_id=login_id,
            password_hash=password_hash_for(GOOD_PASSWORD),
            name="담당자",
            role="CLIENT",
        )
        session.add(row)
        session.commit()
        return row.id


def _state(engine: Engine, staff_id: uuid.UUID) -> tuple[int, datetime | None]:
    with Session(engine) as session:
        row = session.get(Staff, staff_id)
        assert row is not None
        return row.login_fail_count, row.login_locked_until


def test_failed_logins_are_committed_by_the_real_get_db(
    api_client: TestClient, engine: Engine, clean_tables: None
) -> None:
    """11.7 실패해도 commit하는 곳: 401로 끝난 로그인의 실패 횟수가 DB에 남는다.

    client 픽스처를 쓰지 않아 get_db가 바뀌어 끼워지지 않는다(예외면 rollback하는 실제 get_db).
    """
    staff_id = _committed_staff(engine)
    for failures in range(1, LOGIN_MAX_FAILURES + 1):
        wrong = _login(api_client, login_id="lock01", password=WRONG)
        assert wrong.status_code == 401
        assert wrong.json()["error"]["code"] == "LOGIN_FAILED"
        assert _state(engine, staff_id)[0] == failures
    assert _state(engine, staff_id)[1] is not None
    assert _login(api_client, login_id="lock01").status_code == 401  # 잠겼다

    # 없는 아이디의 실패(예외로 올라가 rollback)는 아무것도 남기지 않는다
    assert _login(api_client, login_id="nobody-here", password=WRONG).status_code == 401
    assert _state(engine, staff_id)[0] == LOGIN_MAX_FAILURES


def _attempt_together(engine: Engine, passwords: list[str]) -> list[str]:
    """여러 연결이 같은 계정에 동시에 로그인한다. 결과는 'ok'·'rejected'·'failed'."""
    barrier = threading.Barrier(len(passwords))

    def attempt(password: str) -> str:
        with Session(engine) as session:
            barrier.wait(timeout=30)
            try:
                authenticate(session, login_id="lock01", password=password)
            except LoginRejected:
                session.commit()  # 라우트가 하는 일: 예외로 올리지 않아 commit된다
                return "rejected"
            except AppError:
                session.rollback()
                return "failed"
            session.commit()
            return "ok"

    with ThreadPoolExecutor(max_workers=len(passwords)) as pool:
        return list(pool.map(attempt, passwords))


def test_concurrent_wrong_passwords_are_each_counted(engine: Engine, clean_tables: None) -> None:
    """동시에 틀려도 횟수가 틀린 수와 같다(행 잠금). 덮어써서 1이 되지 않는다."""
    staff_id = _committed_staff(engine)
    together = LOGIN_MAX_FAILURES - 1
    results = _attempt_together(engine, [f"wrong-pass-{n}" for n in range(together)])
    assert results == ["rejected"] * together
    assert _state(engine, staff_id) == (together, None)


def test_concurrent_guesses_cannot_get_past_the_lock(engine: Engine, clean_tables: None) -> None:
    """네 번 틀린 계정에 여러 비밀번호를 한꺼번에 넣는다. 첫 실패에서 잠기고, 횟수는 5에서 멈춘다."""
    staff_id = _committed_staff(engine)
    with Session(engine) as session:
        session.execute(update(Staff).where(Staff.id == staff_id).values(login_fail_count=LOGIN_MAX_FAILURES - 1))
        session.commit()
    results = _attempt_together(engine, [f"wrong-pass-{n}" for n in range(6)])
    assert results == ["rejected"] * 6
    count, locked_until = _state(engine, staff_id)
    assert count == LOGIN_MAX_FAILURES and locked_until is not None
    assert _attempt_together(engine, [GOOD_PASSWORD]) == ["rejected"]


# ---- 보안 로그 (11.8) ----


def test_login_logs_carry_ids_but_never_what_was_typed(
    client: TestClient, db: Session, staff, caplog: pytest.LogCaptureFixture
) -> None:
    staff.login_fail_count = LOGIN_MAX_FAILURES - 2
    db.flush()
    with caplog.at_level(logging.DEBUG):
        _login(client, login_id="typed-secret-as-id", password="typed-password-9")
        _login(client, password="typed-password-9")  # 4번째
        _login(client, password="typed-password-9")  # 5번째: 잠김
        _login(client)  # 잠긴 계정에 맞는 비밀번호
    text = caplog.text
    assert "login failed: unknown account" in text
    assert f"login failed staff={staff.id} failures={LOGIN_MAX_FAILURES - 1}" in text
    assert f"login locked staff={staff.id} failures={LOGIN_MAX_FAILURES} until=" in text
    assert f"login refused: locked staff={staff.id}" in text
    locked = next(record for record in caplog.records if record.getMessage().startswith("login locked"))
    assert locked.levelno == logging.WARNING
    for typed in ("typed-secret-as-id", "typed-password-9", GOOD_PASSWORD, "staff1", staff.name):
        assert typed not in text
