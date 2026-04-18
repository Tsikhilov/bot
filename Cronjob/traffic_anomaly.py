"""Traffic anomaly detection cronjob.

Runs periodically (e.g. every 6 hours) to:
1. Snapshot current traffic usage per subscription
2. Detect anomalies: sudden spikes, multi-device sharing
3. Alert admins via Telegram
"""
import sqlite3
import logging
from datetime import datetime, timedelta

from AdminBot.bot import bot
from config import ADMINS_ID, USERS_DB_LOC
from Utils.utils import (
    non_order_user_info,
    order_user_info,
    all_configs_settings,
    USERS_DB,
)

try:
    bot.remove_webhook()
except Exception:
    pass

_ANOMALY_MULTIPLIER = 3.0  # alert if delta > N× 7-day average
_MIN_DAILY_GB_FOR_ALERT = 2.0  # don't alert for tiny absolute values
_MULTI_DEVICE_THRESHOLD = 3  # alert if >= N unique devices per sub
_SNAPSHOT_RETENTION_DAYS = 30


def _ensure_tables(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS traffic_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sub_uuid TEXT NOT NULL,
            sub_name TEXT,
            current_usage_gb REAL NOT NULL,
            usage_limit_gb REAL,
            remaining_day INTEGER,
            recorded_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_traffic_snap_uuid_date
        ON traffic_snapshots(sub_uuid, recorded_at)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS anomaly_alerts_sent (
            sub_uuid TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            alert_date TEXT NOT NULL,
            PRIMARY KEY (sub_uuid, alert_type, alert_date)
        )
        """
    )
    conn.commit()


def _was_alerted_today(conn, sub_uuid, alert_type):
    today = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT 1 FROM anomaly_alerts_sent WHERE sub_uuid=? AND alert_type=? AND alert_date=?",
        (sub_uuid, alert_type, today),
    ).fetchone()
    return bool(row)


def _mark_alerted(conn, sub_uuid, alert_type):
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        "INSERT OR IGNORE INTO anomaly_alerts_sent(sub_uuid, alert_type, alert_date) VALUES(?,?,?)",
        (sub_uuid, alert_type, today),
    )
    conn.commit()


def _record_snapshot(conn, sub_uuid, sub_name, current_gb, limit_gb, remaining_day):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO traffic_snapshots(sub_uuid, sub_name, current_usage_gb, usage_limit_gb, remaining_day, recorded_at) "
        "VALUES(?,?,?,?,?,?)",
        (sub_uuid, sub_name, current_gb, limit_gb, remaining_day, now),
    )


def _get_avg_daily_delta(conn, sub_uuid, days=7):
    """Calculate average daily traffic delta over the last N days."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        "SELECT current_usage_gb, recorded_at FROM traffic_snapshots "
        "WHERE sub_uuid=? AND recorded_at>=? ORDER BY recorded_at ASC",
        (sub_uuid, cutoff),
    ).fetchall()
    if len(rows) < 2:
        return None
    first_gb, first_time = rows[0]
    last_gb, last_time = rows[-1]
    delta_gb = last_gb - first_gb
    t0 = datetime.strptime(first_time, "%Y-%m-%d %H:%M:%S")
    t1 = datetime.strptime(last_time, "%Y-%m-%d %H:%M:%S")
    days_span = max((t1 - t0).total_seconds() / 86400, 0.01)
    return delta_gb / days_span


def _get_latest_snapshot_gb(conn, sub_uuid):
    row = conn.execute(
        "SELECT current_usage_gb FROM traffic_snapshots "
        "WHERE sub_uuid=? ORDER BY recorded_at DESC LIMIT 1",
        (sub_uuid,),
    ).fetchone()
    return row[0] if row else None


def _get_device_count(conn, sub_uuid):
    row = conn.execute(
        "SELECT COUNT(*) FROM device_connections WHERE sub_uuid=?",
        (sub_uuid,),
    ).fetchone()
    return row[0] if row else 0


def _cleanup_old_snapshots(conn):
    cutoff = (datetime.now() - timedelta(days=_SNAPSHOT_RETENTION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("DELETE FROM traffic_snapshots WHERE recorded_at < ?", (cutoff,))
    conn.execute("DELETE FROM anomaly_alerts_sent WHERE alert_date < ?",
                 ((datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),))
    conn.commit()


def _send_admin_alert(message):
    for admin_id in ADMINS_ID:
        try:
            bot.send_message(admin_id, message, disable_notification=False)
        except Exception as e:
            logging.warning(f"Failed to send anomaly alert to {admin_id}: {e}")


def _collect_all_subscriptions():
    """Collect all subscriptions across all telegram users."""
    all_subs = []
    telegram_users = USERS_DB.select_users()
    if not telegram_users:
        return all_subs
    for user in telegram_users:
        tid = user['telegram_id']
        try:
            subs = non_order_user_info(tid) + order_user_info(tid)
            for s in subs:
                s['_telegram_id'] = tid
            all_subs.extend(subs)
        except Exception as e:
            logging.debug(f"Error collecting subs for {tid}: {e}")
    return all_subs


def cron_traffic_anomaly():
    """Main entry point for traffic anomaly detection."""
    conn = sqlite3.connect(USERS_DB_LOC)
    _ensure_tables(conn)
    _cleanup_old_snapshots(conn)

    subs = _collect_all_subscriptions()
    if not subs:
        conn.close()
        return

    alerts = []

    for sub in subs:
        uuid = sub.get('uuid')
        if not uuid:
            continue
        name = sub.get('name', '?')
        usage = sub.get('usage', {})
        current_gb = float(usage.get('current_usage_GB', 0))
        limit_gb = float(usage.get('usage_limit_GB', 0))
        remaining_day = int(sub.get('remaining_day', 0))

        if remaining_day <= 0:
            continue  # skip expired

        # Get previous snapshot to calculate delta
        prev_gb = _get_latest_snapshot_gb(conn, uuid)

        # Record current snapshot
        _record_snapshot(conn, uuid, name, current_gb, limit_gb, remaining_day)

        # --- Check 1: Traffic spike ---
        if prev_gb is not None:
            delta_gb = current_gb - prev_gb
            avg_daily = _get_avg_daily_delta(conn, uuid)
            if (
                avg_daily is not None
                and avg_daily > 0
                and delta_gb > _MIN_DAILY_GB_FOR_ALERT
                and delta_gb > avg_daily * _ANOMALY_MULTIPLIER
            ):
                if not _was_alerted_today(conn, uuid, 'traffic_spike'):
                    alerts.append(
                        f"⚡ *Всплеск трафика*\n"
                        f"Подписка: `{name}` (`{uuid[:8]}…`)\n"
                        f"Дельта: {delta_gb:.2f} ГБ (норма: ~{avg_daily:.2f} ГБ/день)\n"
                        f"Превышение: ×{delta_gb/avg_daily:.1f}"
                    )
                    _mark_alerted(conn, uuid, 'traffic_spike')

        # --- Check 2: Multi-device sharing ---
        device_count = _get_device_count(conn, uuid)
        if device_count >= _MULTI_DEVICE_THRESHOLD:
            if not _was_alerted_today(conn, uuid, 'multi_device'):
                alerts.append(
                    f"📱 *Много устройств*\n"
                    f"Подписка: `{name}` (`{uuid[:8]}…`)\n"
                    f"Устройств: {device_count} (порог: {_MULTI_DEVICE_THRESHOLD})"
                )
                _mark_alerted(conn, uuid, 'multi_device')

        # --- Check 3: High absolute usage (>80% consumed) ---
        if limit_gb > 0:
            usage_pct = (current_gb / limit_gb) * 100
            if usage_pct >= 80 and remaining_day > 5:
                if not _was_alerted_today(conn, uuid, 'high_usage'):
                    alerts.append(
                        f"📊 *Высокое потребление*\n"
                        f"Подписка: `{name}` (`{uuid[:8]}…`)\n"
                        f"Использовано: {usage_pct:.0f}% ({current_gb:.1f}/{limit_gb:.0f} ГБ)\n"
                        f"Осталось дней: {remaining_day}"
                    )
                    _mark_alerted(conn, uuid, 'high_usage')

    conn.commit()
    conn.close()

    # Send collected alerts
    if alerts:
        header = f"🔔 *Отчёт аномалий трафика*\n{'─' * 28}\n\n"
        # Split into chunks to stay within Telegram message limit
        chunk = header
        for alert in alerts:
            if len(chunk) + len(alert) + 2 > 4000:
                _send_admin_alert(chunk)
                chunk = ""
            chunk += alert + "\n\n"
        if chunk.strip():
            _send_admin_alert(chunk)
        logging.info(f"Traffic anomaly: sent {len(alerts)} alert(s) to admins")
    else:
        logging.info("Traffic anomaly: no anomalies detected")
