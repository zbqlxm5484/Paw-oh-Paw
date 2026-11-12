"""내 기관의 측정 기기(15.4 GET /auth/me/device, 17.2 BE-36, v1.46). 코드는 가운데를 가려서만 준다."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.dates import today_local
from app.models import DeviceCode
from app.schemas.common import to_utc_z
from app.services.device_codes import format_code, mask_code
from tests.conftest import bearer

URL = "/api/v1/auth/me/device"
CODE = "ABCDEFGHJKMNPQRSTUVW"  # 20자, 모두 코드 글자
OTHER_CODE = "23456789ABCDEFGHJKMN"


def _code(db: Session, institution_id, code: str = CODE, **values) -> DeviceCode:
    row = DeviceCode(institution_id=institution_id, code=code, note="1호기", **values)
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


@pytest.mark.parametrize(
    ("code", "masked"),
    [
        (CODE, "ABCDE-*****-*****-STUVW"),
        ("ABCDEFGHJKMNPQRSTUVW2345", "ABCDE-*****-*****-*****-2345"),  # 길어도 첫 묶음과 끝 묶음만
        ("ABCDEFGHJKMNPQR", "*****-*****-*****"),  # 네 묶음보다 짧으면 전부 가린다
        ("ABCDE", "*****"),
        ("", ""),
    ],
)
def test_mask_code(code: str, masked: str) -> None:
    assert mask_code(code) == masked


def test_gives_the_masked_code_and_issue_time(client: TestClient, db: Session, staff, auth_headers: dict) -> None:
    row = _code(db, staff.institution_id)
    response = client.get(URL, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {
        "device": {"code_masked": "ABCDE-*****-*****-STUVW", "issued_at": to_utc_z(row.created_at)}
    }
    # 전체 코드도, 가린 묶음도, 운영 메모도 응답에 없다
    for secret in (CODE, format_code(CODE), "FGHJK", "MNPQR", "1호기"):
        assert secret not in response.text


def test_null_without_a_usable_code(client: TestClient, db: Session, staff, auth_headers: dict) -> None:
    assert client.get(URL, headers=auth_headers).json() == {"device": None}

    row = _code(db, staff.institution_id)
    row.revoked_at = datetime.now(UTC)
    db.flush()
    assert client.get(URL, headers=auth_headers).json() == {"device": None}  # 회수한 코드는 주지 않는다

    _code(db, staff.institution_id, code=OTHER_CODE)  # 새로 발급하면 그 코드가 나온다
    assert client.get(URL, headers=auth_headers).json()["device"]["code_masked"] == "23456-*****-*****-HJKMN"


def test_another_institutions_code_is_not_shown(
    client: TestClient, db: Session, staff, auth_headers: dict, other_staff
) -> None:
    _code(db, other_staff.institution_id, code=OTHER_CODE)
    assert client.get(URL, headers=auth_headers).json() == {"device": None}
    theirs = client.get(URL, headers=bearer(other_staff)).json()
    assert theirs["device"]["code_masked"] == "23456-*****-*****-HJKMN"

    _code(db, staff.institution_id)
    assert client.get(URL, headers=auth_headers).json()["device"]["code_masked"] == "ABCDE-*****-*****-STUVW"


def test_guest_can_read_and_a_token_is_needed(client: TestClient, db: Session, staff, auth_headers: dict) -> None:
    _code(db, staff.institution_id)
    assert client.get(URL).status_code == 401

    staff.institution.contract_ends_at = today_local() - timedelta(days=1)
    db.flush()
    guest = client.get(URL, headers=auth_headers)  # GET /auth/me처럼 계약이 끝나도 된다
    assert guest.status_code == 200 and guest.json()["device"]["code_masked"] == "ABCDE-*****-*****-STUVW"
