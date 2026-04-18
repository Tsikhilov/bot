# Crontab
import argparse
from config import CLIENT_TOKEN

# use argparse to get the arguments
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", action="store_true", help="Backup the panel")
    parser.add_argument("--backup-bot", action="store_true", help="Backup the bot database")
    parser.add_argument("--reminder", action="store_true", help="Send reminder to users")
    parser.add_argument("--anomaly", action="store_true", help="Traffic anomaly detection")
    parser.add_argument("--cleanup", action="store_true", help="Auto-cleanup expired subscriptions")
    parser.add_argument("--payment-check", action="store_true", help="Auto-check pending online payments")
    parser.add_argument("--status-channel", action="store_true", help="Post status to Telegram channel")
    args = parser.parse_args()

    # run the functions based on the arguments
    if args.backup:
        from Cronjob.backup import cron_backup
        cron_backup()

    elif args.backup_bot:
        if CLIENT_TOKEN:
            from Cronjob.backupBot import cron_backup_bot
            cron_backup_bot()

    elif args.reminder:
        if CLIENT_TOKEN:
            from Cronjob.reminder import cron_reminder
            cron_reminder()

    elif args.anomaly:
        if CLIENT_TOKEN:
            from Cronjob.traffic_anomaly import cron_traffic_anomaly
            cron_traffic_anomaly()

    elif args.cleanup:
        if CLIENT_TOKEN:
            from Cronjob.auto_cleanup import cron_auto_cleanup
            cron_auto_cleanup()

    elif args.payment_check:
        if CLIENT_TOKEN:
            from Cronjob.payment_check import cron_payment_check
            cron_payment_check()

    elif args.status_channel:
        from Cronjob.status_channel import cron_status_channel
        cron_status_channel()


# To run this file, use this command:
# python3 crontab.py --backup
# python3 crontab.py --backup-bot
# python3 crontab.py --reminder
# python3 crontab.py --anomaly
# python3 crontab.py --cleanup
# python3 crontab.py --payment-check
# python3 crontab.py --status-channel
