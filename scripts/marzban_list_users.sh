#!/bin/bash
set -e
TOKEN=$(curl -s http://127.0.0.1:8000/api/admin/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=Tsikhilovk&password=Haker05dag%24' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

echo "=== GET USER test-01dcf49b ==="
curl -s "http://127.0.0.1:8000/api/user/test-01dcf49b" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool 2>&1

echo ""
echo "=== LIST ALL USERS ==="
curl -s "http://127.0.0.1:8000/api/users?limit=50" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool 2>&1

echo "DONE"
