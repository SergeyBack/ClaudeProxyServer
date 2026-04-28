# How to Connect to Claude Proxy

## What is this?

This is a corporate proxy for **Claude Code** — a CLI tool for developers.  
Employees do **not** use the browser app (claude.ai) — they use Claude Code in the terminal or VS Code.

The employee never sees the real Anthropic API key (`sk-ant-...`).  
They only know their personal proxy key (`ccp_...`) and the proxy address.

---

## How it works

```
Employee's computer
    │
    │  ANTHROPIC_BASE_URL = proxy address
    │  ANTHROPIC_API_KEY  = ccp_xxxxx  (personal proxy key)
    │
    ▼
Claude Code (terminal / VS Code)
    │
    │  sends request to the proxy, NOT directly to Anthropic
    │
    ▼
Proxy server
    │
    │  selects the least-loaded Anthropic account
    │  substitutes the real sk-ant-... key
    │  logs token usage per user
    │
    ▼
api.anthropic.com  ←── real request goes here
```

---

## Admin: initial setup

### 1. Open the admin panel

```
URL:      https://<your-proxy-url>/ui/login
Username: admin
Password: <your FIRST_ADMIN_PASSWORD from .env>
```

### 2. Get Anthropic API keys

The proxy is designed for companies that maintain several **Anthropic API accounts**.  
Each account has its own API key from [console.anthropic.com](https://console.anthropic.com).

**For each account:**
1. Go to [console.anthropic.com](https://console.anthropic.com) → **API Keys**
2. Click **Create Key**
3. Copy the key (`sk-ant-api03-...`)

### 3. Add each account to the proxy

**Admin panel → Accounts → Add Account** (repeat for every API account):

| Field | Value |
|---|---|
| Name | Company Account 1 |
| Email | account1@company.com |
| Auth Token | `sk-ant-api03-...` *(paste API key)* |
| Auth Type | `api_key` |

Status will change to `available` immediately. Add all accounts — the proxy will balance load between them automatically using least-connections routing.

### 4. Create users for employees

**Admin panel → Users → Create User** — one per employee.  
After creation the panel shows a one-time `ccp_...` key — save it and send it to the employee securely.

---

## Employee: install and configure Claude Code

### Step 1 — Install Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```

### Step 2 — Configure the proxy (once)

```bash
# Add to ~/.zshrc or ~/.bashrc:
export ANTHROPIC_BASE_URL=https://<your-proxy-url>
export ANTHROPIC_API_KEY=ccp_xxxxx...   # key received from admin
```

Then reload the shell:

```bash
source ~/.zshrc
```

### Step 3 — Use Claude Code as usual

```bash
claude "write a sorting function"
claude "explain this code"
claude "add unit tests to this file"
```

Or open VS Code and use Claude Code from the integrated terminal — it picks up the environment variables automatically.

---

## Quick API test (curl)

```bash
# 1. Get admin JWT
TOKEN=$(curl -s -X POST https://<your-proxy-url>/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<your-admin-password>"}' | jq -r .access_token)

# 2. Add an Anthropic account
curl -s -X POST https://<your-proxy-url>/admin/accounts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Company Account 1",
    "email": "account1@company.com",
    "auth_token": "sk-ant-api03-...",
    "auth_type": "api_key"
  }' | jq '{id, name, status}'

# 3. Create a test user and get their API key
API_KEY=$(curl -s -X POST https://<your-proxy-url>/admin/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "email": "alice@company.com",
    "password": "pass123!"
  }' | jq -r .api_key)

echo "Employee API key: $API_KEY"

# 4. Send a test request through the proxy
curl -s -X POST https://<your-proxy-url>/v1/messages \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-haiku-4-5-20251001",
    "max_tokens": 20,
    "messages": [{"role": "user", "content": "say hello"}]
  }' | jq '{model, text: .content[0].text, usage}'
```

---

## What the admin sees in the panel

| Section | Shows |
|---|---|
| **Dashboard** | Total requests, tokens used today |
| **Accounts** | Status of each API key (`available` / `rate_limited` / `banned`) |
| **Users** | Employee list, their `ccp_` key prefixes |
| **My Usage** | Personal token stats broken down by model |

---

## Revoking access

To revoke an employee's access — go to **Users**, find the user, deactivate or delete them.  
Their `ccp_` key stops working immediately. The real Anthropic API keys are never exposed to employees.
