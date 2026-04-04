# Description: This file contains all the reply and inline keyboard markups used in the bot.
from telebot import types
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from UserBot.content import KEY_MARKUP, MESSAGES
from UserBot.content import MESSAGES
from Utils.utils import rial_to_toman,all_configs_settings
from Utils.api import *

# Main Menu Reply Keyboard Markup
def main_menu_keyboard_markup():
    markup = ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    markup.add(KeyboardButton(KEY_MARKUP['SUBSCRIPTION_STATUS']))
    markup.add(KeyboardButton(KEY_MARKUP['LINK_SUBSCRIPTION']), KeyboardButton(KEY_MARKUP['BUY_SUBSCRIPTION']))
    markup.add(KeyboardButton(KEY_MARKUP['FREE_TEST']), KeyboardButton(KEY_MARKUP['WALLET']))
    # KeyboardButton(KEY_MARKUP['TO_QR']),
    settings = all_configs_settings()
    if settings['msg_faq']:
        markup.add(KeyboardButton(KEY_MARKUP['SEND_TICKET']),
                   KeyboardButton(KEY_MARKUP['MANUAL']), KeyboardButton(KEY_MARKUP['FAQ']))
    else:
        markup.add(KeyboardButton(KEY_MARKUP['SEND_TICKET']),
                   KeyboardButton(KEY_MARKUP['MANUAL']))
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
        markup.add(InlineKeyboardButton(KEY_MARKUP['CONFIGS_HIDDIFY'], callback_data=f"conf_hiddify:{uuid}"))
    if settings['visible_conf_sub_sing_box']:
        markup.add(InlineKeyboardButton(KEY_MARKUP['CONFIGS_SING_BOX'], callback_data=f"conf_sub_sing_box:{uuid}"))
    if settings['visible_conf_sub_full_sing_box']:
        markup.add(InlineKeyboardButton(KEY_MARKUP['CONFIGS_FULL_SING_BOX'],
                                        callback_data=f"conf_sub_full_sing_box:{uuid}"))

    markup.add(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data=f"back_to_user_panel:{uuid}"))

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
    markup.add(*keys)
    return markup


def subscription_type_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("👤 Индивидуальный (2 устройства)", callback_data="buy_type_selected:individual"))
    markup.add(InlineKeyboardButton("👨‍👩‍👧‍👦 Семейный (5 устройств)", callback_data="buy_type_selected:family"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data="del_msg:None"))
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
        InlineKeyboardButton(KEY_MARKUP['INCREASE_WALLET_BALANCE'], callback_data=f"increase_wallet_balance:wallet"))
    return markup

def wallet_info_specific_markup(amount):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton(KEY_MARKUP['INCREASE_WALLET_BALANCE'], callback_data=f"increase_wallet_balance_specific:{amount}"))
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

def payment_method_selection_markup():
    """Markup for selecting payment method (Card or YooKassa)"""
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton(KEY_MARKUP['PAYMENT_METHOD_CARD'], callback_data=f"increase_wallet_balance:wallet"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['PAYMENT_METHOD_YOOKASSA'], callback_data=f"yookassa_payment:None"))
    markup.add(InlineKeyboardButton(KEY_MARKUP['BACK'], callback_data=f"del_msg:None"))
    return markup


def velvet_vpn_subscriptions_markup(subscriptions):
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
            markup.add(InlineKeyboardButton(f"🔹 {title}", callback_data=f"velvet_sub_open:{cb_val}"))
    markup.add(InlineKeyboardButton("🔙 В меню", callback_data="del_msg:None"))
    return markup


def velvet_subscription_actions_markup(uuid, sub_id='-'):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("⚙️ Настройка", callback_data=f"velvet_setup:{uuid}"))
    markup.add(InlineKeyboardButton(f"📱 Мои устройства (#{sub_id})", callback_data=f"velvet_devices:{uuid}:1"))
    markup.add(InlineKeyboardButton("🌐 Подписка", callback_data=f"velvet_params:{uuid}"))
    markup.add(InlineKeyboardButton("🔙 К подпискам", callback_data="velvet_vpn_menu:None"))
    return markup


def velvet_setup_markup(uuid):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("📱 Показать QR-код подписки", callback_data=f"conf_sub_auto:{uuid}"))
    markup.add(InlineKeyboardButton("📘 Инструкция", callback_data=f"velvet_manual:{uuid}"))
    markup.add(InlineKeyboardButton("🆘 Не получается подключить", callback_data=f"velvet_support:{uuid}"))
    markup.add(InlineKeyboardButton("📶 LTE пакеты", callback_data=f"velvet_lte:{uuid}"))
    markup.add(InlineKeyboardButton("✅ Готово", callback_data=f"velvet_done:{uuid}"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data=f"velvet_sub_open:{uuid}"))
    return markup


def velvet_devices_markup(uuid, page, total_pages, item_indexes=None):
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    current_page = max(1, int(page) + 1)
    prev_page = current_page - 1 if current_page > 1 else 1
    next_page = current_page + 1 if current_page < total_pages else total_pages
    markup.add(
        InlineKeyboardButton("⬅️", callback_data=f"velvet_devices:{uuid}:{prev_page}"),
        InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data=f"velvet_devices:{uuid}:{current_page}"),
        InlineKeyboardButton("➡️", callback_data=f"velvet_devices:{uuid}:{next_page}")
    )
    if item_indexes:
        for idx in item_indexes:
            pos = int(idx) + 1
            markup.add(
                InlineKeyboardButton(f"🔒 Блок #{pos}", callback_data=f"velvet_dev_block:{uuid}|{idx}"),
                InlineKeyboardButton(f"🗑 Удалить #{pos}", callback_data=f"velvet_dev_del:{uuid}|{idx}"),
            )
    markup.add(InlineKeyboardButton("🔙 К подписке", callback_data=f"velvet_sub_open:{uuid}"))
    return markup


def velvet_lte_packages_markup(uuid):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("1 ГБ - 99 ₽", callback_data=f"velvet_lte_buy:{uuid}:1:99"))
    markup.add(InlineKeyboardButton("5 ГБ - 399 ₽", callback_data=f"velvet_lte_buy:{uuid}:5:399"))
    markup.add(InlineKeyboardButton("10 ГБ - 699 ₽", callback_data=f"velvet_lte_buy:{uuid}:10:699"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data=f"velvet_setup:{uuid}"))
    return markup


def velvet_referral_markup(ref_link):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("📋 Скопировать ссылку", switch_inline_query=ref_link))
    return markup


def velvet_params_markup(uuid, home_web_url=None):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("🔗 Подписка", callback_data=f"conf_sub_auto:{uuid}"))
    if home_web_url:
        markup.add(InlineKeyboardButton("🌐 Открыть сайт подписки", url=home_web_url))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data=f"velvet_sub_open:{uuid}"))
    return markup


def velvet_help_markup(support_username=None):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    if support_username:
        username = str(support_username).replace("@", "")
        markup.add(InlineKeyboardButton("💬 Поддержка", url=f"https://t.me/{username}"))
    return markup


def velvet_about_markup():
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("📝 Отзывы", callback_data="velvet_info:reviews"))
    markup.add(InlineKeyboardButton("🔐 Политика", callback_data="velvet_info:privacy"))
    markup.add(InlineKeyboardButton("📜 Соглашение", callback_data="velvet_info:agreement"))
    markup.add(InlineKeyboardButton("🗂 Персональные данные", callback_data="velvet_info:pd"))
    markup.add(InlineKeyboardButton("🛡 Поддержка", callback_data="velvet_info:support"))
    return markup
