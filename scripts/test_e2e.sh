#!/usr/bin/env bash
# Autonomous E2E test script — Claude runs this to verify the whole system.
# Usage: bash scripts/test_e2e.sh [PROXY_URL]
#
# Requires: curl, jq
# Stack must be running: docker compose up -d

set -eo pipefail

PROXY="${1:-http://localhost:8000}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin}"
PASS=0
FAIL=0

green() { echo -e "\033[32m✓ $1\033[0m"; }
red()   { echo -e "\033[31m✗ $1\033[0m"; }

assert_status() {
  local label=$1 expected=$2 actual=$3
  if [ "$actual" -eq "$expected" ]; then
    green "$label (HTTP $actual)"
    PASS=$((PASS + 1))
  else
    red "$label — expected HTTP $expected, got HTTP $actual"
    FAIL=$((FAIL + 1))
  fi
}

echo ""
echo "=== Claude Proxy E2E Test ==="
echo "Target: $PROXY"
echo ""

# 1. Health
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$PROXY/health")
assert_status "GET /health" 200 "$STATUS"

# 2. Ready
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$PROXY/ready")
assert_status "GET /ready" 200 "$STATUS"

# 3. Admin login
echo ""
echo "--- Auth ---"
LOGIN=$(curl -s -X POST "$PROXY/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}")
ADMIN_TOKEN=$(echo "$LOGIN" | jq -r '.access_token // empty')
if [ -n "$ADMIN_TOKEN" ]; then
  green "Admin login → got JWT"
  PASS=$((PASS + 1))
else
  red "Admin login failed: $LOGIN"
  FAIL=$((FAIL + 1))
  exit 1
fi

# 4. Wrong password → 401
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$PROXY/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"wrong"}')
assert_status "Login with wrong password → 401" 401 "$STATUS"

# 5. Admin: create a Claude account (pointing to mock)
echo ""
echo "--- Accounts ---"
ACC=$(curl -s -X POST "$PROXY/admin/accounts" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Account","email":"mock@test.com","auth_token":"fake-test-token","auth_type":"api_key"}')
ACC_ID=$(echo "$ACC" | jq -r '.id // empty')
if [ -n "$ACC_ID" ]; then
  green "Create Claude account → id=$ACC_ID"
  PASS=$((PASS + 1))
else
  red "Create account failed: $ACC"
  FAIL=$((FAIL + 1))
fi

# 6. List accounts
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$PROXY/admin/accounts" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
assert_status "GET /admin/accounts" 200 "$STATUS"

# 7. Test account connectivity
if [ -n "$ACC_ID" ]; then
  TEST=$(curl -s -X POST "$PROXY/admin/accounts/$ACC_ID/test" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
  TEST_STATUS=$(echo "$TEST" | jq -r '.status // empty')
  if [ "$TEST_STATUS" = "ok" ]; then
    green "Account connectivity test → ok"
    PASS=$((PASS + 1))
  else
    red "Account test failed: $TEST"
    FAIL=$((FAIL + 1))
  fi
fi

# 8. Admin: create user
echo ""
echo "--- Users ---"
UNAME="testuser_$$"
USER=$(curl -s -X POST "$PROXY/admin/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$UNAME\",\"email\":\"$UNAME@test.com\",\"password\":\"pass123!\"}")
API_KEY=$(echo "$USER" | jq -r '.api_key // empty')
if [ -n "$API_KEY" ]; then
  green "Create user → api_key prefix=${API_KEY:0:12}"
  PASS=$((PASS + 1))
else
  red "Create user failed: $USER"
  FAIL=$((FAIL + 1))
fi

# Get JWT for the test user (needed for /user/usage)
USER_JWT=$(curl -s -X POST "$PROXY/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$UNAME\",\"password\":\"pass123!\"}" | jq -r '.access_token // empty')

# 9. User: GET /v1/models
echo ""
echo "--- Proxy ---"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$PROXY/v1/models" \
  -H "Authorization: Bearer $API_KEY")
assert_status "GET /v1/models (with user API key)" 200 "$STATUS"

# 10. Proxy: POST /v1/messages (non-streaming)
RESP=$(curl -s -X POST "$PROXY/v1/messages" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-haiku-4-5-20251001","max_tokens":20,"messages":[{"role":"user","content":"say TEST_OK"}]}')
MSG_TEXT=$(echo "$RESP" | jq -r '.content[0].text // empty')
if [ -n "$MSG_TEXT" ]; then
  green "POST /v1/messages → \"$MSG_TEXT\""
  PASS=$((PASS + 1))
else
  red "Proxy message failed: $RESP"
  FAIL=$((FAIL + 1))
fi

# 10b. Verify token usage was logged (JWT required for /user/usage)
USAGE=$(curl -s "$PROXY/user/usage" -H "Authorization: Bearer $USER_JWT")
INPUT_TOK=$(echo "$USAGE" | jq -r '.total_input_tokens // 0')
if [ "$INPUT_TOK" -gt 0 ] 2>/dev/null; then
  green "Token tracking → input_tokens=$INPUT_TOK logged correctly"
  PASS=$((PASS + 1))
else
  red "Token tracking failed — input_tokens=0 after proxy request"
  FAIL=$((FAIL + 1))
fi

# 11. Proxy: POST /v1/messages (streaming)
STREAM_RESP=$(curl -s -X POST "$PROXY/v1/messages" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-haiku-4-5-20251001","max_tokens":20,"stream":true,"messages":[{"role":"user","content":"hi"}]}' \
  --max-time 10)
if echo "$STREAM_RESP" | grep -q "message_start"; then
  green "POST /v1/messages?stream=true → got SSE events"
  PASS=$((PASS + 1))
else
  red "Streaming failed: ${STREAM_RESP:0:200}"
  FAIL=$((FAIL + 1))
fi

# 12. Unauthenticated → 401
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$PROXY/v1/messages" \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-haiku-4-5-20251001","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}')
assert_status "POST /v1/messages without auth → 401" 401 "$STATUS"

# 13. Stats
echo ""
echo "--- Stats ---"
STATS=$(curl -s "$PROXY/admin/stats/overview" -H "Authorization: Bearer $ADMIN_TOKEN")
TOTAL=$(echo "$STATS" | jq -r '.total_requests // -1')
if [ "$TOTAL" -ge 0 ] 2>/dev/null; then
  green "GET /admin/stats/overview → total_requests=$TOTAL"
  PASS=$((PASS + 1))
else
  red "Stats failed: $STATS"
  FAIL=$((FAIL + 1))
fi

# 14. User profile
ME=$(curl -s "$PROXY/user/me" -H "Authorization: Bearer $ADMIN_TOKEN")
UNAME_GOT=$(echo "$ME" | jq -r '.username // empty')
if [ "$UNAME_GOT" = "$ADMIN_USER" ]; then
  green "GET /user/me → username=$UNAME_GOT"
  PASS=$((PASS + 1))
else
  red "GET /user/me failed: $ME"
  FAIL=$((FAIL + 1))
fi

# 15. Cleanup: delete test account
if [ -n "$ACC_ID" ]; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$PROXY/admin/accounts/$ACC_ID" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
  assert_status "DELETE /admin/accounts/$ACC_ID" 204 "$STATUS"
fi

# Summary
echo ""
echo "================================"
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -eq 0 ]; then
  echo -e "\033[32mAll tests passed!\033[0m"
  exit 0
else
  echo -e "\033[31m$FAIL test(s) failed\033[0m"
  exit 1
fi
