# Claude Proxy Server

A corporate proxy that multiplexes Claude Code traffic across multiple Anthropic accounts using least-connections routing.

> **For employees and end-users** — see [how_to_connect.md](how_to_connect.md) for setup instructions.

## Overview

Companies running Claude Code at scale often maintain several Anthropic accounts ($200/month each) to stay within per-account rate limits. This proxy sits between employees and Anthropic: each developer points `ANTHROPIC_BASE_URL` at the proxy and authenticates with a personal `ccp_` API key. The proxy selects the least-loaded account, substitutes its token, forwards the request, and logs token usage — all transparently to the Claude Code client.

Rate-limited (429) and banned (401/403) accounts are detected automatically and taken out of rotation until they recover.

## Architecture

```
Claude Code clients
        |
        v
    Nginx :80
        |
        v
  Proxy App :8000
  ┌─────────────────────────────────┐
  │  FastAPI (api layer)            │
  │    ↓                            │
  │  ProxyService (application)     │
  │    ↓                            │
  │  LeastConnectionsStrategy       │
  │    ↓                            │
  │  AccountStateManager            │
  │  (in-memory, asyncio.Lock)      │
  └──────────┬──────────────────────┘
             |
   ┌─────────┴──────────┐
   │                    │
   v                    v
Claude Account 1   Claude Account 2  ...
(api.anthropic.com)
```

**Clean Architecture layers:**

```
api → application → domain ← infrastructure
```

| Layer | Location | Responsibility |
|---|---|---|
| API | `src/api/` | FastAPI routers, JWT + API key auth, Jinja2 web panel |
| Application | `src/application/` | ProxyService, routing strategies, account/user/stats services |
| Domain | `src/domain/` | Pure Python dataclasses, Protocol interfaces (no framework imports) |
| Infrastructure | `src/infrastructure/` | SQLAlchemy ORM, async repos, httpx ClientPool, AccountStateManager |

## Quick Start

### Prerequisites

The following tools must be installed on your machine before you begin:

| Tool | Version | Install |
|---|---|---|
| **Docker Desktop** | ≥ 24 | [docs.docker.com/get-docker](https://docs.docker.com/get-docker/) |
| **Docker Compose** | ≥ 2.20 (bundled with Docker Desktop) | — |
| **curl** | any | `brew install curl` / pre-installed on Linux |
| **jq** | ≥ 1.6 | `brew install jq` / `apt install jq` |
| **Poetry** | ≥ 1.8 | `pip install poetry` or [python-poetry.org](https://python-poetry.org/docs/#installation) |
| **Python** | 3.12 | [python.org](https://www.python.org/downloads/) or `brew install python@3.12` |
| **ngrok** *(optional, for demos)* | ≥ 3 | `brew install ngrok` / [ngrok.com/download](https://ngrok.com/download) |

> **macOS one-liner:**
> ```bash
> brew install curl jq poetry ngrok && brew install --cask docker
> ```

> **Ubuntu/Debian one-liner:**
> ```bash
> sudo apt update && sudo apt install -y curl jq
> pip install poetry
> # Docker: https://docs.docker.com/engine/install/ubuntu/
> ```

### 1. Clone & configure

```bash
git clone <repo-url>
cd ClaudeProxyServer
cp .env.example .env
```

Edit `.env` — the three values that must change before first boot:

```bash
# Generate a 64-char secret:
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(64))")

DB_PASSWORD=<strong-password>
FIRST_ADMIN_PASSWORD=<strong-password>
```

The default `.env` points `ANTHROPIC_BASE_URL` at the bundled mock server (`http://mock-anthropic:8001`), so no real Anthropic account is required to run locally.

### 2. Start the stack

```bash
docker compose up -d --build
```

Services started: `db` (Postgres 16), `migrate` (Alembic), `proxy` (FastAPI), `mock-anthropic`, `nginx`.

### 3. Verify

```bash
# Wait for readiness
until curl -sf http://localhost:8000/ready > /dev/null; do sleep 2; done
echo "Ready"

# Add a Claude account (fake token is fine against the mock)
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<FIRST_ADMIN_PASSWORD>"}' | jq -r .access_token)

ACC_ID=$(curl -s -X POST http://localhost:8000/admin/accounts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Mock","email":"mock@test.com","auth_token":"fake-key"}' \
  | jq -r .id)

# Create a user and get their API key
API_KEY=$(curl -s -X POST http://localhost:8000/admin/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","email":"alice@co.com","password":"pass123!"}' | jq -r .api_key)

# Send a message through the proxy
curl -s -X POST http://localhost:8000/v1/messages \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-haiku-4-5-20251001","max_tokens":20,"messages":[{"role":"user","content":"say hello"}]}'
```

Web panel: `http://localhost/ui/login` — log in as `admin` with `FIRST_ADMIN_PASSWORD`.

## Configuration

All settings are read from the `.env` file (or environment variables).

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:changeme@db:5432/claude_proxy` | Async Postgres DSN |
| `DB_PASSWORD` | `changeme` | Postgres password (used by docker-compose) |
| `SECRET_KEY` | *(must change)* | 64+ hex chars — signs JWTs and encrypts account tokens (AES-256-GCM) |
| `FIRST_ADMIN_USERNAME` | `admin` | Admin username created on first boot |
| `FIRST_ADMIN_EMAIL` | `admin@example.com` | Admin email |
| `FIRST_ADMIN_PASSWORD` | `changeme123!` | Admin password — change before deploying |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | Upstream API; set to `http://mock-anthropic:8001` for local dev |
| `REQUEST_TIMEOUT_SECONDS` | `300.0` | Per-request timeout forwarded to Anthropic |
| `MAX_PROMPT_LOG_CHARS` | `50000` | Maximum characters stored per prompt/response in the DB |
| `ENABLE_PROMPT_LOGGING` | `true` | Set `false` to suppress prompt/response content (GDPR) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | JWT access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | JWT refresh token lifetime |
| `LOG_LEVEL` | `INFO` | Loguru log level |

## API Reference

### Proxy

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/v1/messages` | API key | Forward message to Claude (streaming + sync) |
| `GET` | `/v1/models` | API key | Passthrough model list |

### Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/login` | — | Obtain access + refresh tokens |
| `POST` | `/auth/refresh` | Refresh token | Rotate access token |
| `POST` | `/auth/logout` | Bearer | Revoke refresh token |

### Admin

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/admin/accounts` | Bearer | List Claude accounts |
| `POST` | `/admin/accounts` | Bearer | Add Claude account |
| `PATCH` | `/admin/accounts/{id}` | Bearer | Update account |
| `DELETE` | `/admin/accounts/{id}` | Bearer | Remove account |
| `POST` | `/admin/accounts/{id}/test` | Bearer | Test account connectivity |
| `POST` | `/admin/accounts/{id}/unban` | Bearer | Manually unban account |
| `GET` | `/admin/users` | Bearer | List users |
| `POST` | `/admin/users` | Bearer | Create user (returns API key) |
| `POST` | `/admin/users/{id}/rotate-key` | Bearer | Rotate user API key |
| `GET` | `/admin/stats/overview` | Bearer | Aggregate request/token stats |
| `GET` | `/admin/stats/accounts` | Bearer | Per-account stats |
| `GET` | `/admin/stats/models` | Bearer | Per-model stats |

### User

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/user/me` | Bearer | Current user profile |
| `GET` | `/user/usage` | Bearer | Personal token usage |
| `GET` | `/user/logs` | Bearer | Personal request log |

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check (always 200) |
| `GET` | `/ready` | Readiness check (200 when DB is reachable) |

## Web Panel

The Jinja2 admin panel is served at `http://localhost/ui/` (via nginx) or `http://localhost:8000/ui/` (direct).

- **Login:** `http://localhost/ui/login`
- **Default credentials:** `admin` / value of `FIRST_ADMIN_PASSWORD`
- **Features:** account management, user management, request logs, token usage charts

## Development

### Running tests

All test scripts are in `scripts/` and can be run by any developer after `docker compose up -d --build`.

#### 1. Unit tests — no Docker required

```bash
poetry run pytest tests/unit/ -v
```

Tests routing strategy, account state manager, and security functions in pure Python (no DB).

#### 2. Integration tests — requires running Postgres

```bash
TEST_DATABASE_URL=postgresql+asyncpg://postgres:<DB_PASSWORD>@localhost:5433/claude_proxy \
  poetry run pytest tests/integration/ -v
```

#### 3. E2E test — 16 checks against the full stack

```bash
docker compose up -d --build
bash scripts/test_e2e.sh http://localhost:8000
```

Covers: health, auth (login/logout/wrong password), account CRUD, user CRUD, proxy (sync + streaming), token tracking, stats, unauthenticated requests.

#### 4. Routing test — multi-account load distribution

```bash
bash scripts/test_routing.sh http://localhost:8000 12
```

Creates 3 Claude accounts, sends N requests, verifies least-connections strategy distributes load across accounts. Cleans up after itself.

#### 5. Token tracking demo

```bash
bash scripts/verify_tokens.sh http://localhost:8000
```

Creates a user, sends 3 requests through the proxy, then prints the user's input/output token totals to confirm tracking works end-to-end.

### Project structure

```
src/
├── main.py                  Application entry point
├── core/                    Config, database session, security (AES-GCM + JWT + bcrypt), logger
├── domain/                  Pure dataclasses, exceptions, Protocol interfaces
├── infrastructure/          SQLAlchemy ORM, async repos, httpx ClientPool, AccountStateManager
├── application/             Routing strategies, ProxyService, account/user/stats services, DTOs
└── api/                     FastAPI app, lifespan, deps, middleware, routers
mock_anthropic/
└── main.py                  FastAPI mock of api.anthropic.com (used in dev and tests)
scripts/
├── test_e2e.sh              Full end-to-end test (16 checks, curl-based)
└── verify_tokens.sh         Token tracking demo — creates user, sends requests, prints usage
tests/
├── unit/                    No DB — routing strategy, state manager, security
├── integration/             Real test DB (set TEST_DATABASE_URL)
└── e2e/                     Full stack (set PROXY_URL)
```

### Mock Anthropic

The `mock-anthropic` service (`mock_anthropic/main.py`) emulates `api.anthropic.com` locally. It supports four modes, configurable via the `MOCK_MODE` environment variable or the `x-mock-mode` per-request header:

| Mode | Behaviour |
|---|---|
| `normal` | Returns a valid streamed response |
| `rate_limit` | Returns HTTP 429 |
| `banned` | Returns HTTP 401 |
| `slow` | Adds a delay before responding |

```bash
# Trigger rate-limit for a single request:
curl -X POST http://localhost:8001/v1/messages \
  -H "x-mock-mode: rate_limit" \
  -H "Content-Type: application/json" \
  -d '{"model":"test","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}'
```

## Production Deployment

1. **Point at the real API.** In `.env`, set:
   ```
   ANTHROPIC_BASE_URL=https://api.anthropic.com
   ```

2. **Add real accounts.** Use Anthropic API keys (`sk-ant-api03-...`) from [console.anthropic.com](https://console.anthropic.com). Account tokens are encrypted at rest with AES-256-GCM.

3. **Security checklist:**
   - Generate a new `SECRET_KEY` (64+ random hex chars).
   - Set a strong `DB_PASSWORD`.
   - Set a strong `FIRST_ADMIN_PASSWORD`.
   - Set `ENABLE_PROMPT_LOGGING=false` if GDPR compliance is required.
   - Restrict port 8000 at the firewall — expose only port 80 via nginx.
   - Use TLS termination at the nginx or load-balancer level.

4. **Scaling.** The proxy uses Redis for shared state (`AccountStateManager`), so multiple workers and instances are supported out of the box.

## Showing to Clients (Demo)

Expose the local stack over the internet with ngrok:

```bash
brew install ngrok         # macOS
ngrok config add-authtoken <your-ngrok-token>
ngrok http 80
```

ngrok prints a public URL such as `https://abc123.ngrok-free.app`. Share with the client:

- **Admin panel:** `https://abc123.ngrok-free.app/ui/login`
- **Employee setup guide:** [how_to_connect.md](how_to_connect.md)

The free ngrok tier is sufficient for demos. For persistent URLs, use a paid plan or a VPS with a reverse proxy.
