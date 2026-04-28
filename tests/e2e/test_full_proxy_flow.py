"""
E2E tests — requires full stack running.

Usage:
    # Start stack first:
    docker compose up -d

    # Then run:
    PROXY_URL=http://localhost:8000 pytest tests/e2e/ -v
"""

import os

import pytest
import pytest_asyncio
from httpx import AsyncClient

PROXY_URL = os.getenv("PROXY_URL", "http://localhost:8000")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "changeme123!")

pytestmark = pytest.mark.skipif(
    not os.getenv("PROXY_URL"),
    reason="PROXY_URL not set — skipping e2e tests",
)


@pytest_asyncio.fixture(scope="module")
async def http():
    async with AsyncClient(base_url=PROXY_URL, timeout=30) as c:
        yield c


@pytest_asyncio.fixture(scope="module")
async def admin_token(http):
    resp = await http.post("/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_health(http):
    resp = await http.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ready(http):
    resp = await http.get("/ready")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_login(admin_token):
    assert admin_token is not None


@pytest.mark.asyncio
async def test_list_accounts(http, admin_token):
    resp = await http.get("/admin/accounts", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_users(http, admin_token):
    resp = await http.get("/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_overview_stats(http, admin_token):
    resp = await http.get(
        "/admin/stats/overview", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_requests" in data
    assert "active_users" in data


@pytest.mark.asyncio
async def test_banned_stats(http, admin_token):
    resp = await http.get("/admin/stats/banned", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_user_get_api_key(http, admin_token):
    import uuid

    username = f"e2e_user_{uuid.uuid4().hex[:6]}"
    resp = await http.post(
        "/admin/users",
        json={"username": username, "email": f"{username}@test.com", "password": "pass123!"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["api_key"].startswith("ccp_")
    assert data["prefix"] == data["api_key"][:12]

    # New user can hit /v1/models
    models_resp = await http.get(
        "/v1/models",
        headers={"Authorization": f"Bearer {data['api_key']}"},
    )
    assert models_resp.status_code == 200


@pytest.mark.asyncio
async def test_user_can_see_own_profile(http, admin_token):
    resp = await http.get("/user/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"
