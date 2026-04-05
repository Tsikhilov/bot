import base64
import json
import requests

BASE = "https://127.0.0.1:55445/panelsmartkama"
USER = "Tsikhilovk"
PASS = "Haker05dag$"
SUB = "ec0a9260"


def get_8443_line() -> str:
    r = requests.get(f"https://sub.smartkama.ru:2096/sub/{SUB}", timeout=20)
    text = (r.text or "").strip()
    decoded = base64.b64decode(text + "===").decode("utf-8", errors="ignore")
    for line in decoded.splitlines():
        if ":8443?" in line:
            return line
    return ""


s = requests.Session()
s.verify = False
s.post(BASE + "/login", data={"username": USER, "password": PASS}, timeout=20)

before = get_8443_line()
print("before", before)

objs = s.get(BASE + "/panel/api/inbounds/list", timeout=20).json().get("obj", [])
obj = next((x for x in objs if int(x.get("id", 0)) == 1), None)
if not obj:
    raise SystemExit("inbound #1 not found")

ss = obj.get("streamSettings", "{}")
ss = json.loads(ss) if isinstance(ss, str) else (ss or {})
ss.setdefault("realitySettings", {})["show"] = True
obj["streamSettings"] = json.dumps(ss, separators=(",", ":"))
upd = s.post(BASE + "/panel/api/inbounds/update/1", json=obj, timeout=20).json()
print("update", upd.get("success"), upd.get("msg"))

after = get_8443_line()
print("after", after)
