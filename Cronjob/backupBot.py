from Utils.utils import all_configs_settings, backup_json_bot
from AdminBot.bot import bot
from config import ADMINS_ID
import logging
try:
    bot.remove_webhook()
except:
    pass

# Send backup file to admins
def cron_backup_bot():
    file_name = backup_json_bot()
    settings = all_configs_settings()
    if not settings['bot_auto_backup']:
        return
    if file_name:
        for admin_id in ADMINS_ID:
            try:
                with open(file_name, 'rb') as f:
                    bot.send_document(admin_id, f, caption="🤖Bot Backup",disable_notification=True)
            except Exception as e:
                logging.warning(f"Bot backup send failed for admin {admin_id}: {e}")