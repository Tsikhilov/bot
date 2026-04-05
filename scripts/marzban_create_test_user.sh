#!/bin/bash
set -e

# Get token
TOKEN=$(curl -s http://127.0.0.1:8000/api/admin/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=Tsikhilovk&password=Haker05dag%24' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
echo "TOKEN_OK"

# Create test user with sub_id 01dcf49b
# expire = far future (2027-01-01)
PAYLOAD='{"username":"test-01dcf49b","status":"active","expire":1798761600,"data_limit":10737418240,"data_limit_reset_strategy":"no_reset","note":"HidyBot:test;type=individual;max_ips=2","proxies":{"vless":{},"trojan":{}},"inbounds":{"vless":["VLESS_WS_TLS_443","VLESS_REALITY_9443","VLESS_REALITY_10443","VLESS_REALITY_11443","VLESS_REALITY_12443","VLESS_GRPC_TLS_15443"],"trojan":["TROJAN_TLS_16443"]}}'

echo "Creating user..."
RESULT=$(curl -s -X POST http://127.0.0.1:8000/api/user \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" -w "\n__HTTP_CODE__%{http_code}" 2>&1)

HTTP_CODE=$(echo "$RESULT" | grep -oP '__HTTP_CODE__\K\d+')
BODY=$(echo "$RESULT" | sed 's/__HTTP_CODE__[0-9]*//')
echo "http_code=$HTTP_CODE"
echo "body=$BODY"

echo "$BODY" | python3 -c '
import sys,json
data = json.load(sys.stdin)
un = data.get("username","")
st = data.get("status","")
sub_url = data.get("subscription_url","")
print("username=" + un)
print("status=" + st)
print("subscription_url=" + sub_url)
if "/sub/" in sub_url:
    token = sub_url.split("/sub/")[-1]
    print("sub_token=" + token)
links = data.get("links",[])
print("links_count=" + str(len(links)))
for i,l in enumerate(links[:3]):
    print("  link[" + str(i) + "]=" + l[:80] + "...")
'

echo ""
echo "=== Verify subscription works ==="
SUB_TOKEN=$(echo "$RESULT" | python3 -c 'import sys,json; d=json.load(sys.stdin); u=d.get("subscription_url",""); print(u.split("/sub/")[-1] if "/sub/" in u else "")')
echo "sub_token=$SUB_TOKEN"
curl -s -o /dev/null -w "direct_sub_status=%{http_code}\n" "http://127.0.0.1:8000/sub/$SUB_TOKEN"
curl -s -o /dev/null -w "nginx_sub_status=%{http_code}\n" "https://sub.smartkama.ru:2096/sub/$SUB_TOKEN" -k

echo "DONE"
