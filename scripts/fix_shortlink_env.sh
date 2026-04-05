#!/bin/bash
set -e

# Add SUB_EXPORT_HOST env var to shortlink service
SERVICE_FILE="/etc/systemd/system/smartkama-shortlink.service"

if grep -q "SUB_EXPORT_HOST" "$SERVICE_FILE" 2>/dev/null; then
    echo "SUB_EXPORT_HOST already set in service"
else
    # Add Environment line before ExecStart
    sed -i '/^ExecStart=/i Environment=SUB_EXPORT_HOST=sub.smartkama.ru' "$SERVICE_FILE"
    echo "Added SUB_EXPORT_HOST=sub.smartkama.ru to service"
fi

echo "=== Updated service file ==="
cat "$SERVICE_FILE"

echo ""
echo "=== Reload and restart ==="
systemctl daemon-reload
systemctl restart smartkama-shortlink.service
sleep 1
systemctl is-active smartkama-shortlink.service && echo "SERVICE: active" || echo "SERVICE: FAILED"

echo ""
echo "=== Test raw shortlink ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" --max-time 10 "http://127.0.0.1:9101/s/guard-27f5f10e?raw=1" 2>&1 || echo "TIMEOUT"
