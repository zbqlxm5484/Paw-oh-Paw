"""계약이 끝난 기관의 자동 파기(명세 7절, 12.5, 13.6, 17.6 BE-19, S15P31A404-199)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClientError
from app.core.dates import CONTRACT_RETENTION_DAYS, today_local
from app.models import DeviceCode, Dog, Institution, Staff
from app.services.retention import purge_expired_contracts
from app.storage.base import get_storage
from app.storage.keys import institution_prefix
from tests.conftest import GOOD_PASSWORD, password_hash_for
from tests.history_fixtures import another_dog
from tests.test_purge import (
    _expected_files,
    _FakeAnalysis,
    _fill,
    _give_job_ids,
    _purge_logs,
    _rows_of_dog,
    admin,  # noqa: F401  (픽스처)
    admin_headers,  # noqa: F401  (픽스처)
)

INSTITUTIONS = "/api/v1/admin/institutions"


def _end_contract(db: Session, institution_id, days_ago: int) -> None:
    """계약 종료일을 days_ago일 전으로 둔다(입력 규칙을 거치지 않고 DB에 직접)."""
    institution = db.get(Institution, institution_id)
    institution.contract_ends_at = today_local() - timedelta(days=days_ago)
    db.flush()


def _account(db: Session, institution_id, login_id: str, *, role: str = "CLIENT", is_active: bool = True) -> Staff:
    row = Staff(
        institution_id=institution_id,
        login_id=login_id,
        password_hash=password_hash_for(GOOD_PASSWORD),
        name="계정",
        role=role,
        is_active=is_active,
    )
    db.add(row)
    db.flush()
    return row


def _accounts(db: Session, institution_id) -> dict[str, str]:
    rows = db.execute(select(Staff.login_id, Staff.role).where(Staff.institution_id == institution_id)).all()
    return dict(rows)


def test_data_and_accounts_go_ninety_days_after_the_contract_ended(db: Session, dog, staff, other_staff) -> None:
    institution_id, other_id, dog_id = staff.institution_id, other_staff.institution_id, dog.id
    rows = _fill(db, dog, staff, sessions=2)
    trashed = another_dog(db, institution_id, name="휴지통")
    trashed_id = trashed.id
    trashed_rows = _fill(db, trashed, staff, sessions=1)
    trashed.deleted_at = func.now()
    job_ids = _give_job_ids(db, dog) + _give_job_ids(db, trashed)
    code = DeviceCode(institution_id=institution_id, code="A" * 20)
    db.add(code)
    db.flush()
    code_id = code.id
    _account(db, institution_id, "stopped01", is_active=False)
    _account(db, institution_id, "keeper01", role="STAFF")  # 크림오프 계정은 지우지 않는다
    before = _accounts(db, institution_id)
    client_accounts = sum(1 for role in before.values() if role == "CLIENT")
    foreign = another_dog(db, other_id, name="남의 개")
    foreign_id = foreign.id
    foreign_rows = _fill(db, foreign, other_staff, sessions=1)
    _end_contract(db, institution_id, CONTRACT_RETENTION_DAYS + 1)
    _end_contract(db, other_id, CONTRACT_RETENTION_DAYS)  # 딱 90일째는 아직 대상이 아니다
    fake = _FakeAnalysis()

    assert purge_expired_contracts(db, get_storage(), fake) == (1, 0)

    # 측정 자료: 휴지통에 있던 것까지 행·파일·분석 사본이 모두 없다
    assert (_rows_of_dog(db, dog_id), _rows_of_dog(db, trashed_id)) == (0, 0)
    assert get_storage().stat_prefix(institution_prefix(institution_id)) == (0, 0)
    assert sorted(fake.deleted) == sorted(job_ids)
    # 가입 계정(중지한 것 포함)은 지워지고 크림오프 계정은 남는다
    assert _accounts(db, institution_id) == {"keeper01": "STAFF"}
    # 기관과 디바이스 코드는 지우지 않는다
    assert db.get(Institution, institution_id) is not None
    assert db.get(DeviceCode, code_id) is not None
    # 기록: 사람이 누른 것이 아니고, 지운 행 수에 계정이 들어 있다
    (log,) = _purge_logs(db)
    assert (log.scope, log.target_id, log.executed_by) == ("INSTITUTION", institution_id, None)
    assert log.rows_deleted == rows + trashed_rows + client_accounts
    # 90일째인 기관은 그대로다
    assert _rows_of_dog(db, foreign_id) == foreign_rows
    assert db.get(Staff, other_staff.id) is not None

    # 다 지운 기관은 다시 보지 않는다(기록도 더 남기지 않는다)
    assert purge_expired_contracts(db, get_storage(), fake) == (0, 0)
    assert len(_purge_logs(db)) == 1
    # 하루가 더 지나면 그 기관도 대상이다
    assert purge_expired_contracts(db, get_storage(), fake, today=today_local() + timedelta(days=1)) == (1, 0)
    assert _rows_of_dog(db, foreign_id) == 0


def test_active_and_open_ended_contracts_are_never_touched(db: Session, dog, staff, other_staff) -> None:
    rows = _fill(db, dog, staff, sessions=1)
    foreign = another_dog(db, other_staff.institution_id, name="남의 개")
    foreign_rows = _fill(db, foreign, other_staff, sessions=1)
    _end_contract(db, other_staff.institution_id, CONTRACT_RETENTION_DAYS - 1)
    assert db.get(Institution, staff.institution_id).contract_ends_at is None  # 기한 없음

    assert purge_expired_contracts(db, get_storage(), _FakeAnalysis()) == (0, 0)
    assert (_rows_of_dog(db, dog.id), _rows_of_dog(db, foreign.id)) == (rows, foreign_rows)
    assert db.scalar(select(func.count()).select_from(Staff)) == 2
    assert _purge_logs(db) == []


def test_accounts_alone_are_enough_to_purge(db: Session, staff) -> None:
    """반려견이 없어도 가입 계정이 남아 있으면 지운다."""
    institution_id = staff.institution_id
    _end_contract(db, institution_id, CONTRACT_RETENTION_DAYS + 30)
    assert purge_expired_contracts(db, get_storage(), _FakeAnalysis()) == (1, 0)
    assert _accounts(db, institution_id) == {}
    (log,) = _purge_logs(db)
    assert log.rows_deleted == 1


def test_nothing_is_deleted_when_the_analysis_api_is_down(db: Session, dog, staff) -> None:
    institution_id, dog_id = staff.institution_id, dog.id
    rows = _fill(db, dog, staff, sessions=1)
    fake = _FakeAnalysis()
    for job_id in _give_job_ids(db, dog):
        fake.fail[job_id] = AnalysisClientError("연결 실패")
    _end_contract(db, institution_id, CONTRACT_RETENTION_DAYS + 1)

    assert purge_expired_contracts(db, get_storage(), fake) == (0, 1)
    assert _rows_of_dog(db, dog_id) == rows
    assert get_storage().stat_prefix(institution_prefix(institution_id)) == _expected_files(1)
    assert db.scalar(select(func.count()).select_from(Dog).where(Dog.institution_id == institution_id)) == 1
    assert _accounts(db, institution_id) != {}  # 계정도 그대로다
    assert _purge_logs(db) == []
    fake.fail.clear()
    assert purge_expired_contracts(db, get_storage(), fake) == (1, 0)


def test_admin_purge_still_keeps_the_accounts(
    client: TestClient,
    db: Session,
    dog,
    staff,
    admin_headers,  # noqa: F811
) -> None:
    """관리자가 누르는 기관 파기는 자료만 지운다. 계정까지 지우는 것은 계약 종료 뒤 자동 파기뿐이다(15.9)."""
    _fill(db, dog, staff, sessions=1)
    before = _accounts(db, staff.institution_id)
    response = client.post(
        "/api/v1/admin/purge", json={"scope": "INSTITUTION", "dry_run": False}, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    assert _accounts(db, staff.institution_id) == before


@pytest.mark.parametrize("method", ["post", "patch"])
def test_a_contract_end_older_than_the_retention_is_rejected(
    client: TestClient,
    db: Session,
    staff,
    admin_headers,  # noqa: F811
    method: str,
) -> None:
    """13.6: 넣자마자 자동 파기 대상이 되는 날짜는 받지 않는다(날짜를 잘못 적어 자료가 지워지는 일을 막는다)."""
    too_old = (today_local() - timedelta(days=CONTRACT_RETENTION_DAYS + 1)).isoformat()
    oldest_allowed = (today_local() - timedelta(days=CONTRACT_RETENTION_DAYS)).isoformat()

    def send(value: str):
        if method == "post":
            return client.post(INSTITUTIONS, json={"name": "새 병원", "contract_ends_at": value}, headers=admin_headers)
        url = f"{INSTITUTIONS}/{staff.institution_id}"
        return client.patch(url, json={"contract_ends_at": value}, headers=admin_headers)

    rejected = send(too_old)
    assert rejected.status_code == 422, rejected.text
    assert [item["field"] for item in rejected.json()["error"]["detail"]["fields"]] == ["contract_ends_at"]
    accepted = send(oldest_allowed)
    assert accepted.status_code in (200, 201), accepted.text
    assert accepted.json()["contract_ends_at"] == oldest_allowed
