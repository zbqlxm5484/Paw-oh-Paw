"""문구 파일(14.5): 14절의 모든 코드가 messages/ko.yaml에 있다(17.1)."""

from app.core.errors import HTTP_STATUS, ErrorCode, all_code_values, message_for, messages, reason_payload


def test_every_code_in_section_14_has_a_message() -> None:
    assert all_code_values() - set(messages()) == set()


def test_message_file_has_no_unknown_codes() -> None:
    """오타로 생긴 키를 잡는다. 코드를 더하면 errors.py의 StrEnum에도 더한다."""
    assert set(messages()) - all_code_values() == set()


def test_every_response_error_code_has_http_status() -> None:
    assert set(HTTP_STATUS) == set(ErrorCode)


def test_placeholder_is_filled_from_detail() -> None:
    text = message_for("VIDEO_TOO_LARGE", {"max_mb": 100})
    assert "100 MB" in text
    assert "{" not in text


def test_placeholder_without_value_is_left_visible() -> None:
    assert "{max_mb}" in message_for("VIDEO_TOO_LARGE")


def test_reason_payload_shape() -> None:
    assert reason_payload("STOPPED") == {"code": "STOPPED", "message": messages()["STOPPED"]}
