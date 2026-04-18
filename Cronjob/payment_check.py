# Auto-check pending online payments (YooKassa + CryptoPay)
# Run periodically via: python3 crontab.py --payment-check
import logging
import datetime
from config import ADMINS_ID, CLIENT_TOKEN, TELEGRAM_TOKEN
from Database.dbManager import USERS_DB

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def _notify_user(user_bot, telegram_id, text):
    try:
        user_bot.send_message(telegram_id, text, parse_mode="HTML")
    except Exception as e:
        logging.warning(f"Failed to notify user {telegram_id}: {e}")


def _notify_admins(admin_bot, text):
    for admin_id in ADMINS_ID:
        try:
            admin_bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception as e:
            logging.warning(f"Failed to notify admin {admin_id}: {e}")


def _check_yookassa_pending(user_bot, admin_bot):
    """Check all pending YooKassa payments and auto-credit wallets."""
    from Utils.yookassa import YooKassaPayment, get_yookassa_settings

    settings = get_yookassa_settings(USERS_DB)
    if not settings:
        logging.info("YooKassa not configured, skipping")
        return

    client = YooKassaPayment(settings['shop_id'], settings['secret_key'])

    payments = USERS_DB.select_yookassa_payments()
    if not payments:
        return

    pending = [p for p in payments if p['status'] == 'pending']
    logging.info(f"YooKassa: {len(pending)} pending payments to check")

    now = datetime.datetime.now()
    updated_at = now.strftime("%Y-%m-%d %H:%M:%S")

    for p in pending:
        payment_id = p['payment_id']
        telegram_id = p['telegram_id']

        # Skip payments older than 2 hours (YooKassa expires in ~1 hour)
        try:
            created = datetime.datetime.strptime(p['created_at'], "%Y-%m-%d %H:%M:%S")
            if (now - created).total_seconds() > 7200:
                USERS_DB.edit_yookassa_payment(payment_id, status='expired', updated_at=updated_at)
                logging.info(f"YooKassa payment {payment_id}: expired (>2h old)")
                continue
        except Exception:
            pass

        try:
            yookassa_data = client.get_payment(p['yookassa_payment_id'])
            if not yookassa_data:
                continue

            new_status = yookassa_data.get('status', 'pending')
            if new_status == p['status']:
                continue

            USERS_DB.edit_yookassa_payment(payment_id, status=new_status, updated_at=updated_at)

            if new_status == 'succeeded':
                amount = p['amount']
                wallet = USERS_DB.find_wallet(telegram_id=telegram_id)
                if not wallet:
                    USERS_DB.add_wallet(telegram_id)
                USERS_DB.atomic_credit_wallet(telegram_id, amount)

                _notify_user(
                    user_bot, telegram_id,
                    f"✅Автоплатеж ЮKassa прошел!\n💰Сумма: {amount}₽\nБаланс кошелька пополнен."
                )
                _notify_admins(
                    admin_bot,
                    f"💳 Автоплатеж ЮKassa\n"
                    f"Telegram ID: <code>{telegram_id}</code>\n"
                    f"Сумма: {amount}₽\n"
                    f"Статус: ✅ Оплачено"
                )
                logging.info(f"YooKassa payment {payment_id}: succeeded, wallet credited {amount}₽")

            elif new_status == 'canceled':
                _notify_user(user_bot, telegram_id, "❌Платеж через ЮKassa отменен.")
                logging.info(f"YooKassa payment {payment_id}: canceled")

        except Exception as e:
            logging.error(f"Error checking YooKassa payment {payment_id}: {e}")


def _check_crypto_pending(user_bot, admin_bot):
    """Check all pending CryptoPay invoices and auto-credit wallets."""
    from Utils.cryptopay import CryptoPayClient, get_cryptopay_settings

    settings = get_cryptopay_settings(USERS_DB)
    if not settings:
        logging.info("CryptoPay not configured, skipping")
        return

    client = CryptoPayClient(settings['api_token'])

    payments = USERS_DB.select_crypto_payments()
    if not payments:
        return

    pending = [p for p in payments if p['status'] == 'active']
    logging.info(f"CryptoPay: {len(pending)} active invoices to check")

    now = datetime.datetime.now()
    updated_at = now.strftime("%Y-%m-%d %H:%M:%S")

    for p in pending:
        payment_id = p['payment_id']
        telegram_id = p['telegram_id']
        invoice_id = p['invoice_id']

        # Skip invoices older than 2 hours
        try:
            created = datetime.datetime.strptime(p['created_at'], "%Y-%m-%d %H:%M:%S")
            if (now - created).total_seconds() > 7200:
                USERS_DB.edit_crypto_payment(payment_id, status='expired', updated_at=updated_at)
                logging.info(f"CryptoPay invoice {payment_id}: expired (>2h old)")
                continue
        except Exception:
            pass

        try:
            invoice_data = client.get_invoice(invoice_id)
            if not invoice_data:
                continue

            new_status = invoice_data.get('status', 'active')
            if new_status == p['status']:
                continue

            USERS_DB.edit_crypto_payment(payment_id, status=new_status, updated_at=updated_at)

            if new_status == 'paid':
                amount_rub = p['amount_rub']
                wallet = USERS_DB.find_wallet(telegram_id=telegram_id)
                if not wallet:
                    USERS_DB.add_wallet(telegram_id)
                USERS_DB.atomic_credit_wallet(telegram_id, amount_rub)

                _notify_user(
                    user_bot, telegram_id,
                    f"✅Крипто-платеж прошел!\n"
                    f"💰{p['amount_crypto']} {p['asset']}\n"
                    f"Баланс кошелька пополнен на {amount_rub}₽."
                )
                _notify_admins(
                    admin_bot,
                    f"🪙 Крипто-платеж\n"
                    f"Telegram ID: <code>{telegram_id}</code>\n"
                    f"Сумма: {p['amount_crypto']} {p['asset']} ({amount_rub}₽)\n"
                    f"Статус: ✅ Оплачено"
                )
                logging.info(f"CryptoPay invoice {payment_id}: paid, wallet credited {amount_rub}₽")

            elif new_status == 'expired':
                logging.info(f"CryptoPay invoice {payment_id}: expired on CryptoPay side")

        except Exception as e:
            logging.error(f"Error checking CryptoPay invoice {payment_id}: {e}")


def cron_payment_check():
    """Main entry point for payment auto-check cron job."""
    import telebot

    user_bot = telebot.TeleBot(CLIENT_TOKEN, parse_mode="HTML")
    try:
        user_bot.remove_webhook()
    except Exception:
        pass

    admin_bot_instance = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")
    try:
        admin_bot_instance.remove_webhook()
    except Exception:
        pass

    logging.info("=== Payment auto-check started ===")

    _check_yookassa_pending(user_bot, admin_bot_instance)
    _check_crypto_pending(user_bot, admin_bot_instance)

    logging.info("=== Payment auto-check finished ===")
