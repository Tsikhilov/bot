#!/bin/bash
set -e

echo "=== [1/7] Creating cert symlinks for Marzban ==="
mkdir -p /var/lib/marzban/certs/sub.smartkama.ru
ln -sf /etc/letsencrypt/live/sub.smartkama.ru/fullchain.pem /var/lib/marzban/certs/sub.smartkama.ru/fullchain.pem
ln -sf /etc/letsencrypt/live/sub.smartkama.ru/privkey.pem   /var/lib/marzban/certs/sub.smartkama.ru/privkey.pem
ls -la /var/lib/marzban/certs/sub.smartkama.ru/
echo "OK"

echo "=== [2/7] Backing up current Marzban xray config ==="
cp /var/lib/marzban/xray_config.json /var/lib/marzban/xray_config.json.bak.$(date +%s)
echo "OK"

echo "=== [3/7] Installing new xray_config.json ==="
cp /tmp/marzban_xray_config.json /var/lib/marzban/xray_config.json
python3 -c 'import json; json.load(open("/var/lib/marzban/xray_config.json")); print("JSON_VALID=1")'
echo "OK"

echo "=== [4/7] Stopping and disabling 3x-ui ==="
systemctl stop x-ui 2>&1 || true
systemctl disable x-ui 2>&1 || true
echo "x-ui stopped: $(systemctl is-active x-ui 2>&1)"

echo "=== [5/7] Stopping and disabling ALL hiddify services ==="
for svc in hiddify-xray hiddify-haproxy hiddify-nginx hiddify-panel hiddify-panel-background-tasks hiddify-redis hiddify-singbox hiddify-ss-faketls hiddify-cli; do
    systemctl stop "$svc" 2>/dev/null || true
    systemctl disable "$svc" 2>/dev/null || true
    echo "  $svc: $(systemctl is-active $svc 2>&1)"
done
echo "OK"

echo "=== [6/7] Stopping haproxy (system) ==="
systemctl stop haproxy 2>/dev/null || true
systemctl disable haproxy 2>/dev/null || true
echo "haproxy: $(systemctl is-active haproxy 2>&1)"

echo "=== [7/7] Restarting Marzban ==="
cd /opt/marzban
docker compose restart 2>&1
sleep 5
echo "Marzban status: $(docker compose ps --format json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("State","?"))' 2>/dev/null || echo 'check manually')"

echo ""
echo "=== PORT CHECK ==="
ss -tlnp | grep -E ':443|:9443|:10443|:11443|:12443|:15443|:16443|:8000|:2097|:2096|:55445'
echo ""
echo "=== XRAY PROCESSES ==="
ps aux | grep xray | grep -v grep
echo ""
echo "=== MIGRATION DONE ==="
