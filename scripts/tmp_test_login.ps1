. .\scripts\prod_tools.ps1
$cmd = @'
python3 - <<'"'"'PY'"'"'
import re
import requests

panel = "https://bot.smartkama.ru/XG2KXE1cOyMGJVEW"
uuid = "7d9eac4a-b716-460b-b521-a6d5db6a790d"
next_path = "/XG2KXE1cOyMGJVEW/all.txt"
login_url = f"{panel}/?force=1&next={next_path}&user={uuid}"

s = requests.Session()
r = s.get(login_url, timeout=20)
m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
csrf = m.group(1) if m else ""
print("csrf_found", bool(csrf))

for pwd in ["", "123456", uuid]:
    form = {
        "csrf_token": csrf,
        "secret_textbox": uuid,
        "password_textbox": pwd,
        "submit": "login",
    }
    r2 = s.post(login_url, data=form, timeout=20, allow_redirects=True)
    print("pwd", repr(pwd), "status", r2.status_code, "url", r2.url)
    t = r2.text.lower()
    for needle in ["invalid", "password", "uuid", "error", "alert", "danger", "csrf"]:
        if needle in t:
            print("contains", needle)
    m2 = re.findall(r"<div[^>]+alert[^>]*>(.*?)</div>", r2.text, flags=re.I|re.S)
    if m2:
        print("alerts:", [x[:120] for x in m2][:2])

r3 = s.get(f"{panel}/{uuid}/all.txt", timeout=20, allow_redirects=True)
print("all", r3.status_code, r3.url, r3.headers.get("content-type"), len(r3.text))
print(r3.text[:180])
PY
'@
Invoke-ProdSSH $cmd
