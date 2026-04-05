import base64
import json
from urllib.parse import unquote

import requests

BASE = "http://127.0.0.1:9101/s/copilot-test"
URL = BASE + "?raw=1"


def maybe_decode_base64(text: str) -> str:
    payload = (text or "").strip()
    if not payload:
        return ""
    if "vless://" in payload or "vmess://" in payload or "trojan://" in payload:
        return payload
    try:
        padded = payload + "=" * ((4 - len(payload) % 4) % 4)
        decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
        if "vless://" in decoded or "vmess://" in decoded or "trojan://" in decoded:
            return decoded
    except Exception:
        pass
    return payload


def test_raw(label, url):
    print(f"\n=== {label} ===")
    r = requests.get(url, timeout=20)
    print("status", r.status_code)
    text = maybe_decode_base64(r.text or "")
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    print("count", len(lines))

    for idx, line in enumerate(lines, 1):
        title = ""
        if "#" in line:
            title = unquote(line.split("#", 1)[1])
        if "security=reality" in line:
            print(
                f"line {idx} reality_flags pbk={('pbk=' in line)} fp={('fp=' in line)} sid={('sid=' in line)} flow={('flow=xtls-rprx-vision' in line)} title={title}"
            )
        elif line.startswith("trojan://"):
            print(f"line {idx} trojan_title={title}")
        elif "type=grpc" in line:
            print(f"line {idx} grpc_title={title}")
        else:
            print(f"line {idx} direct_title={title}")


def test_singbox(label, url):
    print(f"\n=== {label} ===")
    r = requests.get(url, timeout=20)
    print("status", r.status_code, "content-type", r.headers.get("Content-Type"))
    try:
        cfg = r.json()
        outbounds = cfg.get("outbounds", [])
        proxy_tags = [o["tag"] for o in outbounds if o.get("type") not in ("direct", "block", "dns", "selector", "urltest")]
        auto_ob = next((o for o in outbounds if o.get("tag") == "auto"), None)
        print("proxy_outbounds", len(proxy_tags), proxy_tags)
        if auto_ob:
            print("auto_order", auto_ob.get("outbounds"))
        print("route_rules", len(cfg.get("route", {}).get("rules", [])))
        print("rule_sets", len(cfg.get("route", {}).get("rule_set", [])))
    except Exception as e:
        print("json_error", e)


# Default order
test_raw("raw default", URL)

# Operator order: МТС (reality first)
test_raw("raw op=mts", BASE + "?raw=1&op=mts")

# Operator order: Теле2 (ws first)
test_raw("raw op=tele2", BASE + "?raw=1&op=tele2")

# sing-box default
test_singbox("singbox default", BASE + "?format=singbox")

# sing-box МТС
test_singbox("singbox op=mts", BASE + "?format=singbox&op=mts")

# App client UA
print("\n=== app-ua ===")
r = requests.get(BASE, headers={"User-Agent": "Hiddify/1.0"}, timeout=20)
print("status", r.status_code, "ct", r.headers.get("Content-Type"))
text = maybe_decode_base64(r.text or "")
lines = [x.strip() for x in text.splitlines() if x.strip()]
print("count", len(lines))
