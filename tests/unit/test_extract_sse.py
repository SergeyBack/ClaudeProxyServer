"""Unit tests for _extract_usage_from_sse and _build_upstream_headers."""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.application.services.proxy_service import (
    _build_upstream_headers,
    _extract_usage_from_sse,
)
from src.domain.models.request_log import RequestLog


def make_log() -> RequestLog:
    return RequestLog(
        user_id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        request_id="test-req-001",
        model="claude-haiku",
        status_code=200,
        duration_ms=0,
        is_streaming=True,
    )


def make_sse(events: list[dict]) -> bytes:
    """Encode a list of event dicts as SSE data lines."""
    lines = []
    for event in events:
        lines.append(f"data: {json.dumps(event)}")
    return "\n".join(lines).encode()


def make_mock_request(headers: dict) -> MagicMock:
    req = MagicMock()
    req.headers = MagicMock()
    req.headers.items.return_value = list(headers.items())
    return req


def test_extract_message_delta_usage():
    """message_delta events carry output_tokens in a top-level 'usage' key."""
    log = make_log()
    data = make_sse(
        [
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"output_tokens": 42},
            }
        ]
    )
    _extract_usage_from_sse(data, log)
    assert log.output_tokens == 42


def test_extract_message_start_usage():
    """message_start events carry input_tokens inside 'message.usage'."""
    log = make_log()
    data = make_sse(
        [
            {
                "type": "message_start",
                "message": {
                    "id": "msg_abc",
                    "usage": {"input_tokens": 15},
                },
            }
        ]
    )
    _extract_usage_from_sse(data, log)
    assert log.input_tokens == 15


def test_extract_both_input_and_output_tokens():
    """Combining message_start and message_delta populates both fields."""
    log = make_log()
    data = make_sse(
        [
            {
                "type": "message_start",
                "message": {"usage": {"input_tokens": 10}},
            },
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"output_tokens": 5},
            },
        ]
    )
    _extract_usage_from_sse(data, log)
    assert log.input_tokens == 10
    assert log.output_tokens == 5


def test_extract_done_sentinel_is_ignored():
    """[DONE] lines must not cause errors."""
    log = make_log()
    data = b"data: [DONE]\n"
    _extract_usage_from_sse(data, log)
    assert log.input_tokens is None
    assert log.output_tokens is None


def test_extract_malformed_json_is_ignored():
    """Lines with invalid JSON must not raise — just silently skip."""
    log = make_log()
    data = b"data: {this is not valid json\ndata: also bad]\n"
    _extract_usage_from_sse(data, log)  # should not raise
    assert log.input_tokens is None
    assert log.output_tokens is None


def test_extract_empty_bytes():
    """Empty SSE buffer should leave log untouched."""
    log = make_log()
    _extract_usage_from_sse(b"", log)
    assert log.input_tokens is None
    assert log.output_tokens is None


def test_extract_no_usage_in_event():
    """Events without a 'usage' key don't update log."""
    log = make_log()
    data = make_sse(
        [{"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "hi"}}]
    )
    _extract_usage_from_sse(data, log)
    assert log.input_tokens is None
    assert log.output_tokens is None


def test_extract_cache_read_tokens():
    log = make_log()
    data = make_sse(
        [
            {
                "type": "message_delta",
                "usage": {
                    "output_tokens": 10,
                    "cache_read_input_tokens": 500,
                },
            }
        ]
    )
    _extract_usage_from_sse(data, log)
    assert log.cache_read_tokens == 500
    assert log.output_tokens == 10


def test_extract_cache_creation_tokens():
    log = make_log()
    data = make_sse(
        [
            {
                "type": "message_delta",
                "usage": {
                    "output_tokens": 8,
                    "cache_creation_input_tokens": 1000,
                },
            }
        ]
    )
    _extract_usage_from_sse(data, log)
    assert log.cache_write_tokens == 1000
    assert log.output_tokens == 8


def test_extract_all_token_types():
    log = make_log()
    data = make_sse(
        [
            {
                "type": "message_start",
                "message": {"usage": {"input_tokens": 20}},
            },
            {
                "type": "message_delta",
                "usage": {
                    "output_tokens": 15,
                    "cache_read_input_tokens": 300,
                    "cache_creation_input_tokens": 50,
                },
            },
        ]
    )
    _extract_usage_from_sse(data, log)
    assert log.input_tokens == 20
    assert log.output_tokens == 15
    assert log.cache_read_tokens == 300
    assert log.cache_write_tokens == 50


def test_extract_later_event_overwrites_earlier():
    """Later usage values overwrite earlier ones (last-write wins)."""
    log = make_log()
    data = make_sse(
        [
            {"type": "message_start", "message": {"usage": {"input_tokens": 10}}},
            {"type": "message_delta", "usage": {"input_tokens": 20, "output_tokens": 5}},
        ]
    )
    _extract_usage_from_sse(data, log)
    # The second event has input_tokens=20, which should overwrite 10
    assert log.input_tokens == 20
    assert log.output_tokens == 5


def test_extract_non_data_lines_ignored():
    """Lines not starting with 'data: ' should be silently skipped."""
    log = make_log()
    raw = (
        b"event: message_start\nid: 1\n: comment\ndata: "
        + json.dumps({"type": "message_start", "message": {"usage": {"input_tokens": 7}}}).encode()
    )
    _extract_usage_from_sse(raw, log)
    assert log.input_tokens == 7


def test_extract_handles_non_utf8_gracefully():
    """Invalid UTF-8 bytes should not raise — errors='ignore' covers this."""
    log = make_log()
    # Mix valid SSE data with some non-UTF8 bytes
    valid_part = (
        b"data: " + json.dumps({"type": "message_delta", "usage": {"output_tokens": 3}}).encode()
    )
    garbage = b"\xff\xfe"
    _extract_usage_from_sse(garbage + valid_part, log)
    # log may or may not be updated depending on split, but must not raise
    # (the garbage bytes are before "data: " so the line starts correctly after split)


def test_extract_usage_from_real_sse_stream():
    """Replicate the actual SSE format from conftest.make_sse_stream."""
    log = make_log()
    events = [
        {
            "type": "message_start",
            "message": {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "usage": {"input_tokens": 10},
            },
        },
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "Hello!"},
        },
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 5},
        },
        {"type": "message_stop"},
    ]
    lines = []
    for event in events:
        lines.append(f"event: {event['type']}\ndata: {json.dumps(event)}\n")
    lines.append("data: [DONE]\n")
    sse_bytes = "\n".join(lines).encode()

    _extract_usage_from_sse(sse_bytes, log)
    assert log.input_tokens == 10
    assert log.output_tokens == 5


def test_build_headers_strips_host():
    req = make_mock_request({"host": "localhost:8000", "content-type": "application/json"})
    headers = _build_upstream_headers(req, "Bearer sometoken")
    assert "host" not in headers


def test_build_headers_strips_content_length():
    req = make_mock_request({"content-length": "123", "content-type": "application/json"})
    headers = _build_upstream_headers(req, "tok")
    assert "content-length" not in headers


def test_build_headers_strips_transfer_encoding():
    req = make_mock_request({"transfer-encoding": "chunked"})
    headers = _build_upstream_headers(req, "tok")
    assert "transfer-encoding" not in headers


def test_build_headers_strips_connection():
    req = make_mock_request({"connection": "keep-alive"})
    headers = _build_upstream_headers(req, "tok")
    assert "connection" not in headers


def test_build_headers_strips_x_forwarded_for():
    req = make_mock_request({"x-forwarded-for": "192.168.1.1"})
    headers = _build_upstream_headers(req, "tok")
    assert "x-forwarded-for" not in headers


def test_build_headers_strips_x_real_ip():
    req = make_mock_request({"x-real-ip": "10.0.0.1"})
    headers = _build_upstream_headers(req, "tok")
    assert "x-real-ip" not in headers


def test_build_headers_strips_x_request_id():
    req = make_mock_request({"x-request-id": "req-abc-123"})
    headers = _build_upstream_headers(req, "tok")
    assert "x-request-id" not in headers


def test_build_headers_strips_incoming_authorization():
    req = make_mock_request({"authorization": "Bearer user-ccp-key"})
    headers = _build_upstream_headers(req, "account-token")
    # The incoming authorization must not appear verbatim — only the injected one
    assert headers.get("authorization") == "Bearer account-token"


def test_build_headers_strips_incoming_x_api_key():
    req = make_mock_request({"x-api-key": "user-api-key"})
    headers = _build_upstream_headers(req, "account-token")
    # The incoming x-api-key is stripped; injected value depends on token prefix
    assert headers.get("x-api-key") != "user-api-key"


def test_build_headers_injects_x_api_key_for_sk_ant_token():
    """If auth_token starts with 'sk-ant-', inject as x-api-key."""
    req = make_mock_request({})
    headers = _build_upstream_headers(req, "sk-ant-api03-secret-key")
    assert headers.get("x-api-key") == "sk-ant-api03-secret-key"
    assert "authorization" not in headers


def test_build_headers_injects_bearer_for_non_sk_ant_token():
    """If auth_token does NOT start with 'sk-ant-', inject as Authorization Bearer."""
    req = make_mock_request({})
    headers = _build_upstream_headers(req, "session-token-value")
    assert headers.get("authorization") == "Bearer session-token-value"
    assert "x-api-key" not in headers


def test_build_headers_passes_through_anthropic_version():
    req = make_mock_request({"anthropic-version": "2023-06-01"})
    headers = _build_upstream_headers(req, "sk-ant-secret")
    assert headers.get("anthropic-version") == "2023-06-01"


def test_build_headers_passes_through_content_type():
    req = make_mock_request({"content-type": "application/json"})
    headers = _build_upstream_headers(req, "sk-ant-secret")
    assert headers.get("content-type") == "application/json"


def test_build_headers_passes_through_custom_headers():
    req = make_mock_request({"x-custom-header": "custom-value", "accept": "application/json"})
    headers = _build_upstream_headers(req, "tok")
    assert headers.get("x-custom-header") == "custom-value"
    assert headers.get("accept") == "application/json"


def test_build_headers_empty_incoming_headers():
    req = make_mock_request({})
    headers = _build_upstream_headers(req, "sk-ant-key")
    assert headers.get("x-api-key") == "sk-ant-key"


def test_build_headers_all_stripped_headers_together():
    req = make_mock_request(
        {
            "host": "localhost",
            "content-length": "100",
            "transfer-encoding": "chunked",
            "connection": "keep-alive",
            "x-forwarded-for": "1.2.3.4",
            "x-real-ip": "5.6.7.8",
            "x-request-id": "req-id",
            "authorization": "Bearer user-key",
            "x-api-key": "user-key",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
    )
    headers = _build_upstream_headers(req, "sk-ant-real-token")

    # All stripped headers gone
    for stripped in (
        "host",
        "content-length",
        "transfer-encoding",
        "connection",
        "x-forwarded-for",
        "x-real-ip",
        "x-request-id",
    ):
        assert stripped not in headers

    # Incoming auth replaced by injected account token
    assert headers.get("x-api-key") == "sk-ant-real-token"
    assert headers.get("authorization") is None

    # Non-stripped headers preserved
    assert headers.get("anthropic-version") == "2023-06-01"
    assert headers.get("content-type") == "application/json"


def test_build_headers_sk_ant_prefix_check_is_exact():
    """Token starting with 'sk-ant-' should use x-api-key; anything else uses Bearer."""
    # Starts with 'sk-ant-'
    req = make_mock_request({})
    h1 = _build_upstream_headers(req, "sk-ant-abc")
    assert "x-api-key" in h1
    assert "authorization" not in h1

    # Does NOT start with 'sk-ant-'
    req2 = make_mock_request({})
    h2 = _build_upstream_headers(req2, "sk-ant")  # too short — doesn't match 'sk-ant-'
    assert "authorization" in h2
    assert "x-api-key" not in h2

    req3 = make_mock_request({})
    h3 = _build_upstream_headers(req3, "xsk-ant-abc")  # different prefix
    assert "authorization" in h3
    assert "x-api-key" not in h3
