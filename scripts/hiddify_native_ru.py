#!/usr/bin/env python3
"""Harden native Hiddify RU localization.

What this script can do:
- Keep ru.json in sync with en.json + explicit Russian overrides.
- Optionally force selected en.json labels to Russian as a compatibility fallback.
- Add dedicated no-cache nginx locations for i18n JSON files.
- Install a cron task that reapplies the patch after panel updates.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

I18N_BASE = Path(
    "/opt/hiddify-manager/.venv313/lib/python3.13/site-packages/"
    "hiddifypanel/static/new/i18n"
)
STATIC_ROOT = Path(
    "/opt/hiddify-manager/.venv313/lib/python3.13/site-packages/"
    "hiddifypanel/static"
)
NGINX_COMMON = Path("/opt/hiddify-manager/nginx/parts/common.conf")
HIDDIFY_NGINX_CONF = "/opt/hiddify-manager/nginx/nginx.conf"

MARKER_BEGIN = "# smartkama_i18n_nocache_begin"
MARKER_END = "# smartkama_i18n_nocache_end"

TRANSLATIONS: Dict[str, str] = {
    "Welcome": "Добро пожаловать",
    "Used Traffic": "Использовано трафика",
    "Remaining Traffic": "Оставшийся трафик",
    "Remaining time": "Оставшееся время",
    "Remaining Time": "Оставшееся время",
    "Support": "Поддержка",
    "View More": "Показать больше",
    "Home": "Главная",
    "Devices": "Устройства",
    "Settings": "Настройки",
    "Dashboard": "Панель",
    "Language Settings": "Настройки языка",
    "Choose your preferred language:": "Выберите предпочитаемый язык:",
    "Import To App": "Импорт в приложение",
    "Copy Link": "Скопировать ссылку",
    "Setup Guide": "Инструкция по настройке",
    "Days": "Дни",
    "Hours": "Часы",
    "Minutes": "Минуты",
    "Total": "Всего",
    "Used": "Использовано",
    "Remaining": "Осталось",
    "No Time Limit": "Без ограничения по времени",
    "No Data Limit": "Без лимита трафика",
}


@dataclass
class ApplyResult:
    ru_changed: bool = False
    en_changed: bool = False
    nginx_changed: bool = False
    cron_changed: bool = False


def _load_json(path: Path) -> Dict[str, str]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_if_changed(path: Path, payload: Dict[str, str]) -> bool:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if old == rendered:
        return False
    path.write_text(rendered, encoding="utf-8")
    return True


def patch_i18n(force_en_ru: bool) -> Tuple[bool, bool]:
    en_path = I18N_BASE / "en.json"
    ru_path = I18N_BASE / "ru.json"

    en = _load_json(en_path)
    ru_existing = _load_json(ru_path)

    ru = dict(en)
    ru.update(ru_existing)
    ru.update(TRANSLATIONS)

    ru_changed = _write_json_if_changed(ru_path, ru)

    en_changed = False
    if force_en_ru:
        en_forced = dict(en)
        en_forced.update(TRANSLATIONS)
        en_changed = _write_json_if_changed(en_path, en_forced)

    return ru_changed, en_changed


def _extract_proxy_paths(common_conf_text: str) -> List[str]:
    paths = re.findall(r"location\s+/([^/\s]+)/static\s*\{", common_conf_text)
    uniq = []
    for p in paths:
        if p not in uniq:
            uniq.append(p)
    return uniq


def _build_i18n_locations(paths: List[str]) -> str:
    blocks = [MARKER_BEGIN]
    for p in paths:
        blocks.extend(
            [
                f"location /{p}/static/new/i18n/ {{",
                '  add_header X-Robots-Tag "noindex, nofollow";',
                "  expires -1;",
                '  add_header Cache-Control "no-cache, no-store, must-revalidate" always;',
                '  add_header Pragma "no-cache" always;',
                '  add_header Expires "0" always;',
                "  etag on;",
                "  if_modified_since exact;",
                f"  alias {STATIC_ROOT}/new/i18n/;",
                "}",
                "",
            ]
        )
    blocks.append(MARKER_END)
    return "\n".join(blocks).rstrip() + "\n"


def patch_nginx_i18n_cache(common_conf_path: Path) -> bool:
    text = common_conf_path.read_text(encoding="utf-8")
    proxy_paths = _extract_proxy_paths(text)
    if not proxy_paths:
        raise RuntimeError("No /<proxy>/static locations found in common.conf")

    managed_block = _build_i18n_locations(proxy_paths)

    if MARKER_BEGIN in text and MARKER_END in text:
        updated = re.sub(
            rf"{re.escape(MARKER_BEGIN)}.*?{re.escape(MARKER_END)}\n?",
            managed_block,
            text,
            flags=re.DOTALL,
        )
    else:
        anchor = re.search(r"location\s+/[^/\s]+/static\s*\{", text)
        if not anchor:
            raise RuntimeError("Cannot find insertion point for i18n no-cache block")
        updated = text[: anchor.start()] + managed_block + "\n" + text[anchor.start() :]

    if updated == text:
        return False

    common_conf_path.write_text(updated, encoding="utf-8")
    return True


def _run(cmd: List[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    output = (res.stdout or "").strip()
    if not output:
        output = (res.stderr or "").strip()
    return output


def install_cron(script_path: Path, force_en_ru: bool) -> bool:
    marker = "# smartkama_hiddify_ru_maintenance"
    cmd = f"/usr/bin/python3 {script_path} --apply --nginx-reload"
    if force_en_ru:
        cmd += " --force-en-ru"
    line = f"*/20 * * * * {cmd} >> /var/log/hiddify-ru-maint.log 2>&1 {marker}"

    try:
        current = _run(["crontab", "-l"])
    except subprocess.CalledProcessError:
        current = ""

    if marker in current:
        return False

    new_cron = (current + "\n" + line + "\n").lstrip("\n")
    p = subprocess.run(["crontab", "-"], input=new_cron, text=True, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"Failed to install cron: {p.stderr.strip()}")
    return True


def validate_and_reload_nginx(reload: bool) -> None:
    _run(["/usr/sbin/nginx", "-t", "-c", HIDDIFY_NGINX_CONF])
    if reload:
        _run(["systemctl", "reload", "hiddify-nginx"])
        _run(["systemctl", "is-active", "hiddify-nginx"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Hiddify native RU hardening")
    parser.add_argument("--apply", action="store_true", help="Apply all selected patches")
    parser.add_argument(
        "--force-en-ru",
        action="store_true",
        help="Also override selected en.json keys with Russian as fallback",
    )
    parser.add_argument(
        "--skip-nginx-cache",
        action="store_true",
        help="Do not patch nginx i18n no-cache locations",
    )
    parser.add_argument(
        "--nginx-reload",
        action="store_true",
        help="Reload hiddify-nginx after successful nginx config validation",
    )
    parser.add_argument(
        "--install-cron",
        action="store_true",
        help="Install periodic maintenance cron entry",
    )
    args = parser.parse_args()

    if not args.apply:
        print("Nothing to do. Use --apply.")
        return 0

    result = ApplyResult()

    ru_changed, en_changed = patch_i18n(force_en_ru=args.force_en_ru)
    result.ru_changed = ru_changed
    result.en_changed = en_changed

    if not args.skip_nginx_cache:
        result.nginx_changed = patch_nginx_i18n_cache(NGINX_COMMON)
        validate_and_reload_nginx(reload=args.nginx_reload)

    if args.install_cron:
        result.cron_changed = install_cron(
            script_path=Path("/opt/SmartKamaVPN/scripts/hiddify_native_ru.py"),
            force_en_ru=args.force_en_ru,
        )

    print(
        "APPLY_OK "
        f"ru_changed={int(result.ru_changed)} "
        f"en_changed={int(result.en_changed)} "
        f"nginx_changed={int(result.nginx_changed)} "
        f"cron_changed={int(result.cron_changed)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
