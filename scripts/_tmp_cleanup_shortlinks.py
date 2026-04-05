#!/usr/bin/env python3
"""One-shot: delete stale 3x-ui shortlinks (8-hex sub_ids), keep Marzban ones."""
import re, sqlite3

DB = "/opt/SmartKamaVPN/Database/smartkamavpn.db"
conn = sqlite3.connect(DB)
rows = conn.execute("SELECT token, target_url FROM short_links").fetchall()
print(f"=== all shortlinks: {len(rows)} ===")
for tok, url in rows:
    print(f"  {tok} -> {url}")

stale = [(tok, url) for tok, url in rows if re.search(r"/sub/[0-9a-f]{8}$", url)]
print(f"\n=== stale (old 3x-ui 8-hex): {len(stale)} ===")
for tok, url in stale:
    print(f"  DELETE {tok}")
    conn.execute("DELETE FROM short_links WHERE token=?", (tok,))
conn.commit()

remaining = conn.execute("SELECT token, target_url FROM short_links").fetchall()
print(f"\n=== remaining: {len(remaining)} ===")
for tok, url in remaining:
    print(f"  {tok} -> {url}")
conn.close()
