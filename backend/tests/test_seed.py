"""scripts/seed.py: 기관·계정 만들기와 비밀번호 규칙(13.4)."""

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import Institution, Staff
from scripts.seed import SeedError, create_account, main

GOOD = "pass1234"


def _create(db: Session, **overrides: object):
    values = {
        "institution_code": "DEMO",
        "institution_name": "데모 병원",
        "login_id": "admin",
        "name": "관리자",
        "password": GOOD,
        "role": "ADMIN",
    }
    values.update(overrides)
    return create_account(db, **values)


def test_creates_institution_and_account(db: Session) -> None:
    result = _create(db)
    staff = db.get(Staff, result.staff_id)
    assert result.institution_created is True
    assert staff is not None
    assert staff.role == "ADMIN"
    assert staff.institution.code == "DEMO"
    # 비밀번호는 bcrypt 해시로만 저장된다
    assert staff.password_hash != GOOD
    assert staff.password_hash.startswith("$2b$")
    assert verify_password(GOOD, staff.password_hash)
    assert not verify_password("wrong-pass", staff.password_hash)


def test_reuses_existing_institution(db: Session) -> None:
    first = _create(db)
    second = _create(db, institution_name=None, login_id="staff1", role="STAFF")
    assert second.institution_created is False
    assert second.institution_id == first.institution_id
    assert db.scalar(select(func.count()).select_from(Institution)) == 1


def test_same_login_id_in_other_institution_is_allowed(db: Session) -> None:
    _create(db)
    other = _create(db, institution_code="OTHER", institution_name="다른 병원")
    assert other.institution_created is True


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"password": "short7!"}, "8자 이상"),
        ({"password": "가" * 25}, "72바이트"),
        ({"login_id": " admin"}, "공백"),
        ({"login_id": ""}, "비어"),
        ({"institution_code": "C" * 21}, "20자"),
        ({"name": "이" * 51}, "50자"),
        ({"role": "BOSS"}, "역할"),
        ({"institution_code": "NEW", "institution_name": None}, "--institution-name"),
    ],
)
def test_rejects_bad_input(db: Session, overrides: dict, message: str) -> None:
    with pytest.raises(SeedError, match=message):
        _create(db, **overrides)
    assert db.scalar(select(func.count()).select_from(Staff)) == 0


def test_password_byte_limit_edges(db: Session) -> None:
    # 한글 24자 = 72바이트는 된다. 영문 72자도 된다.
    _create(db, login_id="kor", password="가" * 24)
    _create(db, institution_name=None, login_id="eng", password="a" * 72)
    with pytest.raises(SeedError, match="72바이트"):
        _create(db, institution_name=None, login_id="eng73", password="a" * 73)


def test_rejects_duplicate_login(db: Session) -> None:
    _create(db)
    with pytest.raises(SeedError, match="이미 있습니다"):
        _create(db, institution_name=None)


def test_rejects_different_name_for_existing_code(db: Session) -> None:
    _create(db)
    with pytest.raises(SeedError, match="다른 이름"):
        _create(db, institution_name="이름이 다른 병원", login_id="staff2")


def test_main_commits_and_reports_duplicate(engine: Engine, clean_tables: None, capsys) -> None:
    args = [
        "--institution-code", "MAIN",
        "--institution-name", "스크립트 병원",
        "--login-id", "admin",
        "--name", "관리자",
        "--role", "ADMIN",
        "--password", GOOD,
    ]  # fmt: skip
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "기관을 만들었습니다: MAIN" in out
    assert GOOD not in out

    with Session(engine) as check:
        staff = check.scalars(select(Staff).where(Staff.login_id == "admin")).one()
        assert staff.role == "ADMIN"

    assert main(args) == 1
    assert "이미 있습니다" in capsys.readouterr().err


def test_main_asks_password_twice(clean_tables: None, monkeypatch, capsys) -> None:
    answers = iter([GOOD, "different"])
    monkeypatch.setattr("scripts.seed.getpass.getpass", lambda prompt: next(answers))
    args = ["--institution-code", "ASK", "--institution-name", "병원", "--login-id", "a", "--name", "b"]
    assert main(args) == 1
    assert "다릅니다" in capsys.readouterr().err
