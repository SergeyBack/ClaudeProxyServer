"""
Integration tests for auth endpoints.

These tests work WITHOUT a real database — they fail at the
validation/auth layer before any DB lookup is attempted.

Run with:
    pytest tests/integration/test_auth_endpoints.py -v
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import create_app


@pytest.fixture
async def client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_login_wrong_password(client):
    """POST /auth/login with wrong password → 401."""
    resp = await client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


async def test_login_missing_fields(client):
    """POST /auth/login with empty body → 422 validation error."""
    resp = await client.post("/auth/login", json={})
    assert resp.status_code == 422


async def test_protected_no_token(client):
    """GET /user/me without Authorization header → 401."""
    resp = await client.get("/user/me")
    assert resp.status_code == 401


async def test_protected_bad_token(client):
    """GET /user/me with an invalid Bearer token → 401."""
    resp = await client.get("/user/me", headers={"Authorization": "Bearer invalid_token"})
    assert resp.status_code == 401
