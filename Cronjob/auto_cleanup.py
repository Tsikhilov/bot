"""Auto-cleanup cronjob for expired subscriptions.

Runs periodically to:
1. Disable subscriptions that have been expired for a configurable grace period
2. Clean up stale device_connections records
3. Send summary report to admins
"""
import sqlite3
import logging
from datetime import datetime, timedelta

from AdminBot.bot import bot
from config import ADMINS_ID, USERS_DB_LOC, API_PATH
from Utils.utils import (
    non_order_user_info,
    order_user_info,
    all_configs_settings,
    USERS_DB,
)
from Utils import api

try:
    bot.remove_webhook()
except Exception:
    pass

_GRACE_PERIOD_DAYS = 7  # days after expiry before auto-disable
_DEVICE_CLEANUP_DAYS = 30  # remove device records not seen for N days


def _ensure_cleanup_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS auto_cleanup_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sub_uuid TEXT NOT NULL,
            sub_name TEXT,
            action TEXT NOT NULL,
            performed_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _already_cleaned(conn, sub_uuid, action):
    row = conn.execute(
        "SELECT 1 FROM auto_cleanup_log WHERE sub_uuid=? AND action=?",
        (sub_uuid, action),
    ).fetchone()
    return bool(row)


def _log_cleanup(conn, sub_uuid, sub_name, action):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO auto_cleanup_log(sub_uuid, sub_name, action, performed_at) VALUES(?,?,?,?)",
        (sub_uuid, sub_name, action, now),
    )
    conn.commit()


def _cleanup_stale_devices(conn):
    """Remove device_connections not seen in _DEVICE_CLEANUP_DAYS."""
    cutoff = (datetime.now() - timedelta(days=_DEVICE_CLEANUP_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur = conn.execute(
            "DELETE FROM device_connections WHERE last_seen < ?", (cutoff,)
        )
        return cur.rowcount
    except Exception:
        return 0


def _send_admin_report(message):
    for admin_id in ADMINS_ID:
        try:
            bot.send_message(admin_id, message, disable_notification=True)
        except Exception as e:
            logging.warning(f"Failed to send cleanup report to {admin_id}: {e}")


def cron_auto_cleanup():
    """Main entry point for auto-cleanup of expired subscriptions."""
    conn = sqlite3.connect(USERS_DB_LOC)
    _ensure_cleanup_table(conn)

    telegram_users = USERS_DB.select_users()
    if not telegram_users:
        conn.close()
        return

    disabled_subs = []
    errors = []

    for user in telegram_users:
        tid = user['telegram_id']
        try:
            subs = non_order_user_info(tid) + order_user_info(tid)
        except Exception as e:
            logging.debug(f"Error collecting subs for {tid}: {e}")
            continue

        for sub in subs:
            uuid = sub.get('uuid')
            if not uuid:
                continue
            name = sub.get('name', '?')
            remaining_day = int(sub.get('remaining_day', 0))
            is_enabled = sub.get('enable', True)

            # Skip active or already disabled subs
            if remaining_day > -_GRACE_PERIOD_DAYS:
                continue
            if not is_enabled:
                continue
            if _already_cleaned(conn, uuid, 'disabled'):
                continue

            # Disable on panel
            server_id = sub.get('server_id')
            server = USERS_DB.find_server(id=server_id)
            if not server:
                continue
            server = server[0]
            url = server['url'] + API_PATH

            try:
                result = api.update(url=url, uuid=uuid, enable=False)
                if result:
                    disabled_subs.append(f"  • {name} (UUID: {uuid[:8]}…, просрочка: {abs(remaining_day)} дн.)")
                    _log_cleanup(conn, uuid, name, 'disabled')
                else:
                    errors.append(f"  • {name}: не удалось отключить")
            except Exception as e:
                errors.append(f"  • {name}: {e}")
                logging.error(f"Auto-cleanup disable failed for {uuid}: {e}")

    # Clean up stale device records
    stale_count = _cleanup_stale_devices(conn)
    conn.close()

    # Build report
    parts = [f"🧹 *Авто-очистка — отчёт*\n{'─' * 28}"]

    if disabled_subs:
        parts.append(f"\n🔴 Отключены ({len(disabled_subs)}):")
        parts.extend(disabled_subs)

    if stale_count:
        parts.append(f"\n🗑 Удалено устаревших устройств: {stale_count}")

    if errors:
        parts.append(f"\n⚠️ Ошибки ({len(errors)}):")
        parts.extend(errors)

    if not disabled_subs and not stale_count and not errors:
        logging.info("Auto-cleanup: nothing to do")
        return

    _send_admin_report("\n".join(parts))
    logging.info(f"Auto-cleanup: disabled={len(disabled_subs)}, stale_devices={stale_count}, errors={len(errors)}")
