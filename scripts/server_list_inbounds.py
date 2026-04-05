import json
import requests

BASE = "https://127.0.0.1:55445/902184284ee0d060"
USER = "admin"
PASS = "SmartKama2026!"

s = requests.Session()
s.verify = False
s.post(BASE + "/login", data={"username": USER, "password": PASS}, timeout=15)
res = s.get(BASE + "/panel/api/inbounds/list", timeout=15).json()
for o in res.get("obj", []):
    ss = o.get("streamSettings")
    if isinstance(ss, str):
        try:
            ss = json.loads(ss)
        except Exception:
            ss = {}
    sec = ss.get("security")
    net = ss.get("network")
    print(f"id={o.get('id')} port={o.get('port')} remark={o.get('remark')} sec={sec} net={net}")
