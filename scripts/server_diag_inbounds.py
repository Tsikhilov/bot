#!/usr/bin/env python3
"""Diagnose all 3x-ui inbounds: enable status, ports, certs, traffic, xray listen."""
import json
import subprocess
import requests

BASE = "https://127.0.0.1:55445/panelsmartkama"
USER = "Tsikhilovk"
PASS = "Haker05dag$"

s = requests.Session()
s.verify = False
login = s.post(BASE + "/login", data={"username": USER, "password": PASS}, timeout=20).json()
print("login", login.get("success"))

objs = s.get(BASE + "/panel/api/inbounds/list", timeout=20).json().get("obj", [])

for o in sorted(objs, key=lambda x: x.get("id", 0)):
    iid = o.get("id")
    port = o.get("port")
    proto = o.get("protocol", "")
    up = o.get("up", 0)
    down = o.get("down", 0)
    enable = o.get("enable")
    remark = o.get("remark", "")
    total = o.get("total", 0)
    ss_raw = o.get("streamSettings", "{}")
    ss = json.loads(ss_raw) if isinstance(ss_raw, str) else ss_raw

    sec = ss.get("security", "")
    net = ss.get("network", "")

    tls = ss.get("tlsSettings") or {}
    certs = tls.get("certificates") or []
    cert_files = [(c.get("certificateFile", "")[-50:], c.get("keyFile", "")[-50:]) for c in certs] if certs else "none"

    reality = ss.get("realitySettings") or {}
    sni_list = reality.get("serverNames", [])
    dest = reality.get("dest", "")

    settings = o.get("settings", "{}")
    if isinstance(settings, str):
        try:
            settings = json.loads(settings)
        except Exception:
            settings = {}
    clients = settings.get("clients", [])

    print(f"\n--- inbound {iid} ---")
    print(f"  port={port} proto={proto} sec={sec} net={net} enable={enable}")
    print(f"  remark={remark}")
    print(f"  clients={len(clients)} up={up} down={down} total={total}")
    print(f"  certs={cert_files}")
    if reality:
        print(f"  reality_sni={sni_list} dest={dest}")
    if proto == "trojan":
        # Show first client password
        if clients:
            print(f"  trojan_password_sample={str(clients[0].get('password',''))[:20]}...")

# Check which ports are actually listening
print("\n=== listening ports ===")
try:
    out = subprocess.check_output(
        "ss -ltnp | grep -E ':443 |:9443 |:10443 |:11443 |:12443 |:15443 |:16443 |:55445 '",
        shell=True, text=True, timeout=10
    )
    print(out)
except Exception as e:
    print("ss error:", e)

# Check xray process
print("=== xray process ===")
try:
    out = subprocess.check_output("ps aux | grep xray | grep -v grep", shell=True, text=True, timeout=10)
    print(out)
except Exception:
    print("xray not found")

# Check x-ui status
print("=== x-ui status ===")
try:
    out = subprocess.check_output("systemctl is-active x-ui", shell=True, text=True, timeout=10).strip()
    print(out)
except Exception as e:
    print(e)

# Try connecting to each port
print("\n=== port connectivity ===")
import socket, ssl
for port in [443, 15443, 16443, 9443, 10443, 11443, 12443]:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=3) as sock:
            print(f"  port {port}: OPEN")
    except Exception as e:
        print(f"  port {port}: CLOSED ({e})")
