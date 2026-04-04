#!/usr/bin/env python3
"""SmartKamaVPN API self-check.

Validates Hiddify API v2 connectivity by:
1) reading the default server URL from local SQLite DB,
2) creating a temporary test user,
3) confirming user fetch,
4) deleting the test user.

Exit codes:
0 - success
1 - any validation failure
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "Database" / "smartkamavpn.db"
API_PATH = "/api/v2"
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def fail(msg: str) -> int:
    print(f"SELF_CHECK_FAILED: {msg}")
    return 1


def get_default_server_url() -> str | None:
    if not DB_PATH.exists():
        return None

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT url FROM servers WHERE default_server=1 LIMIT 1")
        row = cur.fetchone()
        if row and row[0]:
            return str(row[0]).strip().rstrip("/")

        cur.execute("SELECT url FROM servers ORDER BY id ASC LIMIT 1")
        row = cur.fetchone()
        if row and row[0]:
            return str(row[0]).strip().rstrip("/")
        return None
    finally:
        conn.close()


def extract_api_key_from_url(url: str) -> str | None:
    parts = [p for p in urlparse(url).path.split("/") if p]
    for p in parts:
        if UUID_RE.fullmatch(p):
            return p
    return None


def main() -> int:
    server_url = os.getenv("SMARTKAMA_PANEL_URL", "").strip() or get_default_server_url()
    if not server_url:
        return fail("Server URL not found in env or database")

    api_key = os.getenv("SMARTKAMA_API_KEY", "").strip() or extract_api_key_from_url(server_url)
    if not api_key:
        return fail("API key UUID not found in env or panel URL")

    base = server_url.rstrip("/") + API_PATH
    endpoint = base + "/admin/user/"
    headers = {"Content-Type": "application/json", "Hiddify-API-Key": api_key}

    user_uuid = str(uuid.uuid4())
    payload = {
        "uuid": user_uuid,
        "name": f"smartkama-selfcheck-{user_uuid[:8]}",
        "usage_limit_GB": 1.0,
        "package_days": 1,
        "added_by_uuid": api_key,
        "last_reset_time": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "start_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "mode": "no_reset",
        "current_usage_GB": 0.0,
    }

    session = requests.Session()
    try:
        create = session.post(endpoint, headers=headers, data=json.dumps(payload), timeout=30)
        if create.status_code not in (200, 201):
            return fail(f"Create failed: HTTP {create.status_code} {create.text[:240]}")

        read = session.get(endpoint + user_uuid + "/", headers=headers, timeout=30)
        if read.status_code != 200:
            return fail(f"Read failed: HTTP {read.status_code} {read.text[:240]}")

        delete = session.delete(endpoint + user_uuid + "/", headers=headers, timeout=30)
        if delete.status_code not in (200, 204):
            return fail(f"Delete failed: HTTP {delete.status_code} {delete.text[:240]}")

        print("SELF_CHECK_OK")
        print(f"BASE={base}")
        return 0
    except requests.RequestException as exc:
        return fail(f"Request error: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
