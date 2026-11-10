"""인쇄 토큰(명세 11.6, 15.2의 18·22번, S15P31A404-276).

웹의 보고서 인쇄 화면이 로그인 없이 회차 하나를 읽을 때 쓰는 토큰이다. 토큰 자체(만들기·풀기)와, 받는 API 둘이
그 회차만 여는지, 그 밖의 API는 받지 않는지를 본다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dates import today_local
from app.core.security import (
    TokenError,
    TokenExpiredError,
    create_access_token,
    create_print_token,
    decode_access_token,
    decode_print_token,
)
from app.models import Institution
from tests.conftest import bearer
from tests.history_fixtures import add_metric, another_dog, make_session

RESULT = "/api/v1/sessions/{}/result"
COMPARE = "/api/v1/dogs/{}/compare"
DOGS = "/api/v1/dogs"


def _print_headers(session, staff, **kwargs) -> dict[str, str]:
    token, _ = create_print_token(session_id=session.id, institution_id=staff.institution_id, **kwargs)
    return {"Authorization": f"Bearer {token}"}


def _code(response) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


@pytest.fixture
def two_sessions(db: Session, dog, staff):
    """같은 반려견의 DONE 회차 둘(앞, 뒤). 무릎 가동 범위 한 줄씩."""
    first = make_session(db, dog, staff, date(2026, 10, 1))
    second = make_session(db, dog, staff, date(2026, 10, 15))
    add_metric(db, first, "rom_stifle", "LH", 40.0)
    add_metric(db, second, "rom_stifle", "LH", 47.0)
    return first, second


# ---- 토큰 ----


def test_print_token_round_trip_and_ttl(staff) -> None:
    session_id = uuid.uuid4()
    now = datetime(2026, 11, 10, 9, 0, 0, 500000, tzinfo=UTC)
    token, expires_at = create_print_token(session_id=session_id, institution_id=staff.institution_id, now=now)

    assert expires_at == datetime(2026, 11, 10, 9, 0, tzinfo=UTC) + timedelta(seconds=get_settings().FILE_URL_TTL_SEC)
    payload = jwt.decode(token, options={"verify_signature": False})
    assert set(payload) == {"typ", "sid", "inst", "exp"}
    assert payload["typ"] == "print"

    fresh, _ = create_print_token(session_id=session_id, institution_id=staff.institution_id)
    claims = decode_print_token(fresh)
    assert (claims.session_id, claims.institution_id) == (session_id, staff.institution_id)


def test_expired_print_token_raises_expired(staff) -> None:
    past = datetime.now(UTC) - timedelta(seconds=get_settings().FILE_URL_TTL_SEC + 5)
    token, _ = create_print_token(session_id=uuid.uuid4(), institution_id=staff.institution_id, now=past)
    with pytest.raises(TokenExpiredError):
        decode_print_token(token)


def test_login_token_and_print_token_do_not_stand_in_for_each_other(staff) -> None:
    login, _ = create_access_token(staff_id=staff.id, institution_id=staff.institution_id, role=staff.role)
    printing, _ = create_print_token(session_id=uuid.uuid4(), institution_id=staff.institution_id)

    with pytest.raises(TokenError):
        decode_print_token(login)
    with pytest.raises(TokenError):
        decode_access_token(printing)


@pytest.mark.parametrize(
    "payload",
    [
        {"typ": "other", "sid": str(uuid.uuid4()), "inst": str(uuid.uuid4()), "exp": 4102444800},
        {"sid": str(uuid.uuid4()), "inst": str(uuid.uuid4()), "exp": 4102444800},
        {"typ": "print", "sid": "not-a-uuid", "inst": str(uuid.uuid4()), "exp": 4102444800},
    ],
)
def test_wrong_type_or_claims_is_rejected(payload: dict) -> None:
    token = jwt.encode(payload, get_settings().FILE_URL_SECRET.get_secret_value(), algorithm="HS256")
    with pytest.raises(TokenError):
        decode_print_token(token)


# ---- 회차 결과(18번) ----


def test_result_opens_with_print_token_like_login(client: TestClient, staff, two_sessions) -> None:
    _, second = two_sessions
    by_login = client.get(RESULT.format(second.id), headers=bearer(staff))
    by_print = client.get(RESULT.format(second.id), headers=_print_headers(second, staff))

    assert by_login.status_code == by_print.status_code == 200
    assert by_print.json() == by_login.json()


def test_result_of_another_session_is_404_with_print_token(client: TestClient, staff, two_sessions) -> None:
    first, second = two_sessions
    assert _code(client.get(RESULT.format(first.id), headers=_print_headers(second, staff))) == (404, "NOT_FOUND")


def test_print_token_of_another_institution_opens_nothing(client: TestClient, staff, other_staff, two_sessions) -> None:
    """기관이 다른 토큰은 회차 ID가 맞아도 열리지 않는다(기관 필터는 그대로다)."""
    _, second = two_sessions
    headers = _print_headers(second, other_staff)
    assert _code(client.get(RESULT.format(second.id), headers=headers)) == (404, "NOT_FOUND")


def test_expired_print_token_is_401_auth_expired(client: TestClient, staff, two_sessions) -> None:
    _, second = two_sessions
    past = datetime.now(UTC) - timedelta(seconds=get_settings().FILE_URL_TTL_SEC + 5)
    response = client.get(RESULT.format(second.id), headers=_print_headers(second, staff, now=past))
    assert _code(response) == (401, "AUTH_EXPIRED")


def test_print_token_ignores_contract_state(client: TestClient, db: Session, staff, two_sessions) -> None:
    """계약이 끝난 기관: 로그인 토큰은 403 CONTRACT_EXPIRED지만 서버가 만든 인쇄 토큰은 그 회차를 연다(11.6)."""
    _, second = two_sessions
    db.get(Institution, staff.institution_id).contract_ends_at = today_local() - timedelta(days=1)
    db.flush()

    assert _code(client.get(RESULT.format(second.id), headers=bearer(staff))) == (403, "CONTRACT_EXPIRED")
    assert client.get(RESULT.format(second.id), headers=_print_headers(second, staff)).status_code == 200


def test_print_token_is_not_a_login_for_other_apis(client: TestClient, staff, two_sessions) -> None:
    _, second = two_sessions
    assert _code(client.get(DOGS, headers=_print_headers(second, staff))) == (401, "AUTH_REQUIRED")


# ---- 회차 비교(22번) ----


def test_compare_opens_for_the_token_session_as_target(client: TestClient, staff, dog, two_sessions) -> None:
    first, second = two_sessions
    params = {"target": str(second.id), "base": "PREVIOUS"}
    by_login = client.get(COMPARE.format(dog.id), params=params, headers=bearer(staff))
    by_print = client.get(COMPARE.format(dog.id), params=params, headers=_print_headers(second, staff))

    assert by_login.status_code == by_print.status_code == 200
    assert by_print.json() == by_login.json()
    assert by_print.json()["base"]["session_id"] == str(first.id)


def test_compare_needs_the_token_session_as_target(client: TestClient, staff, dog, two_sessions) -> None:
    first, second = two_sessions
    headers = _print_headers(second, staff)

    # target을 안 주면 "가장 최근 회차"인데, 그것이 토큰의 회차라는 보장이 없어 막는다
    assert _code(client.get(COMPARE.format(dog.id), headers=headers)) == (404, "NOT_FOUND")
    other = client.get(COMPARE.format(dog.id), params={"target": str(first.id)}, headers=headers)
    assert _code(other) == (404, "NOT_FOUND")


def test_compare_of_another_dog_is_404_with_print_token(
    client: TestClient, db: Session, staff, dog, two_sessions
) -> None:
    _, second = two_sessions
    stranger = another_dog(db, staff.institution_id)
    response = client.get(
        COMPARE.format(stranger.id), params={"target": str(second.id)}, headers=_print_headers(second, staff)
    )
    assert _code(response) == (404, "NOT_FOUND")
