#!/bin/bash
set -e

echo "=== [1/5] Verifying 3x-ui and Hiddify are STOPPED ==="
for svc in x-ui hiddify-xray hiddify-haproxy hiddify-nginx hiddify-panel hiddify-panel-background-tasks hiddify-redis hiddify-singbox hiddify-ss-faketls hiddify-cli haproxy; do
    status=$(systemctl is-active "$svc" 2>&1 || true)
    if [ "$status" = "active" ]; then
        echo "FATAL: $svc is still active! Aborting."
        exit 1
    fi
    echo "  $svc: $status"
done
echo "All services stopped. OK"

echo ""
echo "=== [2/5] Removing 3x-ui ==="
rm -f /etc/systemd/system/x-ui.service
systemctl daemon-reload
rm -rf /usr/local/x-ui/
rm -rf /etc/x-ui/
rm -f /usr/bin/x-ui
echo "3x-ui removed: OK"

echo ""
echo "=== [3/5] Removing Hiddify Manager ==="
for svc_file in /etc/systemd/system/hiddify-*.service; do
    if [ -f "$svc_file" ]; then
        rm -f "$svc_file"
        echo "  Removed: $svc_file"
    fi
done
systemctl daemon-reload
rm -rf /opt/hiddify-manager/
rm -rf /opt/hiddify-cli/
rm -rf /opt/hiddify-panel/
for d in /var/lib/hiddify* /etc/hiddify*; do
    if [ -e "$d" ]; then
        rm -rf "$d"
        echo "  Removed: $d"
    fi
done
echo "Hiddify removed: OK"

echo ""
echo "=== [4/5] Disabling haproxy ==="
systemctl disable haproxy 2>/dev/null || true
echo "haproxy disabled: OK"

echo ""
echo "=== [5/5] Verification ==="
echo "--- Remaining services ---"
systemctl list-unit-files | grep -iE 'x-ui|hiddify' || echo "  None found (GOOD)"
echo "--- Remaining dirs ---"
ls -d /usr/local/x-ui /etc/x-ui /opt/hiddify-manager /opt/hiddify-cli /opt/hiddify-panel 2>&1 || echo "  All cleaned (GOOD)"
echo "--- Active listeners ---"
ss -tlnp | grep -E ':2097|:55445' || echo "  No old ports listening (GOOD)"
echo ""
echo "=== CLEANUP COMPLETE ==="
