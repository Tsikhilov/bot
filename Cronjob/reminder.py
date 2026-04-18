from Utils.utils import *
from UserBot.bot import bot
from config import CLIENT_TOKEN, LANG
import logging
import sqlite3
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

try:
    bot.remove_webhook()
except:
    pass

settings = all_configs_settings()
ALERT_PACKAGE_GB = settings.get('reminder_notification_usage', 3)
ALERT_PACKAGE_DAYS = settings.get('reminder_notification_days', 3)


def _ensure_reminders_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reminder_notifications (
            telegram_id INTEGER NOT NULL,
            uuid TEXT NOT NULL,
            event_key TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            PRIMARY KEY (telegram_id, uuid, event_key)
        )
        """
    )
    conn.commit()


def _was_sent(conn, telegram_id, uuid, event_key):
    row = conn.execute(
        "SELECT 1 FROM reminder_notifications WHERE telegram_id=? AND uuid=? AND event_key=?",
        (telegram_id, uuid, event_key),
    ).fetchone()
    return bool(row)


def _mark_sent(conn, telegram_id, uuid, event_key):
    conn.execute(
        "INSERT OR REPLACE INTO reminder_notifications(telegram_id, uuid, event_key, sent_at) VALUES(?,?,?,?)",
        (telegram_id, uuid, event_key, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()


def _renewal_markup(uuid):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("💰 Продлить подписку", callback_data=f"smartkamavpn_sub_open:{uuid}"))
    return markup


def _msg_days_left(sub_id, days):
    if LANG == 'EN':
        return (
            f"⏰ Subscription #{sub_id} is expiring soon.\n"
            f"Only {days} day(s) left.\n\n"
            f"Please renew now to avoid connection interruption."
        )
    return (
        f"⏰ Подписка #{sub_id} скоро закончится.\n"
        f"Осталось: {days} дн.\n\n"
        f"Продлите сейчас, чтобы избежать паузы в доступе."
    )


def _msg_gb_left(sub_id, remaining_gb):
    if LANG == 'EN':
        return (
            f"📉 Low traffic on subscription #{sub_id}.\n"
            f"Only {remaining_gb:.2f} GB left.\n\n"
            f"Renew to keep stable access."
        )
    return (
        f"📉 На подписке #{sub_id} мало трафика.\n"
        f"Осталось: {remaining_gb:.2f} ГБ.\n\n"
        f"Продлите подписку для стабильного доступа."
    )


def _msg_expired(sub_id):
    if LANG == 'EN':
        return (
            f"💤 Subscription #{sub_id} has expired.\n"
            f"VPN is paused until renewal."
        )
    return (
        f"💤 Подписка #{sub_id} завершилась.\n"
        f"VPN сейчас на паузе до продления."
    )


def alert_package_gb(package_remaining_gb):
    if package_remaining_gb <= ALERT_PACKAGE_GB:
        return True
    return False


def alert_package_days(package_remaining_days):
    if package_remaining_days <= ALERT_PACKAGE_DAYS:
        return True
    return False


# Send a reminder to users about their packages
def cron_reminder():
    if not CLIENT_TOKEN:
        return
    if not settings['reminder_notification']:
        return

    conn = sqlite3.connect(USERS_DB_LOC)
    try:
        _ensure_reminders_table(conn)

        telegram_users = USERS_DB.select_users()
        if telegram_users:
            for user in telegram_users:
                user_telegram_id = user['telegram_id']
                user_subscriptions_list = non_order_user_info(user_telegram_id) + order_user_info(user_telegram_id)
                if user_subscriptions_list:
                    for user_subscription in user_subscriptions_list:
                        package_days = user_subscription.get('remaining_day', 0)
                        package_gb = user_subscription.get('usage', {}).get('remaining_usage_GB', 0)
                        sub_id = user_subscription.get('sub_id')
                        uuid = user_subscription.get('uuid')
                        if not uuid:
                            continue

                        if package_days <= 0:
                            event_key = 'expired_once'
                            if not _was_sent(conn, user_telegram_id, uuid, event_key):
                                try:
                                    bot.send_message(user_telegram_id, _msg_expired(sub_id), reply_markup=_renewal_markup(uuid))
                                except Exception as e:
                                    logging.warning(f"Reminder send failed for {user_telegram_id}: {e}")
                                    continue
                                _mark_sent(conn, user_telegram_id, uuid, event_key)
                            continue

                        # Time-based reminders: at configured threshold and at 1 day left.
                        if package_days in (int(ALERT_PACKAGE_DAYS), 1):
                            event_key = f'days_left_{int(package_days)}'
                            if not _was_sent(conn, user_telegram_id, uuid, event_key):
                                try:
                                    bot.send_message(user_telegram_id, _msg_days_left(sub_id, int(package_days)), reply_markup=_renewal_markup(uuid))
                                except Exception as e:
                                    logging.warning(f"Reminder send failed for {user_telegram_id}: {e}")
                                    continue
                                _mark_sent(conn, user_telegram_id, uuid, event_key)

                        # Traffic-based reminder once when below threshold.
                        if alert_package_gb(package_gb):
                            event_key = 'traffic_low_once'
                            if not _was_sent(conn, user_telegram_id, uuid, event_key):
                                try:
                                    bot.send_message(user_telegram_id, _msg_gb_left(sub_id, float(package_gb or 0)), reply_markup=_renewal_markup(uuid))
                                except Exception as e:
                                    logging.warning(f"Reminder send failed for {user_telegram_id}: {e}")
                                    continue
                                _mark_sent(conn, user_telegram_id, uuid, event_key)
    finally:
        conn.close()
