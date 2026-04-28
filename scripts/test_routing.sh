#!/usr/bin/env bash
# Test least-connections routing across multiple Claude accounts.
# Creates 3 accounts, sends N parallel requests, verifies load is spread.
#
# Usage: bash scripts/test_routing.sh [PROXY_URL] [NUM_REQUESTS]
#   PROXY_URL     default: http://localhost:8000
#   NUM_REQUESTS  default: 12

set -eo pipefail

PROXY="${1:-http://localhost:8000}"
N="${2:-12}"

green() { echo -e "\033[32m✓ $1\033[0m"; }
red()   { echo -e "\033[31m✗ $1\033[0m"; }

echo ""
echo "=== Multi-Account Routing Test ==="
echo "Proxy: $PROXY  |  Requests: $N"
echo ""

# 1. Admin login
TOKEN=$(curl -s -X POST "$PROXY/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | jq -r '.access_token // empty')
[ -z "$TOKEN" ] && { red "Admin login failed"; exit 1; }
green "Admin login OK"

# 2. Create 3 test accounts
ACC_IDS=()
for i in 1 2 3; do
  ID=$(curl -s -X POST "$PROXY/admin/accounts" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"Route Test $i\",\"email\":\"route$i@test.com\",\"auth_token\":\"fake-key-$i\",\"auth_type\":\"api_key\"}" \
    | jq -r '.id // empty')
  [ -z "$ID" ] && { red "Failed to create account $i"; exit 1; }
  ACC_IDS+=("$ID")
  green "Created account $i: ${ID:0:8}..."
done

# 3. Create test user
UNAME="routetest_$$"
API_KEY=$(curl -s -X POST "$PROXY/admin/users" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$UNAME\",\"email\":\"$UNAME@test.com\",\"password\":\"pass123!\"}" \
  | jq -r '.api_key // empty')
[ -z "$API_KEY" ] && { red "Failed to create test user"; exit 1; }
green "Created user $UNAME"

# 4. Send N requests sequentially
echo ""
echo "--- Sending $N requests ---"
FAIL_COUNT=0
for i in $(seq 1 "$N"); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$PROXY/v1/messages" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -H "anthropic-version: 2023-06-01" \
    -d "{\"model\":\"claude-haiku-4-5-20251001\",\"max_tokens\":5,\"messages\":[{\"role\":\"user\",\"content\":\"req $i\"}]}")
  if [ "$STATUS" -eq 200 ]; then
    printf "."
  else
    printf "E"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
done
echo ""
[ "$FAIL_COUNT" -eq 0 ] && green "All $N requests succeeded" || red "$FAIL_COUNT requests failed"

# 5. Show per-account distribution
echo ""
echo "--- Routing distribution ---"
STATS=$(curl -s "$PROXY/admin/stats/accounts" -H "Authorization: Bearer $TOKEN")

TOTAL_SPREAD=0
for ID in "${ACC_IDS[@]}"; do
  COUNT=$(echo "$STATS" | jq -r --arg id "$ID" '.[] | select(.account_id == $id) | .count // 0')
  COUNT="${COUNT:-0}"
  TOTAL_SPREAD=$((TOTAL_SPREAD + COUNT))
  echo "  Account ${ID:0:8}... → $COUNT requests"
done

echo ""
echo "  Total routed through test accounts: $TOTAL_SPREAD / $N"
if [ "$TOTAL_SPREAD" -ge "$N" ]; then
  green "Routing OK — all requests distributed across accounts"
else
  red "Routing issue — only $TOTAL_SPREAD / $N accounted for"
fi

# Check that no single account got 100% of load (only if N >= 3)
if [ "$N" -ge 3 ] && [ "${#ACC_IDS[@]}" -ge 2 ]; then
  MAX=0
  for ID in "${ACC_IDS[@]}"; do
    COUNT=$(echo "$STATS" | jq -r --arg id "$ID" '.[] | select(.account_id == $id) | .count // 0')
    COUNT="${COUNT:-0}"
    [ "$COUNT" -gt "$MAX" ] && MAX=$COUNT
  done
  if [ "$MAX" -lt "$N" ]; then
    green "Load spread verified — max on single account: $MAX / $N"
  else
    red "Load NOT spread — one account got all $N requests"
  fi
fi

# 6. Cleanup
echo ""
for ID in "${ACC_IDS[@]}"; do
  curl -s -X DELETE "$PROXY/admin/accounts/$ID" -H "Authorization: Bearer $TOKEN" > /dev/null
done
green "Cleaned up test accounts"

echo ""
echo "=== Routing test complete ==="
