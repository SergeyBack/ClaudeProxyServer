#!/usr/bin/env bash
# Verify token tracking works end-to-end
# Usage: bash scripts/verify_tokens.sh http://localhost:8000
set -eo pipefail
PROXY="${1:-http://localhost:8000}"

echo "=== Token Tracking Verification ==="
echo ""

# 1. Admin login
TOKEN=$(curl -s -X POST "$PROXY/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | jq -r .access_token)
echo "✓ Logged in as admin"

# 2. Create test user
UNAME="tokentest_$$"
USER=$(curl -s -X POST "$PROXY/admin/users" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$UNAME\",\"email\":\"$UNAME@test.com\",\"password\":\"pass123!\"}")
API_KEY=$(echo "$USER" | jq -r '.api_key')
echo "✓ Created user $UNAME, API key prefix: ${API_KEY:0:12}"

# Get JWT for the test user (needed for /user/usage)
USER_JWT=$(curl -s -X POST "$PROXY/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$UNAME\",\"password\":\"pass123!\"}" | jq -r .access_token)

# 3. Create account
ACC_ID=$(curl -s -X POST "$PROXY/admin/accounts" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Token Test Account","email":"t@t.com","auth_token":"fake","auth_type":"api_key"}' | jq -r .id)
echo "✓ Created Claude account"

# 4. Send 3 requests through proxy
for i in 1 2 3; do
  curl -s -X POST "$PROXY/v1/messages" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -H "anthropic-version: 2023-06-01" \
    -d "{\"model\":\"claude-haiku-4-5-20251001\",\"max_tokens\":10,\"messages\":[{\"role\":\"user\",\"content\":\"request $i\"}]}" > /dev/null
done
echo "✓ Sent 3 proxy requests"

# 5. Check usage
echo ""
echo "--- Usage stats for $UNAME ---"
curl -s "$PROXY/user/usage" \
  -H "Authorization: Bearer $USER_JWT" | jq '{total_requests,total_input_tokens,total_output_tokens}'

# 6. Admin stats
echo ""
echo "--- Global overview ---"
curl -s "$PROXY/admin/stats/overview" \
  -H "Authorization: Bearer $TOKEN" | jq .

# 7. Cleanup
curl -s -X DELETE "$PROXY/admin/accounts/$ACC_ID" -H "Authorization: Bearer $TOKEN" > /dev/null
echo ""
echo "✓ Done. Check the numbers above — input_tokens and output_tokens should be > 0."
