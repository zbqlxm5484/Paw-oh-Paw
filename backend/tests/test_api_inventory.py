"""명세 15.2 엔드포인트 표와 앱에 등록된 경로 대조(S15P31A404-198 API 테스트 보강).

`/api/v1` 아래의 65개가 빠짐없이 등록돼 있는지 본다. 나머지 하나(26 metrics)는 루트 `/metrics`이고
METRICS_ENABLED를 켰을 때만 있어 여기서 세지 않는다(tests/test_metrics.py가 본다). NOT_YET은 그 표시다.
라우터를 main.py에 등록하지 않아 API가 통째로 빠지는 실수를 잡는다.
거꾸로 15.2에 없는 경로가 앱에 등록돼 있어도 걸린다(S15P31A404-277 기능 동결 점검에서 62~66번을 더함).
"""

from __future__ import annotations

from fastapi import FastAPI

from app.main import API_PREFIX

IMPLEMENTED: set[tuple[str, str]] = {
    ("POST", "/auth/login"),
    ("GET", "/auth/me"),
    ("GET", "/dogs"),
    ("POST", "/dogs"),
    ("GET", "/dogs/{dog_id}"),
    ("PATCH", "/dogs/{dog_id}"),
    ("POST", "/dogs/{dog_id}/sessions"),
    ("GET", "/dogs/{dog_id}/sessions"),
    ("GET", "/sessions/{session_id}"),
    ("DELETE", "/sessions/{session_id}"),
    ("POST", "/sessions/{session_id}/shots"),
    ("POST", "/sessions/{session_id}/complete"),
    ("GET", "/shots/{shot_id}"),
    ("POST", "/shots/{shot_id}/retry"),
    ("DELETE", "/shots/{shot_id}"),
    ("GET", "/shots/{shot_id}/video"),
    ("GET", "/sessions/{session_id}/result"),
    ("GET", "/sessions/{session_id}/reports"),
    ("POST", "/reports/{report_id}/regenerate"),
    ("GET", "/reports/{report_id}/file"),
    ("GET", "/dogs/{dog_id}/compare"),
    ("GET", "/dogs/{dog_id}/trends"),
    ("GET", "/health"),
    ("POST", "/auth/device-codes/verify"),
    ("POST", "/auth/signup"),
    ("GET", "/admin/institutions"),
    ("POST", "/admin/institutions"),
    ("PATCH", "/admin/institutions/{institution_id}"),
    ("GET", "/admin/institutions/{institution_id}/device-codes"),
    ("POST", "/admin/institutions/{institution_id}/device-codes"),
    ("PATCH", "/admin/device-codes/{device_code_id}"),
    ("POST", "/admin/device-codes/{device_code_id}/revoke"),
    ("GET", "/admin/institutions/{institution_id}/staff"),
    ("PATCH", "/admin/staff/{staff_id}"),
    ("PATCH", "/auth/password"),
    ("PATCH", "/auth/me"),
    ("DELETE", "/auth/me"),
    ("POST", "/auth/password-reset/request"),
    ("POST", "/auth/password-reset/confirm"),
    ("POST", "/admin/purge"),
    ("DELETE", "/dogs/{dog_id}"),
    ("POST", "/dogs/{dog_id}/restore"),
    ("DELETE", "/dogs/{dog_id}/permanent"),
    ("GET", "/dogs/{dog_id}/vitals"),
    ("PUT", "/dogs/{dog_id}/vitals/{measured_on}"),
    ("GET", "/dogs/{dog_id}/history"),
    ("POST", "/dogs/{dog_id}/history"),
    ("PATCH", "/dogs/{dog_id}/history/{history_id}"),
    ("DELETE", "/dogs/{dog_id}/history/{history_id}"),
    ("GET", "/dogs/{dog_id}/notes"),
    ("POST", "/dogs/{dog_id}/notes"),
    ("POST", "/dogs/{dog_id}/notes/batch"),
    ("PATCH", "/notes/{note_id}"),
    ("GET", "/notes/{note_id}/revisions"),
    ("GET", "/shots/{shot_id}/angles"),  # 17
    ("GET", "/sessions"),  # 55
    ("GET", "/dogs/{dog_id}/images"),
    ("POST", "/dogs/{dog_id}/images"),
    ("GET", "/images/{image_id}/file"),
    ("DELETE", "/images/{image_id}"),
    ("GET", "/sessions/{session_id}/report-content"),  # 62
    ("DELETE", "/dogs/{dog_id}/vitals/{measured_on}"),  # 63
    ("DELETE", "/notes/{note_id}"),  # 64
    ("GET", "/daily-records"),  # 65
    ("GET", "/auth/me/device"),  # 66
}
NOT_YET: set[tuple[str, str]] = {
    ("GET", "/metrics"),  # 26, 선택. /api/v1 아래가 아니라 루트이고 기본은 꺼짐이다
}


def _registered(app: FastAPI) -> set[tuple[str, str]]:
    """앱이 만든 OpenAPI 문서의 경로. app.routes는 include_router 묶음이라 경로가 바로 보이지 않는다."""
    return {
        (method.upper(), path.removeprefix(API_PREFIX))
        for path, operations in app.openapi()["paths"].items()
        if path.startswith(API_PREFIX) and not path.startswith(f"{API_PREFIX}/_test")
        for method in operations
    }


def test_every_implemented_endpoint_of_15_2_is_registered(api_app: FastAPI) -> None:
    registered = _registered(api_app)
    assert IMPLEMENTED - registered == set()
    assert len(IMPLEMENTED) == 65  # 66개 중 26(/metrics)은 /api/v1 밖이다


def test_the_missing_endpoint_is_still_missing(api_app: FastAPI) -> None:
    assert NOT_YET & _registered(api_app) == set()
    assert len(IMPLEMENTED | NOT_YET) == 66


def test_nothing_outside_15_2_is_registered(api_app: FastAPI) -> None:
    """명세 표에 없는 경로가 앱에 있으면 안 된다(명세를 먼저 쓴다). 시험 전용 라우트(/_test)는 뺀다."""
    assert _registered(api_app) - IMPLEMENTED == set()
