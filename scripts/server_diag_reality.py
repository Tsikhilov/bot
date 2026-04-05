#!/usr/bin/env python3
"""Check Reality keys and subscription pbk consistency."""
import base64
import json
import sqlite3
from urllib.parse import parse_qs, urlsplit

import requests

BASE = "https://127.0.0.1:55445/panelsmartkama"
s = requests.Session()
s.verify = False
s.post(BASE + "/login", data={"username": "Tsikhilovk", "password": "Haker05dag$"}, timeout=20)
objs = s.get(BASE + "/panel/api/inbounds/list", timeout=20).json().get("obj", [])

for o in objs:
    iid = o.get("id")
    ss = o.get("streamSettings", "{}")
    if isinstance(ss, str):
        try:
            ss = json.loads(ss)
        except Exception:
            ss = {}
    if ss.get("security") != "reality":
        continue
    r = ss.get("realitySettings", {})
    pk = r.get("privateKey", "")
    sids = r.get("shortIds", [])
    snames = r.get("serverNames", [])
    show = r.get("show")
    print(f"id={iid} pk_len={len(pk)} pk_start={pk[:15]}... sids={sids} snames={snames} show={show}")

# DB pbk
conn = sqlite3.connect("/opt/SmartKamaVPN/Database/smartkamavpn.db")
row = conn.execute("SELECT value FROM str_config WHERE key='threexui_reality_public_key'").fetchone()
db_pbk = row[0] if row else "NONE"
print(f"\ndb_pbk={db_pbk}")

# Sub reality lines
r2 = requests.get("https://sub.smartkama.ru:2096/sub/ec0a9260", timeout=20)
text = base64.b64decode((r2.text or "").strip() + "===").decode("utf-8", errors="ignore")
for ln in text.splitlines():
    ln = ln.strip()
    if "security=reality" in ln:
        q = parse_qs(urlsplit(ln.split("#", 1)[0]).query)
        pbk = q.get("pbk", [""])[0]
        fp = q.get("fp", [""])[0]
        sid = q.get("sid", [""])[0]
        flow = q.get("flow", [""])[0]
        enc = q.get("encryption", [""])[0]
        sni = q.get("sni", [""])[0]
        frag = ""
        if "#" in ln:
            frag = ln.split("#", 1)[1][:60]
        print(f"sub_line pbk={pbk[:20]}... fp={fp} sid={sid} flow={flow} enc={enc} sni={sni} tag={frag}")

# Check if pbk matches any inbound
print(f"\npbk_match = {db_pbk == pk}")  # pk from last reality inbound
conn.close()

# Test external connectivity
print("\n=== external port test (from server itself) ===")
import socket, ssl
for port, label in [(443, "WS"), (15443, "gRPC"), (16443, "Trojan"), (9443, "Reality1"), (10443, "Reality2")]:
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection(("72.56.100.45", port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname="sub.smartkama.ru") as ssock:
                print(f"  {port} ({label}): TLS OK version={ssock.version()}")
    except Exception as e:
        print(f"  {port} ({label}): FAIL {e}")
