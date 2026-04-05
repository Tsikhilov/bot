#!/bin/bash
set -e
TOKEN=$(curl -s http://127.0.0.1:8000/api/admin/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=Tsikhilovk&password=Haker05dag%24' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
echo "TOKEN_OK=1"

echo "=== INBOUNDS ==="
curl -s http://127.0.0.1:8000/api/inbounds \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo "=== USERS ==="
curl -s 'http://127.0.0.1:8000/api/users?limit=50' \
  -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys,json
data = json.load(sys.stdin)
total = data.get('total', 0)
print(f'total={total}')
for u in data.get('users', []):
    ib = list(u.get('inbounds', {}).keys())
    print(f'  {u[\"username\"]}  status={u.get(\"status\")}  inbounds={ib}')
"
echo "=== DONE ==="
