"""
Integration tests for proxy endpoints.

These tests work WITHOUT a real database — they all fail at the
auth layer before any DB or upstream Anthropic call is made.

Run with:
    pytest tests/integration/test_proxy_endpoint.py -v
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import create_app


@pytest.fixture
async def client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_messages_no_auth(client):
    """POST /v1/messages without auth → 401."""
    resp = await client.post(
        "/v1/messages",
        json={
            "model": "x",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert resp.status_code == 401


async def test_messages_bad_api_key(client):
    """POST /v1/messages with an invalid API key → 401."""
    resp = await client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer bad_key"},
        json={
            "model": "x",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert resp.status_code == 401


async def test_models_no_auth(client):
    """GET /v1/models without auth → 401."""
    resp = await client.get("/v1/models")
    assert resp.status_code == 401
