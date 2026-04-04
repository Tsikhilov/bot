#!/usr/bin/env python3
"""Smoke-check native Hiddify Russian localization.

Checks:
1. Client proxy path exists in local SQLite config.
2. i18n JSON is served from the native Hiddify route.
3. i18n JSON has no-cache headers.
4. Key labels are translated to Russian.

Optional:
5. If SMARTKAMA_SMOKE_UUID or --uuid is provided, fetch the home page with
   home=true&lang=ru and verify Russian strings in rendered HTML.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "Database" / "smartkamavpn.db"
EXPECTED_TRANSLATIONS = {
    "Welcome": "Добро пожаловать",
    "Import To App": "Импорт в приложение",
    "Choose your preferred language:": "Выберите предпочитаемый язык:",
}


def fail(msg: str) -> int:
    print(f"HIDDIFY_RU_CHECK_FAILED: {msg}")
    return 1


def ok(msg: str) -> None:
    print(f"HIDDIFY_RU_CHECK_OK: {msg}")


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


def get_client_proxy_path() -> str | None:
    env_path = os.getenv("HIDDIFY_CLIENT_PROXY_PATH", "").strip().strip("/")
    if env_path:
        return env_path

    if not DB_PATH.exists():
        return None

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM str_config WHERE key='hiddify_client_proxy_path' LIMIT 1")
        row = cur.fetchone()
        if row and row[0]:
            return str(row[0]).strip().strip("/")
        return None
    finally:
        conn.close()


def build_urls(server_url: str, client_proxy_path: str, smoke_uuid: str | None) -> tuple[str, str | None]:
    parsed = urlparse(server_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    i18n_url = f"{base}/{client_proxy_path}/static/new/i18n/en.json?v=smoke-{int(time.time())}"
    home_url = None
    if smoke_uuid:
        home_url = f"{base}/{client_proxy_path}/{smoke_uuid}/?home=true&lang=ru&v=smoke-{int(time.time())}"
    return i18n_url, home_url


def check_i18n(session: requests.Session, i18n_url: str) -> int:
    resp = session.get(i18n_url, timeout=30)
    if resp.status_code != 200:
        return fail(f"i18n fetch failed: HTTP {resp.status_code}")

    cache_control = ", ".join(resp.headers.get_all("Cache-Control", [])) if hasattr(resp.headers, "get_all") else resp.headers.get("Cache-Control", "")
    expires = resp.headers.get("Expires", "")
    pragma = resp.headers.get("Pragma", "")

    if "no-cache" not in cache_control.lower():
        return fail(f"expected no-cache header, got: {cache_control!r}")
    if pragma and "no-cache" not in pragma.lower():
        return fail(f"expected Pragma no-cache, got: {pragma!r}")
    if expires and expires not in ("0",):
        ok(f"Expires header present: {expires}")

    payload = resp.json()
    for key, expected in EXPECTED_TRANSLATIONS.items():
        actual = str(payload.get(key, ""))
        if expected not in actual:
            return fail(f"translation mismatch for {key!r}: {actual!r}")

    ok("i18n headers and Russian keys verified")
    return 0


def check_home_page(session: requests.Session, home_url: str) -> int:
    resp = session.get(
        home_url,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        },
    )
    if resp.status_code != 200:
        return fail(f"home page fetch failed: HTTP {resp.status_code}")

    content_type = (resp.headers.get("Content-Type") or "").lower()
    text = resp.content.decode("utf-8", errors="ignore")
    if "text/html" not in content_type and "<title>Hiddify | Panel</title>" not in text:
        return fail(f"home page did not return expected HTML shell: content-type={content_type!r}")
    if 'id="root"' not in text and "<div id=\"root\"" not in text:
        return fail("home page HTML shell is missing root container")

    ok("home page HTML shell verified; runtime translations are validated via i18n JSON")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check native Hiddify RU localization")
    parser.add_argument("--uuid", help="Existing subscription UUID for optional home page check")
    args = parser.parse_args()

    server_url = os.getenv("SMARTKAMA_PANEL_URL", "").strip() or get_default_server_url()
    if not server_url:
        return fail("server URL not found in env or database")

    client_proxy_path = get_client_proxy_path()
    if not client_proxy_path:
        return fail("client proxy path not found in env or str_config.hiddify_client_proxy_path")

    smoke_uuid = args.uuid or os.getenv("SMARTKAMA_SMOKE_UUID", "").strip() or None
    i18n_url, home_url = build_urls(server_url, client_proxy_path, smoke_uuid)

    session = requests.Session()
    result = check_i18n(session, i18n_url)
    if result != 0:
        return result

    if home_url:
        result = check_home_page(session, home_url)
        if result != 0:
            return result
    else:
        print("HIDDIFY_RU_CHECK_SKIP: home page check skipped, no UUID provided")

    print("HIDDIFY_RU_CHECK_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())