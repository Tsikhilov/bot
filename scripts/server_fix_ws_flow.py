import json
import requests

BASE = "https://127.0.0.1:55445/panelsmartkama"
USER = "Tsikhilovk"
PASS = "Haker05dag$"
WS_INBOUND_ID = 2

s = requests.Session()
s.verify = False
s.post(BASE + "/login", data={"username": USER, "password": PASS}, timeout=20)

objs = s.get(BASE + "/panel/api/inbounds/list", timeout=20).json().get("obj", [])
ws = next((x for x in objs if int(x.get("id", 0)) == WS_INBOUND_ID), None)
if not ws:
    raise SystemExit("WS inbound not found")

settings_raw = ws.get("settings", "{}")
settings = json.loads(settings_raw) if isinstance(settings_raw, str) else (settings_raw or {})
clients = settings.get("clients", [])
changed = 0
for c in clients:
    if c.get("flow"):
        c["flow"] = ""
        changed += 1
    if c.get("security", "") != "none":
        c["security"] = "none"

if changed:
    payload = {"id": WS_INBOUND_ID, "settings": json.dumps({"clients": clients})}
    r = s.post(BASE + f"/panel/api/inbounds/updateClient/{clients[0].get('id')}", json=payload, timeout=20)
    # updateClient works per-client id, so apply each client to ensure persist
    for c in clients:
        p = {"id": WS_INBOUND_ID, "settings": json.dumps({"clients": [c]})}
        s.post(BASE + f"/panel/api/inbounds/updateClient/{c.get('id')}", json=p, timeout=20)

print("clients", len(clients), "flow_fixed", changed)
