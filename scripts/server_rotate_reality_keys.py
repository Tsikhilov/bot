#!/usr/bin/env python3
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
from datetime import datetime

XUI_DB_PATH = "/etc/x-ui/x-ui.db"
BOT_DB_PATH = "/opt/SmartKamaVPN/Database/smartkamavpn.db"
XRAY_CANDIDATES = [
    "/usr/local/x-ui/bin/xray-linux-amd64.real",
    "/usr/local/x-ui/bin/xray-linux-amd64",
    "/usr/local/bin/xray",
    "/usr/bin/xray",
]


def _pick_xray_binary() -> str:
    for candidate in XRAY_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    raise RuntimeError("xray binary not found")


def _generate_keypair(binary: str) -> tuple[str, str]:
    output = subprocess.check_output([binary, "x25519"], text=True, stderr=subprocess.STDOUT)
    private_match = re.search(r"Private\s*key:\s*(\S+)", output, re.IGNORECASE)
    public_match = re.search(r"Public\s*key:\s*(\S+)", output, re.IGNORECASE)
    if not public_match:
        public_match = re.search(r"Password:\s*(\S+)", output, re.IGNORECASE)
    if not private_match or not public_match:
        raise RuntimeError(f"unable to parse x25519 output: {output}")
    return private_match.group(1), public_match.group(1)


def _new_short_id(used_ids: set[str]) -> str:
    while True:
        short_id = secrets.token_hex(4)
        if short_id not in used_ids:
            used_ids.add(short_id)
            return short_id


def _update_bot_defaults(public_key: str) -> None:
    conn = sqlite3.connect(BOT_DB_PATH)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO str_config(key,value) VALUES(?,?)",
            ("threexui_reality_public_key", public_key),
        )
        conn.execute(
            "INSERT OR REPLACE INTO str_config(key,value) VALUES(?,?)",
            ("threexui_reality_fingerprint", "chrome"),
        )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    if not os.path.exists(XUI_DB_PATH):
        raise SystemExit(f"missing x-ui db: {XUI_DB_PATH}")

    backup_path = f"/root/x-ui.db.backup.{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(XUI_DB_PATH, backup_path)

    xray_binary = _pick_xray_binary()
    conn = sqlite3.connect(XUI_DB_PATH)
    used_ids: set[str] = set()
    results: list[tuple[int, int, str, str, str]] = []
    first_public_key = None

    try:
        rows = conn.execute("SELECT id, port, remark, stream_settings FROM inbounds ORDER BY id").fetchall()
        for inbound_id, port, remark, raw_stream in rows:
            try:
                stream = json.loads(raw_stream or "{}")
            except Exception:
                continue
            if str(stream.get("security") or "").lower() != "reality":
                continue

            private_key, public_key = _generate_keypair(xray_binary)
            short_id = _new_short_id(used_ids)
            reality = dict(stream.get("realitySettings") or {})
            reality["privateKey"] = private_key
            reality["publicKey"] = public_key
            reality["shortIds"] = [short_id]
            reality["fingerprint"] = "chrome"
            stream["realitySettings"] = reality

            conn.execute(
                "UPDATE inbounds SET stream_settings=? WHERE id=?",
                (json.dumps(stream, ensure_ascii=False, separators=(",", ":")), inbound_id),
            )
            if first_public_key is None:
                first_public_key = public_key
            results.append((int(inbound_id), int(port), str(remark or ""), short_id, public_key))

        conn.commit()
    finally:
        conn.close()

    if first_public_key:
        _update_bot_defaults(first_public_key)

    print(f"backup={backup_path}")
    for inbound_id, port, remark, short_id, public_key in results:
        print(
            f"updated inbound_id={inbound_id} port={port} short_id={short_id} public_key={public_key} remark={remark}"
        )


if __name__ == "__main__":
    main()