import base64
import json
import requests

BASE = "https://127.0.0.1:55445/panelsmartkama"
USER = "Tsikhilovk"
PASS = "Haker05dag$"
SUB = "ec0a9260"
PBK = "BeBt_TKfIg0v4jo2Pk4ZcMCX7jaKADBzEdzhJKd7-3A"


def get_line():
    r = requests.get(f"https://sub.smartkama.ru:2096/sub/{SUB}", timeout=20)
    dec = base64.b64decode((r.text or "").strip() + "===").decode("utf-8", errors="ignore")
    for line in dec.splitlines():
        if ":8443?" in line:
            return line
    return ""


s = requests.Session()
s.verify = False
s.post(BASE + "/login", data={"username": USER, "password": PASS}, timeout=20)

print("before", get_line())

objs = s.get(BASE + "/panel/api/inbounds/list", timeout=20).json().get("obj", [])
obj = next((x for x in objs if int(x.get("id", 0)) == 1), None)
ss = obj.get("streamSettings", "{}")
ss = json.loads(ss) if isinstance(ss, str) else (ss or {})
rs = ss.setdefault("realitySettings", {})
rs["password"] = PBK
rs["publicKey"] = PBK
ss["realitySettings"] = rs
obj["streamSettings"] = json.dumps(ss, separators=(",", ":"))
upd = s.post(BASE + "/panel/api/inbounds/update/1", json=obj, timeout=20).json()
print("update", upd.get("success"), upd.get("msg"))

print("after", get_line())
