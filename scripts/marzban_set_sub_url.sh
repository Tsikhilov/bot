#!/bin/bash
set -e
cd /opt/marzban

# Set XRAY_SUBSCRIPTION_URL_PREFIX
sed -i '/^# XRAY_SUBSCRIPTION_URL_PREFIX/c\XRAY_SUBSCRIPTION_URL_PREFIX = "https://sub.smartkama.ru:2096"' .env

# Set XRAY_SUBSCRIPTION_PATH
sed -i '/^# XRAY_SUBSCRIPTION_PATH/c\XRAY_SUBSCRIPTION_PATH = "sub"' .env

echo "=== VERIFY ==="
grep XRAY_SUBSCRIPTION .env
echo ""

echo "=== RESTARTING MARZBAN ==="
docker compose restart 2>&1
sleep 8

echo "=== CHECK ==="
curl -s http://127.0.0.1:8000/api/admin/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=Tsikhilovk&password=Haker05dag%24' > /dev/null && echo "API_OK" || echo "API_FAIL"

ss -tlnp | grep -c ':443\|:9443\|:10443\|:11443\|:12443\|:15443\|:16443'
echo "PORTS_LISTENING"

echo "DONE"
