#!/bin/bash
set -e
cd /opt/SmartKamaVPN
export MARZBAN_PANEL_URL=http://127.0.0.1:8000
export MARZBAN_USERNAME=Tsikhilovk
export MARZBAN_PASSWORD='Haker05dag$'

echo "=== GUARD ==="
.venv/bin/python scripts/server_ops_guard.py --mode all 2>&1
GUARD_RC=$?
echo "GUARD_EXIT=$GUARD_RC"

echo ""
echo "=== AUTOTUNE ==="
.venv/bin/python scripts/server_autotune_stack.py --full --guard-mode all 2>&1
AUTOTUNE_RC=$?
echo "AUTOTUNE_EXIT=$AUTOTUNE_RC"

echo ""
echo "=== CLEANUP STALE SHORTLINKS ==="
.venv/bin/python - <<'PY'
import sqlite3, datetime as dt
DB = "/opt/SmartKamaVPN/Database/smartkamavpn.db"
conn = sqlite3.connect(DB)
rows = conn.execute("SELECT token, target_url FROM short_links").fetchall()
print(f"total shortlinks: {len(rows)}")
stale = []
for token, url in rows:
    # Keep guard-* tokens (created by Guard with valid Marzban URLs)
    if token.startswith("guard-"):
        print(f"  KEEP {token} -> {url[:80]}")
        continue
    # Old 3x-ui shortlinks with short sub_ids (8 hex chars)
    import re
    m = re.search(r'/sub/([a-f0-9]{8})$', url)
    if m:
        stale.append(token)
        print(f"  STALE {token} -> {url[:80]}")
    else:
        print(f"  KEEP {token} -> {url[:80]}")

if stale:
    for t in stale:
        conn.execute("DELETE FROM short_links WHERE token=?", (t,))
        conn.execute("DELETE FROM short_links_meta WHERE token=?", (t,))
    conn.commit()
    print(f"deleted {len(stale)} stale shortlinks")
else:
    print("no stale shortlinks found")
conn.close()
PY
echo "CLEANUP_DONE"

echo ""
echo "=== FINAL STATE ==="
sqlite3 "$DB" "SELECT token, target_url FROM short_links ORDER BY rowid;" 2>/dev/null || true
echo "ALL_DONE"
