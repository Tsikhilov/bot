import json
import requests

BASE = "https://127.0.0.1:55445/panelsmartkama"
USER = "Tsikhilovk"
PASS = "Haker05dag$"
TARGET_UUID = "ec0a9260-4ed2-4e09-957d-c2f05843c6d2"

s = requests.Session()
s.verify = False
s.post(BASE + "/login", data={"username": USER, "password": PASS}, timeout=20)
objs = s.get(BASE + "/panel/api/inbounds/list", timeout=20).json().get("obj", [])

for o in objs:
    iid = int(o.get("id", 0))
    settings = o.get("settings", "{}")
    settings = json.loads(settings) if isinstance(settings, str) else (settings or {})
    clients = settings.get("clients", [])
    c = next((x for x in clients if x.get("id") == TARGET_UUID), None)
    if not c:
        continue
    ss = o.get("streamSettings", "{}")
    ss = json.loads(ss) if isinstance(ss, str) else (ss or {})
    print(
        "inbound", iid,
        "port", o.get("port"),
        "sec", ss.get("security"),
        "net", ss.get("network"),
        "flow", c.get("flow"),
        "email", c.get("email"),
    )
