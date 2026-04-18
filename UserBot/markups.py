# Description: This file contains all the reply and inline keyboard markups used in the bot.
from telebot import types
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from UserBot.content import KEY_MARKUP, MESSAGES
from UserBot.content import MESSAGES
from Utils.utils import rial_to_toman,all_configs_settings
from Utils.api import *
import config as _cfg

# Main Menu Reply Keyboard Markup
def main_menu_keyboard_markup():
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    # Row 1: Primary actions — subscription & status
    markup.add(KeyboardButton(KEY_MARKUP['SUBSCRIPTION_STATUS']),
               KeyboardButton(KEY_MARKUP['BUY_SUBSCRIPTION']))
    # Row 2: Connect & wallet
    markup.add(KeyboardButton(KEY_MARKUP['LINK_SUBSCRIPTION']),
               KeyboardButton(KEY_MARKUP['WALLET']))
    # Row 3: Free trial & promo
    markup.add(KeyboardButton(KEY_MARKUP['FREE_TEST']),
               KeyboardButton(KEY_MARKUP['MTPROMO']))
    # Row 4: Social — invite & gift
    markup.add(KeyboardButton(KEY_MARKUP['INVITE_FRIEND']),
               KeyboardButton(KEY_MARKUP['GIFT_VPN']))
    # Row 5: Conditional proxy services
    proxy_buttons = []
    if _cfg.MTPROTO_ENABLED:
        proxy_buttons.append(KeyboardButton(KEY_MARKUP['TG_PROXY']))
    if _cfg.WHATSAPP_PROXY_ENABLED:
        proxy_buttons.append(KeyboardButton(KEY_MARKUP['WA_PROXY']))
    if _cfg.SIGNAL_PROXY_ENABLED:
        proxy_buttons.append(KeyboardButton(KEY_MARKUP['SIGNAL_PROXY']))
    if proxy_buttons:
        markup.add(*proxy_buttons)
    # Row 6: Account & help
    markup.add(KeyboardButton(KEY_MARKUP['MY_ACCOUNT']),
               KeyboardButton(KEY_MARKUP['HELP_MENU']))
    # Row 7: Support & manual
    settings = all_configs_settings()
    if settings['msg_faq']:
        markup.add(KeyboardButton(KEY_MARKUP['SEND_TICKET']),
                   KeyboardButton(KEY_MARKUP['MANUAL']),
                   KeyboardButton(KEY_MARKUP['FAQ']))
    else:
        markup.add(KeyboardButton(KEY_MARKUP['SEND_TICKET']),
                   KeyboardButton(KEY_MARKUP['MANUAL']))
    # Row 8: About & main menu return
    markup.add(KeyboardButton(KEY_MARKUP['ABOUT_SERVICE']),
               KeyboardButton(KEY_MARKUP['MAIN_MENU']))
    return markup


def user_info_markup(uuid):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton(KEY_MARKUP['CONFIGS_LIST'], callback_data=f"configs_list:{uuid}"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['RENEWAL_SUBSCRIPTION'], callback_data=f"renewal_subscription:{uuid}"))
    markup.add(
        InlineKeyboardButton(KEY_MARKUP['UPDATE_SUBSCRIPTION_INFO'], callback_data=f"update_info_subscription:{uuid}"))
    return markup


# Subscription URL Inline Keyboard Markup
def sub_url_user_list_markup(uuid):
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    settings = all_configs_settings()
    if settings['visible_conf_dir']:
        markup.add(InlineKeyboardButton(KEY_MARKUP['CONFIGS_DIR'], callback_data=f"conf_dir:{uuid}"))
    if settings['visible_conf_sub_auto']:
        markup.add(InlineKeyboardButton(KEY_MARKUP['CONFIGS_SUB_AUTO'], callback_data=f"conf_sub_auto:{uuid}"))
    if settings['visible_conf_sub_url']:
        markup.add(InlineKeyboardButton(KEY_MARKUP['CONFIGS_SUB'], callback_data=f"conf_sub_url:{uuid}"))
    if settings['visible_conf_sub_url_b64']:
        markup.add(InlineKeyboardButton(KEY_MARKUP['CONFIGS_SUB_B64'], callback_data=f"conf_sub_url_b64:{uuid}"))
    if settings['visible_conf_clash']:
        markup.add(InlineKeyboardButton(KEY_MARKUP['CONFIGS_CLASH'], callback_data=f"conf_clash:{uuid}"))
    if settings['visible_conf_hiddify']:
        markup.add(InlineKeyboardButton(KEY_MARKUP['CONFIGS_HIDDIFY'], callback_data=f"smartkamavpn_conf_hiddify:{uuid}"))
    if settings['visible_conf_sub_sing_box']:
        markup.add(InlineKeyboardButton(KEY_MARKUP['CONFIGS_SING_BOX'], callback_data=f"smartkamavpn_conf_singbox:{uuid}"))
    if settings['visible_conf_sub_full_sing_box']:
        markup.add(InlineKeyboardButton(KEY_MARKUP['CONFIGS_FULL_SING_BOX'],
                                        callback_data=f"conf_sub_full_sing_box:{uuid}"))

    markup.add(InlineKeyboardButton("📡 Оператор связи", callback_data=f"select_operator:{uuid}"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data=f"back_to_user_panel:{uuid}"))

    return markup


# Operator Selection Inline Keyboard Markup
def operator_select_markup(uuid):
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    operators = [
        ("🔴 МТС", "mts"),
        ("🟡 Билайн", "beeline"),
        ("🔵 Tele2", "tele2"),
        ("🟢 Мегафон", "megafon"),
        ("📶 Yota", "yota"),
        ("🔄 Авто", "auto"),
    ]
    for label, op in operators:
        markup.add(InlineKeyboardButton(label, callback_data=f"set_operator:{op}:{uuid}"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data=f"configs_list:{uuid}"))
    return markup


# Subscription Configs Inline Keyboard Markup
def sub_user_list_markup(uuid,configs):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    if configs['vless']:
        markup.add(InlineKeyboardButton('Vless', callback_data=f"conf_dir_vless:{uuid}"))
    if configs['vmess']:
        markup.add(InlineKeyboardButton('Vmess', callback_data=f"conf_dir_vmess:{uuid}"))
    if configs['trojan']:
        markup.add(InlineKeyboardButton('Trojan', callback_data=f"conf_dir_trojan:{uuid}"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data=f"back_to_user_panel:{uuid}"))
    # markup.add(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data=f"back_to_user_panel:{uuid}"))
    # markup.add(InlineKeyboardButton('Vmess', callback_data=f"conf_dir_vmess:{uuid}"))
    # markup.add(InlineKeyboardButton('Trojan', callback_data=f"conf_dir_trojan:{uuid}"))

    return markup

def user_info_non_sub_markup(uuid):
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(InlineKeyboardButton(KEY_MARKUP['CONFIGS_LIST'], callback_data=f"configs_list:{uuid}"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['RENEWAL_SUBSCRIPTION'], callback_data=f"renewal_subscription:{uuid}"))
    markup.add(
        InlineKeyboardButton(KEY_MARKUP['UPDATE_SUBSCRIPTION_INFO'], callback_data=f"update_info_subscription:{uuid}"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['UNLINK_SUBSCRIPTION'], callback_data=f"unlink_subscription:{uuid}"))
    return markup


def confirm_subscription_markup(uuid):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton(KEY_MARKUP['YES'], callback_data=f"confirm_subscription:{uuid}"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['NO'], callback_data=f"cancel_subscription:{uuid}"))
    return markup


def confirm_buy_plan_markup(plan_id, renewal=False,uuid=None):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    callback = "confirm_buy_from_wallet" if not renewal else "confirm_renewal_from_wallet"
    markup.add(InlineKeyboardButton(KEY_MARKUP['BUY_FROM_WALLET'], callback_data=f"{callback}:{plan_id}"))
    if renewal:
        markup.add(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data=f"back_to_renewal_plans:{uuid}"))
    else:
        markup.add(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data=f"back_to_plans:None"))
    markup.add(InlineKeyboardButton("🏠 В титульное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


def send_screenshot_markup(plan_id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton(KEY_MARKUP['SEND_SCREENSHOT'], callback_data=f"send_screenshot:{plan_id}"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['CANCEL'], callback_data=f"cancel_increase_wallet_balance:{plan_id}"))
    return markup


def plans_list_markup(plans, renewal=False,uuid=None):
    markup = InlineKeyboardMarkup(row_width=1)
    callback = "renewal_plan_selected" if renewal else "plan_selected"
    keys = []
    for plan in plans:
        if plan['status']:
            keys.append(InlineKeyboardButton(
                f"{plan['size_gb']}{MESSAGES['GB']} | {plan['days']}{MESSAGES['DAY_EXPIRE']} | {rial_to_toman(plan['price'])} {MESSAGES['TOMAN']}",
                callback_data=f"{callback}:{plan['id']}"))
    if len(keys) == 0:
        return None
    if renewal:
        keys.append(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data=f"back_to_user_panel:{uuid}"))
    else:
        keys.append(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data=f"back_to_buy_types:None"))
    keys.append(InlineKeyboardButton("🏠 В титульное меню", callback_data="smartkamavpn_title_menu:None"))
    markup.add(*keys)
    return markup


def subscription_type_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("👤 Индивидуальный: 2 телефона + 2 ПК/планшета", callback_data="buy_type_selected:individual"))
    markup.add(InlineKeyboardButton("👨‍👩‍👧‍👦 Семейный: 5 телефонов + 3 ПК/планшета", callback_data="buy_type_selected:family"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data="smartkamavpn_vpn_menu:None"))
    markup.add(InlineKeyboardButton("🏠 В титульное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


# Server List - Server List - Inline Keyboard Markup
def servers_list_markup(servers, free_test=False):
    markup = InlineKeyboardMarkup(row_width=1)
    callback = "free_test_server_selected" if free_test else "server_selected"
    keys = []
    if servers:
        for server in servers:
            server_title = server[0]['title'] if server[1] else f"{server[0]['title']}⛔️"
            callback_2 = f"{server[0]['id']}" if server[1] else "False"
            keys.append(InlineKeyboardButton(f"{server_title}",
                                             callback_data=f"{callback}:{callback_2}"))
        keys.append(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data=f"del_msg:None"))
    if len(keys) == 0:
        return None
    markup.add(*keys)
    return markup

def confirm_payment_by_admin(order_id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton(KEY_MARKUP['CONFIRM_PAYMENT'], callback_data=f"confirm_payment_by_admin:{order_id}"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['NO'], callback_data=f"cancel_payment_by_admin:{order_id}"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['SEND_MESSAGE'], callback_data=f"send_message_by_admin:{order_id}"))
    return markup

def notify_to_admin_markup(user):
    name = user['full_name'] if user['full_name'] else user['telegram_id']
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton(f"{name}", callback_data=f"bot_user_info:{user['telegram_id']}"))
    return markup

def send_ticket_to_admin():
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton(KEY_MARKUP['SEND_TICKET_TO_SUPPORT'], callback_data=f"send_ticket_to_support:None"))
    markup.add(
        InlineKeyboardButton(KEY_MARKUP['CANCEL'], callback_data=f"del_msg:None"))
    
    return markup

def answer_to_user_markup(user,user_id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    name = user['full_name'] if user['full_name'] else user['telegram_id']
    markup.add(InlineKeyboardButton(f"{name}", callback_data=f"bot_user_info:{user['telegram_id']}"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['ANSWER'], callback_data=f"users_bot_send_message_by_admin:{user_id}"))
    return markup

def cancel_markup():
    markup = ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    markup.add(KeyboardButton(KEY_MARKUP['CANCEL']))
    return markup


def wallet_info_markup():
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton(KEY_MARKUP['INCREASE_WALLET_BALANCE'], callback_data="select_payment_method:None"))
    return markup

def wallet_info_specific_markup(amount):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton(KEY_MARKUP['INCREASE_WALLET_BALANCE'], callback_data=f"select_payment_method_specific:{amount}"))
    return markup

def force_join_channel_markup(channel_id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    channel_id = channel_id.replace("@", "")
    markup.add(
        InlineKeyboardButton(KEY_MARKUP['JOIN_CHANNEL'], url=f"https://t.me/{channel_id}",)
    )
    markup.add(
        InlineKeyboardButton(KEY_MARKUP['FORCE_JOIN_CHANNEL_ACCEPTED'], callback_data=f"force_join_status:None")
    )
    return markup


def users_bot_management_settings_panel_manual_markup():
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton(KEY_MARKUP['MANUAL_ANDROID'],
                                    callback_data=f"msg_manual:android"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['MANUAL_IOS'],
                                    callback_data=f"msg_manual:ios"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['MANUAL_WIN'],
                                    callback_data=f"msg_manual:win"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['MANUAL_MAC'],
                                    callback_data=f"msg_manual:mac"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['MANUAL_LIN'],
                                    callback_data=f"msg_manual:lin"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data=f"del_msg:None"))
    return markup

def payment_method_selection_markup(amount=None):
    """Markup for selecting payment method (Card, YooKassa, Pally)."""
    markup = InlineKeyboardMarkup()
    markup.row_width = 1

    settings = all_configs_settings()
    amount_rub = int(int(amount) / 10) if amount else None
    card_callback = f"increase_wallet_balance_specific:{amount}" if amount else "increase_wallet_balance:wallet"
    yookassa_callback = f"yookassa_payment:{amount_rub}" if amount_rub else "yookassa_payment:None"
    pally_callback = f"pally_payment:{amount_rub}" if amount_rub else "pally_payment:None"
    crypto_callback = f"crypto_payment:{amount_rub}" if amount_rub else "crypto_payment:None"

    added = 0
    if settings.get('payment_method_card_enabled', 1):
        markup.add(InlineKeyboardButton(KEY_MARKUP['PAYMENT_METHOD_CARD'], callback_data=card_callback))
        added += 1
    if settings.get('payment_method_yookassa_enabled', 1):
        markup.add(InlineKeyboardButton(KEY_MARKUP['PAYMENT_METHOD_YOOKASSA'], callback_data=yookassa_callback))
        added += 1
    if settings.get('payment_method_pally_enabled', 0):
        markup.add(InlineKeyboardButton(KEY_MARKUP['PAYMENT_METHOD_PALLY'], callback_data=pally_callback))
        added += 1
    if settings.get('payment_method_crypto_enabled', 0):
        markup.add(InlineKeyboardButton(KEY_MARKUP['PAYMENT_METHOD_CRYPTO'], callback_data=crypto_callback))
        added += 1

    if added == 0:
        markup.add(InlineKeyboardButton(KEY_MARKUP['PAYMENT_METHOD_CARD'], callback_data=card_callback))

    markup.add(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data=f"del_msg:None"))
    return markup


def sk_vpn_subscriptions_markup(subscriptions):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    if subscriptions:
        for sub in subscriptions:
            uuid = sub.get('uuid') if isinstance(sub, dict) else None
            if not uuid:
                continue
            title = sub.get('name') if isinstance(sub, dict) else None
            if not title:
                title = sub.get('title') if isinstance(sub, dict) else None
            if not title:
                title = f"Подписка {str(uuid)[:8]}" if uuid else "Подписка"
            cb_val = uuid if uuid else "None"
            remaining = int(sub.get('remaining_day', 0) or 0)
            if not sub.get('active'):
                icon = "❌"
            elif remaining <= 3:
                icon = "⚠️"
            else:
                icon = "✅"
            markup.add(InlineKeyboardButton(f"{icon} {title}", callback_data=f"smartkamavpn_sub_open:{cb_val}"))

    markup.add(InlineKeyboardButton("⚡ Приобрести новую", callback_data="smartkamavpn_buy_sub:None"))
    markup.add(InlineKeyboardButton("🔄 Продлить старую", callback_data="smartkamavpn_renew_menu:None"))
    markup.add(InlineKeyboardButton("🎁 Подарки", callback_data="smartkamavpn_gift:None"))
    markup.add(InlineKeyboardButton("🏠 В титульное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


def sk_renew_subscriptions_markup(subscriptions):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    if subscriptions:
        for sub in subscriptions:
            uuid = sub.get('uuid') if isinstance(sub, dict) else None
            if not uuid:
                continue
            title = sub.get('name') if isinstance(sub, dict) else None
            if not title:
                title = sub.get('title') if isinstance(sub, dict) else None
            if not title:
                title = f"Подписка {str(uuid)[:8]}" if uuid else "Подписка"
            cb_val = uuid if uuid else "None"
            remaining = int(sub.get('remaining_day', 0) or 0)
            if not sub.get('active'):
                icon = "❌"
            elif remaining <= 3:
                icon = "⚠️"
            else:
                icon = "✅"
            markup.add(InlineKeyboardButton(f"{icon} {title}", callback_data=f"smartkamavpn_sub_open:{cb_val}"))
    markup.add(InlineKeyboardButton("🔙 К подпискам", callback_data="smartkamavpn_vpn_menu:None"))
    markup.add(InlineKeyboardButton("🏠 В титульное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


def sk_subscription_actions_markup(uuid, sub_id='-', is_active=True):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("⚙️ Настройка", callback_data=f"smartkamavpn_setup:{uuid}"))
    markup.add(InlineKeyboardButton("📱 Мои устройства", callback_data=f"smartkamavpn_devices:{uuid}:1"))
    markup.add(InlineKeyboardButton("🌐 Подписка и приложения", callback_data=f"smartkamavpn_sub_page:{uuid}"))
    markup.add(InlineKeyboardButton("🔄 Обновить данные", callback_data=f"smartkamavpn_sub_open:{uuid}"))
    markup.add(InlineKeyboardButton("🔄 Продлить подписку", callback_data=f"renewal_subscription:{uuid}"))
    markup.add(InlineKeyboardButton("⚡ Приобрести новую", callback_data="smartkamavpn_buy_sub:None"))
    if is_active:
        markup.add(InlineKeyboardButton("⏸ Приостановить подписку", callback_data=f"smartkamavpn_sub_pause:{uuid}"))
    else:
        markup.add(InlineKeyboardButton("▶️ Возобновить подписку", callback_data=f"smartkamavpn_sub_resume:{uuid}"))
    markup.add(InlineKeyboardButton("🗑 Удалить подписку", callback_data=f"smartkamavpn_sub_delete:{uuid}"))
    markup.add(InlineKeyboardButton("🔙 К подпискам", callback_data="smartkamavpn_vpn_menu:None"))
    markup.add(InlineKeyboardButton("🏠 В титульное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


def sk_sub_delete_confirm_markup(uuid):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("✅ Да, удалить", callback_data=f"smartkamavpn_sub_delete_yes:{uuid}"))
    markup.add(InlineKeyboardButton("❌ Отмена", callback_data=f"smartkamavpn_sub_open:{uuid}"))
    return markup


def sk_setup_markup(uuid):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("🌐 Подписка и приложения", callback_data=f"smartkamavpn_sub_page:{uuid}"))
    markup.add(InlineKeyboardButton("📘 Инструкция", callback_data=f"smartkamavpn_manual:{uuid}"))
    markup.add(InlineKeyboardButton("🆘 Не получается подключить", callback_data=f"smartkamavpn_support:{uuid}"))
    markup.add(InlineKeyboardButton("✅ Готово", callback_data=f"smartkamavpn_done:{uuid}"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data=f"smartkamavpn_sub_open:{uuid}"))
    markup.add(InlineKeyboardButton("🏠 В титульное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


def sk_manual_markup(context, support_username=None):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("🤖 Android", callback_data=f"smartkamavpn_manual:{context}|android"))
    markup.add(InlineKeyboardButton("🍏 iPhone / iPad", callback_data=f"smartkamavpn_manual:{context}|ios"))
    markup.add(InlineKeyboardButton("🖥 Windows", callback_data=f"smartkamavpn_manual:{context}|win"))
    markup.add(InlineKeyboardButton("🍎 Mac", callback_data=f"smartkamavpn_manual:{context}|mac"))
    markup.add(InlineKeyboardButton("🐧 Linux", callback_data=f"smartkamavpn_manual:{context}|lin"))
    if support_username:
        username = str(support_username).replace("@", "")
        markup.add(InlineKeyboardButton("🆘 Написать в поддержку", url=f"https://t.me/{username}"))
    if str(context) == "general":
        markup.add(InlineKeyboardButton("🏠 В главное меню", callback_data="smartkamavpn_title_menu:None"))
    else:
        markup.add(InlineKeyboardButton("🔙 Назад к настройке", callback_data=f"smartkamavpn_setup:{context}"))
        markup.add(InlineKeyboardButton("🏠 В главное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


def sk_manual_detail_markup(context, support_username=None):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    if support_username:
        username = str(support_username).replace("@", "")
        markup.add(InlineKeyboardButton("🆘 Написать в поддержку", url=f"https://t.me/{username}"))
    markup.add(InlineKeyboardButton("✉️ Описать проблему в боте", callback_data="send_ticket_to_support:None"))
    markup.add(InlineKeyboardButton("‹ Назад к руководству", callback_data=f"smartkamavpn_manual:{context}"))
    if str(context) != "general":
        markup.add(InlineKeyboardButton("🔙 Назад к настройке", callback_data=f"smartkamavpn_setup:{context}"))
    markup.add(InlineKeyboardButton("🏠 В главное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


def sk_support_markup(back_callback=None, support_username=None):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    if support_username:
        username = str(support_username).replace("@", "")
        markup.add(InlineKeyboardButton("🆘 Открыть поддержку", url=f"https://t.me/{username}"))
    markup.add(InlineKeyboardButton("✉️ Описать проблему в боте", callback_data="send_ticket_to_support:None"))
    if back_callback:
        markup.add(InlineKeyboardButton("‹ Назад", callback_data=back_callback))
    markup.add(InlineKeyboardButton("🏠 В главное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


def sk_setup_ready_markup(uuid, support_username=None):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("🌐 Подписка и приложения", callback_data=f"smartkamavpn_sub_page:{uuid}"))
    markup.add(InlineKeyboardButton("📱 Показать QR-код подписки", callback_data=f"conf_sub_auto:{uuid}"))
    markup.add(InlineKeyboardButton("📘 Открыть инструкцию", callback_data=f"smartkamavpn_manual:{uuid}"))
    if support_username:
        username = str(support_username).replace("@", "")
        markup.add(InlineKeyboardButton("🆘 Написать в поддержку", url=f"https://t.me/{username}"))
    markup.add(InlineKeyboardButton("✉️ Описать проблему в боте", callback_data="send_ticket_to_support:None"))
    markup.add(InlineKeyboardButton("🏠 В главное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


def sk_devices_markup(uuid, page, total_pages, item_indexes=None):
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    current_page = max(1, int(page) + 1)
    prev_page = current_page - 1 if current_page > 1 else 1
    next_page = current_page + 1 if current_page < total_pages else total_pages
    markup.add(
        InlineKeyboardButton("⬅️", callback_data=f"smartkamavpn_devices:{uuid}:{prev_page}"),
        InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data=f"smartkamavpn_devices:{uuid}:{current_page}"),
        InlineKeyboardButton("➡️", callback_data=f"smartkamavpn_devices:{uuid}:{next_page}")
    )
    if item_indexes:
        for idx in item_indexes:
            pos = int(idx) + 1
            markup.add(
                InlineKeyboardButton(f"🔒 Блок #{pos}", callback_data=f"smartkamavpn_dev_block:{uuid}|{idx}"),
                InlineKeyboardButton(f"🗑 Удалить #{pos}", callback_data=f"smartkamavpn_dev_del:{uuid}|{idx}"),
            )
    markup.add(InlineKeyboardButton("🔙 К подписке", callback_data=f"smartkamavpn_sub_open:{uuid}"))
    markup.add(InlineKeyboardButton("🏠 В титульное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup



def sk_referral_markup(ref_link):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    share_text = "Попробуй SmartKamaVPN — быстрый и надёжный VPN! Переходи по ссылке: " + ref_link
    markup.add(InlineKeyboardButton("📤 Поделиться с другом", switch_inline_query=share_text))
    markup.add(InlineKeyboardButton("📋 Скопировать ссылку", callback_data="smartkamavpn_copy_ref:None"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="smartkamavpn_gift:None"))
    return markup


def sk_params_markup(uuid, home_web_url=None, settings=None):
    if settings is None:
        try:
            from Utils import utils as _utils
            settings = _utils.all_configs_settings()
        except Exception:
            settings = {}
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    # Happ — always shown (нет отдельного флага в админке)
    markup.add(InlineKeyboardButton("📱 Happ / V2RayTun", callback_data=f"smartkamavpn_conf_happ:{uuid}"))
    # Hiddify — visible_conf_hiddify
    if settings.get('visible_conf_hiddify', True):
        markup.add(InlineKeyboardButton("🟢 SmartKamaVPN (Hiddify)", callback_data=f"smartkamavpn_conf_hiddify:{uuid}"))
    # Sing-box — visible_conf_sub_sing_box
    if settings.get('visible_conf_sub_sing_box', True):
        markup.add(InlineKeyboardButton("📦 Sing-box", callback_data=f"smartkamavpn_conf_singbox:{uuid}"))
    # Full Sing-box — visible_conf_sub_full_sing_box
    if settings.get('visible_conf_sub_full_sing_box', False):
        markup.add(InlineKeyboardButton("📦+ Полный Sing-box", callback_data=f"conf_sub_full_sing_box:{uuid}"))
    # Clash — visible_conf_clash
    if settings.get('visible_conf_clash', True):
        markup.add(InlineKeyboardButton("🥷 Clash Meta", callback_data=f"smartkamavpn_conf_clash:{uuid}"))
    # Dir (все конфиги) — visible_conf_dir
    if settings.get('visible_conf_dir', False):
        markup.add(InlineKeyboardButton("📋 Все конфиги (по протоколу)", callback_data=f"conf_dir:{uuid}"))
    # Авто-подключение — visible_conf_sub_auto
    if settings.get('visible_conf_sub_auto', True):
        markup.add(InlineKeyboardButton("⚡ Авто-подключение", callback_data=f"conf_sub_auto:{uuid}"))
    # Универсальная ссылка — visible_conf_sub_url
    if settings.get('visible_conf_sub_url', True):
        markup.add(InlineKeyboardButton("🔗 Универсальная ссылка", callback_data=f"conf_sub_url:{uuid}"))
    # Base64 ссылка — visible_conf_sub_url_b64
    if settings.get('visible_conf_sub_url_b64', False):
        markup.add(InlineKeyboardButton("🔗 Ссылка Base64", callback_data=f"conf_sub_url_b64:{uuid}"))
    if home_web_url:
        markup.add(InlineKeyboardButton("🌐 Открыть сайт подписки", url=home_web_url))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data=f"smartkamavpn_sub_open:{uuid}"))
    markup.add(InlineKeyboardButton("🏠 В титульное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


def sk_help_markup(support_username=None):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("🔰 Первое подключение", callback_data="smartkamavpn_faq:first_connect"))
    markup.add(InlineKeyboardButton("⚠️ Был подключён, но что-то не так", callback_data="smartkamavpn_faq:not_working"))
    markup.add(InlineKeyboardButton("📱 Инструкции по устройствам", callback_data="smartkamavpn_faq:devices_guide"))
    markup.add(InlineKeyboardButton("➕ Как добавить второе устройство", callback_data="smartkamavpn_faq:add_device"))
    markup.add(InlineKeyboardButton("💬 Не работает WhatsApp/Telegram", callback_data="smartkamavpn_faq:messengers"))
    markup.add(InlineKeyboardButton("🌍 Как включить все страны", callback_data="smartkamavpn_faq:all_countries"))
    markup.add(InlineKeyboardButton("🎵 Не работает TikTok", callback_data="smartkamavpn_faq:tiktok"))
    markup.add(InlineKeyboardButton("💰 Сколько стоит VPN", callback_data="smartkamavpn_faq:pricing"))
    if support_username:
        username = str(support_username).replace("@", "")
        markup.add(InlineKeyboardButton("🆘 Написать в поддержку", url=f"https://t.me/{username}"))
    markup.add(InlineKeyboardButton("🏠 В главное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


def sk_about_markup():
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("⭐ Отзывы", callback_data="smartkamavpn_info:reviews"))
    markup.add(InlineKeyboardButton("🔒 Политика", callback_data="smartkamavpn_info:privacy"))
    markup.add(InlineKeyboardButton("📄 Соглашение", callback_data="smartkamavpn_info:agreement"))
    markup.add(InlineKeyboardButton("🗂 Персональные данные", callback_data="smartkamavpn_info:pd"))
    markup.add(InlineKeyboardButton("🛟 Поддержка", callback_data="smartkamavpn_info:support"))
    markup.add(InlineKeyboardButton("📊 Статус системы", callback_data="smartkamavpn_info:status"))
    markup.add(InlineKeyboardButton("📣 Канал", callback_data="smartkamavpn_info:channel"))
    markup.add(InlineKeyboardButton("🏠 В главное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


def my_account_markup(section="overview"):
    """Inline markup for My Account screen with tab navigation."""
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    ovr = "◉ 📋 Обзор" if section == "overview" else "📋 Обзор"
    pay = "◉ 💳 Платежи" if section == "payments" else "💳 Платежи"
    markup.row(
        InlineKeyboardButton(ovr, callback_data="my_account:overview"),
        InlineKeyboardButton(pay, callback_data="my_account:payments"),
    )
    markup.add(InlineKeyboardButton(KEY_MARKUP['MY_ACCOUNT_REFRESH'], callback_data="my_account:refresh"))
    markup.add(InlineKeyboardButton("🏠 В главное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


def smartkamavpn_gift_menu_markup():
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("👥 Пригласить друга и получить бонус", callback_data="smartkamavpn_referral:None"))
    markup.add(InlineKeyboardButton("🎟 Подарить промокод", callback_data="smartkamavpn_gift_promo:None"))
    markup.add(InlineKeyboardButton("🎁 Поделиться подпиской", callback_data="smartkamavpn_gift_subscription:None"))
    markup.add(InlineKeyboardButton("🎫 Мои подарки", callback_data="smartkamavpn_bought_gifts:None"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="smartkamavpn_title_menu:None"))
    return markup


def smartkamavpn_gift_subscription_markup(subscriptions):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    for sub in subscriptions:
        uuid = sub.get('uuid') if isinstance(sub, dict) else None
        if not uuid:
            continue
        title = sub.get('name') if isinstance(sub, dict) else None
        if not title:
            title = sub.get('title') if isinstance(sub, dict) else None
        if not title:
            title = f"Подписка {str(uuid)[:8]}"
        markup.add(InlineKeyboardButton(f"🎁 {title}", callback_data=f"smartkamavpn_gift_sub_pick:{uuid}"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data="smartkamavpn_gift:None"))
    markup.add(InlineKeyboardButton("🏠 В титульное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


def sk_tg_proxy_menu_markup(proxy_link_tg, proxy_link_https):
    """Inline markup for MTProto Telegram proxy section."""
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton(KEY_MARKUP['TG_PROXY_CONNECT'], url=proxy_link_tg))
    markup.add(InlineKeyboardButton(KEY_MARKUP['TG_PROXY_SHARE'], callback_data="smartkamavpn_tg_proxy:share"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['TG_PROXY_QR'], callback_data="smartkamavpn_tg_proxy:qr"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['TG_PROXY_WHAT'], callback_data="smartkamavpn_tg_proxy:what"))
    markup.add(InlineKeyboardButton("🏠 В главное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


def sk_tg_proxy_back_markup():
    """Back button from proxy sub-pages."""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data="smartkamavpn_tg_proxy:menu"))
    return markup


def sk_wa_proxy_menu_markup(server_ip):
    """Inline markup for WhatsApp proxy section."""
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton(KEY_MARKUP['WA_PROXY_COPY'], callback_data="smartkamavpn_wa_proxy:copy"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['WA_PROXY_SHARE'], callback_data="smartkamavpn_wa_proxy:share"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['WA_PROXY_HOW'], callback_data="smartkamavpn_wa_proxy:how"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['WA_PROXY_WHAT'], callback_data="smartkamavpn_wa_proxy:what"))
    markup.add(InlineKeyboardButton("🏠 В главное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


def sk_wa_proxy_back_markup():
    """Back button from WhatsApp proxy sub-pages."""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data="smartkamavpn_wa_proxy:menu"))
    return markup


def sk_signal_proxy_menu_markup(share_link):
    """Inline markup for Signal proxy section."""
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton(KEY_MARKUP['SIGNAL_PROXY_LINK'], url=share_link))
    markup.add(InlineKeyboardButton(KEY_MARKUP['SIGNAL_PROXY_SHARE'], callback_data="smartkamavpn_signal_proxy:share"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['SIGNAL_PROXY_HOW'], callback_data="smartkamavpn_signal_proxy:how"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['SIGNAL_PROXY_WHAT'], callback_data="smartkamavpn_signal_proxy:what"))
    markup.add(InlineKeyboardButton("🏠 В главное меню", callback_data="smartkamavpn_title_menu:None"))
    return markup


def sk_signal_proxy_back_markup():
    """Back button from Signal proxy sub-pages."""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data="smartkamavpn_signal_proxy:menu"))
    return markup
