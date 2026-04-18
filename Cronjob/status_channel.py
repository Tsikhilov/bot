"""Post system status summary to a Telegram channel.

Usage:  python3 crontab.py --status-channel
"""
from __future__ import annotations

import logging
import requests

from AdminBot.bot import bot
from config import TELEGRAM_TOKEN, API_PATH
from Database.dbManager import USERS_DB

try:
    bot.remove_webhook()
except Exception:
    pass


def _get_status_channel_id() -> str:
    """Read status_channel_id from str_config."""
    try:
        configs = USERS_DB.select_str_config()
        for c in (configs or []):
            if c["key"] == "status_channel_id" and c.get("value"):
                return str(c["value"]).strip()
    except Exception:
        pass
    return ""


def _collect_server_status() -> list[str]:
    """Collect status lines from all servers."""
    from Utils.serverInfo import get_server_status

    servers = USERS_DB.select_servers()
    if not servers:
        return ["Серверы не настроены."]

    lines: list[str] = []
    for server in servers:
        title = server.get("title", "?")
        try:
            status_text = get_server_status(server)
            if status_text:
                lines.append(status_text)
            else:
                lines.append(f"<b>{title}</b>\n  ⚠️ Нет данных статуса")
        except Exception as exc:
            lines.append(f"<b>{title}</b>\n  ❌ Ошибка: {exc}")
    return lines


def _collect_user_stats() -> str:
    """Collect user and subscription counts."""
    try:
        total_users = len(USERS_DB.select_users() or [])
    except Exception:
        total_users = "?"

    active_subs = 0
    try:
        order_subs = USERS_DB.select_order_subscription()
        non_order_subs = USERS_DB.select_non_order_subscriptions()
        active_subs = len(order_subs or []) + len(non_order_subs or [])
    except Exception:
        active_subs = "?"

    return f"👥 Пользователей: {total_users}\n📱 Подписок: {active_subs}"


def cron_status_channel() -> None:
    """Main entry point: post status to Telegram channel."""
    channel_id = _get_status_channel_id()
    if not channel_id:
        logging.info("status_channel: channel_id not configured, skipping")
        return

    server_lines = _collect_server_status()
    user_stats = _collect_user_stats()

    text = "📊 <b>Статус SmartKamaVPN</b>\n\n"
    text += "\n\n".join(server_lines)
    text += f"\n\n{user_stats}"

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": channel_id,
                "text": text[:4000],
                "parse_mode": "HTML",
                "disable_notification": True,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            logging.info("status_channel: posted successfully")
        else:
            logging.warning("status_channel: %s %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logging.warning("status_channel: %s", exc)
