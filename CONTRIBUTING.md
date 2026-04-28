# Contributing

## Development setup

Prerequisites: Python 3.12, Poetry, Docker Desktop

1. Fork and clone the repository
2. Install dependencies:
   ```bash
   poetry install
   ```
3. Copy and configure environment:
   ```bash
   cp .env.example .env
   # Edit .env: set SECRET_KEY, DB_PASSWORD, FIRST_ADMIN_PASSWORD
   ```
4. Start the stack:
   ```bash
   docker compose up -d
   ```

## Running tests

```bash
# Unit tests (no DB required)
poetry run pytest tests/unit/ -v

# Integration tests (requires running DB)
TEST_DATABASE_URL=postgresql+asyncpg://postgres:changeme@localhost:5433/claude_proxy \
  poetry run pytest tests/integration/ -v

# Full e2e (requires running stack)
bash scripts/test_e2e.sh http://localhost:8000
```

## Code style

The project uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
poetry run ruff check .
poetry run ruff format .
```

All code must pass ruff before committing.

## Architecture rules

Dependency direction is strictly inward:
```
api → application → domain ← infrastructure
```

- `domain/` must have zero imports from other layers
- `application/services/` depend on `domain/interfaces/` (Protocols), not concrete repos
- New features follow the same layered pattern

## Branch naming

```
feature/<short-description>
fix/<issue-or-description>
docs/<what>
```

## Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add per-account request quotas
fix: handle 529 overloaded response from Anthropic
docs: update deployment guide
chore: bump httpx to 0.28
```

## Pull requests

- One feature per PR
- All tests must pass
- Add tests for new behaviour
- Update `.env.example` if adding new env vars
