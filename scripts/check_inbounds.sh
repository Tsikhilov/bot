#!/bin/bash
# Проверить inbounds и при необходимости создать их заново
set -euo pipefail

DOMAIN="sub.smartkama.ru"
PANEL_PORT="55445"
PANEL_USER="admin"
PANEL_PASS="SmartKama2026!"
SECRET_PATH="902184284ee0d060"
API="https://127.0.0.1:${PANEL_PORT}/${SECRET_PATH}"

# В 3x-ui >=2.8 путь API изменился: /panel/api/  вместо /xui/API/
API_INBOUNDS="${API}/panel/api/inbounds"
LOGIN_URL="${API}/login"

echo "[LOGIN]"
JAR=$(mktemp)
curl -sk -c "$JAR" -X POST "$LOGIN_URL" \
    -d "username=${PANEL_USER}&password=${PANEL_PASS}" -o /tmp/login_r.json
cat /tmp/login_r.json; echo ""

echo "[LIST INBOUNDS]"
curl -skL -b "$JAR" "$API_INBOUNDS" -o /tmp/inbounds.json
python3 << 'PYEOF'
import json
with open('/tmp/inbounds.json') as f:
    d = json.load(f)
objs = d.get('obj', [])
print(f"Total inbounds: {len(objs)}")
for o in objs:
    print(f"  ID={o['id']} port={o.get('port')} remark={o.get('remark')} protocol={o.get('protocol')}")
PYEOF

# Сохраним правильный API path в credentials
echo ""
echo "API base path: ${API}"
echo "Inbounds path: ${API_INBOUNDS}"
rm -f "$JAR"
