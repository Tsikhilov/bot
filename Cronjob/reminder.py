from Utils.utils import *
from UserBot.bot import bot
from config import CLIENT_TOKEN
from UserBot.templates import package_size_end_soon_template, package_days_expire_soon_template
try:
    bot.remove_webhook()
except Exception:
    pass

settings = all_configs_settings()
ALERT_PACKAGE_GB = settings.get('reminder_notification_usage', 3)
ALERT_PACKAGE_DAYS = settings.get('reminder_notification_days', 3)


def alert_package_gb(package_remaining_gb):
    return package_remaining_gb <= ALERT_PACKAGE_GB


def alert_package_days(package_remaining_days):
    return package_remaining_days <= ALERT_PACKAGE_DAYS


def cron_reminder():
    if not CLIENT_TOKEN:
        return
    if not settings.get('reminder_notification'):
        return

    telegram_users = USERS_DB.select_users()
    if not telegram_users:
        return

    sent = 0
    for user in telegram_users:
        user_telegram_id = user['telegram_id']
        try:
            user_subscriptions_list = non_order_user_info(user_telegram_id) + order_user_info(user_telegram_id)
        except Exception as e:
            logging.warning("reminder: failed to fetch subs for %s: %s", user_telegram_id, e)
            continue

        for user_subscription in user_subscriptions_list:
            try:
                package_days = user_subscription.get('remaining_day', 0)
                package_gb = user_subscription.get('usage', {}).get('remaining_usage_GB', 0)
                sub_id = user_subscription.get('sub_id')
                if package_days == 0:
                    continue
                if alert_package_gb(package_gb):
                    bot.send_message(user_telegram_id, package_size_end_soon_template(sub_id, package_gb), parse_mode="HTML")
                    sent += 1
                if alert_package_days(package_days):
                    bot.send_message(user_telegram_id, package_days_expire_soon_template(sub_id, package_days), parse_mode="HTML")
                    sent += 1
            except Exception as e:
                logging.warning("reminder: failed to notify %s (sub %s): %s", user_telegram_id, user_subscription.get('sub_id'), e)

    logging.info("cron_reminder: %d notifications sent", sent)
