#!/bin/bash
set -e
echo "=== SHORTLINK SERVICE ==="
cat /etc/systemd/system/smartkama-shortlink.service
echo ""
echo "=== ENV VARS IN SERVICE ==="
grep -i "Environment" /etc/systemd/system/smartkama-shortlink.service 2>/dev/null || echo "(none)"
echo ""
echo "=== TEST PROXY_SUB VIA LOCALHOST ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" --max-time 5 "http://127.0.0.1:9101/s/guard-27f5f10e?raw=1" 2>&1 || echo "TIMEOUT"
echo ""
echo "=== VERBOSE TEST ==="
curl -v --max-time 5 "http://127.0.0.1:9101/s/guard-27f5f10e?raw=1" 2>&1 | head -40
echo ""
echo "=== XUI_DB_PATH CHECK ==="
ls -la /etc/x-ui/x-ui.db 2>&1 || echo "x-ui.db NOT FOUND"
echo "=== EXPORT_HOST env ==="
grep SUB_EXPORT_HOST /etc/systemd/system/smartkama-shortlink.service 2>/dev/null || echo "(not set in service)"
