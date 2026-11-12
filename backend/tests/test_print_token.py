"""인쇄 토큰(명세 11.6, 15.2의 2·3·8·9·13·17·18·22·23·55·62번, S15P31A404-276. 13·23번은 278에서 열었다).

웹의 보고서 인쇄 화면이 로그인 없이 그 기관의 자료를 읽을 때 쓰는 토큰이다(박규원 11-10 결정 (가): 인쇄 화면이
보고서 화면과 같은 자료로 그린다). 토큰 자체(만들기·풀기)와, 받는 조회가 로그인한 그 기관의 CLIENT와 같은 것을
읽는지, 그 밖의 API와 쓰기는 받지 않는지를 본다. 촬영 상세(13번)는 토큰을 만든 회차의 촬영만 여는지도 본다.
보고서 내용(62번)은 test_report_content_api.py가 본다.
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
from tests.history_fixtures import add_metric, add_report, add_shot, make_session

ME = "/api/v1/auth/me"
SESSIONS = "/api/v1/sessions"
HISTORY = "/api/v1/dogs/{}/sessions"
COMPARE = "/api/v1/dogs/{}/compare"
TRENDS = "/api/v1/dogs/{}/trends"
TREND_QUERY = {"metric_code": "rom_stifle", "gait_type": "TROT"}
RESULT = "/api/v1/sessions/{}/result"
SESSION = "/api/v1/sessions/{}"
ANGLES = "/api/v1/shots/{}/angles"
SHOT = "/api/v1/shots/{}"
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


# ---- 그 기관의 읽기 전용: 로그인한 CLIENT가 읽는 것과 같다 ----


def _readable(dog, first, second, shot) -> list[tuple[str, dict | None]]:
    """인쇄 토큰이 여는 조회(62번은 test_report_content_api.py). 2번(내 정보)과 13번(촬영 상세)은 따로 본다."""
    return [
        (DOGS, None),
        (HISTORY.format(dog.id), None),
        (SESSIONS, None),
        (SESSION.format(first.id), None),  # 토큰을 만든 회차가 아니어도 그 기관의 회차면 열린다
        (SESSION.format(second.id), None),
        (RESULT.format(first.id), None),
        (RESULT.format(second.id), None),
        (COMPARE.format(dog.id), {"target": str(second.id), "base": "PREVIOUS"}),
        (TRENDS.format(dog.id), TREND_QUERY),
        (ANGLES.format(shot.id), None),
    ]


def test_reads_what_a_logged_in_client_reads(client: TestClient, db: Session, staff, dog, two_sessions) -> None:
    first, second = two_sessions
    shot = add_shot(db, first, 1, passes={"LEFT": (1, 0)})
    headers = _print_headers(second, staff)

    for url, params in _readable(dog, first, second, shot):
        by_print = client.get(url, params=params, headers=headers)
        by_login = client.get(url, params=params, headers=bearer(staff))
        assert by_print.status_code == by_login.status_code == 200, url
        assert by_print.json() == by_login.json(), url


def test_no_file_address_comes_with_a_print_token(client: TestClient, db: Session, staff, dog, two_sessions) -> None:
    """결과 영상이 READY이고 보고서가 DONE이어도, 아래 조회의 응답에는 파일을 여는 서명 주소가 없다(11.6).

    결과 영상 주소는 촬영 상세(13번)에만 있고, 보고서 파일 주소는 인쇄 토큰으로 받는 어느 응답에도 없다.
    """
    first, second = two_sessions
    shot = add_shot(db, second, 1, passes={"LEFT": (2, 0)})
    shot.video_status, shot.result_key = "READY", "some/result.mp4"
    add_report(db, second, "OWNER", "DONE")
    db.flush()
    headers = _print_headers(second, staff)

    for url, params in [*_readable(dog, first, second, shot), (ME, None)]:
        response = client.get(url, params=params, headers=headers)
        assert response.status_code == 200, url
        for mark in ("/video?", "/file?", "sig=", "video_url", "file_url"):
            assert mark not in response.text, (url, mark)


def test_me_looks_like_a_client_of_that_institution(client: TestClient, db: Session, staff, two_sessions) -> None:
    """인쇄 토큰에는 사람이 없다. 인쇄 화면이 읽는 기관·역할만 채운 값을 준다(15.4)."""
    _, second = two_sessions
    login = client.get(ME, headers=bearer(staff)).json()
    body = client.get(ME, headers=_print_headers(second, staff)).json()

    assert set(body) == set(login)
    assert body["institution"] == login["institution"]
    assert (body["role"], body["effective_role"]) == ("CLIENT", "CLIENT")
    assert (body["id"], body["login_id"], body["name"]) == (str(uuid.UUID(int=0)), "print", "print")
    assert body["email"] is None and body["notif_on"] is False

    # 계약이 끝나도 인쇄 토큰은 CLIENT로 보인다(계약 상태를 보지 않는다). 기관의 계약 값은 실제 값이다
    db.get(Institution, staff.institution_id).contract_ends_at = today_local() - timedelta(days=1)
    db.flush()
    expired = client.get(ME, headers=_print_headers(second, staff)).json()
    assert expired["effective_role"] == "CLIENT" and expired["institution"]["contract_status"] == "EXPIRED"
    assert client.get(ME, headers=bearer(staff)).json()["effective_role"] == "GUEST"


def test_print_token_of_another_institution_opens_nothing(
    client: TestClient, db: Session, staff, other_staff, dog, two_sessions
) -> None:
    """기관이 다른 토큰은 ID가 맞아도 열리지 않고, 목록은 그 토큰의 기관 것만 준다(기관 필터는 그대로다)."""
    _, second = two_sessions
    shot = add_shot(db, second, 1, passes={"LEFT": (1, 0)})
    headers = _print_headers(second, other_staff)
    closed = (
        RESULT.format(second.id),
        SESSION.format(second.id),
        HISTORY.format(dog.id),
        COMPARE.format(dog.id),
        ANGLES.format(shot.id),
        SHOT.format(shot.id),  # 토큰의 회차는 맞지만 기관이 다르다
    )
    for url in closed:
        assert _code(client.get(url, headers=headers)) == (404, "NOT_FOUND"), url
    assert _code(client.get(TRENDS.format(dog.id), params=TREND_QUERY, headers=headers)) == (404, "NOT_FOUND")
    assert client.get(DOGS, headers=headers).json()["total"] == 0
    assert client.get(SESSIONS, headers=headers).json()["total"] == 0
    assert client.get(ME, headers=headers).json()["institution"]["id"] == str(other_staff.institution_id)


def test_trashed_dog_is_404_like_a_login(client: TestClient, db: Session, staff, dog, two_sessions) -> None:
    """휴지통에 든 반려견은 인쇄 토큰으로도 안 열린다. 워커는 그런 보고서를 기본 템플릿으로 만든다(8절 6번)."""
    _, second = two_sessions
    shot = add_shot(db, second, 1, passes={"LEFT": (1, 0)})
    dog.deleted_at = datetime.now(UTC)
    db.flush()
    headers = _print_headers(second, staff)

    urls = (
        SESSION.format(second.id),
        RESULT.format(second.id),
        ANGLES.format(shot.id),
        SHOT.format(shot.id),
        HISTORY.format(dog.id),
    )
    for url in urls:
        assert _code(client.get(url, headers=headers)) == (404, "NOT_FOUND"), url
        assert _code(client.get(url, headers=bearer(staff))) == (404, "NOT_FOUND"), url
    for who in (headers, bearer(staff)):
        assert _code(client.get(TRENDS.format(dog.id), params=TREND_QUERY, headers=who)) == (404, "NOT_FOUND")
    assert client.get(DOGS, headers=headers).json()["total"] == 0
    assert client.get(SESSIONS, headers=headers).json()["total"] == 0


def test_expired_print_token_is_401_auth_expired(client: TestClient, staff, dog, two_sessions) -> None:
    _, second = two_sessions
    past = datetime.now(UTC) - timedelta(seconds=get_settings().FILE_URL_TTL_SEC + 5)
    headers = _print_headers(second, staff, now=past)
    for url in (RESULT.format(second.id), DOGS, ME, HISTORY.format(dog.id)):
        assert _code(client.get(url, headers=headers)) == (401, "AUTH_EXPIRED"), url


def test_print_token_ignores_contract_state(client: TestClient, db: Session, staff, two_sessions) -> None:
    """계약이 끝난 기관: 로그인 토큰은 403 CONTRACT_EXPIRED지만 서버가 만든 인쇄 토큰은 연다(11.6)."""
    _, second = two_sessions
    db.get(Institution, staff.institution_id).contract_ends_at = today_local() - timedelta(days=1)
    db.flush()

    assert _code(client.get(RESULT.format(second.id), headers=bearer(staff))) == (403, "CONTRACT_EXPIRED")
    assert client.get(RESULT.format(second.id), headers=_print_headers(second, staff)).status_code == 200
    assert client.get(DOGS, headers=_print_headers(second, staff)).status_code == 200


# ---- 촬영 상세(13번): 토큰을 만든 회차의 촬영만 ----


def test_shot_detail_opens_only_for_the_session_of_the_token(
    client: TestClient, db: Session, staff, dog, two_sessions
) -> None:
    """촬영 상세에는 결과 영상 주소가 실린다. 그래서 인쇄 토큰은 그 토큰을 만든 회차의 촬영만 연다(11.6)."""
    first, second = two_sessions
    mine = add_shot(db, second, 1, passes={"LEFT": (2, 0)})
    other = add_shot(db, first, 1, passes={"LEFT": (1, 0)})
    headers = _print_headers(second, staff)

    by_print = client.get(SHOT.format(mine.id), headers=headers)
    by_login = client.get(SHOT.format(mine.id), headers=bearer(staff))
    assert by_print.status_code == by_login.status_code == 200
    assert by_print.json() == by_login.json()

    # 같은 기관이어도 다른 회차의 촬영은 없는 것과 같다. 로그인한 담당자에게는 열린다
    assert _code(client.get(SHOT.format(other.id), headers=headers)) == (404, "NOT_FOUND")
    assert client.get(SHOT.format(other.id), headers=bearer(staff)).status_code == 200
    # 각도(17번)는 주소가 실리지 않는 조회라 회차로 좁히지 않는다
    assert client.get(ANGLES.format(other.id), headers=headers).status_code == 200


def test_result_video_address_comes_only_with_that_shot_detail(
    client: TestClient, db: Session, staff, dog, two_sessions
) -> None:
    """결과 영상이 READY면 그 회차의 촬영 상세에 서명 주소가 실린다. 인쇄 화면이 그 영상에서 장면을 잘라 싣는다."""
    first, second = two_sessions
    shot = add_shot(db, second, 1, passes={"LEFT": (2, 0)})
    shot.video_status, shot.result_key = "READY", "some/result.mp4"
    db.flush()

    body = client.get(SHOT.format(shot.id), headers=_print_headers(second, staff)).json()
    assert body["video_status"] == "READY"
    assert f"/shots/{shot.id}/video?" in body["video_url"] and "sig=" in body["video_url"]

    # 다른 회차로 만든 토큰으로는 같은 촬영이 열리지 않는다
    assert _code(client.get(SHOT.format(shot.id), headers=_print_headers(first, staff))) == (404, "NOT_FOUND")


# ---- 그 밖의 조회와 쓰기는 받지 않는다 ----


def test_other_reads_and_every_write_are_closed(client: TestClient, db: Session, staff, dog, two_sessions) -> None:
    """인쇄 토큰은 로그인이 아니다. 받는 조회 열하나 말고는 401이고, 그 요청으로 바뀌는 것이 없다."""
    first, second = two_sessions
    shot = add_shot(db, second, 1, passes={"LEFT": (1, 0)})
    headers = _print_headers(second, staff)
    closed = [
        # 조회: 보고서 목록(파일 주소가 실린다), 차트 자료, 관리자
        ("GET", f"/api/v1/sessions/{second.id}/reports"),
        ("GET", f"{DOGS}/{dog.id}"),
        ("GET", f"{DOGS}/{dog.id}/vitals"),
        ("GET", f"{DOGS}/{dog.id}/notes"),
        ("GET", f"{DOGS}/{dog.id}/history"),
        ("GET", f"{DOGS}/{dog.id}/images"),
        ("GET", "/api/v1/admin/institutions"),
        ("GET", "/api/v1/daily-records"),  # 그날 기록(65번)
        ("GET", f"{ME}/device"),  # 기기 정보(66번). 내 정보(2번)는 열리지만 이것은 아니다
        # 쓰기
        ("POST", DOGS),
        ("PATCH", f"{DOGS}/{dog.id}"),
        ("DELETE", f"{DOGS}/{dog.id}"),
        ("POST", f"{DOGS}/{dog.id}/sessions"),
        ("POST", f"/api/v1/sessions/{second.id}/complete"),
        ("DELETE", f"/api/v1/sessions/{second.id}"),
        ("POST", f"/api/v1/shots/{shot.id}/retry"),
        ("DELETE", SHOT.format(shot.id)),
        ("PUT", f"{DOGS}/{dog.id}/vitals/2026-10-15"),
        ("DELETE", f"{DOGS}/{dog.id}/vitals/2026-10-15"),  # 63번
        ("POST", f"{DOGS}/{dog.id}/notes"),
        ("DELETE", f"/api/v1/notes/{uuid.uuid4()}"),  # 64번
        ("PATCH", ME),
        ("DELETE", ME),
        ("PATCH", "/api/v1/auth/password"),
        ("POST", "/api/v1/admin/purge"),
    ]
    for method, url in closed:
        assert _code(client.request(method, url, headers=headers, json={})) == (401, "AUTH_REQUIRED"), (method, url)

    db.expire_all()
    assert db.get(type(dog), dog.id).deleted_at is None
    assert {db.get(type(second), s.id).status for s in (first, second)} == {"DONE"}
