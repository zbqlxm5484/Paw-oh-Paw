"""15.1 인증 약속을 등록된 모든 경로에서 본다(17.1, S15P31A404-277 기능 동결 점검).

엔드포인트마다 따로 있는 시험은 그 엔드포인트를 만든 사람이 넣어야 생긴다. 여기서는 앱에 등록된 경로를 OpenAPI에서
읽어 하나도 빼지 않고 돈다. 새 엔드포인트에 인증 의존성을 빼먹으면 여기서 걸린다. Spring에 빗대면
RequestMappingHandlerMapping의 모든 핸들러에 대해 SecurityFilterChain 규칙을 한 번에 확인하는 시험이다.

본문 없이 부른다. 토큰·계약 검사(get_current_staff)는 의존성이라 본문·쿼리 검증(422)보다 먼저 답한다.
"""

from __future__ import annotations

import re
from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.dates import today_local
from app.main import API_PREFIX
from tests.conftest import bearer

UNKNOWN_ID = "00000000-0000-4000-8000-000000000000"
# 토큰 없이 여는 것(15.1): 로그인, 상태 확인, 디바이스 코드 확인·가입, 비밀번호 재설정 둘, 서명 주소로 여는 파일 셋
PUBLIC: set[tuple[str, str]] = {
    ("POST", "/auth/login"),
    ("GET", "/health"),
    ("POST", "/auth/device-codes/verify"),
    ("POST", "/auth/signup"),
    ("POST", "/auth/password-reset/request"),
    ("POST", "/auth/password-reset/confirm"),
    ("GET", "/shots/{shot_id}/video"),
    ("GET", "/reports/{report_id}/file"),
    ("GET", "/images/{image_id}/file"),
}
# 계약이 끝난 기관의 CLIENT(GUEST)도 부를 수 있는 것(15.1): 내 정보, 탈퇴, 측정 기기 정보
GUEST_ALLOWED: set[tuple[str, str]] = {
    ("GET", "/auth/me"),
    ("DELETE", "/auth/me"),
    ("GET", "/auth/me/device"),
}


def _routes(app: FastAPI) -> list[tuple[str, str]]:
    """앱에 등록된 (메서드, 경로). 시험 전용 라우트(/_test)는 뺀다."""
    return sorted(
        (method.upper(), path.removeprefix(API_PREFIX))
        for path, operations in app.openapi()["paths"].items()
        if path.startswith(API_PREFIX) and not path.startswith(f"{API_PREFIX}/_test")
        for method in operations
    )


def _url(path: str) -> str:
    """주소의 ID 자리에 없는 UUID를, 날짜 자리에 날짜를 넣는다."""
    filled = path.replace("{measured_on}", "2026-01-05")
    return API_PREFIX + re.sub(r"\{[^}]+\}", UNKNOWN_ID, filled)


def _code(response) -> tuple[int, str | None]:
    try:
        return response.status_code, response.json()["error"]["code"]
    except (ValueError, KeyError, TypeError):
        return response.status_code, None


def test_sets_name_only_registered_routes(api_app: FastAPI) -> None:
    """위 두 묶음에 지워진 경로가 남아 있으면 예외가 조용히 넓어진다."""
    registered = set(_routes(api_app))
    assert PUBLIC - registered == set()
    assert GUEST_ALLOWED - registered == set()
    assert len(registered) == 65  # 15.2의 66개 중 26(/metrics, 선택)은 루트이고 기본은 꺼짐이다


def test_every_route_but_the_public_ones_needs_a_token(client: TestClient, api_app: FastAPI) -> None:
    """17.1: 토큰 없이 부르면 401 AUTH_REQUIRED. 토큰 없이 여는 아홉은 401이 아니다."""
    wrong = {}
    for method, path in _routes(api_app):
        got = _code(client.request(method, _url(path)))
        if (method, path) in PUBLIC:
            if got[0] == 401:
                wrong[(method, path)] = got
        elif got != (401, "AUTH_REQUIRED"):
            wrong[(method, path)] = got
    assert wrong == {}


def test_a_guest_is_stopped_on_every_route_but_three(client: TestClient, db: Session, api_app: FastAPI, staff) -> None:
    """17.1: 계약이 끝난 기관의 CLIENT는 내 정보·탈퇴·측정 기기 정보 말고 어디서나 403 CONTRACT_EXPIRED다.

    /admin/* 도 역할 검사(403 FORBIDDEN)보다 계약 검사가 먼저다.
    """
    staff.institution.contract_ends_at = today_local() - timedelta(days=1)
    db.flush()
    headers = bearer(staff)

    wrong = {}
    for method, path in _routes(api_app):
        if (method, path) in PUBLIC:
            continue
        got = _code(client.request(method, _url(path), headers=headers))
        if (method, path) in GUEST_ALLOWED:
            if got[0] in (401, 403):
                wrong[(method, path)] = got
        elif got != (403, "CONTRACT_EXPIRED"):
            wrong[(method, path)] = got
    assert wrong == {}


def test_a_client_of_a_live_contract_gets_past_the_gate(client: TestClient, api_app: FastAPI, staff) -> None:
    """같은 요청이 계약이 살아 있으면 401·CONTRACT_EXPIRED가 아니다(위 시험이 헛도는지 본다)."""
    headers = bearer(staff)
    stopped = {}
    for method, path in _routes(api_app):
        if (method, path) in PUBLIC:
            continue
        got = _code(client.request(method, _url(path), headers=headers))
        if got[0] == 401 or got[1] == "CONTRACT_EXPIRED":
            stopped[(method, path)] = got
    assert stopped == {}
