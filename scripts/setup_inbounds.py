#!/usr/bin/env python3
"""
SmartKamaVPN — создание VLESS+Reality и VLESS+WS+TLS inbound-ов в 3x-ui 2.8
"""
import json
import subprocess
import sys
import urllib.request
import urllib.parse
import ssl
import http.cookiejar

BASE = "https://127.0.0.1:55445/902184284ee0d060"
USER = "admin"
PASS = "SmartKama2026!"
DOMAIN = "sub.smartkama.ru"
CERT = "/etc/letsencrypt/live/sub.smartkama.ru/fullchain.pem"
KEY  = "/etc/letsencrypt/live/sub.smartkama.ru/privkey.pem"

REALITY_UUID  = "f9bb989a-891a-479d-8cb7-02a3e273e9a3"
REALITY_PRIV  = "mLYMWFI-tPEhB612x4UTBK9Ja89rSpuUM6ZeFXDxTWc"
REALITY_PUB   = "BeBt_TKfIg0v4jo2Pk4ZcMCX7jaKADBzEdzhJKd7-3A"
REALITY_SHORT = "2ecaea3b"

WS_UUID = "63166c7b-236c-4665-83d0-84fc29c02bf0"
WS_PATH = "/fe790875b1d6"

# --- HTTP клиент с cookie поддержкой ---
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=ctx),
    urllib.request.HTTPCookieProcessor(jar),
)

def api(method, path, data=None):
    url = f"{BASE}{path}"
    if data is not None:
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"},
                                     method=method)
    else:
        req = urllib.request.Request(url, method=method)
    try:
        with opener.open(req) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- Логин ---
print("[1] Логин...")
login_data = urllib.parse.urlencode({"username": USER, "password": PASS}).encode()
try:
    resp = opener.open(urllib.request.Request(
        f"{BASE}/login", data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    ))
    result = json.loads(resp.read())
    print(f"   {result}")
except Exception as e:
    print(f"   ERROR: {e}"); sys.exit(1)

if not result.get("success"):
    print("Логин не удался"); sys.exit(1)

# --- VLESS+Reality ---
print("[2] Создание VLESS+Reality (порт 8443)...")
reality_inbound = {
    "remark": "VLESS-Reality",
    "port": 8443,
    "protocol": "vless",
    "enable": True,
    "expiryTime": 0,
    "listen": "",
    "settings": json.dumps({
        "clients": [{
            "id": REALITY_UUID,
            "flow": "xtls-rprx-vision",
            "email": "default@smartkama",
            "limitIp": 0,
            "totalGB": 0,
            "expiryTime": 0,
            "enable": True
        }],
        "decryption": "none"
    }),
    "streamSettings": json.dumps({
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
            "show": False,
            "dest": "www.microsoft.com:443",
            "xver": 0,
            "serverNames": ["www.microsoft.com"],
            "privateKey": REALITY_PRIV,
            "shortIds": [REALITY_SHORT]
        }
    }),
    "sniffing": json.dumps({
        "enabled": True,
        "destOverride": ["http", "tls", "quic"]
    })
}

r = api("POST", "/panel/api/inbounds/add", reality_inbound)
print(f"   {r}")

# --- VLESS+WS+TLS ---
print("[3] Создание VLESS+WS+TLS (порт 443)...")
ws_inbound = {
    "remark": "VLESS-WS-TLS",
    "port": 443,
    "protocol": "vless",
    "enable": True,
    "expiryTime": 0,
    "listen": "",
    "settings": json.dumps({
        "clients": [{
            "id": WS_UUID,
            "flow": "",
            "email": "default-ws@smartkama",
            "limitIp": 0,
            "totalGB": 0,
            "expiryTime": 0,
            "enable": True
        }],
        "decryption": "none"
    }),
    "streamSettings": json.dumps({
        "network": "ws",
        "security": "tls",
        "tlsSettings": {
            "serverName": DOMAIN,
            "certificates": [{
                "certificateFile": CERT,
                "keyFile": KEY
            }]
        },
        "wsSettings": {
            "path": WS_PATH
        }
    }),
    "sniffing": json.dumps({
        "enabled": True,
        "destOverride": ["http", "tls", "quic"]
    })
}

r = api("POST", "/panel/api/inbounds/add", ws_inbound)
print(f"   {r}")

# --- Список inbound-ов ---
print("[4] Список inbound-ов:")
r = api("GET", "/panel/api/inbounds/list")
objs = r.get("obj", [])
if not objs:
    print("   Пусто!")
for o in objs:
    print(f"   ID={o['id']} remark={o['remark']} port={o['port']} proto={o['protocol']}")

print("\nГотово!")
