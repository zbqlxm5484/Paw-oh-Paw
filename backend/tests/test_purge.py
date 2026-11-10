"""자료 파기(명세 7절 보관과 파기, 12.5 삭제 순서, 15.9 POST /admin/purge, 17.6 BE-19, 17.7의 6단계, S15P31A404-199)."""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_analysis_client
from app.clients.analysis import AnalysisClientError
from app.core.errors import AppError, ErrorCode
from app.models import Dog, Institution, MeasureSession, PurgeLog, Report, SessionMetric, Shot, Staff, WalkPass
from app.schemas.admin import PurgeOut
from app.services.analysis_copies import OutOfTime
from app.services.purge import purge
from app.storage.base import get_storage
from app.storage.keys import analysis_key, dog_prefix, institution_prefix, original_key, report_key, result_key
from scripts import purge as purge_script
from tests.conftest import GOOD_PASSWORD, bearer, password_hash_for
from tests.history_fixtures import add_metric, add_report, add_shot, another_dog, make_session

PURGE = "/api/v1/admin/purge"
# 회차 하나에 넣는 파일: 원본 10, 분석 결과 5, 결과 영상 7, 보고서 4 바이트 = 4개 26바이트
FILE_SIZES = {"original": 10, "analysis": 5, "result": 7, "report": 4}
ROWS_PER_SESSION = 1 + 1 + 2 + 2 + 1  # 회차 + 촬영 + 통과 2 + 수치 2 + 보고서


@pytest.fixture
def admin(db: Session, staff) -> Staff:
    """staff와 같은 기관(T01)의 ADMIN. 자료 파기는 ADMIN만 부를 수 있다(15.9)."""
    row = Staff(
        institution_id=staff.institution_id,
        login_id="admin1",
        password_hash=password_hash_for(GOOD_PASSWORD),
        name="관리자",
        role="ADMIN",
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


@pytest.fixture
def admin_headers(admin: Staff) -> dict[str, str]:
    return bearer(admin)


def _fill(db: Session, dog, staff, *, sessions: int = 2) -> int:
    """반려견 하나에 회차·촬영·통과·수치·보고서 행과 파일을 넣고, 넣은 행 수(반려견 포함)를 돌려준다."""
    storage = get_storage()
    for day in range(1, sessions + 1):
        session = make_session(db, dog, staff, date(2026, 10, day))
        shot = add_shot(db, session, 1, passes={"LEFT": (1, 0), "RIGHT": (1, 0)})
        add_metric(db, session, "rom_stifle", "LH", 38.2)
        add_metric(db, session, "rom_stifle", "RH", 42.0)
        report = add_report(db, session, "OWNER", "DONE")
        inst, dog_id, sid = dog.institution_id, dog.id, session.id
        storage.write_bytes(original_key(inst, dog_id, sid, shot.id, "mp4"), b"o" * FILE_SIZES["original"])
        storage.write_bytes(analysis_key(inst, dog_id, sid, shot.id), b"a" * FILE_SIZES["analysis"])
        storage.write_bytes(result_key(inst, dog_id, sid, shot.id), b"r" * FILE_SIZES["result"])
        storage.write_bytes(report_key(inst, dog_id, sid, report.id), b"p" * FILE_SIZES["report"])
    return 1 + sessions * ROWS_PER_SESSION


def _expected_files(sessions: int) -> tuple[int, int]:
    return len(FILE_SIZES) * sessions, sum(FILE_SIZES.values()) * sessions


def _rows_of_dog(db: Session, dog_id: uuid.UUID) -> int:
    """DB에 남은 반려견 + 회차 + 촬영 + 통과 + 수치 + 보고서 행 수."""
    sessions = select(MeasureSession.id).where(MeasureSession.dog_id == dog_id)
    shots = select(Shot.id).where(Shot.session_id.in_(sessions))

    def count(model, condition) -> int:
        return db.scalar(select(func.count()).select_from(model).where(condition)) or 0

    return (
        count(Dog, Dog.id == dog_id)
        + count(MeasureSession, MeasureSession.dog_id == dog_id)
        + count(Shot, Shot.session_id.in_(sessions))
        + count(WalkPass, WalkPass.shot_id.in_(shots))
        + count(SessionMetric, SessionMetric.session_id.in_(sessions))
        + count(Report, Report.session_id.in_(sessions))
    )


def _purge_logs(db: Session) -> list[PurgeLog]:
    return list(db.scalars(select(PurgeLog)))


# ---- dry run과 반려견 파기 ----


def test_dry_run_is_the_default_and_counts_without_deleting(
    client: TestClient, db: Session, dog, staff, admin_headers
) -> None:
    rows = _fill(db, dog, staff)
    files, size = _expected_files(2)
    response = client.post(PURGE, json={"scope": "DOG", "target_id": str(dog.id)}, headers=admin_headers)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "scope": "DOG",
        "target_id": str(dog.id),
        "dry_run": True,
        "rows": rows,
        "files": files,
        "bytes": size,
        "analysis_jobs": 0,
        "purge_log_id": None,
    }
    assert _rows_of_dog(db, dog.id) == rows
    assert get_storage().stat_prefix(dog_prefix(dog.institution_id, dog.id)) == (files, size)
    assert _purge_logs(db) == []


def test_dog_purge_removes_every_row_and_file_and_leaves_one_log(
    client: TestClient, db: Session, dog, staff, admin: Staff, admin_headers
) -> None:
    rows = _fill(db, dog, staff)
    files, size = _expected_files(2)
    dog.baseline_session_id = db.scalar(select(MeasureSession.id).where(MeasureSession.dog_id == dog.id))
    db.flush()
    keep = another_dog(db, staff.institution_id)
    keep_rows = _fill(db, keep, staff, sessions=1)

    response = client.post(
        PURGE, json={"scope": "DOG", "target_id": str(dog.id), "dry_run": False}, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["dry_run"], body["rows"], body["files"], body["bytes"]) == (False, rows, files, size)
    assert body["purge_log_id"] is not None

    # 17.6·17.7: 대상의 행과 파일이 0개, 기록은 1행
    assert _rows_of_dog(db, dog.id) == 0
    assert get_storage().stat_prefix(dog_prefix(dog.institution_id, dog.id)) == (0, 0)
    (log,) = _purge_logs(db)
    assert str(log.id) == body["purge_log_id"]
    assert (log.scope, log.target_id, log.rows_deleted, log.files_deleted, log.bytes_deleted, log.executed_by) == (
        "DOG",
        dog.id,
        rows,
        files,
        size,
        admin.id,
    )
    assert log.executed_at is not None
    # 같은 기관의 다른 반려견은 그대로
    assert _rows_of_dog(db, keep.id) == keep_rows
    assert get_storage().stat_prefix(dog_prefix(keep.institution_id, keep.id)) == _expected_files(1)
    assert client.get(f"/api/v1/dogs/{dog.id}", headers=admin_headers).status_code == 404


def test_institution_purge_keeps_accounts_and_other_institutions(
    client: TestClient, db: Session, dog, staff, other_staff, admin: Staff, admin_headers
) -> None:
    rows = _fill(db, dog, staff) + _fill(db, another_dog(db, staff.institution_id), staff, sessions=1)
    files, size = (a + b for a, b in zip(_expected_files(2), _expected_files(1), strict=True))
    foreign = another_dog(db, other_staff.institution_id, name="남의 개")
    foreign_rows = _fill(db, foreign, other_staff, sessions=1)

    response = client.post(PURGE, json={"scope": "INSTITUTION", "dry_run": False}, headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["scope"], body["target_id"], body["rows"], body["files"], body["bytes"]) == (
        "INSTITUTION",
        str(admin.institution_id),
        rows,
        files,
        size,
    )
    assert db.scalar(select(func.count()).select_from(Dog).where(Dog.institution_id == admin.institution_id)) == 0
    assert get_storage().stat_prefix(institution_prefix(admin.institution_id)) == (0, 0)
    # 기관·담당자 계정은 남는다(15.9)
    assert db.get(Institution, admin.institution_id) is not None
    assert db.scalar(select(func.count()).select_from(Staff).where(Staff.institution_id == admin.institution_id)) == 2
    # 다른 기관은 그대로
    assert _rows_of_dog(db, foreign.id) == foreign_rows
    assert get_storage().stat_prefix(institution_prefix(other_staff.institution_id)) == _expected_files(1)
    (log,) = _purge_logs(db)
    assert (log.scope, log.target_id, log.executed_by) == ("INSTITUTION", admin.institution_id, admin.id)


def test_a_shot_in_progress_blocks_purge_even_as_dry_run(
    client: TestClient, db: Session, dog, staff, admin_headers
) -> None:
    rows = _fill(db, dog, staff)
    session = make_session(db, dog, staff, date(2026, 10, 25), status="MEASURING", model_version=None)
    add_shot(db, session, 1, status="SUBMITTED", passes={})
    for dry_run in (True, False):
        response = client.post(
            PURGE, json={"scope": "DOG", "target_id": str(dog.id), "dry_run": dry_run}, headers=admin_headers
        )
        assert response.status_code == 409 and response.json()["error"]["code"] == "SHOT_IN_PROGRESS"
    assert _rows_of_dog(db, dog.id) == rows + 2  # 측정 중 회차와 촬영까지 그대로
    assert _purge_logs(db) == []


# ---- 권한·입력 ----


class _MarkingStorage:
    """delete_prefix가 불린 순간을 SQL 기록 사이에 표시한다. 나머지는 실제 저장소에 맡긴다."""

    MARK = "storage.delete_prefix"

    def __init__(self, inner, events: list[str]) -> None:
        self.inner, self.events = inner, events

    def __getattr__(self, name: str):
        return getattr(self.inner, name)

    def delete_prefix(self, prefix: str) -> tuple[int, int]:
        self.events.append(self.MARK)
        return self.inner.delete_prefix(prefix)


@contextmanager
def _recorded_sql(db: Session):
    """이 세션의 연결이 보내는 SQL을 순서대로 모은다."""
    events: list[str] = []
    connection = db.connection()

    def record(_conn, _cursor, statement: str, _params, _context, _many) -> None:
        events.append(statement)

    event.listen(connection, "before_cursor_execute", record)
    try:
        yield events
    finally:
        event.remove(connection, "before_cursor_execute", record)


def _is_session_lock(statement: str) -> bool:
    return "FOR UPDATE" in statement and "FROM measure_session" in statement


def _is_dog_lock(statement: str) -> bool:
    return "FOR UPDATE" in statement and "FROM dog" in statement


def _is_institution_lock(statement: str) -> bool:
    return "FOR UPDATE" in statement and "FROM institution" in statement


def test_purge_locks_the_target_sessions_before_files_and_rows(db: Session, dog, staff) -> None:
    """12.4 잠금(199 리뷰): 실제 파기는 대상 회차 행을 FOR UPDATE로 잠근 뒤 진행 중 촬영을 보고 파일·행을 지운다.

    워커 claim_uploaded가 같은 행을 잠그므로 확인과 삭제 사이에 UPLOADED 촬영이 분석 API로 나가지 못한다. dry_run은
    세기만 하므로 잠그지 않는다.
    """
    _fill(db, dog, staff, sessions=1)
    with _recorded_sql(db) as events:
        purge(db, get_storage(), "DOG", institution_id=dog.institution_id, target_id=dog.id, dry_run=True)
    assert not any("FOR UPDATE" in statement for statement in events)

    with _recorded_sql(db) as events:
        storage = _MarkingStorage(get_storage(), events)
        purge(
            db,
            storage,
            "DOG",
            institution_id=dog.institution_id,
            target_id=dog.id,
            dry_run=False,
            analysis=_FakeAnalysis(),  # 작업 ID가 없는 촬영도 촬영 단위로 부르므로 클라이언트가 있어야 한다
        )
    lock = next(i for i, statement in enumerate(events) if _is_session_lock(statement))
    files = events.index(_MarkingStorage.MARK)
    first_delete = next(i for i, statement in enumerate(events) if statement.lstrip().upper().startswith("DELETE"))
    assert lock < files < first_delete
    assert _rows_of_dog(db, dog.id) == 0


def test_only_an_admin_can_purge(client: TestClient, db: Session, dog, staff, auth_headers, other_staff) -> None:
    body = {"scope": "DOG", "target_id": str(dog.id)}
    assert client.post(PURGE, json=body).status_code == 401
    client_user = client.post(PURGE, json=body, headers=auth_headers)  # CLIENT
    assert client_user.status_code == 403 and client_user.json()["error"]["code"] == "FORBIDDEN"
    temp = Staff(
        institution_id=staff.institution_id,
        login_id="temp1",
        password_hash=password_hash_for(GOOD_PASSWORD),
        name="임시",
        role="STAFF",
    )
    db.add(temp)
    db.flush()
    assert client.post(PURGE, json=body, headers=bearer(temp)).status_code == 403
    # 다른 기관의 ADMIN에게 이 반려견은 없는 것과 같다(15.1)
    foreign_admin = Staff(
        institution_id=other_staff.institution_id,
        login_id="admin2",
        password_hash=password_hash_for(GOOD_PASSWORD),
        name="다른 관리자",
        role="ADMIN",
    )
    db.add(foreign_admin)
    db.flush()
    assert client.post(PURGE, json=body, headers=bearer(foreign_admin)).status_code == 404


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"scope": "DOG"}, "target_id"),
        ({"scope": "INSTITUTION", "target_id": "3f2a9c1e-5b7d-4e8a-9c21-7d4e5f6a8b90"}, "target_id"),
        ({"scope": "ALL"}, "scope"),
        ({"scope": "DOG", "target_id": "not-a-uuid"}, "target_id"),
        ({}, "scope"),
    ],
)
def test_request_rules(client: TestClient, admin_headers, body: dict, field: str) -> None:
    response = client.post(PURGE, json=body, headers=admin_headers)
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["detail"]["fields"][0]["field"] == field


def test_unknown_dog_is_404(client: TestClient, admin_headers) -> None:
    response = client.post(PURGE, json={"scope": "DOG", "target_id": str(uuid.uuid4())}, headers=admin_headers)
    assert response.status_code == 404


# ---- 대상 기관 지정(15.9. 크림오프 관리자가 병원 자료를 지운다) ----


def test_admin_purges_another_institution_and_own_is_untouched(
    client: TestClient, db: Session, dog, staff, other_staff, admin: Staff, admin_headers
) -> None:
    own_rows = _fill(db, dog, staff, sessions=1)
    foreign = another_dog(db, other_staff.institution_id, name="남의 개")
    foreign_rows = _fill(db, foreign, other_staff, sessions=2)
    body = {"scope": "INSTITUTION", "institution_id": str(other_staff.institution_id)}

    counted = client.post(PURGE, json=body, headers=admin_headers)  # dry_run 기본값
    assert counted.status_code == 200, counted.text
    assert (counted.json()["target_id"], counted.json()["rows"]) == (str(other_staff.institution_id), foreign_rows)
    assert _rows_of_dog(db, foreign.id) == foreign_rows

    response = client.post(PURGE, json={**body, "dry_run": False}, headers=admin_headers)
    assert response.status_code == 200, response.text
    assert (response.json()["rows"], response.json()["files"]) == (foreign_rows, _expected_files(2)[0])
    assert db.get(Dog, foreign.id) is None
    assert get_storage().stat_prefix(institution_prefix(other_staff.institution_id)) == (0, 0)
    # 기관·담당자 계정은 남고, 부른 관리자의 기관 자료는 그대로다
    assert db.get(Institution, other_staff.institution_id) is not None
    assert db.get(Staff, other_staff.id) is not None
    assert _rows_of_dog(db, dog.id) == own_rows
    assert get_storage().stat_prefix(institution_prefix(admin.institution_id)) == _expected_files(1)
    (log,) = _purge_logs(db)
    assert (log.scope, log.target_id, log.executed_by) == ("INSTITUTION", other_staff.institution_id, admin.id)


def test_admin_purges_one_dog_of_another_institution(
    client: TestClient, db: Session, dog, staff, other_staff, admin: Staff, admin_headers
) -> None:
    foreign = another_dog(db, other_staff.institution_id, name="남의 개")
    kept = another_dog(db, other_staff.institution_id, name="남는 개")
    foreign_rows = _fill(db, foreign, other_staff, sessions=1)
    kept_rows = _fill(db, kept, other_staff, sessions=1)
    body = {"scope": "DOG", "target_id": str(foreign.id), "dry_run": False}

    # 기관을 지정하지 않으면 자기 기관에서 찾으므로 없는 것과 같다(15.1)
    assert client.post(PURGE, json=body, headers=admin_headers).status_code == 404
    assert _rows_of_dog(db, foreign.id) == foreign_rows

    response = client.post(
        PURGE, json={**body, "institution_id": str(other_staff.institution_id)}, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    assert (response.json()["target_id"], response.json()["rows"]) == (str(foreign.id), foreign_rows)
    assert db.get(Dog, foreign.id) is None
    assert _rows_of_dog(db, kept.id) == kept_rows
    assert get_storage().stat_prefix(dog_prefix(other_staff.institution_id, kept.id)) == _expected_files(1)
    (log,) = _purge_logs(db)
    assert (log.scope, log.target_id, log.executed_by) == ("DOG", foreign.id, admin.id)


def test_unknown_institution_and_a_dog_outside_it_are_404(
    client: TestClient, db: Session, dog, staff, other_staff, admin_headers
) -> None:
    rows = _fill(db, dog, staff, sessions=1)
    unknown = {"scope": "INSTITUTION", "institution_id": str(uuid.uuid4()), "dry_run": False}
    assert client.post(PURGE, json=unknown, headers=admin_headers).status_code == 404
    # 자기 기관의 반려견이라도 지정한 기관에 없으면 404다
    wrong = {
        "scope": "DOG",
        "target_id": str(dog.id),
        "institution_id": str(other_staff.institution_id),
        "dry_run": False,
    }
    assert client.post(PURGE, json=wrong, headers=admin_headers).status_code == 404
    assert _rows_of_dog(db, dog.id) == rows
    assert _purge_logs(db) == []


def test_institution_id_does_not_let_a_non_admin_purge(
    client: TestClient, db: Session, dog, staff, other_staff, auth_headers
) -> None:
    rows = _fill(db, dog, staff, sessions=1)
    body = {"scope": "INSTITUTION", "institution_id": str(staff.institution_id), "dry_run": False}
    assert client.post(PURGE, json=body, headers=auth_headers).status_code == 403  # 자기 기관을 적어도 CLIENT는 안 된다
    assert client.post(PURGE, json=body, headers=bearer(other_staff)).status_code == 403
    assert _rows_of_dog(db, dog.id) == rows


def test_institution_id_must_be_a_uuid(client: TestClient, admin_headers) -> None:
    response = client.post(PURGE, json={"scope": "INSTITUTION", "institution_id": "x"}, headers=admin_headers)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["detail"]["fields"][0]["field"] == "institution_id"


# ---- 분석 API 사본(7절, 15.9, 조유진 185) ----


class _FakeAnalysis:
    """분석 클라이언트 자리. 지운 작업을 기록하고, fail에 든 작업에서는 그 오류를 낸다.

    hook은 지우기 호출 도중(HTTP를 기다리는 사이)에 다른 요청이 끼어드는 상황을 만든다.
    촬영 단위 지우기(delete_shot)는 shot_jobs에 넣어 둔 작업만 안다. 비워 두면 빈 목록을 돌려주어, 팀 서비스가 아는
    작업은 작업 단위(delete)로 온다. shot_jobs에는 팀 서비스가 모르는 작업도 넣을 수 있다.
    """

    MARK = "analysis.delete"

    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events
        self.deleted: list[str] = []
        self.fail: dict[str, AnalysisClientError] = {}
        self.hook = None
        self.shot_calls: list[uuid.UUID] = []
        self.shot_jobs: dict[uuid.UUID, list[str]] = {}
        self.shot_fail: dict[uuid.UUID, AnalysisClientError] = {}
        self.shot_error: AnalysisClientError | None = None  # 모든 촬영 단위 호출에 내는 오류

    def delete(self, job_id: str) -> None:
        if self.events is not None:
            self.events.append(self.MARK)
        if self.hook is not None:
            self.hook(job_id)
        if job_id in self.fail:
            raise self.fail[job_id]
        self.deleted.append(job_id)

    def delete_shot(self, shot_id: uuid.UUID) -> list[str]:
        if self.events is not None:
            self.events.append(self.MARK)
        self.shot_calls.append(shot_id)
        if self.shot_error is not None:
            raise self.shot_error
        if shot_id in self.shot_fail:
            raise self.shot_fail[shot_id]
        jobs = self.shot_jobs.pop(shot_id, [])
        self.deleted.extend(jobs)
        return list(jobs)


@pytest.fixture
def analysis(api_app) -> Iterator[_FakeAnalysis]:
    """POST /admin/purge가 쓸 분석 클라이언트를 가짜로 바꿔 끼운다."""
    fake = _FakeAnalysis()
    api_app.dependency_overrides[get_analysis_client] = lambda: fake
    yield fake
    api_app.dependency_overrides.pop(get_analysis_client, None)


def _give_job_ids(db: Session, dog) -> list[str]:
    """반려견의 촬영마다 작업 ID를 넣고 돌려준다(분석 API에 제출한 촬영)."""
    shots = db.scalars(
        select(Shot).join(MeasureSession, Shot.session_id == MeasureSession.id).where(MeasureSession.dog_id == dog.id)
    ).all()
    for shot in shots:
        shot.job_id = f"job-{shot.id}"
    db.flush()
    return [shot.job_id for shot in shots]


def _purge_dog(client: TestClient, dog, headers, *, dry_run: bool = False):
    return client.post(PURGE, json={"scope": "DOG", "target_id": str(dog.id), "dry_run": dry_run}, headers=headers)


def test_analysis_copies_go_before_the_session_lock_and_before_files_and_rows(db: Session, dog, staff) -> None:
    """분석 API를 먼저 불러야 가장 흔한 실패(무응답)에서 팀 서비스 쪽을 하나도 지우지 않고 멈출 수 있다.

    HTTP라 오래 걸릴 수 있어 회차 행을 잠그기 전에 부른다(199 리뷰 박규원). 잠근 채 기다리면 업로드·측정 종료와
    워커의 주 반복이 같은 행에서 멈춘다. DOG의 반려견 행은 그보다 먼저 잠가, 그사이 복원하지 못하게 한다.
    """
    _fill(db, dog, staff, sessions=2)
    job_ids = _give_job_ids(db, dog)
    with _recorded_sql(db) as events:
        fake = _FakeAnalysis(events)
        storage = _MarkingStorage(get_storage(), events)
        result = purge(
            db, storage, "DOG", institution_id=dog.institution_id, target_id=dog.id, dry_run=False, analysis=fake
        )
    dog_lock = next(i for i, statement in enumerate(events) if _is_dog_lock(statement))
    lock = next(i for i, statement in enumerate(events) if _is_session_lock(statement))
    first_call = events.index(_FakeAnalysis.MARK)
    last_call = len(events) - 1 - events[::-1].index(_FakeAnalysis.MARK)
    files = events.index(_MarkingStorage.MARK)
    first_delete = next(i for i, statement in enumerate(events) if statement.lstrip().upper().startswith("DELETE"))
    assert dog_lock < first_call <= last_call < lock < files < first_delete
    assert sorted(fake.deleted) == sorted(job_ids)
    assert result.analysis_jobs == 2
    (log,) = _purge_logs(db)
    assert log.analysis_jobs_deleted == 2


def test_dry_run_counts_analysis_jobs_without_calling(
    client: TestClient, db: Session, dog, staff, admin_headers, analysis: _FakeAnalysis
) -> None:
    _fill(db, dog, staff, sessions=2)
    _give_job_ids(db, dog)
    response = _purge_dog(client, dog, admin_headers, dry_run=True)
    assert response.status_code == 200, response.text
    assert response.json()["analysis_jobs"] == 2
    assert analysis.deleted == [] and analysis.shot_calls == []


def test_every_shot_of_the_target_is_asked_about_and_only_its_jobs_are_deleted(
    client: TestClient, db: Session, dog, staff, admin_headers, analysis: _FakeAnalysis
) -> None:
    """작업 ID가 없는 촬영도 촬영 단위로 부른다(분석 API에 모르는 작업이 있을 수 있다). 남의 것은 안 부른다."""
    _fill(db, dog, staff, sessions=1)
    job_ids = _give_job_ids(db, dog)
    never_submitted = make_session(db, dog, staff, date(2026, 10, 20))
    add_shot(db, never_submitted, 1, status="UPLOADED", passes={})  # job_id가 없다
    shot_ids = {shot.id for shot in _shots_of(db, dog)}
    keep = another_dog(db, staff.institution_id)
    _fill(db, keep, staff, sessions=1)
    kept_jobs = _give_job_ids(db, keep)

    response = _purge_dog(client, dog, admin_headers)
    assert response.status_code == 200, response.text
    assert response.json()["analysis_jobs"] == 1
    assert analysis.deleted == job_ids
    assert not set(kept_jobs) & set(analysis.deleted)
    assert len(shot_ids) == 2 and set(analysis.shot_calls) == shot_ids


def test_jobs_the_team_service_does_not_know_are_deleted_and_counted(db: Session, dog, staff) -> None:
    """제출 응답을 못 받아 job_id를 못 적은 작업도 촬영 ID로 지워진다(조유진 258). 실제 파기의 수에는 그것도 든다."""
    _fill(db, dog, staff, sessions=1)
    (known,) = _give_job_ids(db, dog)
    (submitted,) = _shots_of(db, dog)
    lost = add_shot(db, make_session(db, dog, staff, date(2026, 10, 20)), 1, status="FAILED", passes={})
    fake = _FakeAnalysis()
    fake.shot_jobs = {submitted.id: [known, "lost-1"], lost.id: ["lost-2"]}
    fake.hook = lambda job_id: pytest.fail("촬영 단위 답에 든 작업을 작업 단위로 또 불렀다")
    args = dict(institution_id=dog.institution_id, target_id=dog.id, analysis=fake)

    counted = purge(db, get_storage(), "DOG", dry_run=True, **args)
    assert counted.analysis_jobs == 1 and fake.shot_calls == []  # 세기만 할 때는 아는 것만 센다

    result = purge(db, get_storage(), "DOG", dry_run=False, **args)
    assert sorted(fake.deleted) == sorted([known, "lost-1", "lost-2"])
    assert result.analysis_jobs == 3
    (log,) = _purge_logs(db)
    assert log.analysis_jobs_deleted == 3
    assert _rows_of_dog(db, dog.id) == 0


def test_an_analysis_api_without_the_shot_delete_still_deletes_the_known_jobs(db: Session, dog, staff) -> None:
    """분석 API가 옛 판이면(405) 아는 작업을 작업 단위로 지운다. 배포 순서가 어긋나도 파기가 막히지 않는다."""
    _fill(db, dog, staff, sessions=2)
    job_ids = _give_job_ids(db, dog)
    add_shot(db, make_session(db, dog, staff, date(2026, 10, 20)), 1, status="UPLOADED", passes={})
    fake = _FakeAnalysis()
    fake.shot_error = AnalysisClientError("405", retryable=False, status_code=405)
    result = purge(
        db, get_storage(), "DOG", institution_id=dog.institution_id, target_id=dog.id, dry_run=False, analysis=fake
    )
    assert sorted(fake.deleted) == sorted(job_ids) and len(fake.shot_calls) == 3
    assert result.analysis_jobs == 2 and _rows_of_dog(db, dog.id) == 0


@pytest.mark.parametrize(("answer", "code"), [(409, "SHOT_IN_PROGRESS"), (500, "ANALYSIS_UNAVAILABLE")])
def test_a_refused_shot_delete_stops_the_purge_with_everything_in_place(
    db: Session, dog, staff, answer: int, code: str
) -> None:
    """409는 팀 서비스가 모르는 작업이 분석 API에서 아직 도는 경우에도 온다. 팀 서비스 쪽은 그대로다."""
    rows = _fill(db, dog, staff, sessions=1)
    (shot,) = _shots_of(db, dog)  # job_id가 없다
    fake = _FakeAnalysis()
    fake.shot_fail[shot.id] = AnalysisClientError("거절", status_code=answer)
    with pytest.raises(AppError) as caught:
        purge(
            db, get_storage(), "DOG", institution_id=dog.institution_id, target_id=dog.id, dry_run=False, analysis=fake
        )
    assert caught.value.code == code
    assert _rows_of_dog(db, dog.id) == rows and _purge_logs(db) == []


def test_institution_purge_deletes_every_job_of_the_institution_only(
    client: TestClient, db: Session, dog, staff, other_staff, admin_headers, analysis: _FakeAnalysis
) -> None:
    _fill(db, dog, staff, sessions=2)
    job_ids = _give_job_ids(db, dog)
    foreign = another_dog(db, other_staff.institution_id, name="남의 개")
    _fill(db, foreign, other_staff, sessions=1)
    _give_job_ids(db, foreign)

    response = client.post(PURGE, json={"scope": "INSTITUTION", "dry_run": False}, headers=admin_headers)
    assert response.status_code == 200, response.text
    assert response.json()["analysis_jobs"] == 2
    assert sorted(analysis.deleted) == sorted(job_ids)


def test_analysis_failure_stops_before_anything_is_deleted_and_a_retry_finishes(
    client: TestClient, db: Session, dog, staff, admin_headers, analysis: _FakeAnalysis
) -> None:
    """무응답이면 멈춘다(조영운 결정 11-05). job_id가 행에 남아 있어야 사본을 다시 찾을 수 있다."""
    rows = _fill(db, dog, staff, sessions=2)
    files, size = _expected_files(2)
    job_ids = _give_job_ids(db, dog)
    for job_id in job_ids:
        analysis.fail[job_id] = AnalysisClientError("연결 실패")

    response = _purge_dog(client, dog, admin_headers)
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "ANALYSIS_UNAVAILABLE"
    assert _rows_of_dog(db, dog.id) == rows
    assert get_storage().stat_prefix(dog_prefix(dog.institution_id, dog.id)) == (files, size)
    assert _purge_logs(db) == []
    assert sum(1 for job_id in job_ids if db.scalar(select(Shot.id).where(Shot.job_id == job_id))) == 2

    analysis.fail.clear()
    retry = _purge_dog(client, dog, admin_headers)
    assert retry.status_code == 200, retry.text
    assert retry.json()["analysis_jobs"] == 2
    assert _rows_of_dog(db, dog.id) == 0
    (log,) = _purge_logs(db)
    assert log.analysis_jobs_deleted == 2


@pytest.mark.parametrize(
    ("status", "code", "http_status"),
    [
        (409, "SHOT_IN_PROGRESS", 409),
        (401, "ANALYSIS_UNAVAILABLE", 503),
        (500, "ANALYSIS_UNAVAILABLE", 503),
    ],
)
def test_analysis_answers_map_to_our_error_codes(
    client: TestClient,
    db: Session,
    dog,
    staff,
    admin_headers,
    analysis: _FakeAnalysis,
    status: int,
    code: str,
    http_status: int,
) -> None:
    rows = _fill(db, dog, staff, sessions=1)
    for job_id in _give_job_ids(db, dog):
        analysis.fail[job_id] = AnalysisClientError("거절", status_code=status)
    response = _purge_dog(client, dog, admin_headers)
    assert response.status_code == http_status, response.text
    assert response.json()["error"]["code"] == code
    assert _rows_of_dog(db, dog.id) == rows


def test_api_process_left_on_mock_refuses_real_job_ids(
    client: TestClient, db: Session, dog, staff, admin_headers
) -> None:
    """API 프로세스에 ANALYSIS_API_*가 빠져 mock으로 뜨면 실제 사본을 지운 것으로 치지 않고 멈춘다(6절)."""
    rows = _fill(db, dog, staff, sessions=1)
    _give_job_ids(db, dog)  # Mock이 만든 형식이 아닌 작업 ID
    response = _purge_dog(client, dog, admin_headers)
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "ANALYSIS_UNAVAILABLE"
    assert _rows_of_dog(db, dog.id) == rows


def test_a_purge_with_jobs_needs_a_client(db: Session, dog, staff) -> None:
    _fill(db, dog, staff, sessions=1)
    _give_job_ids(db, dog)
    with pytest.raises(ValueError, match="분석 클라이언트"):
        purge(db, get_storage(), "DOG", institution_id=dog.institution_id, target_id=dog.id, dry_run=False)


def test_all_scope_leaves_the_analysis_copies_to_the_other_command(db: Session, dog, staff) -> None:
    """ALL은 작업마다 부르지 않는다. 버려진 작업까지 쓸어 가는 분석 API 전체 파기 명령으로 나눈다(15.9)."""
    _fill(db, dog, staff, sessions=1)
    _give_job_ids(db, dog)
    assert purge(db, get_storage(), "ALL").analysis_jobs == 0
    result = purge(db, get_storage(), "ALL", dry_run=False)  # 클라이언트 없이 끝난다
    assert result.analysis_jobs == 0
    (log,) = _purge_logs(db)
    assert log.analysis_jobs_deleted == 0


# ---- 전체 파기(ALL): 서비스와 스크립트 ----


def test_all_scope_purges_every_institution_but_keeps_accounts(db: Session, dog, staff, other_staff) -> None:
    rows = _fill(db, dog, staff) + _fill(db, another_dog(db, other_staff.institution_id), other_staff, sessions=1)
    files, size = (a + b for a, b in zip(_expected_files(2), _expected_files(1), strict=True))

    dry = purge(db, get_storage(), "ALL")
    assert (dry.dry_run, dry.rows, dry.files, dry.bytes, dry.purge_log_id) == (True, rows, files, size, None)

    result = purge(db, get_storage(), "ALL", dry_run=False)
    assert (result.scope, result.target_id, result.rows, result.files, result.bytes) == (
        "ALL",
        None,
        rows,
        files,
        size,
    )
    assert db.scalar(select(func.count()).select_from(Dog)) == 0
    assert db.scalar(select(func.count()).select_from(Institution)) == 2
    assert db.scalar(select(func.count()).select_from(Staff)) == 2
    for institution_id in (staff.institution_id, other_staff.institution_id):
        assert get_storage().stat_prefix(institution_prefix(institution_id)) == (0, 0)
    (log,) = _purge_logs(db)
    assert (log.scope, log.target_id, log.executed_by, log.rows_deleted) == ("ALL", None, None, rows)


class _FakeSessionLocal:
    """스크립트의 SessionLocal 자리. DB 없이 with 블록과 begin()만 흉내 낸다."""

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False

    @contextmanager
    def begin(self):
        yield


@pytest.fixture
def fake_purge(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """scripts.purge가 부르는 purge()를 기록만 하는 함수로 바꿔 끼운다."""
    calls: list[dict] = []

    def _purge(session, storage, scope, **kwargs) -> PurgeOut:
        calls.append({"scope": scope, **kwargs})
        dry_run = kwargs.get("dry_run", True)
        return PurgeOut(
            scope=scope,
            target_id=None,
            dry_run=dry_run,
            rows=12,
            files=3,
            bytes=4096,
            purge_log_id=None if dry_run else uuid.UUID("3f2a9c1e-5b7d-4e8a-9c21-7d4e5f6a8b90"),
        )

    monkeypatch.setattr(purge_script, "SessionLocal", _FakeSessionLocal)
    monkeypatch.setattr(purge_script, "purge", _purge)
    monkeypatch.setattr(purge_script, "get_storage", lambda: None)
    return calls


def test_script_without_execute_only_counts(fake_purge: list[dict], capsys) -> None:
    assert purge_script.run(["--all"]) == 0
    assert fake_purge == [{"scope": "ALL", "dry_run": True}]
    out = capsys.readouterr().out
    assert "지울 양" in out and "행 12개, 파일 3개, 4096 bytes" in out and "파기 기록" not in out


def test_script_execute_asks_for_the_confirm_word(fake_purge: list[dict], capsys) -> None:
    assert purge_script.run(["--all", "--execute"], ask=lambda _prompt: "no") == 1
    assert fake_purge == []
    assert "취소" in capsys.readouterr().err

    assert purge_script.run(["--all", "--execute"], ask=lambda _prompt: " PURGE ") == 0
    assert fake_purge == [{"scope": "ALL", "dry_run": False}]
    out = capsys.readouterr().out
    assert "지운 양" in out and "파기 기록 ID: 3f2a9c1e-5b7d-4e8a-9c21-7d4e5f6a8b90" in out
    assert "python purge.py --all --execute" in out  # 분석 API 저장소는 그쪽 명령으로 따로 지운다


def test_script_yes_skips_the_question_and_all_is_required(fake_purge: list[dict]) -> None:
    assert purge_script.run(["--all", "--execute", "--yes"], ask=lambda _prompt: pytest.fail("물으면 안 된다")) == 0
    assert fake_purge == [{"scope": "ALL", "dry_run": False}]
    with pytest.raises(SystemExit):
        purge_script.run([])


def test_dog_fixture_weight_is_not_touched_by_fixtures(dog) -> None:
    """history_fixtures가 반려견 행을 바꾸지 않는지(파기 집계가 반려견 1행을 세는 전제)."""
    assert dog.weight_kg == Decimal("28.40")


# ---- 잠금과 두 단계(12.4, 199 리뷰 박규원) ----


def _shots_of(db: Session, dog) -> list[Shot]:
    return list(
        db.scalars(
            select(Shot)
            .join(MeasureSession, Shot.session_id == MeasureSession.id)
            .where(MeasureSession.dog_id == dog.id)
            .order_by(MeasureSession.measured_on)
        )
    )


def test_a_job_that_appears_while_waiting_is_deleted_under_the_lock(db: Session, dog, staff) -> None:
    """1단계(잠금 밖)에서 분석 API를 기다리는 사이 생긴 작업은 2단계에서 회차 행을 잠근 뒤 마저 지운다."""
    _fill(db, dog, staff, sessions=2)
    first, second = _shots_of(db, dog)
    first.job_id = "job-first"
    db.flush()
    second_id = second.id
    with _recorded_sql(db) as events:
        fake = _FakeAnalysis(events)

        def meanwhile(job_id: str) -> None:
            if job_id == "job-first":
                db.execute(update(Shot).where(Shot.id == second_id).values(job_id="job-late"))

        fake.hook = meanwhile
        result = purge(
            db, get_storage(), "DOG", institution_id=dog.institution_id, target_id=dog.id, dry_run=False, analysis=fake
        )
    assert fake.deleted == ["job-first", "job-late"]
    assert result.analysis_jobs == 2
    lock = next(i for i, statement in enumerate(events) if _is_session_lock(statement))
    calls = [i for i, statement in enumerate(events) if statement == _FakeAnalysis.MARK]
    # 잠그기 전: 촬영 둘의 촬영 단위 호출과 job-first. 잠근 뒤: 작업 ID가 바뀐 촬영의 촬영 단위 호출과 job-late
    assert [i < lock for i in calls] == [True, True, True, False, False]
    assert _rows_of_dog(db, dog.id) == 0
    (log,) = _purge_logs(db)
    assert log.analysis_jobs_deleted == 2


def test_a_shot_submitted_while_waiting_stops_the_purge_with_everything_in_place(db: Session, dog, staff) -> None:
    """미리 볼 때는 없던 분석 중 촬영이 2단계에서 잠근 뒤 보이면 409이고 팀 서비스 쪽은 그대로다."""
    rows = _fill(db, dog, staff, sessions=1)
    _give_job_ids(db, dog)
    waiting = add_shot(db, make_session(db, dog, staff, date(2026, 10, 20)), 1, status="UPLOADED", passes={})
    waiting_id = waiting.id
    fake = _FakeAnalysis()
    fake.hook = lambda job_id: db.execute(update(Shot).where(Shot.id == waiting_id).values(status="SUBMITTED"))

    with pytest.raises(AppError) as caught:
        purge(
            db, get_storage(), "DOG", institution_id=dog.institution_id, target_id=dog.id, dry_run=False, analysis=fake
        )
    assert caught.value.code == ErrorCode.SHOT_IN_PROGRESS
    assert _rows_of_dog(db, dog.id) == rows + 2  # 회차와 촬영 하나가 더 있다
    assert get_storage().stat_prefix(dog_prefix(dog.institution_id, dog.id)) == _expected_files(1)
    assert _purge_logs(db) == []


def test_institution_purge_locks_the_institution_then_dogs_then_sessions_after_the_calls(
    db: Session, dog, staff
) -> None:
    """INSTITUTION은 분석 API를 부른 뒤에 잠근다. 기관의 반려견을 모두 쥔 채 HTTP를 기다리지 않는다.

    기관 행을 잠그면 그사이 새 반려견이 생기지 못하고(FK), 반려견 행을 잠그면 회차 시작·복원이 기다린다.
    """
    _fill(db, dog, staff, sessions=1)
    _give_job_ids(db, dog)
    with _recorded_sql(db) as events:
        fake = _FakeAnalysis(events)
        purge(db, get_storage(), "INSTITUTION", institution_id=dog.institution_id, dry_run=False, analysis=fake)
    last_call = len(events) - 1 - events[::-1].index(_FakeAnalysis.MARK)
    institution_lock = next(i for i, statement in enumerate(events) if _is_institution_lock(statement))
    dog_lock = next(i for i, statement in enumerate(events) if _is_dog_lock(statement))
    session_lock = next(i for i, statement in enumerate(events) if _is_session_lock(statement))
    first_delete = next(i for i, statement in enumerate(events) if statement.lstrip().upper().startswith("DELETE"))
    assert last_call < institution_lock < dog_lock < session_lock < first_delete
    assert _rows_of_dog(db, dog.id) == 0


def test_the_accounts_flag_is_refused_before_anything_is_deleted(db: Session, dog, staff) -> None:
    rows = _fill(db, dog, staff, sessions=1)
    _give_job_ids(db, dog)
    fake = _FakeAnalysis()
    with pytest.raises(ValueError, match="INSTITUTION"):
        purge(
            db,
            get_storage(),
            "DOG",
            institution_id=dog.institution_id,
            target_id=dog.id,
            dry_run=False,
            analysis=fake,
            include_accounts=True,
        )
    assert fake.deleted == [] and _rows_of_dog(db, dog.id) == rows


def test_a_deadline_that_has_passed_defers_the_purge_without_deleting(db: Session, dog, staff) -> None:
    """워커의 자동 파기가 넘기는 시간 상한. 넘겼으면 OutOfTime이고 아무것도 지우지 않는다."""
    rows = _fill(db, dog, staff, sessions=1)
    _give_job_ids(db, dog)
    fake = _FakeAnalysis()
    with pytest.raises(OutOfTime):
        purge(
            db,
            get_storage(),
            "DOG",
            institution_id=dog.institution_id,
            target_id=dog.id,
            dry_run=False,
            analysis=fake,
            deadline=time.monotonic() - 1,
        )
    assert fake.deleted == [] and _rows_of_dog(db, dog.id) == rows and _purge_logs(db) == []
