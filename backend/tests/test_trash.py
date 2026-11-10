"""반려견 휴지통(명세 12.5, 15.5 DELETE /dogs/{dog_id}·restore·permanent, 17.6 BE-19, S15P31A404-199)."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClientError
from app.models import Dog, MeasureSession
from app.services.dogs import TRASH_RETENTION_DAYS
from app.services.purge import SweepResult
from app.services.trash import purge_expired
from app.storage.base import get_storage
from app.storage.keys import dog_prefix
from tests.conftest import bearer
from tests.history_fixtures import add_shot, another_dog, make_session
from tests.test_purge import (
    _expected_files,
    _FakeAnalysis,
    _fill,
    _give_job_ids,
    _is_dog_lock,
    _purge_logs,
    _recorded_sql,
    _rows_of_dog,
    admin,  # noqa: F401  (픽스처)
    admin_headers,  # noqa: F401  (픽스처)
    analysis,  # noqa: F401  (픽스처)
)

DOGS = "/api/v1/dogs"
PURGE = "/api/v1/admin/purge"


def _trash(client: TestClient, dog_id: uuid.UUID, headers: dict[str, str]):
    return client.delete(f"{DOGS}/{dog_id}", headers=headers)


def _trash_ids(client: TestClient, headers: dict[str, str]) -> list[str]:
    return [item["id"] for item in client.get(DOGS, params={"trash": "true"}, headers=headers).json()["items"]]


def _age_trash(db: Session, dog: Dog, days: int) -> None:
    """휴지통에 넣은 시각을 days일 전으로 돌린다."""
    dog.deleted_at = datetime.now(UTC) - timedelta(days=days)
    db.flush()


def test_delete_moves_the_dog_to_the_trash_and_keeps_everything(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    dog_id, institution_id = dog.id, staff.institution_id
    rows = _fill(db, dog, staff, sessions=2)
    kept = another_dog(db, institution_id)
    session_id = db.scalar(select(MeasureSession.id).where(MeasureSession.dog_id == dog_id).limit(1))

    response = _trash(client, dog_id, auth_headers)  # CLIENT
    assert response.status_code == 204, response.text
    assert response.content == b""
    # 아무것도 지우지 않았다. 기록도 없다
    assert _rows_of_dog(db, dog_id) == rows
    assert get_storage().stat_prefix(dog_prefix(institution_id, dog_id)) == _expected_files(2)
    assert _purge_logs(db) == []

    # 목록·상세·회차·수정 어디에서도 보이지 않는다(없는 것과 같은 404)
    listed = client.get(DOGS, headers=auth_headers).json()
    assert ([item["id"] for item in listed["items"]], listed["total"]) == ([str(kept.id)], 1)
    assert client.get(f"{DOGS}/{dog_id}", headers=auth_headers).status_code == 404
    assert client.get(f"{DOGS}/{dog_id}/sessions", headers=auth_headers).status_code == 404
    assert client.get(f"/api/v1/sessions/{session_id}", headers=auth_headers).status_code == 404
    assert client.get(f"/api/v1/sessions/{session_id}/result", headers=auth_headers).status_code == 404
    assert client.post(f"{DOGS}/{dog_id}/sessions", json={}, headers=auth_headers).status_code == 404
    assert client.patch(f"{DOGS}/{dog_id}", json={"version": 0, "memo": "x"}, headers=auth_headers).status_code == 404
    assert _trash(client, dog_id, auth_headers).status_code == 404  # 이미 휴지통에 있다

    # 휴지통 목록에는 넣은 시각과 영구 삭제 예정 시각이 함께 온다
    trash = client.get(DOGS, params={"trash": "true"}, headers=auth_headers).json()
    assert (trash["total"], [item["id"] for item in trash["items"]]) == (1, [str(dog_id)])
    item = trash["items"][0]
    deleted_at = datetime.fromisoformat(item["deleted_at"])
    assert datetime.now(UTC) - timedelta(minutes=1) <= deleted_at <= datetime.now(UTC) + timedelta(minutes=1)
    assert datetime.fromisoformat(item["purge_at"]) - deleted_at == timedelta(days=TRASH_RETENTION_DAYS)
    assert item["session_count"] == 2
    # 휴지통에 없는 반려견은 두 값이 null이다
    assert (listed["items"][0]["deleted_at"], listed["items"][0]["purge_at"]) == (None, None)


def test_restore_brings_everything_back(client: TestClient, db: Session, dog, staff, auth_headers, other_staff) -> None:
    dog_id = dog.id
    rows = _fill(db, dog, staff, sessions=1)
    assert client.post(f"{DOGS}/{dog_id}/restore", headers=auth_headers).status_code == 404  # 휴지통에 없다
    assert _trash(client, dog_id, auth_headers).status_code == 204
    assert client.post(f"{DOGS}/{dog_id}/restore", headers=bearer(other_staff)).status_code == 404  # 다른 기관

    restored = client.post(f"{DOGS}/{dog_id}/restore", headers=auth_headers)
    assert restored.status_code == 200, restored.text
    body = restored.json()
    assert (body["id"], body["deleted_at"], body["purge_at"], body["session_count"]) == (str(dog_id), None, None, 1)
    assert client.get(f"{DOGS}/{dog_id}", headers=auth_headers).status_code == 200
    assert client.get(f"{DOGS}/{dog_id}/sessions", headers=auth_headers).json()["total"] == 1
    assert _trash_ids(client, auth_headers) == []
    assert _rows_of_dog(db, dog_id) == rows


def test_permanent_delete_works_only_from_the_trash(
    client: TestClient,
    db: Session,
    dog,
    staff,
    auth_headers,
    other_staff,
    analysis: _FakeAnalysis,  # noqa: F811
) -> None:
    dog_id, staff_id, institution_id = dog.id, staff.id, staff.institution_id
    rows = _fill(db, dog, staff, sessions=2)
    kept = another_dog(db, institution_id)
    kept_id = kept.id
    kept_rows = _fill(db, kept, staff, sessions=1)
    job_ids = _give_job_ids(db, dog)
    url = f"{DOGS}/{dog_id}/permanent"

    # 휴지통을 거치지 않으면 영구 삭제할 수 없다
    assert client.delete(url, headers=auth_headers).status_code == 404
    assert _rows_of_dog(db, dog_id) == rows
    assert _trash(client, dog_id, auth_headers).status_code == 204
    assert client.delete(url).status_code == 401
    assert client.delete(url, headers=bearer(other_staff)).status_code == 404

    # 분석 API가 지우지 못하면 멈추고 휴지통에 그대로 남는다. 다시 누르면 끝난다
    analysis.fail[job_ids[0]] = AnalysisClientError("연결 실패")
    failed = client.delete(url, headers=auth_headers)
    assert failed.status_code == 503 and failed.json()["error"]["code"] == "ANALYSIS_UNAVAILABLE"
    assert _rows_of_dog(db, dog_id) == rows
    assert _trash_ids(client, auth_headers) == [str(dog_id)]
    analysis.fail.clear()

    response = client.delete(url, headers=auth_headers)
    assert response.status_code == 204, response.text
    assert _rows_of_dog(db, dog_id) == 0
    assert get_storage().stat_prefix(dog_prefix(institution_id, dog_id)) == (0, 0)
    # 실패 전에 먼저 지운 작업은 다시 누를 때 한 번 더 불린다(실제 분석 API는 404로 답하고 성공으로 친다)
    assert set(analysis.deleted) == set(job_ids)
    assert _trash_ids(client, auth_headers) == []
    # 같은 기관의 다른 반려견은 그대로다
    assert _rows_of_dog(db, kept_id) == kept_rows
    # 관리자 파기와 같이 기록이 남는다(D-13)
    (log,) = _purge_logs(db)
    assert (log.scope, log.target_id, log.rows_deleted, log.executed_by) == ("DOG", dog_id, rows, staff_id)


def test_a_shot_in_progress_blocks_the_trash(client: TestClient, db: Session, dog, staff, auth_headers) -> None:
    _fill(db, dog, staff, sessions=1)
    session = make_session(db, dog, staff, date(2026, 10, 25), status="MEASURING", model_version=None)
    add_shot(db, session, 1, status="SUBMITTED", passes={})
    response = _trash(client, dog.id, auth_headers)
    assert response.status_code == 409 and response.json()["error"]["code"] == "SHOT_IN_PROGRESS"
    assert client.get(f"{DOGS}/{dog.id}", headers=auth_headers).status_code == 200
    assert _trash_ids(client, auth_headers) == []


def test_other_institutions_and_strangers_cannot_trash(
    client: TestClient, db: Session, dog, staff, other_staff, auth_headers
) -> None:
    assert client.delete(f"{DOGS}/{dog.id}").status_code == 401
    assert _trash(client, dog.id, bearer(other_staff)).status_code == 404
    assert _trash(client, uuid.uuid4(), auth_headers).status_code == 404
    assert client.get(f"{DOGS}/{dog.id}", headers=auth_headers).status_code == 200
    # 휴지통 목록도 기관별이다
    assert _trash(client, dog.id, auth_headers).status_code == 204
    assert _trash_ids(client, bearer(other_staff)) == []


def test_the_sweep_empties_only_what_stayed_thirty_days(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    institution_id = staff.institution_id
    old, fresh, active = dog, another_dog(db, institution_id, name="어제 넣음"), another_dog(db, institution_id)
    old_id, fresh_id, active_id = old.id, fresh.id, active.id
    old_rows = _fill(db, old, staff, sessions=1)
    fresh_rows = _fill(db, fresh, staff, sessions=1)
    active_rows = _fill(db, active, staff, sessions=1)
    (job_id,) = _give_job_ids(db, old)
    for target in (old_id, fresh_id):
        assert _trash(client, target, auth_headers).status_code == 204
    _age_trash(db, old, TRASH_RETENTION_DAYS + 1)
    _age_trash(db, fresh, TRASH_RETENTION_DAYS - 1)
    fake = _FakeAnalysis()

    assert purge_expired(db, get_storage(), fake) == SweepResult(1, 0)
    assert fake.deleted == [job_id]
    assert _rows_of_dog(db, old_id) == 0
    assert get_storage().stat_prefix(dog_prefix(institution_id, old_id)) == (0, 0)
    assert (_rows_of_dog(db, fresh_id), _rows_of_dog(db, active_id)) == (fresh_rows, active_rows)
    assert old_rows == fresh_rows
    (log,) = _purge_logs(db)
    assert (log.scope, log.target_id, log.executed_by) == ("DOG", old_id, None)  # 사람이 누른 것이 아니다
    # 한 번 더 돌려도 더 지우지 않는다
    assert purge_expired(db, get_storage(), fake) == SweepResult(0, 0)
    # 30일이 되는 순간부터 대상이다
    assert purge_expired(db, get_storage(), fake, now=datetime.now(UTC) + timedelta(days=2)) == SweepResult(1, 0)
    assert _rows_of_dog(db, fresh_id) == 0


def test_the_sweep_stops_when_the_analysis_api_is_down(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    institution_id = staff.institution_id
    second = another_dog(db, institution_id, name="둘째")
    first_id, second_id = dog.id, second.id
    rows = _fill(db, dog, staff, sessions=1)
    _fill(db, second, staff, sessions=1)
    fake = _FakeAnalysis()
    for target in (dog, second):
        for job_id in _give_job_ids(db, target):
            fake.fail[job_id] = AnalysisClientError("연결 실패")
        assert _trash(client, target.id, auth_headers).status_code == 204
        _age_trash(db, target, TRASH_RETENTION_DAYS + 5)

    assert purge_expired(db, get_storage(), fake) == SweepResult(0, 2)  # 첫 실패에서 멈추고 둘 다 남긴다
    assert (_rows_of_dog(db, first_id), _rows_of_dog(db, second_id)) == (rows, rows)
    assert get_storage().stat_prefix(dog_prefix(institution_id, first_id)) == _expected_files(1)
    assert _purge_logs(db) == []
    assert sorted(_trash_ids(client, auth_headers)) == sorted([str(first_id), str(second_id)])
    fake.fail.clear()
    assert purge_expired(db, get_storage(), fake) == SweepResult(2, 0)


def test_admin_purge_reaches_dogs_in_the_trash(
    client: TestClient,
    db: Session,
    dog,
    staff,
    auth_headers,
    admin_headers,  # noqa: F811
) -> None:
    dog_id = dog.id
    second = another_dog(db, staff.institution_id, name="둘째")
    second_id = second.id
    rows = _fill(db, dog, staff, sessions=1)
    second_rows = _fill(db, second, staff, sessions=1)
    for target in (dog_id, second_id):
        assert _trash(client, target, auth_headers).status_code == 204

    one = client.post(PURGE, json={"scope": "DOG", "target_id": str(dog_id), "dry_run": False}, headers=admin_headers)
    assert (one.status_code, one.json()["rows"]) == (200, rows)
    assert _rows_of_dog(db, dog_id) == 0
    whole = client.post(PURGE, json={"scope": "INSTITUTION", "dry_run": False}, headers=admin_headers)
    assert (whole.status_code, whole.json()["rows"]) == (200, second_rows)
    assert _rows_of_dog(db, second_id) == 0


@pytest.mark.parametrize("value", ["true", "1"])
def test_trash_query_accepts_boolean_spellings(client: TestClient, auth_headers, value: str) -> None:
    response = client.get(DOGS, params={"trash": value}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["items"] == []


# ---- 잠금과 시간 상한(12.4, 199 리뷰 박규원) ----


def test_trash_and_restore_lock_the_dog_row(client: TestClient, db: Session, dog, staff, auth_headers) -> None:
    """넣기·복원은 반려견 행을 잠근 뒤 본다. 파기도 같은 행을 잠그므로 '복원했다'고 답한 반려견이 지워지지 않는다."""
    with _recorded_sql(db) as events:
        assert _trash(client, dog.id, auth_headers).status_code == 204
    assert any(_is_dog_lock(statement) for statement in events)
    with _recorded_sql(db) as events:
        assert client.post(f"{DOGS}/{dog.id}/restore", headers=auth_headers).status_code == 200
    assert any(_is_dog_lock(statement) for statement in events)


def test_the_sweep_skips_a_dog_that_was_restored_after_it_was_listed(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    """후보를 읽은 뒤 복원한 반려견은 지우지 않는다. 잠근 뒤 아직 휴지통에 있는지 다시 본다."""
    institution_id = staff.institution_id
    second = another_dog(db, institution_id, name="둘째")
    first_id, second_id = dog.id, second.id
    _fill(db, dog, staff, sessions=1)
    second_rows = _fill(db, second, staff, sessions=1)
    _give_job_ids(db, dog)
    for target in (dog, second):
        assert _trash(client, target.id, auth_headers).status_code == 204
    _age_trash(db, dog, TRASH_RETENTION_DAYS + 9)  # 먼저 넣은 것부터 지운다
    _age_trash(db, second, TRASH_RETENTION_DAYS + 5)
    fake = _FakeAnalysis()
    # 첫째의 분석 사본을 지우는 사이 담당자가 둘째를 복원했다
    fake.hook = lambda job_id: db.execute(update(Dog).where(Dog.id == second_id).values(deleted_at=None))

    assert purge_expired(db, get_storage(), fake) == SweepResult(1, 0)
    assert _rows_of_dog(db, first_id) == 0
    assert _rows_of_dog(db, second_id) == second_rows
    assert client.get(f"{DOGS}/{second_id}", headers=auth_headers).status_code == 200
    assert len(_purge_logs(db)) == 1


def test_the_sweep_stops_at_the_time_limit_and_finishes_later(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    """시간 상한에 닿으면 남은 것을 다음 차례로 미룬다. 그때까지 지운 분석 사본은 다시 불러도 성공이라 이어진다."""
    dog_id = dog.id
    rows = _fill(db, dog, staff, sessions=2)
    job_ids = _give_job_ids(db, dog)
    assert _trash(client, dog_id, auth_headers).status_code == 204
    _age_trash(db, dog, TRASH_RETENTION_DAYS + 1)
    fake = _FakeAnalysis()
    fake.hook = lambda job_id: time.sleep(0.6)  # 분석 API가 느리게 답한다
    cleared: dict = {}  # 워커가 차례마다 넘기는 것. 끝낸 촬영을 적어 둔다

    result = purge_expired(db, get_storage(), fake, deadline=time.monotonic() + 0.5, cleared=cleared)
    assert result == SweepResult(0, 0, out_of_time=True)
    assert len(fake.deleted) == 1 and _rows_of_dog(db, dog_id) == rows and _purge_logs(db) == []
    (finished,) = fake.shot_calls
    # 이미 지난 상한이면 시작하지 않는다
    late = time.monotonic() - 1
    assert purge_expired(db, get_storage(), fake, deadline=late, cleared=cleared) == SweepResult(0, 0, out_of_time=True)
    assert len(fake.deleted) == 1

    fake.hook = None
    assert purge_expired(db, get_storage(), fake, cleared=cleared) == SweepResult(1, 0)
    assert _rows_of_dog(db, dog_id) == 0 and set(fake.deleted) == set(job_ids)
    # 앞 차례에 끝낸 촬영은 다시 묻지 않았고(분석 API는 물을 때마다 작업을 모두 훑는다), 지운 수에는 그것도 든다
    assert fake.shot_calls.count(finished) == 1 and len(fake.shot_calls) == 2
    (log,) = _purge_logs(db)
    assert log.analysis_jobs_deleted == 2
