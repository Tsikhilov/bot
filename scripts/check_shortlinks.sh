#!/bin/bash
set -e
echo "=== SHORT_LINKS ==="
sqlite3 /opt/SmartKamaVPN/Database/smartkamavpn.db "SELECT token, target_url, created_at FROM short_links ORDER BY rowid DESC LIMIT 20;"
echo ""
echo "=== MARZBAN USERS ==="
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/admin/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=Tsikhilovk&password=Haker05dag%24' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
curl -s http://127.0.0.1:8000/api/users -H "Authorization: Bearer $TOKEN" | python3 -c '
import sys, json
data = json.load(sys.stdin)
users = data.get("users", data) if isinstance(data, dict) else data
for u in users:
    name = u.get("username","?")
    sub = u.get("subscription_url","?")
    print(f"  user={name}  sub_url={sub}")
'
echo ""
echo "=== MARZBAN SUB URL PREFIX ==="
grep XRAY_SUBSCRIPTION_URL_PREFIX /opt/marzban/.env || echo "(not set)"
echo ""
echo "=== TEST SUB FETCH ==="
# Try fetching the first user's subscription
FIRST_SUB=$(curl -s http://127.0.0.1:8000/api/users -H "Authorization: Bearer $TOKEN" | python3 -c '
import sys, json
data = json.load(sys.stdin)
users = data.get("users", data) if isinstance(data, dict) else data
if users:
    u = users[0]
    sub = u.get("subscription_url","")
    print(sub)
')
if [ -n "$FIRST_SUB" ]; then
    echo "First user sub_url: $FIRST_SUB"
    # Extract just the path part after the domain
    SUB_PATH=$(echo "$FIRST_SUB" | sed 's|https\?://[^/]*||')
    echo "Sub path: $SUB_PATH"
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8000${SUB_PATH}")
    echo "Direct Marzban fetch status: $STATUS"
fi
