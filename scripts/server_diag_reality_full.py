#!/usr/bin/env python3
"""Full Reality inbound diagnostic."""
import json, requests, subprocess, base64

BASE = "https://127.0.0.1:55445/panelsmartkama"
s = requests.Session()
s.verify = False
s.post(BASE + "/login", data={"username": "Tsikhilovk", "password": "Haker05dag$"}, timeout=20)
objs = s.get(BASE + "/panel/api/inbounds/list", timeout=20).json().get("obj", [])

for o in sorted(objs, key=lambda x: x.get("id", 0)):
    iid = o.get("id")
    port = o.get("port")
    ss_raw = o.get("streamSettings", "{}")
    if isinstance(ss_raw, str):
        try:
            ss = json.loads(ss_raw)
        except Exception:
            ss = {}
    else:
        ss = ss_raw

    sec = ss.get("security", "")
    if sec != "reality":
        continue

    r = ss.get("realitySettings", {})
    settings_raw = o.get("settings", "{}")
    if isinstance(settings_raw, str):
        try:
            settings = json.loads(settings_raw)
        except Exception:
            settings = {}
    else:
        settings = settings_raw

    clients = settings.get("clients", [])
    print(f"=== inbound {iid} port={port} ===")
    print(f"  protocol={o.get('protocol')}")
    print(f"  network={ss.get('network')}")
    print(f"  show={r.get('show')}")
    print(f"  dest={r.get('dest')}")
    print(f"  serverNames={r.get('serverNames')}")
    print(f"  shortIds={r.get('shortIds')}")
    pk = r.get("privateKey", "")
    print(f"  pk_len={len(pk)} pk_start={pk[:10]}...")
    print(f"  spiderX={r.get('spiderX', '')}")
    print(f"  clients_count={len(clients)}")
    if clients:
        c = clients[0]
        print(f"  first_client: email={c.get('email')} flow={c.get('flow')} id={c.get('id', '')[:8]}...")

# Also check xray error log
print()
print("=== xray error log (last 20 lines) ===")
try:
    out = subprocess.run(
        ["find", "/var/log", "/usr/local/x-ui", "/tmp", "-name", "*.log", "-newer", "/proc/1/stat"],
        capture_output=True, text=True, timeout=5
    )
    print("log files:", out.stdout.strip()[:300])
except Exception:
    pass

# Check xray access/error log path in x-ui settings
try:
    out = subprocess.run(
        ["cat", "/usr/local/x-ui/bin/config.json"],
        capture_output=True, text=True, timeout=5
    )
    cfg = json.loads(out.stdout)
    log = cfg.get("log", {})
    print(f"  xray log config: access={log.get('access','')} error={log.get('error','')}")
except Exception as e:
    print(f"  xray config read error: {e}")

# Check the xray generated config from x-ui
print()
print("=== x-ui xray config template ===")
try:
    r2 = s.get(BASE + "/panel/setting/all", timeout=20)
    data = r2.json().get("obj", {})
    xray_tpl = data.get("xrayTemplateConfig", "")
    if xray_tpl:
        tpl = json.loads(xray_tpl)
        log_section = tpl.get("log", {})
        print(f"  template log: {log_section}")
except Exception as e:
    print(f"  error: {e}")
