import json
import sqlite3
import requests

BASE = "https://127.0.0.1:55445/panelsmartkama"
USER = "Tsikhilovk"
PASS = "Haker05dag$"
DB = "/opt/SmartKamaVPN/Database/smartkamavpn.db"

s = requests.Session()
s.verify = False
s.post(BASE + "/login", data={"username": USER, "password": PASS}, timeout=20)
objs = s.get(BASE + "/panel/api/inbounds/list", timeout=20).json().get("obj", [])
by_id = {int(x.get("id", 0)): x for x in objs}

# 1) rename inbounds for expected display
remark_map = {
    2: "01-NL-Direct-WS",
    3: "02-NL-Bypass-1",
    4: "03-NL-Bypass-2",
    5: "04-NL-Bypass-3",
    6: "05-NL-Bypass-4",
}
for iid, remark in remark_map.items():
    o = by_id.get(iid)
    if not o:
        continue
    if o.get("remark") == remark:
        continue
    o2 = dict(o)
    o2["remark"] = remark
    r = s.post(BASE + f"/panel/api/inbounds/update/{iid}", json=o2, timeout=20).json()
    print("rename", iid, r.get("success"), r.get("msg"))

# 2) remove users from inbound #1 if same UUID already exists in inbound #2
in1 = by_id.get(1)
in2 = by_id.get(2)
if in1 and in2:
    st1 = json.loads(in1.get("settings", "{}")) if isinstance(in1.get("settings"), str) else (in1.get("settings") or {})
    st2 = json.loads(in2.get("settings", "{}")) if isinstance(in2.get("settings"), str) else (in2.get("settings") or {})
    ids2 = {c.get("id") for c in st2.get("clients", [])}
    removed = 0
    for c in st1.get("clients", []):
        uid = c.get("id")
        if uid in ids2:
            rr = s.post(BASE + f"/panel/api/inbounds/1/delClient/{uid}", timeout=20).json()
            if rr.get("success"):
                removed += 1
    print("removed_from_1", removed)

# 3) set bot order to skip inbound #1 in subscriptions
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("INSERT OR REPLACE INTO str_config(key,value) VALUES(?,?)", ("threexui_inbound_id", "2"))
cur.execute("INSERT OR REPLACE INTO str_config(key,value) VALUES(?,?)", ("threexui_inbound_ids", "2,3,4,5,6"))
conn.commit()
conn.close()
print("db_order_set", "2,3,4,5,6")
