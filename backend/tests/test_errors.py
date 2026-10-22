"""오류 응답 형식(11.5, 14.1, 15.1, 17.1 공통 줄). conftest의 테스트 전용 라우트로 확인한다."""

from fastapi.testclient import TestClient
from httpx import Response

from app.core.errors import messages


def _error(response: Response) -> dict:
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "detail"}
    return body["error"]


def test_app_error_uses_spec_shape_and_message_file(client: TestClient) -> None:
    response = client.get("/api/v1/_test/conflict")
    assert response.status_code == 409
    error = _error(response)
    assert error["code"] == "SESSION_ALREADY_OPEN"
    assert error["message"] == messages()["SESSION_ALREADY_OPEN"]
    assert error["detail"] == {"session_id": "3f2a9c1e-5b7d-4e8a-9c21-7d4e5f6a8b90"}


def test_detail_is_null_when_absent(client: TestClient) -> None:
    response = client.get("/api/v1/_test/forbidden")
    assert response.status_code == 403
    assert _error(response)["detail"] is None


def test_placeholder_in_message_is_filled_from_detail(client: TestClient) -> None:
    response = client.get("/api/v1/_test/too-large")
    assert response.status_code == 413
    error = _error(response)
    assert "100 MB" in error["message"]
    assert "{max_mb}" not in error["message"]
    assert error["detail"] == {"max_mb": 100}


def test_validation_error_lists_fields(client: TestClient) -> None:
    response = client.post("/api/v1/_test/dogs", json={"weight_kg": 500, "name": 7})
    assert response.status_code == 422
    error = _error(response)
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == messages()["VALIDATION_ERROR"]
    assert error["detail"] == {
        "fields": [{"field": "weight_kg", "type": "less_than_equal"}, {"field": "name", "type": "string_type"}]
    }


def test_missing_fields_are_reported(client: TestClient) -> None:
    response = client.post("/api/v1/_test/dogs", json={})
    assert response.status_code == 422
    fields = _error(response)["detail"]["fields"]
    assert {field["field"] for field in fields} == {"weight_kg", "name"}
    assert all(field["type"] == "missing" for field in fields)


def test_query_validation_error_names_the_parameter(client: TestClient) -> None:
    response = client.get("/api/v1/_test/search", params={"page": "abc"})
    assert response.status_code == 422
    assert _error(response)["detail"]["fields"] == [{"field": "page", "type": "int_parsing"}]


def test_non_uuid_path_id_is_404_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/_test/items/not-a-uuid")
    assert response.status_code == 404
    error = _error(response)
    assert error["code"] == "NOT_FOUND"
    assert error["message"] == messages()["NOT_FOUND"]
    assert error["detail"] is None


def test_unknown_path_is_404_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/nothing-here")
    assert response.status_code == 404
    assert _error(response)["code"] == "NOT_FOUND"


def test_method_not_allowed_is_405_with_not_found_code(client: TestClient) -> None:
    response = client.post("/api/v1/health")
    assert response.status_code == 405
    assert _error(response)["code"] == "NOT_FOUND"


def test_unexpected_error_is_500_internal_error_without_details(client: TestClient) -> None:
    response = client.get("/api/v1/_test/boom")
    assert response.status_code == 500
    error = _error(response)
    assert error["code"] == "INTERNAL_ERROR"
    assert error["message"] == messages()["INTERNAL_ERROR"]
    assert error["detail"] is None
    assert "RuntimeError" not in response.text and "테스트" not in response.text
    assert "x-request-id" in response.headers
