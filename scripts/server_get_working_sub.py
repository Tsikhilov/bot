import base64
import requests
from Utils import api


def check(sub_id: str):
    url = f"https://sub.smartkama.ru:2096/sub/{sub_id}"
    try:
        r = requests.get(url, timeout=20)
        txt = (r.text or "").strip()
        lines = 0
        if r.status_code == 200:
            try:
                dec = base64.b64decode(txt + "===").decode("utf-8", errors="ignore")
                lines = len([x for x in dec.splitlines() if x.strip()])
            except Exception:
                lines = len([x for x in txt.splitlines() if x.strip()])
        return r.status_code, lines
    except Exception:
        return -1, 0


old_sub = "ec0a9260"
st, cnt = check(old_sub)
print("old", old_sub, st, cnt)

if st != 200 or cnt == 0:
    uid = api.insert(name="bundle_live_user", usage_limit_GB=200, package_days=30)
    user = api.find(uuid=uid)
    sub_id = (user or {}).get("sub_id") or str(uid)[:8]
    st2, cnt2 = check(sub_id)
    print("new_uuid", uid)
    print("new_sub", sub_id, st2, cnt2)
    print("new_url", f"https://sub.smartkama.ru:2096/sub/{sub_id}")
else:
    print("use_url", f"https://sub.smartkama.ru:2096/sub/{old_sub}")
