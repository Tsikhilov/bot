import copy
import json
import uuid
from typing import Any, Dict, cast
import requests

BASE = "https://127.0.0.1:55445/902184284ee0d060"
USER = "admin"
PASS = "SmartKama2026!"
TARGET_PORTS = [9443, 10443, 11443, 12443]

s = requests.Session()
s.verify = False
s.post(BASE + "/login", data={"username": USER, "password": PASS}, timeout=15)

res = s.get(BASE + "/panel/api/inbounds/list", timeout=15).json()
objs = res.get("obj", [])

base_inbound = None
for o in objs:
    if int(o.get("id", 0)) == 1:
        base_inbound = o
        break
if not base_inbound:
    raise SystemExit("Base inbound #1 not found")

existing_ports = {int(o.get("port", 0)): o for o in objs}

for port in TARGET_PORTS:
    if port in existing_ports:
        print(f"skip port={port} exists id={existing_ports[port].get('id')}")
        continue

    obj = copy.deepcopy(base_inbound)
    obj.pop("id", None)
    obj["port"] = port
    obj["remark"] = f"VLESS-Reality-{port}"
    obj["tag"] = f"inbound-{port}"

    # 3x-ui не допускает одинаковые client.email между inbound-ами.
    settings_raw = obj.get("settings", "{}")
    settings = json.loads(settings_raw) if isinstance(settings_raw, str) else dict(settings_raw or {})
    clients = settings.get("clients", [])
    for idx, client in enumerate(clients):
        base_email = (client.get("email") or f"default{idx}@smartkama").split("@", 1)[0]
        client["email"] = f"{base_email}-{port}@smartkama"
        client["id"] = str(uuid.uuid4())
        client["subId"] = uuid.uuid4().hex[:8]
    settings["clients"] = clients
    obj["settings"] = json.dumps(settings, ensure_ascii=False)

    resp = s.post(BASE + "/panel/api/inbounds/add", json=obj, timeout=20)
    print(f"add port={port} -> status={resp.status_code} body={resp.text}")

# print final mapping
res2 = s.get(BASE + "/panel/api/inbounds/list", timeout=15).json()
print("=== FINAL ===")
for o in res2.get("obj", []):
    ss = o.get("streamSettings")
    if isinstance(ss, str):
        try:
            ss = json.loads(ss)
        except Exception:
            ss = {}
    if not isinstance(ss, dict):
        ss = {}
    ss_dict = cast(Dict[str, Any], ss)
    sec = str(ss_dict.get("security") or "")
    net = str(ss_dict.get("network") or "")
    print(f"id={o.get('id')} port={o.get('port')} remark={o.get('remark')} sec={sec} net={net}")
