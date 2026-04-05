import datetime
import random
import os
import time
import sqlite3
import secrets
import string
import re
import html
from urllib.parse import urlparse, quote, parse_qsl, urlencode, urlunparse
import requests

import telebot
from telebot.types import Message, CallbackQuery
from config import *
from AdminBot.templates import configs_template
from UserBot.markups import *
from UserBot.templates import *
from UserBot.content import *

import Utils.utils as utils
from Shared.common import admin_bot
from Database.dbManager import USERS_DB
from Utils import api
from Utils.yookassa import YooKassaPayment, get_yookassa_settings

# *********************************** Configuration Bot ***********************************
bot = telebot.TeleBot(CLIENT_TOKEN, parse_mode="HTML")
try:
    bot.remove_webhook()
except Exception as e:
    logging.warning(f"Failed to remove user bot webhook during init: {e}")
admin_bot = admin_bot()
BASE_URL = f"{urlparse(PANEL_URL).scheme}://{urlparse(PANEL_URL).netloc}"
selected_server_id = 0
buy_subscription_type = {}
_short_link_cache = {}
pending_pally_payments = {}
_MSK_TZ = datetime.timezone(datetime.timedelta(hours=3), name='MSK')

TARIFF_CATALOG = {
    'individual': {
        'max_ips': 2,
        'description': 'индивидуальный (2 телефона + 2 ПК/планшета, до 4 устройств)',
        'plans': [
            {'id': 2101, 'days': 30, 'price_rub': 195},
            {'id': 2103, 'days': 90, 'price_rub': 500},
            {'id': 2106, 'days': 180, 'price_rub': 900},
            {'id': 2112, 'days': 365, 'price_rub': 1600},
        ],
    },
    'family': {
        'max_ips': 5,
        'description': 'семейный (5 телефонов + 3 ПК/планшета, до 8 устройств)',
        'plans': [
            {'id': 2201, 'days': 30, 'price_rub': 195},
            {'id': 2203, 'days': 90, 'price_rub': 500},
            {'id': 2206, 'days': 180, 'price_rub': 900},
            {'id': 2212, 'days': 365, 'price_rub': 1600},
        ],
    },
}

# Initialize YooKassa if configured
yookassa_client = None
if YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY:
    try:
        yookassa_client = YooKassaPayment(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)
        logging.info("YooKassa client initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize YooKassa client: {e}")


def _ensure_yookassa_client():
    global yookassa_client
    if yookassa_client:
        return yookassa_client

    settings = get_yookassa_settings(USERS_DB)
    if not settings:
        return None

    try:
        yookassa_client = YooKassaPayment(settings['shop_id'], settings['secret_key'])
        return yookassa_client
    except Exception as e:
        logging.error(f"Failed to lazy initialize YooKassa client: {e}")
        return None


def _build_pally_payment_url(template, amount_rub, telegram_id, payment_id):
    if not template:
        return None
    url = str(template).strip()
    if not url:
        return None

    try:
        return url.format(amount=amount_rub, telegram_id=telegram_id, payment_id=payment_id)
    except Exception:
        delimiter = '&' if '?' in url else '?'
        return f"{url}{delimiter}amount={amount_rub}&telegram_id={telegram_id}&payment_id={payment_id}"


def _generate_gift_code():
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(10):
        code = f"SKV-{''.join(secrets.choice(alphabet) for _ in range(6))}"
        if not USERS_DB.find_gift_promo_code(code=code):
            return code
    return f"SKV-{int(time.time()) % 1000000:06d}"

# *********************************** Helper Functions ***********************************
# Check if message is digit
def is_it_digit(message: Message,allow_float=False, response=MESSAGES['ERROR_INVALID_NUMBER'], markup=main_menu_keyboard_markup()):
    if not message.text:
        bot.send_message(message.chat.id, response, reply_markup=markup)
        return False
    try:
        value = float(message.text) if allow_float else int(message.text)
        return True
    except ValueError:
        bot.send_message(message.chat.id, response, reply_markup=markup)
        return False


# Check if message is cancel
def is_it_cancel(message: Message, response=MESSAGES['CANCELED']):
    if message.text == KEY_MARKUP['CANCEL']:
        bot.send_message(message.chat.id, response, reply_markup=main_menu_keyboard_markup())
        return True
    return False


# Check if message is command
def is_it_command(message: Message):
    if message.text.startswith("/"):
        return True
    return False


# Check is it UUID, Config or Subscription Link
def type_of_subscription(text):
    if text.startswith("vmess://"):
        config = text.replace("vmess://", "")
        config = utils.base64decoder(config)
        if not config:
            return False
        uuid = config['id']
    else:
        uuid = utils.extract_uuid_from_config(text)
    return uuid

# check is user banned
def is_user_banned(user_id):
    user = USERS_DB.find_user(telegram_id=user_id)
    if user:
        user = user[0]
        if user['banned']:
            bot.send_message(user_id, MESSAGES['BANNED_USER'], reply_markup=main_menu_keyboard_markup())
            return True
    return False
# *********************************** Next-Step Handlers ***********************************
# ----------------------------------- Buy Plan Area -----------------------------------
charge_wallet = {}
renew_subscription_dict = {}


def user_channel_status(user_id):
    try:
        settings = utils.all_configs_settings()
        if settings['channel_id']:
            user = bot.get_chat_member(settings['channel_id'], user_id)
            return user.status in ['member', 'administrator', 'creator']
        else:
            return True
    except telebot.apihelper.ApiException as e:
        logging.error("ApiException: %s" % e)
        return False


def is_user_in_channel(user_id):
    settings = all_configs_settings()
    if settings['force_join_channel'] == 1:
        if not settings['channel_id']:
            return True
        if not user_channel_status(user_id):
            bot.send_message(user_id, MESSAGES['REQUEST_JOIN_CHANNEL'],
                             reply_markup=force_join_channel_markup(settings['channel_id']))
            return False
    return True


def _build_channel_link(settings):
    channel_id = settings.get('channel_id')
    if not channel_id:
        return "не указан"
    if str(channel_id).startswith('@'):
        return f"https://t.me/{str(channel_id).replace('@', '')}"
    return str(channel_id)


def _build_status_link(settings):
    status_cfg = USERS_DB.find_str_config(key='status_page_url')
    if status_cfg and status_cfg[0].get('value'):
        return status_cfg[0]['value']
    return "не указан"


def _get_main_server():
    default_servers = USERS_DB.find_server(default_server=True)
    if default_servers:
        return default_servers[0]
    servers = USERS_DB.select_servers()
    if servers:
        return servers[0]
    return None


def _plan_type_from_max_ips(max_ips):
    normalized = _normalize_tariff_max_ips(max_ips)
    if normalized == 5:
        return 'family'
    if normalized == 2:
        return 'individual'
    if normalized and normalized > 2:
        return 'family'
    return 'individual'


def _plan_device_limit(plan):
    plan_id = int(plan.get('id', 0) or 0)
    if 2200 < plan_id < 2300:
        return 5
    if 2100 < plan_id < 2200:
        return 2

    desc = str(plan.get('description') or '').lower()
    if '5 устрой' in desc or 'семейн' in desc or 'family' in desc:
        return 5
    return 2


def _to_positive_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        iv = int(value)
        return iv if iv > 0 else None
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.isdigit():
            iv = int(cleaned)
            return iv if iv > 0 else None
    return None


def _extract_max_ips_from_comment(comment):
    if not comment:
        return None
    text = str(comment)
    m = re.search(r"(?:^|[;,\s])max_ips\s*=\s*(\d+)(?:$|[;,\s])", text, flags=re.IGNORECASE)
    if not m:
        return None
    return _to_positive_int(m.group(1))


def _normalize_tariff_max_ips(value, default=2):
    normalized = _to_positive_int(value)
    if normalized in (2, 4):
        return 2
    if normalized in (5, 8):
        return 5
    if normalized == 5:
        return 5
    if normalized == 2:
        return 2
    if normalized and normalized > 2:
        return 2
    if normalized and normalized < 2:
        return 2
    return default


def _tariff_device_policy(max_ips):
    normalized = _normalize_tariff_max_ips(max_ips)
    if normalized == 5:
        return {
            'plan': 'family',
            'phones': 5,
            'desktop_tablet': 3,
            'total': 8,
        }
    return {
        'plan': 'individual',
        'phones': 2,
        'desktop_tablet': 2,
        'total': 4,
    }


def _total_device_limit(max_ips):
    return _tariff_device_policy(max_ips)['total']


def _device_policy_label(max_ips):
    p = _tariff_device_policy(max_ips)
    plan_name = 'семейный' if p['plan'] == 'family' else 'индивидуальный'
    return f"{plan_name}: {p['phones']} телефонов + {p['desktop_tablet']} ПК/планшетов (до {p['total']} устройств)"


def _extract_tariff_type_from_comment(comment):
    text = str(comment or '').lower()
    if not text:
        return None
    if 'type=family' in text or 'семейн' in text or '5 устрой' in text or '5 device' in text:
        return 'family'
    if 'type=individual' in text or 'индив' in text or '2 устрой' in text or '2 device' in text:
        return 'individual'
    return None


def _resolve_user_max_ips(raw_user, sub_record):
    # Hard tariff policy: only 2 (individual) or 5 (family) devices.
    if isinstance(raw_user, dict):
        from_comment_type = _extract_tariff_type_from_comment(raw_user.get('comment'))
        if from_comment_type == 'family':
            return 5
        if from_comment_type == 'individual':
            return 2

        for key in ('max_ips', 'maxIps', 'max_clients', 'maxClients'):
            value = _normalize_tariff_max_ips(raw_user.get(key), default=None)
            if value:
                return value

        from_comment = _extract_max_ips_from_comment(raw_user.get('comment'))
        if from_comment:
            return _normalize_tariff_max_ips(from_comment)

    if isinstance(sub_record, dict):
        order_id = sub_record.get('order_id')
        if order_id:
            orders = USERS_DB.find_order(id=order_id)
            if orders:
                order = orders[0]
                plan_id = order.get('plan_id')
                if plan_id:
                    plans = USERS_DB.find_plan(id=plan_id)
                    if plans:
                        return _normalize_tariff_max_ips(_plan_device_limit(plans[0]))

    # Fallback for legacy/linked subscriptions without order metadata.
    return 2


def _plan_type_label(max_ips):
    if isinstance(max_ips, int) and max_ips > 0:
        return _device_policy_label(max_ips)
    return _device_policy_label(2)


def _device_category_from_text(text):
    t = (text or '').lower()
    if any(k in t for k in ('android', 'ios', 'iphone', 'redmi', 'samsung', 'pixel', 'phone', 'телефон', 'смартфон', 'айфон')):
        return 'phone'
    if any(k in t for k in ('ipad', 'tablet', 'tab', 'планшет')):
        return 'tablet'
    if any(k in t for k in ('tv', 'android tv', 'smart tv', 'apple tv', 'телевизор', 'тв')):
        return 'tv'
    if any(k in t for k in ('windows', 'mac', 'linux', 'ubuntu', 'debian', 'pc', 'desktop', 'laptop', 'ноут', 'компьютер', 'пк')):
        return 'pc'
    return 'other'


def _device_usage_summary(devices):
    counts = {'phone': 0, 'tablet': 0, 'pc': 0, 'tv': 0, 'other': 0}
    for item in devices or []:
        counts[_device_category_from_text(item)] += 1
    return (
        f"📱 Телефоны: {counts['phone']}\n"
        f"📟 Планшеты: {counts['tablet']}\n"
        f"💻 Компьютеры: {counts['pc']}\n"
        f"📺 ТВ: {counts['tv']}\n"
        f"🔎 Другое: {counts['other']}"
    )


def _device_icon_from_entry(entry):
    probe = " ".join(
        [
            str(entry.get('name') or ''),
            str(entry.get('label') or ''),
            str(entry.get('os') or ''),
            str(entry.get('platform') or ''),
            str(entry.get('app') or ''),
            str(entry.get('client') or ''),
            str(entry.get('user_agent') or ''),
        ]
    )
    category = _device_category_from_text(probe)
    return {
        'phone': '📱',
        'tablet': '📟',
        'pc': '💻',
        'tv': '📺',
        'other': '🔎',
    }.get(category, '🔎')


def _parse_device_datetime_msk(value):
    if value is None:
        return None

    raw = str(value).strip()
    if not raw or raw in ('0', 'None', 'none', 'null', '1-01-01 00:00:00'):
        return None

    # Unix timestamp (sec/ms) -> MSK
    try:
        num = float(raw)
        if num > 0:
            if num > 10_000_000_000:
                num = num / 1000.0
            dt = datetime.datetime.fromtimestamp(num, tz=datetime.timezone.utc)
            return dt.astimezone(_MSK_TZ)
    except Exception:
        pass

    iso_candidate = raw.replace('Z', '+00:00')
    try:
        dt = datetime.datetime.fromisoformat(iso_candidate)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_MSK_TZ)
        return dt.astimezone(_MSK_TZ)
    except Exception:
        pass

    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%d.%m.%Y %H:%M', '%d.%m.%y %H:%M'):
        try:
            dt = datetime.datetime.strptime(raw, fmt).replace(tzinfo=_MSK_TZ)
            return dt
        except Exception:
            continue

    try:
        dt_short = datetime.datetime.strptime(raw, '%d.%m %H:%M')
        now_msk = datetime.datetime.now(_MSK_TZ)
        dt = dt_short.replace(year=now_msk.year, tzinfo=_MSK_TZ)
        return dt
    except Exception:
        return None


def _extract_device_added_at(entry):
    for key in (
        'added_at', 'addedAt', 'first_seen', 'firstSeen',
        'last_seen', 'lastSeen', 'last_online', 'time', 'timestamp', 'ts',
    ):
        dt = _parse_device_datetime_msk(entry.get(key))
        if dt:
            return dt

    label = str(entry.get('label') or '')
    patterns = [
        r"online:\s*([0-3]?\d\.[01]?\d(?:\.\d{2,4})?\s+[0-2]\d:[0-5]\d)",
        r"last=([0-9\-\.T: ]+)",
        r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)",
        r"([0-3]?\d\.[01]?\d(?:\.\d{2,4})?\s+[0-2]\d:[0-5]\d)",
    ]
    for pattern in patterns:
        m = re.search(pattern, label, flags=re.IGNORECASE)
        if not m:
            continue
        dt = _parse_device_datetime_msk(m.group(1))
        if dt:
            return dt
    return None


def _device_display_name(entry):
    label = str(entry.get('label') or '').strip()
    raw_ua = str(entry.get('user_agent') or '').strip()

    for key in ('name', 'device', 'model'):
        value = str(entry.get(key) or '').strip()
        if value:
            return value

    if raw_ua and raw_ua.lower() != 'panel-last-online':
        return raw_ua

    if label:
        title = label.split('|', 1)[0].strip()
        if title:
            return title

    ip = str(entry.get('ip') or '').strip()
    return ip or 'Устройство'


def _device_os_label(entry):
    value = str(entry.get('os') or entry.get('platform') or '').strip()
    return value or 'Неизвестная ОС'


def _device_app_label(entry):
    value = str(entry.get('app') or entry.get('client') or '').strip()
    if value.lower() == 'panel-last-online':
        return 'Активность в панели'
    return value or 'Неизвестное приложение'


def _format_device_card(index, entry):
    icon = _device_icon_from_entry(entry)
    name = html.escape(_device_display_name(entry))
    os_name = html.escape(_device_os_label(entry))
    app_name = html.escape(_device_app_label(entry))
    added_at = _extract_device_added_at(entry)
    added_text = added_at.strftime('%d.%m.%y %H:%M') if added_at else 'нет данных'
    return (
        f"{index}. {icon} {name}\n"
        f"• {os_name}\n"
        f"• {app_name}\n"
        f"• Добавлено: {added_text} (MSK)"
    )


def _device_actions_supported():
    try:
        caps = api.get_provider_capabilities()
        if isinstance(caps, dict):
            return bool(caps.get('device_actions', True))
    except Exception as e:
        logging.debug("Failed to resolve provider capabilities: %s", e)
    return True


def _resolve_display_sub_id(uuid, raw_user=None, sub_data=None, sub_record=None):
    candidates = []
    if isinstance(raw_user, dict):
        candidates.append(raw_user.get('sub_id'))
    if isinstance(sub_data, dict):
        candidates.append(sub_data.get('sub_id'))
    if isinstance(sub_record, dict):
        candidates.append(sub_record.get('sub_id'))

    for value in candidates:
        token = str(value or '').strip()
        if not token:
            continue
        # Показываем только пользовательский sub_id вида 8+ alnum.
        if re.fullmatch(r"[A-Za-z0-9]{8,}", token):
            return token[:8]

    return str(uuid or '')[:8] or '-'


def _prepare_velvet_devices_screen(uuid, requested_page=0):
    page_size = 5
    page = max(0, int(requested_page or 0))

    server_url = _get_server_api_url_by_uuid(uuid)
    raw_user = api.find(server_url, uuid=uuid) if server_url else None
    device_entries = _extract_device_entries(raw_user)

    sub_record = utils.find_order_subscription_by_uuid(uuid) or {}
    max_ips = _resolve_user_max_ips(raw_user, sub_record)
    _sync_user_max_ips(server_url, uuid, raw_user, max_ips)
    can_manage_devices = _device_actions_supported()

    trimmed = _enforce_device_limit(server_url, uuid, raw_user, max_ips)
    if trimmed > 0:
        raw_user = api.find(server_url, uuid=uuid) if server_url else raw_user
        device_entries = _extract_device_entries(raw_user)

    policy = _tariff_device_policy(max_ips)
    limit_label = policy['total']
    sub_id = _resolve_display_sub_id(uuid, raw_user=raw_user, sub_record=sub_record)
    total = len(device_entries)

    if total <= 0:
        device_action_note = "\n\nℹ️ Для текущего провайдера панели управление устройствами недоступно." if not can_manage_devices else ""
        text = (
            f"🏠 Главная › 🛒 Управление VPN › 🔑 Подписка #{sub_id} › 📱 Устройства\n\n"
            f"Ваши устройства: 0/{limit_label}\n\n"
            f"📌Лимит: {policy['phones']} телефонов + {policy['desktop_tablet']} ПК/планшетов\n\n"
            f"{MESSAGES['VELVET_DEVICES_EMPTY']}{device_action_note}"
        )
        return text, 0, 1, []

    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages - 1)
    start_idx = page * page_size
    page_entries = device_entries[start_idx:(page + 1) * page_size]

    if can_manage_devices:
        page_item_indexes = [
            start_idx + offset
            for offset, entry in enumerate(page_entries)
            if _is_actionable_device_key(entry.get('key'))
        ]
    else:
        page_item_indexes = []

    cards = [
        _format_device_card(start_idx + offset + 1, entry)
        for offset, entry in enumerate(page_entries)
    ]
    cards_text = "\n\n".join(cards)
    shown_from = start_idx + 1
    shown_to = start_idx + len(page_entries)

    device_action_note = "\n\nℹ️ Для текущего провайдера панели управление устройствами недоступно." if not can_manage_devices else ""
    text = (
        f"🏠 Главная › 🛒 Управление VPN › 🔑 Подписка #{sub_id} › 📱 Устройства\n\n"
        f"Ваши устройства: {total}/{limit_label}\n\n"
        f"📌Лимит: {policy['phones']} телефонов + {policy['desktop_tablet']} ПК/планшетов\n\n"
        f"Подключенные устройства:\n\n"
        f"{cards_text}\n\n"
        f"📄 Показано {shown_from}-{shown_to} из {total}{device_action_note}"
    )
    return text, page, total_pages, page_item_indexes


def _build_setup_v2_text(uuid, sub_id):
    server_url = _get_server_api_url_by_uuid(uuid)
    source_url = None
    if server_url:
        links = utils.sub_links(uuid, url=server_url.replace(API_PATH, ''))
        if links:
            source_url = links.get('sub_link') or links.get('sub_link_auto')
    if not source_url:
        links = utils.sub_links(uuid)
        source_url = (links or {}).get('sub_link') or (links or {}).get('sub_link_auto')
    if not source_url:
        return MESSAGES['VELVET_SETUP_TEXT'].format(sub_id=sub_id)

    happ_source_url = _add_url_query_params(source_url, {'app': '1', 'client': 'happ'})
    hiddify_source_url = _add_url_query_params(source_url, {'app': '1', 'client': 'hiddify'})

    happ_encoded = quote(happ_source_url, safe='')
    hiddify_encoded = quote(hiddify_source_url, safe='')
    happ_deeplink = f"v2raytun://install-config?url={happ_encoded}"
    hiddify_deeplink = f"hiddify://install-config?url={hiddify_encoded}"

    return (
        f"🔧Настройка SmartKamaVPN #{sub_id}\n\n"
        f"1️⃣ Установите приложение:\n"
        f"• iPhone: <a href=\"https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973\">App Store (RU)</a> | "
        f"<a href=\"https://apps.apple.com/us/app/happ-proxy-utility/id6504287215\">App Store (Global)</a>\n"
        f"• Android: <a href=\"https://play.google.com/store/apps/details?id=com.happproxy\">Google Play</a> | "
        f"<a href=\"https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk\">APK</a>\n"
        f"• Windows: <a href=\"https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe\">Скачать</a>\n"
        f"• Linux: <a href=\"https://github.com/Happ-proxy/happ-desktop/releases/\">GitHub релизы</a>\n\n"
        f"2️⃣ Добавьте подписку:\n"
        f"• Авто-импорт (V2RayTun): <code>{html.escape(happ_deeplink)}</code>\n"
        f"• Авто-импорт (Hiddify): <code>{html.escape(hiddify_deeplink)}</code>\n"
        f"• Универсальная ссылка подписки: <code>{html.escape(source_url)}</code>\n\n"
        f"Если авто-импорт не сработал, нажмите «🔧 Ручная настройка» или «🆘 Не получается подключить»."
    )


def _add_url_query_params(url, extra_params):
    if not url:
        return url
    parsed = urlparse(url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    changed = False
    for key, value in (extra_params or {}).items():
        if value is None:
            continue
        value_text = str(value)
        if params.get(key) == value_text:
            continue
        params[key] = value_text
        changed = True

    if not changed:
        return url

    new_query = urlencode(params, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


def _direct_home_url_from_sub_link(sub_link):
    if not sub_link:
        return None
    parsed = urlparse(sub_link)
    parts = [p for p in (parsed.path or '').split('/') if p]
    uuid_idx = None
    for i, p in enumerate(parts):
        if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", p):
            uuid_idx = i
            break
    if uuid_idx is None:
        return None
    direct_path = "/" + "/".join(parts[:uuid_idx + 1]) + "/"
    return f"{parsed.scheme}://{parsed.netloc}{direct_path}?home=true"


def _short_link_base():
    parsed = urlparse(PANEL_URL)
    return f"{parsed.scheme}://{parsed.netloc}/s"


def _ensure_short_links_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS short_links (
            token TEXT PRIMARY KEY,
            target_url TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS short_links_meta (
            token TEXT PRIMARY KEY,
            remaining_days INTEGER,
            remaining_hours INTEGER,
            remaining_minutes INTEGER,
            usage_current REAL,
            usage_limit REAL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(token) REFERENCES short_links(token) ON DELETE CASCADE
        )
        """
    )
    conn.commit()


def _get_or_create_short_token(target_url):
    conn = sqlite3.connect(USERS_DB_LOC)
    try:
        _ensure_short_links_table(conn)
        row = conn.execute("SELECT token FROM short_links WHERE target_url=?", (target_url,)).fetchone()
        if row:
            return row[0]

        alphabet = string.ascii_lowercase + string.digits
        for _ in range(20):
            token = ''.join(secrets.choice(alphabet) for _ in range(5))
            exists = conn.execute("SELECT 1 FROM short_links WHERE token=?", (token,)).fetchone()
            if exists:
                continue
            conn.execute(
                "INSERT INTO short_links(token, target_url, created_at) VALUES(?,?,?)",
                (token, target_url, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            return token

        # Fallback to a longer token if collisions continue.
        token = ''.join(secrets.choice(alphabet) for _ in range(8))
        conn.execute(
            "INSERT OR REPLACE INTO short_links(token, target_url, created_at) VALUES(?,?,?)",
            (token, target_url, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        return token
    finally:
        conn.close()


def _shorten_url(url):
    if not url:
        return url
    if url in _short_link_cache:
        return _short_link_cache[url]

    try:
        token = _get_or_create_short_token(url)
        short = f"{_short_link_base()}/{token}"
        _short_link_cache[url] = short
        return short
    except Exception as e:
        logging.warning(f"Failed to create internal short link: {e}")
        _short_link_cache[url] = url
        return url


def _remaining_time_parts(remaining_day):
    try:
        import pytz
        now = datetime.datetime.now(pytz.timezone('Asia/Tehran'))
    except Exception:
        now = datetime.datetime.now()

    days = int(remaining_day) if remaining_day is not None else 0
    if days <= 0:
        return 0, 0, 0

    minutes_to_midnight = (24 * 60) - (now.hour * 60 + now.minute)
    if minutes_to_midnight < 0:
        minutes_to_midnight = 0
    total_minutes = max(0, (days - 1) * 24 * 60 + minutes_to_midnight)

    d = total_minutes // (24 * 60)
    h = (total_minutes % (24 * 60)) // 60
    m = total_minutes % 60
    return d, h, m


def _format_time_left(remaining_day):
    d, h, m = _remaining_time_parts(remaining_day)
    return f"{d} дн. {h} ч. {m} мин."


def _total_hours_left(remaining_day):
    d, h, _ = _remaining_time_parts(remaining_day)
    return (d * 24) + h


def _format_expire_at(remaining_day):
    try:
        import pytz
        now = datetime.datetime.now(pytz.timezone('Asia/Tehran'))
    except Exception:
        now = datetime.datetime.now()

    try:
        days_value = float(remaining_day or 0)
    except (TypeError, ValueError):
        days_value = 0.0

    if days_value <= 0:
        return "истекло"

    return (now + datetime.timedelta(days=days_value)).strftime("%d.%m.%Y %H:%M")


def _usage_numbers(usage):
    usage = usage if isinstance(usage, dict) else {}
    used = float(usage.get('current_usage_GB', 0) or 0)
    limit = float(usage.get('usage_limit_GB', 0) or 0)
    remaining = max(0.0, limit - used)
    return used, limit, remaining


def _save_short_link_meta(token, sub_data):
    if not token or not isinstance(sub_data, dict):
        return

    usage = sub_data.get('usage', {}) if isinstance(sub_data.get('usage'), dict) else {}
    remaining_day = sub_data.get('remaining_day', 0)
    d, h, m = _remaining_time_parts(remaining_day)

    conn = sqlite3.connect(USERS_DB_LOC)
    try:
        _ensure_short_links_table(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO short_links_meta(
                token, remaining_days, remaining_hours, remaining_minutes,
                usage_current, usage_limit, updated_at
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (
                token,
                int(d),
                int(h),
                int(m),
                float(usage.get('current_usage_GB', 0) or 0),
                float(usage.get('usage_limit_GB', 0) or 0),
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _shorten_subscription_url(url, sub_data=None):
    if not url:
        return url

    try:
        token = _get_or_create_short_token(url)
        if sub_data:
            _save_short_link_meta(token, sub_data)
        short = f"{_short_link_base()}/{token}"
        short_app = f"{short}?app=1" if '?' not in short else f"{short}&app=1"
        _short_link_cache[url] = short_app
        return short_app
    except Exception as e:
        logging.warning(f"Failed to build subscription short link: {e}")
        return _shorten_url(url)


def _subscription_belongs_to_user(uuid, telegram_id):
    if utils.is_it_subscription_by_uuid_and_telegram_id(uuid, telegram_id):
        return True
    for sub in _get_subscriptions_for_user(telegram_id):
        if str(sub.get('uuid')) == str(uuid):
            return True
    return False


def _ensure_single_server_tariff_plans():
    server = _get_main_server()
    if not server:
        return False

    # Internal prices are x10; UI converts to visible rub with rial_to_toman.
    for tariff in TARIFF_CATALOG.values():
        for item in tariff['plans']:
            plan_id = item['id']
            payload = {
                'size_gb': 1000,
                'days': item['days'],
                'price': item['price_rub'] * 10,
                'server_id': server['id'],
                'description': tariff['description'],
                'status': True,
            }
            exists = USERS_DB.find_plan(id=plan_id)
            if exists:
                USERS_DB.edit_plan(
                    plan_id,
                    size_gb=payload['size_gb'],
                    days=payload['days'],
                    price=payload['price'],
                    server_id=payload['server_id'],
                    description=payload['description'],
                    status=payload['status'],
                )
            else:
                USERS_DB.add_plan(
                    plan_id,
                    payload['size_gb'],
                    payload['days'],
                    payload['price'],
                    payload['server_id'],
                    description=payload['description'],
                    status=payload['status'],
                )
    return True


def _get_subscriptions_for_user(telegram_id):
    subs = []
    for item in (utils.order_user_info(telegram_id) + utils.non_order_user_info(telegram_id)):
        active = item['remaining_day'] > 0 and item['usage']['remaining_usage_GB'] > 0
        subs.append({
            'uuid': item['uuid'],
            'sub_id': item['sub_id'],
            'remaining_day': item['remaining_day'],
            'active': active,
            'usage': item['usage'],
            'server_id': item.get('server_id'),
        })
    # Active first, then by remaining days descending.
    subs.sort(key=lambda x: (x['active'], x['remaining_day']), reverse=True)
    return subs


def _get_server_api_url_by_uuid(uuid):
    sub = utils.find_order_subscription_by_uuid(uuid)
    if sub and sub.get('server_id'):
        server = USERS_DB.find_server(id=sub['server_id'])
        if server:
            api_url = server[0]['url'] + API_PATH
            try:
                if api.find(api_url, uuid=uuid):
                    return api_url
            except Exception:
                pass

    # Fallback: search user UUID across all configured servers.
    servers = USERS_DB.select_servers() or []
    for server in servers:
        api_url = server['url'] + API_PATH
        try:
            if api.find(api_url, uuid=uuid):
                return api_url
        except Exception:
            continue

    main_server = _get_main_server()
    if not main_server:
        return None
    return main_server['url'] + API_PATH


def _extract_devices(raw_user):
    return [entry['label'] for entry in _extract_device_entries(raw_user)]


def _extract_device_entries(raw_user):
    if not raw_user:
        return []

    candidate_keys = ['ips', 'connected_ips', 'online_ips', 'devices', 'clients']
    entries = []

    def _append_entry(label, action_key=None, name=None, os_name=None, app_name=None, added_at=None):
        clean_label = str(label or '').strip()
        if not clean_label:
            return
        clean_key = str(action_key or '').strip() if action_key else ''
        entries.append({
            'label': clean_label,
            'key': clean_key or clean_label,
            'name': str(name or '').strip(),
            'os': str(os_name or '').strip(),
            'app': str(app_name or '').strip(),
            'added_at': added_at,
            'ip': str((action_key or '') if str(action_key or '').strip() else '').strip(),
            'user_agent': str(name or '').strip(),
            'platform': str(os_name or '').strip(),
            'client': str(app_name or '').strip(),
        })

    for key in candidate_keys:
        value = raw_user.get(key)
        if not value:
            continue
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    title = item.get('name') or item.get('device') or item.get('model') or item.get('user_agent') or item.get('userAgent') or item.get('label') or item.get('ip')
                    os_name = item.get('os') or item.get('platform')
                    app_name = item.get('app') or item.get('client') or item.get('user_agent') or item.get('userAgent')
                    device_key = item.get('key') or item.get('ip') or item.get('name') or item.get('device') or item.get('id')
                    added_at = (
                        item.get('added_at') or item.get('addedAt') or item.get('first_seen') or
                        item.get('firstSeen') or item.get('last_seen') or item.get('lastSeen') or
                        item.get('last_online') or item.get('time')
                    )
                    label = item.get('label') or ' | '.join([x for x in [title, os_name, app_name] if x])
                    _append_entry(label or title, action_key=device_key, name=title, os_name=os_name, app_name=app_name, added_at=added_at)
                elif isinstance(item, str):
                    _append_entry(item, action_key=item)
        elif isinstance(value, dict):
            for dev_key, dev_val in value.items():
                if isinstance(dev_val, dict):
                    title = dev_val.get('name') or dev_val.get('device') or dev_val.get('label') or str(dev_key)
                    os_name = dev_val.get('os') or dev_val.get('platform') or ''
                    app_name = dev_val.get('app') or dev_val.get('client') or dev_val.get('user_agent') or dev_val.get('userAgent') or ''
                    added_at = (
                        dev_val.get('added_at') or dev_val.get('addedAt') or dev_val.get('first_seen') or
                        dev_val.get('firstSeen') or dev_val.get('last_seen') or dev_val.get('lastSeen') or
                        dev_val.get('last_online') or dev_val.get('time')
                    )
                    label = dev_val.get('label') or ' | '.join([x for x in [title, os_name, app_name] if x])
                    _append_entry(label, action_key=dev_val.get('key') or dev_val.get('ip') or dev_key, name=title, os_name=os_name, app_name=app_name, added_at=added_at)
                else:
                    _append_entry(str(dev_key), action_key=dev_key)

    seen = set()
    result = []
    for item in entries:
        fingerprint = f"{item['label']}|{item['key']}"
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        result.append(item)
    return result


def _is_actionable_device_key(device_key):
    key = str(device_key or '').strip().lower()
    if not key:
        return False
    if key.startswith('virtual:'):
        return False
    if key.startswith('dev:'):
        return True
    if re.search(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)", key):
        return True
    if ':' in key and re.search(r"\b(?:[0-9a-f]{1,4}:){2,}[0-9a-f:]{1,4}\b", key):
        return True
    return False


def _sync_user_max_ips(server_url, uuid, raw_user, max_ips):
    if not server_url or not isinstance(raw_user, dict):
        return False
    if not isinstance(max_ips, int) or max_ips <= 0:
        return False
    desired_total_limit = _total_device_limit(max_ips)
    current = _to_positive_int(raw_user.get('max_ips'))
    if current == desired_total_limit:
        return False
    status = api.update(server_url, uuid, max_ips=desired_total_limit)
    if status:
        raw_user['max_ips'] = desired_total_limit
        return True
    return False


def _enforce_device_limit(server_url, uuid, raw_user, max_ips):
    if not server_url or not isinstance(raw_user, dict):
        return 0
    if not isinstance(max_ips, int) or max_ips <= 0:
        return 0
    desired_total_limit = _total_device_limit(max_ips)

    entries = _extract_device_entries(raw_user)
    overflow = len(entries) - desired_total_limit
    if overflow <= 0:
        return 0

    removed = 0
    for item in entries[desired_total_limit:]:
        key = item.get('key')
        if not _is_actionable_device_key(key):
            continue
        if api.delete_device(server_url, uuid, key):
            removed += 1
    return removed


def _send_velvet_main_menu(chat_id):
    settings = utils.all_configs_settings()
    wallet = USERS_DB.find_wallet(telegram_id=chat_id)
    balance = 0
    if wallet:
        balance = int(wallet[0]['balance'])

    subscriptions = _get_subscriptions_for_user(chat_id)
    active_subs = [s for s in subscriptions if s.get('active')]
    if active_subs:
        nearest = sorted(active_subs, key=lambda s: s.get('remaining_day', 0))[0]
        time_left = _format_time_left(nearest.get('remaining_day', 0))
        _used, limit, remaining = _usage_numbers(nearest.get('usage'))
        sub_status_text = f"активна, осталось {time_left}, трафик: {remaining:.2f}/{limit:.2f} ГБ"
    elif subscriptions:
        sub_status_text = "подписки есть, но активных нет"
    else:
        sub_status_text = "активной подписки нет"

    msg = MESSAGES['VELVET_MAIN_MENU'].format(
        bonus=utils.rial_to_toman(balance),
        channel_link=_build_channel_link(settings),
        subscription_status=sub_status_text,
    )
    bot.send_message(chat_id, msg, reply_markup=main_menu_keyboard_markup())


def _send_velvet_vpn_menu(chat_id):
    subscriptions = _get_subscriptions_for_user(chat_id)
    if not subscriptions:
        bot.send_message(chat_id, MESSAGES['VELVET_NO_SUBS'], reply_markup=velvet_vpn_subscriptions_markup([]))
        return
    bot.send_message(chat_id, MESSAGES['VELVET_VPN_MENU'], reply_markup=velvet_vpn_subscriptions_markup(subscriptions))


def _safe_edit_message_text(**kwargs):
    try:
        return bot.edit_message_text(**kwargs)
    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" in str(e).lower():
            return None
        raise


def _render_subscription_details(uuid):
    sub_data = None
    server_url = _get_server_api_url_by_uuid(uuid)
    if not server_url:
        return None

    all_subs = utils.order_user_info(0) if False else []
    del all_subs

    # Search the selected subscription among all known subscriptions for current user is done in caller.
    user_raw = api.find(server_url, uuid=uuid)
    user_info = utils.users_to_dict([user_raw]) if user_raw else None
    processed = utils.dict_process(server_url, user_info) if user_info else None
    if processed:
        sub_data = processed[0]

    links = utils.sub_links(uuid, url=server_url.replace(API_PATH, ''))
    if not links or not sub_data:
        return None

    sub_record = utils.find_order_subscription_by_uuid(uuid) or {}
    sub_id = _resolve_display_sub_id(uuid, raw_user=user_raw, sub_data=sub_data, sub_record=sub_record)
    remaining_day = sub_data.get('remaining_day', 0)
    usage = sub_data.get('usage', {})
    used_gb, limit_gb, remaining_gb = _usage_numbers(usage)
    time_left = _format_time_left(remaining_day)
    total_hours_left = _total_hours_left(remaining_day)
    expire_at = _format_expire_at(remaining_day)

    max_ips = _resolve_user_max_ips(user_raw, sub_record)
    _sync_user_max_ips(server_url, uuid, user_raw, max_ips)
    trimmed = _enforce_device_limit(server_url, uuid, user_raw, max_ips)
    if trimmed > 0:
        user_raw = api.find(server_url, uuid=uuid) or user_raw
    plan_type = _plan_type_label(max_ips)
    policy = _tariff_device_policy(max_ips)

    connected = len(_extract_devices(user_raw)) if user_raw else 0
    limit = policy['total']

    subscription_link = links.get('public_sub_link') or links.get('sub_link_auto') or links.get('sub_link')
    home_web_url = links.get('public_home_link') or links.get('home_link') or ''

    text = MESSAGES['VELVET_SUB_CARD'].format(
        sub_id=sub_id,
        plan_type=plan_type,
        days=remaining_day,
        sub_link=subscription_link,
    ) + (
        f"\n\n🌐Ссылка на сайт подписки:\n{home_web_url}"
        f"\n\n📊Трафик: израсходовано {used_gb:.2f} / {limit_gb:.2f} ГБ"
        f"\n📉Осталось трафика: {remaining_gb:.2f} ГБ"
        f"\n📅Дней осталось: {int(remaining_day) if remaining_day else 0}"
        f"\n🕒Часов осталось: {total_hours_left}"
        f"\n⏳До окончания: {time_left}"
        f"\n🗓Окончание: {expire_at}"
        f"\n📱Устройства: {connected}/{limit}"
        f"\n📌Лимит: {policy['phones']} телефонов + {policy['desktop_tablet']} ПК/планшетов"
    )
    return text, sub_id


def _get_available_servers_with_capacity():
    server = _get_main_server()
    if not server:
        return []
    users_list = api.select(server['url'] + API_PATH)
    users_count = len(users_list) if users_list else 0
    if server['user_limit'] > users_count:
        return [server]
    return []


def _plans_for_buy_type(type_key, server_id=None):
    if server_id:
        server_rows = USERS_DB.find_server(id=server_id)
        server = server_rows[0] if server_rows else None
    else:
        server = _get_main_server()
    if not server:
        return []

    plans = USERS_DB.find_plan(server_id=server['id']) or []

    plans = [p for p in plans if p.get('status')]
    if not plans:
        return []

    keywords = {
        'individual': ('индив', 'individual', '2 устрой', '2 device', '2 телефон', 'до 4 устройств', '4 device'),
        'family': ('семейн', 'family', '5 устрой', '5 device', '5 телефон', 'до 8 устройств', '8 device'),
    }
    type_words = keywords.get(type_key, ())
    filtered = []
    for plan in plans:
        desc = str(plan.get('description') or '').lower()
        if any(w in desc for w in type_words):
            filtered.append(plan)

    return filtered if filtered else plans

# Next Step Buy From Wallet - Confirm
def buy_from_wallet_confirm(message: Message, plan):
    if not plan:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return

    wallet = USERS_DB.find_wallet(telegram_id=message.chat.id)
    if not wallet:
        # Wallet not created
        bot.send_message(message.chat.id, MESSAGES['LACK_OF_WALLET_BALANCE'],
                         reply_markup=wallet_info_markup())
        return
    if wallet:
        wallet = wallet[0]
        if plan['price'] > wallet['balance']:
            bot.send_message(message.chat.id, MESSAGES['LACK_OF_WALLET_BALANCE'],
                             reply_markup=wallet_info_specific_markup(plan['price'] - wallet['balance']))
            return
        else:
            bot.delete_message(message.chat.id, message.message_id)
            bot.send_message(message.chat.id, MESSAGES['REQUEST_SEND_NAME'], reply_markup=cancel_markup())
            bot.register_next_step_handler(message, next_step_send_name_for_buy_from_wallet, plan)


def renewal_from_wallet_confirm(message: Message):
    if not renew_subscription_dict:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return

    if not renew_subscription_dict[message.chat.id]:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return

    if not renew_subscription_dict[message.chat.id]['plan_id'] or not renew_subscription_dict[message.chat.id][
        'uuid']:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return

    uuid = renew_subscription_dict[message.chat.id]['uuid']
    plan_id = renew_subscription_dict[message.chat.id]['plan_id']

    wallet = USERS_DB.find_wallet(telegram_id=message.chat.id)
    if not wallet:
        status = USERS_DB.add_wallet(telegram_id=message.chat.id)
        if not status:
            bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return

    wallet = wallet[0]
    plan_info = USERS_DB.find_plan(id=plan_id)
    if not plan_info:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return

    plan_info = plan_info[0]
    if plan_info['price'] > wallet['balance']:
        bot.send_message(message.chat.id, MESSAGES['LACK_OF_WALLET_BALANCE'],reply_markup=wallet_info_specific_markup(plan_info['price'] - wallet['balance']))
        del renew_subscription_dict[message.chat.id]
        return

    server_id = plan_info['server_id']
    server = USERS_DB.find_server(id=server_id)
    if not server:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return
    server = server[0]
    URL = server['url'] + API_PATH
    user = api.find(URL, uuid=uuid)
    if not user:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return

    user_info = utils.users_to_dict([user])
    if not user_info:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return

    user_info_process = utils.dict_process(URL, user_info)
    user_info = user_info[0]

    if not user_info_process:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return
    user_info_process = user_info_process[0]
    new_balance = int(wallet['balance']) - int(plan_info['price'])
    edit_wallet = USERS_DB.edit_wallet(message.chat.id, balance=new_balance)
    if not edit_wallet:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return
    last_reset_time = datetime.datetime.now().strftime("%Y-%m-%d")    
    sub = utils.find_order_subscription_by_uuid(uuid) 
    if not sub:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return   
    settings = utils.all_configs_settings()
    max_ips_limit = _plan_device_limit(plan_info)
    tariff_type = _plan_type_from_max_ips(max_ips_limit)
    sub_comment = f"HidyBot:{sub['id']};type={tariff_type};max_ips={max_ips_limit}"
    #Default renewal mode
    if settings['renewal_method'] == 1:
        if user_info_process['remaining_day'] <= 0 or user_info_process['usage']['remaining_usage_GB'] <= 0:
            new_usage_limit = plan_info['size_gb']
            new_package_days = plan_info['days']
            current_usage_GB = 0
            edit_status = api.update(URL, uuid=uuid, usage_limit_GB=new_usage_limit, package_days=new_package_days, start_date=last_reset_time, current_usage_GB=current_usage_GB, comment=sub_comment, max_ips=max_ips_limit)

        else:
            new_usage_limit = user_info['usage_limit_GB'] + plan_info['size_gb']
            new_package_days = plan_info['days'] + (user_info['package_days'] - user_info_process['remaining_day'])
            edit_status = api.update(URL, uuid=uuid, usage_limit_GB=new_usage_limit, package_days=new_package_days, last_reset_time=last_reset_time, comment=sub_comment, max_ips=max_ips_limit)


    #advance renewal mode        
    elif settings['renewal_method'] == 2:
            new_usage_limit = plan_info['size_gb']
            new_package_days = plan_info['days']
            current_usage_GB = 0
            edit_status = api.update(URL, uuid=uuid, usage_limit_GB=new_usage_limit, start_date=last_reset_time, package_days=new_package_days, current_usage_GB=current_usage_GB, comment=sub_comment, max_ips=max_ips_limit)

    
    #Fair renewal mode
    elif settings['renewal_method'] == 3:
        if user_info_process['remaining_day'] <= 0 or user_info_process['usage']['remaining_usage_GB'] <= 0:
            new_usage_limit = plan_info['size_gb']
            new_package_days = plan_info['days']
            current_usage_GB = 0
            edit_status = api.update(URL, uuid=uuid, usage_limit_GB=new_usage_limit, package_days=new_package_days, start_date=last_reset_time, current_usage_GB=current_usage_GB, comment=sub_comment, max_ips=max_ips_limit)
        else:
            print(user_info)
            new_usage_limit = user_info['usage_limit_GB'] + plan_info['size_gb']
            new_package_days = plan_info['days'] + user_info['package_days']
            edit_status = api.update(URL, uuid=uuid, usage_limit_GB=new_usage_limit, package_days=new_package_days, last_reset_time=last_reset_time, comment=sub_comment, max_ips=max_ips_limit)

            

    if not edit_status:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return

    # Add New Order
    order_id = random.randint(1000000, 9999999)
    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = USERS_DB.add_order(order_id, message.chat.id,user_info_process['name'], plan_id, created_at)
    if not status:
        bot.send_message(message.chat.id,
                         f"{MESSAGES['UNKNOWN_ERROR']}\n{MESSAGES['ORDER_ID']} {order_id}",
                         reply_markup=main_menu_keyboard_markup())
        return
    # edit_status = ADMIN_DB.edit_user(uuid=uuid, usage_limit_GB=new_usage_limit, package_days=new_package_days)
    # edit_status = api.update(URL, uuid=uuid, usage_limit_GB=new_usage_limit, package_days=new_package_days)
    # if not edit_status:
    #     bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
    #                      reply_markup=main_menu_keyboard_markup())
    #     return

    bot.send_message(message.chat.id, MESSAGES['SUCCESSFUL_RENEWAL'], reply_markup=main_menu_keyboard_markup())
    update_info_subscription(message, uuid)
    BASE_URL = urlparse(server['url']).scheme + "://" + urlparse(server['url']).netloc
    link = f"{BASE_URL}/{urlparse(server['url']).path.split('/')[1]}/{uuid}/"
    user_name = f"<a href='{link}'> {user_info_process['name']} </a>"
    bot_users = USERS_DB.find_user(telegram_id=message.chat.id)
    if bot_users:
        bot_user = bot_users[0]
    for ADMIN in ADMINS_ID:
        admin_bot.send_message(ADMIN,
                               f"""{MESSAGES['ADMIN_NOTIFY_NEW_RENEWAL']} {user_name} {MESSAGES['ADMIN_NOTIFY_NEW_RENEWAL_2']}
{MESSAGES['SERVER']}<a href='{server['url']}/admin'> {server['title']} </a>
{MESSAGES['INFO_ID']} <code>{sub['id']}</code>""", reply_markup=notify_to_admin_markup(bot_user))


# Next Step Buy Plan - Send Screenshot

def next_step_send_screenshot(message, charge_wallet):
    if is_it_cancel(message):
        return
    if not charge_wallet:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return

    if message.content_type != 'photo':
        bot.send_message(message.chat.id, MESSAGES['ERROR_TYPE_SEND_SCREENSHOT'], reply_markup=cancel_markup())
        bot.register_next_step_handler(message, next_step_send_screenshot, charge_wallet)
        return

    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    file_name = f"{message.chat.id}-{charge_wallet['id']}.jpg"
    path_recp = os.path.join(os.getcwd(), 'UserBot', 'Receiptions', file_name)
    if not os.path.exists(os.path.join(os.getcwd(), 'UserBot', 'Receiptions')):
        os.makedirs(os.path.join(os.getcwd(), 'UserBot', 'Receiptions'))
    with open(path_recp, 'wb') as new_file:
        new_file.write(downloaded_file)

    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    payment_method = "Card"

    status = USERS_DB.add_payment(charge_wallet['id'], message.chat.id,
                                  charge_wallet['amount'], payment_method, file_name, created_at)
    if status:
        payment = USERS_DB.find_payment(id=charge_wallet['id'])
        if not payment:
            bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                             reply_markup=main_menu_keyboard_markup())
            return
        payment = payment[0]
        user_data = USERS_DB.find_user(telegram_id=message.chat.id)
        if not user_data:
            bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                             reply_markup=main_menu_keyboard_markup())
            return
        user_data = user_data[0]
        for ADMIN in ADMINS_ID:
            admin_bot.send_photo(ADMIN, open(path_recp, 'rb'),
                                 caption=payment_received_template(payment,user_data),
                                 reply_markup=confirm_payment_by_admin(charge_wallet['id']))
        bot.send_message(message.chat.id, MESSAGES['WAIT_FOR_ADMIN_CONFIRMATION'],
                         reply_markup=main_menu_keyboard_markup())
    else:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        
# Next Step Payment - Send Answer
def next_step_answer_to_admin(message, admin_id):
    if is_it_cancel(message):
        return
    bot_users = USERS_DB.find_user(telegram_id=message.chat.id)
    if bot_users:
        bot_user = bot_users[0]
    admin_bot.send_message(int(admin_id), f"{MESSAGES['NEW_TICKET_RECEIVED']}\n{MESSAGES['TICKET_TEXT']} {message.text}",
                           reply_markup=answer_to_user_markup(bot_user,message.chat.id))
    bot.send_message(message.chat.id, MESSAGES['SEND_TICKET_TO_ADMIN_RESPONSE'],
                         reply_markup=main_menu_keyboard_markup())

# Next Step Payment - Send Ticket To Admin
def next_step_send_ticket_to_admin(message):
    if is_it_cancel(message):
        return
    bot_users = USERS_DB.find_user(telegram_id=message.chat.id)
    if bot_users:
        bot_user = bot_users[0]
    for ADMIN in ADMINS_ID:
        admin_bot.send_message(ADMIN, f"{MESSAGES['NEW_TICKET_RECEIVED']}\n{MESSAGES['TICKET_TEXT']} {message.text}",
                               reply_markup=answer_to_user_markup(bot_user,message.chat.id))
        bot.send_message(message.chat.id, MESSAGES['SEND_TICKET_TO_ADMIN_RESPONSE'],
                            reply_markup=main_menu_keyboard_markup())



# *********************************** YooKassa Payment Handlers ***********************************

def create_yookassa_payment(message, amount):
    """Create a YooKassa payment for wallet top-up"""
    client = _ensure_yookassa_client()
    if not client:
        bot.send_message(message.chat.id, "❌ЮKassa не настроена. Пожалуйста, используйте другой способ оплаты.",
                         reply_markup=main_menu_keyboard_markup())
        return

    try:
        payment_id = random.randint(1000000, 9999999)
        return_url = f"https://t.me/{bot.get_me().username}"

        payment_data = client.create_payment(
            amount=amount,
            description=f"Пополнение кошелька SmartKamaVPN - {payment_id}",
            return_url=return_url,
            metadata={
                "telegram_id": message.chat.id,
                "payment_id": payment_id
            }
        )

        if payment_data:
            created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            USERS_DB.add_yookassa_payment(
                payment_id=payment_id,
                telegram_id=message.chat.id,
                amount=amount,
                yookassa_payment_id=payment_data['id'],
                confirmation_url=payment_data['confirmation']['confirmation_url'],
                created_at=created_at
            )

            # Send payment link to user
            markup = telebot.types.InlineKeyboardMarkup()
            pay_button = telebot.types.InlineKeyboardButton("💳Оплатить", url=payment_data['confirmation']['confirmation_url'])
            check_button = telebot.types.InlineKeyboardButton("🔄Проверить оплату", callback_data=f"check_yookassa:{payment_id}")
            markup.add(pay_button)
            markup.add(check_button)

            bot.send_message(
                message.chat.id,
                f"{MESSAGES['YOOKASSA_PAYMENT_CREATED']}\n\n💰Сумма: {amount}₽\n⏳Платеж действителен 1 час",
                reply_markup=markup
            )
        else:
            bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                             reply_markup=main_menu_keyboard_markup())
    except Exception as e:
        logging.error(f"Error creating YooKassa payment: {e}")
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())


def check_yookassa_payment_status(payment_id):
    """Check YooKassa payment status and update wallet if paid"""
    try:
        payment_record = USERS_DB.find_yookassa_payment(payment_id=payment_id)
        if not payment_record:
            return None

        payment_record = payment_record[0]

        if payment_record['status'] == 'succeeded':
            return {'status': 'succeeded', 'amount': payment_record['amount']}

        if payment_record['status'] == 'canceled':
            return {'status': 'canceled'}

        # Check with YooKassa API
        client = _ensure_yookassa_client()
        if client:
            yookassa_data = client.get_payment(payment_record['yookassa_payment_id'])
            if yookassa_data:
                new_status = yookassa_data['status']

                if new_status != payment_record['status']:
                    updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    USERS_DB.edit_yookassa_payment(
                        payment_id=payment_id,
                        status=new_status,
                        updated_at=updated_at
                    )

                    if new_status == 'succeeded':
                        # Add to wallet
                        wallet = USERS_DB.find_wallet(telegram_id=payment_record['telegram_id'])
                        if wallet:
                            new_balance = wallet[0]['balance'] + payment_record['amount']
                            USERS_DB.edit_wallet(payment_record['telegram_id'], balance=new_balance)
                        else:
                            USERS_DB.add_wallet(payment_record['telegram_id'])
                            USERS_DB.edit_wallet(payment_record['telegram_id'], balance=payment_record['amount'])

                        return {'status': 'succeeded', 'amount': payment_record['amount']}

                    elif new_status == 'canceled':
                        return {'status': 'canceled'}

                return {'status': new_status}

        return {'status': payment_record['status']}
    except Exception as e:
        logging.error(f"Error checking YooKassa payment: {e}")
        return None


# Next Step - YooKassa Payment Amount
def next_step_yookassa_amount(message: Message):
    if is_it_cancel(message):
        return

    if not is_it_digit(message, response=MESSAGES['ERROR_INVALID_NUMBER']):
        bot.register_next_step_handler(message, next_step_yookassa_amount)
        return

    amount = int(message.text)
    settings = utils.all_configs_settings()
    min_deposit = settings.get('min_deposit_amount', 100)

    if amount < min_deposit:
        bot.send_message(message.chat.id, f"{MESSAGES['MINIMUM_DEPOSIT_AMOUNT']} {min_deposit}₽",
                         reply_markup=cancel_markup())
        bot.register_next_step_handler(message, next_step_yookassa_amount)
        return

    create_yookassa_payment(message, amount)


def create_pally_payment(message: Message, amount):
    settings = utils.all_configs_settings()
    pally_template = settings.get('pally_payment_url')
    if not pally_template:
        bot.send_message(message.chat.id, MESSAGES['PALLY_PAYMENT_NO_URL'], reply_markup=main_menu_keyboard_markup())
        return

    payment_id = random.randint(1000000, 9999999)
    amount_internal = utils.toman_to_rial(amount)
    payment_url = _build_pally_payment_url(pally_template, amount, message.chat.id, payment_id)

    pending_pally_payments[str(payment_id)] = {
        'telegram_id': message.chat.id,
        'amount': int(amount_internal),
        'amount_rub': int(amount),
    }

    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("💸Оплатить через Pally", url=payment_url))
    markup.add(telebot.types.InlineKeyboardButton("✅Я оплатил", callback_data=f"check_pally:{payment_id}"))
    bot.send_message(
        message.chat.id,
        f"{MESSAGES['PALLY_PAYMENT_CREATED']}\n\n💰Сумма: {amount}₽",
        reply_markup=markup,
    )


def next_step_pally_amount(message: Message):
    if is_it_cancel(message):
        return

    if not is_it_digit(message, response=MESSAGES['ERROR_INVALID_NUMBER']):
        bot.register_next_step_handler(message, next_step_pally_amount)
        return

    amount = int(message.text)
    settings = utils.all_configs_settings()
    min_deposit = settings.get('min_deposit_amount', 1000)
    min_deposit_rub = int(min_deposit / 10)

    if amount < min_deposit_rub:
        bot.send_message(
            message.chat.id,
            f"{MESSAGES['MINIMUM_DEPOSIT_AMOUNT']} {min_deposit_rub}₽",
            reply_markup=cancel_markup(),
        )
        bot.register_next_step_handler(message, next_step_pally_amount)
        return

    create_pally_payment(message, amount)


def next_step_gift_promo_amount(message: Message):
    if is_it_cancel(message):
        return

    if not is_it_digit(message, response=MESSAGES['ERROR_INVALID_NUMBER']):
        bot.register_next_step_handler(message, next_step_gift_promo_amount)
        return

    amount_rub = int(message.text)
    if amount_rub <= 0:
        bot.send_message(message.chat.id, MESSAGES['ERROR_INVALID_NUMBER'], reply_markup=cancel_markup())
        bot.register_next_step_handler(message, next_step_gift_promo_amount)
        return

    amount_internal = int(utils.toman_to_rial(amount_rub))
    wallet = USERS_DB.find_wallet(telegram_id=message.chat.id)
    balance = int(wallet[0]['balance']) if wallet else 0
    if balance < amount_internal:
        need_more = amount_internal - balance
        bot.send_message(message.chat.id, MESSAGES['LACK_OF_WALLET_BALANCE'], reply_markup=wallet_info_specific_markup(need_more))
        return

    code = _generate_gift_code()
    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not USERS_DB.add_gift_promo_code(code, message.chat.id, amount_internal, created_at):
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'], reply_markup=main_menu_keyboard_markup())
        return

    if not USERS_DB.edit_wallet(message.chat.id, balance=(balance - amount_internal)):
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'], reply_markup=main_menu_keyboard_markup())
        return

    bot.send_message(
        message.chat.id,
        MESSAGES['SKV_GIFT_PROMO_CREATED'].format(code=code, amount=amount_rub),
        reply_markup=main_menu_keyboard_markup(),
    )


def next_step_redeem_gift_promo(message: Message):
    if is_it_cancel(message):
        return

    code = (message.text or '').strip().upper()
    if not code:
        bot.send_message(message.chat.id, MESSAGES['SKV_GIFT_PROMO_INVALID'], reply_markup=main_menu_keyboard_markup())
        return

    promo_rows = USERS_DB.find_gift_promo_code(code=code)
    if not promo_rows:
        bot.send_message(message.chat.id, MESSAGES['SKV_GIFT_PROMO_INVALID'], reply_markup=main_menu_keyboard_markup())
        return

    promo = promo_rows[0]
    if promo.get('status') != 'new':
        bot.send_message(message.chat.id, MESSAGES['SKV_GIFT_PROMO_ALREADY_USED'], reply_markup=main_menu_keyboard_markup())
        return

    if int(promo.get('creator_telegram_id', 0)) == int(message.chat.id):
        bot.send_message(message.chat.id, MESSAGES['SKV_GIFT_PROMO_SELF_DENIED'], reply_markup=main_menu_keyboard_markup())
        return

    wallet = USERS_DB.find_wallet(telegram_id=message.chat.id)
    if wallet:
        new_balance = int(wallet[0]['balance']) + int(promo['amount'])
        USERS_DB.edit_wallet(message.chat.id, balance=new_balance)
    else:
        USERS_DB.add_wallet(message.chat.id)
        USERS_DB.edit_wallet(message.chat.id, balance=int(promo['amount']))

    redeemed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    USERS_DB.redeem_gift_promo_code(code, message.chat.id, redeemed_at)

    amount_rub = int(int(promo['amount']) / 10)
    bot.send_message(
        message.chat.id,
        MESSAGES['SKV_GIFT_PROMO_SUCCESS'].format(amount=amount_rub),
        reply_markup=main_menu_keyboard_markup(),
    )


# ----------------------------------- Buy From Wallet Area -----------------------------------
# Next Step Buy From Wallet - Send Name
def next_step_send_name_for_buy_from_wallet(message: Message, plan):
    if is_it_cancel(message):
        return

    if not plan:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return
    name = message.text
    while is_it_command(message):
        message = bot.send_message(message.chat.id, MESSAGES['REQUEST_SEND_NAME'])
        bot.register_next_step_handler(message, next_step_send_name_for_buy_from_wallet, plan)
        return
    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    paid_amount = plan['price']

    order_id = random.randint(1000000, 9999999)
    server_id = plan['server_id']
    server = USERS_DB.find_server(id=server_id)
    if not server:
        bot.send_message(message.chat.id, f"{MESSAGES['UNKNOWN_ERROR']}:Server Not Found",
                         reply_markup=main_menu_keyboard_markup())
        return
    server = server[0]
    URL = server['url'] + API_PATH

    # value = ADMIN_DB.add_default_user(name, plan['days'], plan['size_gb'],)
    sub_id = random.randint(1000000, 9999999)
    selected_type = buy_subscription_type.get(message.chat.id, 'individual')
    max_ips = 2 if selected_type == 'individual' else 5
    type_label = 'individual' if selected_type == 'individual' else 'family'
    value = api.insert(
        URL,
        name=name,
        usage_limit_GB=plan['size_gb'],
        package_days=plan['days'],
        comment=f"HidyBot:{sub_id};type={type_label};max_ips={max_ips}",
        max_ips=max_ips,
    )
    if not value:
        bot.send_message(message.chat.id,
                         f"{MESSAGES['UNKNOWN_ERROR']}:Create User Error\n{MESSAGES['ORDER_ID']} {order_id}",
                         reply_markup=main_menu_keyboard_markup())
        return
    add_sub_status = USERS_DB.add_order_subscription(sub_id, order_id, value, server_id)
    if not add_sub_status:
        bot.send_message(message.chat.id,
                         f"{MESSAGES['UNKNOWN_ERROR']}:Add Subscription Error\n{MESSAGES['ORDER_ID']} {order_id}",
                         reply_markup=main_menu_keyboard_markup())
        return
    status = USERS_DB.add_order(order_id, message.chat.id,name, plan['id'], created_at)
    if not status:
        bot.send_message(message.chat.id,
                         f"{MESSAGES['UNKNOWN_ERROR']}:Add Order Error\n{MESSAGES['ORDER_ID']} {order_id}",
                         reply_markup=main_menu_keyboard_markup())
        return
    wallet = USERS_DB.find_wallet(telegram_id=message.chat.id)
    if wallet:
        wallet = wallet[0]
        wallet_balance = int(wallet['balance']) - int(paid_amount)
        user_info = USERS_DB.edit_wallet(message.chat.id, balance=wallet_balance)
        if not user_info:
            bot.send_message(message.chat.id,
                             f"{MESSAGES['UNKNOWN_ERROR']}:Edit Wallet Balance Error\n{MESSAGES['ORDER_ID']} {order_id}",
                             reply_markup=main_menu_keyboard_markup())
            return
    bot.send_message(message.chat.id,
                     f"{MESSAGES['PAYMENT_CONFIRMED']}\n{MESSAGES['ORDER_ID']} {order_id}",
                     reply_markup=main_menu_keyboard_markup())
    
    user_info = api.find(URL, value)
    if not user_info:
        bot.send_message(message.chat.id,
                         f"{MESSAGES['UNKNOWN_ERROR']}:Read Created User Error\n{MESSAGES['ORDER_ID']} {order_id}",
                         reply_markup=main_menu_keyboard_markup())
        return
    user_info = utils.users_to_dict([user_info])
    user_info = utils.dict_process(URL, user_info)
    user_info = user_info[0]
    api_user_data = user_info_template(sub_id, server, user_info, MESSAGES['INFO_USER'])
    bot.send_message(message.chat.id, api_user_data,
                                 reply_markup=user_info_markup(user_info['uuid']))
    
    BASE_URL = urlparse(server['url']).scheme + "://" + urlparse(server['url']).netloc
    link = f"{BASE_URL}/{urlparse(server['url']).path.split('/')[1]}/{value}/"
    user_name = f"<a href='{link}'> {name} </a>"
    bot_users = USERS_DB.find_user(telegram_id=message.chat.id)
    if bot_users:
        bot_user = bot_users[0]
    for ADMIN in ADMINS_ID:
        admin_bot.send_message(ADMIN,
                               f"""{MESSAGES['ADMIN_NOTIFY_NEW_SUB']} {user_name} {MESSAGES['ADMIN_NOTIFY_CONFIRM']}
{MESSAGES['SERVER']}<a href='{server['url']}/admin'> {server['title']} </a>
{MESSAGES['INFO_ID']} <code>{sub_id}</code>""", reply_markup=notify_to_admin_markup(bot_user))


# ----------------------------------- Get Free Test Area -----------------------------------
# Next Step Get Free Test - Send Name
def next_step_send_name_for_get_free_test(message: Message, server_id):
    if is_it_cancel(message):
        return
    name = message.text
    while is_it_command(message):
        message = bot.send_message(message.chat.id, MESSAGES['REQUEST_SEND_NAME'])
        bot.register_next_step_handler(message, next_step_send_name_for_get_free_test)
        return

    settings = utils.all_configs_settings()
    test_user_comment = "HidyBot:FreeTest;type=individual;max_ips=2"
    server = USERS_DB.find_server(id=server_id)
    if not server:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return
    server = server[0]
    URL = server['url'] + API_PATH
    # uuid = ADMIN_DB.add_default_user(name, test_user_days, test_user_size_gb, int(PANEL_ADMIN_ID), test_user_comment)
    uuid = api.insert(
        URL,
        name=name,
        usage_limit_GB=settings['test_sub_size_gb'],
        package_days=settings['test_sub_days'],
        comment=test_user_comment,
        max_ips=2,
    )
    if not uuid:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return
    non_order_id = random.randint(10000000, 99999999)
    non_order_status = USERS_DB.add_non_order_subscription(non_order_id, message.chat.id, uuid, server_id)
    if not non_order_status:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return

    edit_user_status = USERS_DB.edit_user(message.chat.id, test_subscription=True)
    if not edit_user_status:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return
    bot.send_message(message.chat.id, MESSAGES['GET_FREE_CONFIRMED'],
                     reply_markup=main_menu_keyboard_markup())
    user_info = api.find(URL, uuid)
    user_info = utils.users_to_dict([user_info])
    user_info = utils.dict_process(URL, user_info)
    user_info = user_info[0]
    api_user_data = user_info_template(non_order_id, server, user_info, MESSAGES['INFO_USER'])
    bot.send_message(message.chat.id, api_user_data,
                                 reply_markup=user_info_markup(user_info['uuid']))
    BASE_URL = urlparse(server['url']).scheme + "://" + urlparse(server['url']).netloc
    link = f"{BASE_URL}/{urlparse(server['url']).path.split('/')[1]}/{uuid}/"
    user_name = f"<a href='{link}'> {name} </a>"
    bot_users = USERS_DB.find_user(telegram_id=message.chat.id)
    if bot_users:
        bot_user = bot_users[0]
    for ADMIN in ADMINS_ID:
        admin_bot.send_message(ADMIN,
                               f"""{MESSAGES['ADMIN_NOTIFY_NEW_FREE_TEST']} {user_name} {MESSAGES['ADMIN_NOTIFY_CONFIRM']}
{MESSAGES['SERVER']}<a href='{server['url']}/admin'> {server['title']} </a>
{MESSAGES['INFO_ID']} <code>{non_order_id}</code>""", reply_markup=notify_to_admin_markup(bot_user))


# ----------------------------------- To QR Area -----------------------------------
# Next Step QR - QR Code
def next_step_to_qr(message: Message):
    if is_it_cancel(message):
        return
    if not message.text:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return

    is_it_valid = utils.is_it_config_or_sub(message.text)
    if is_it_valid:
        qr_code = utils.txt_to_qr(message.text)
        if qr_code:
            bot.send_photo(message.chat.id, qr_code, reply_markup=main_menu_keyboard_markup())
    else:
        bot.send_message(message.chat.id, MESSAGES['REQUEST_SEND_TO_QR_ERROR'],
                         reply_markup=main_menu_keyboard_markup())


# ----------------------------------- Link Subscription Area -----------------------------------
# Next Step Link Subscription to bot
def next_step_link_subscription(message: Message):
    if not message.text:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return
    if is_it_cancel(message):
        return
    uuid = utils.is_it_config_or_sub(message.text)
    if uuid:
        # check is it already subscribed
        is_it_subscribed = utils.is_it_subscription_by_uuid_and_telegram_id(uuid, message.chat.id)
        if is_it_subscribed:
            bot.send_message(message.chat.id, MESSAGES['ALREADY_SUBSCRIBED'],
                             reply_markup=main_menu_keyboard_markup())
            return
        non_sub_id = random.randint(10000000, 99999999)
        servers = USERS_DB.select_servers()
        if not servers:
            bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'], reply_markup=main_menu_keyboard_markup())
            return
        for server in servers:
            users_list = api.find(server['url'] + API_PATH, uuid)
            if users_list:
                server_id = server['id']
                break
        status = USERS_DB.add_non_order_subscription(non_sub_id, message.chat.id, uuid, server_id)
        if status:
            bot.send_message(message.chat.id, MESSAGES['SUBSCRIPTION_CONFIRMED'],
                             reply_markup=main_menu_keyboard_markup())
        else:
            bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                             reply_markup=main_menu_keyboard_markup())
    else:
        bot.send_message(message.chat.id, MESSAGES['SUBSCRIPTION_INFO_NOT_FOUND'],
                         reply_markup=main_menu_keyboard_markup())


# ----------------------------------- wallet balance Area -----------------------------------
# Next Step increase wallet balance - Send amount
def next_step_increase_wallet_balance(message):
    if is_it_cancel(message):
        return
    if not is_it_digit(message, markup=cancel_markup()):
        bot.register_next_step_handler(message, next_step_increase_wallet_balance)
        return
    minimum_deposit_amount = utils.all_configs_settings()
    minimum_deposit_amount = minimum_deposit_amount['min_deposit_amount']
    amount = utils.toman_to_rial(message.text)
    if amount < minimum_deposit_amount:
        bot.send_message(message.chat.id,
                         f"{MESSAGES['INCREASE_WALLET_BALANCE_AMOUNT']}\n{MESSAGES['MINIMUM_DEPOSIT_AMOUNT']}: "
                         f"{rial_to_toman(minimum_deposit_amount)} {MESSAGES['TOMAN']}", reply_markup=cancel_markup())
        bot.register_next_step_handler(message, next_step_increase_wallet_balance)
        return
    settings = utils.all_configs_settings()
    if not settings:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return

    charge_wallet['amount'] = str(amount)
    if settings['three_random_num_price'] == 1:
        charge_wallet['amount'] = utils.replace_last_three_with_random(str(amount))

    charge_wallet['id'] = random.randint(1000000, 9999999)
    # Send 0 to identify wallet balance charge
    payment_text = owner_info_template(settings['card_number'], settings['card_holder'], charge_wallet['amount'])
    if not payment_text or not str(payment_text).strip():
        payment_text = MESSAGES['UNKNOWN_ERROR']
    bot.send_message(message.chat.id, payment_text,
                     reply_markup=send_screenshot_markup(plan_id=charge_wallet['id']))

def increase_wallet_balance_specific(message,amount):
    settings = utils.all_configs_settings()
    user = USERS_DB.find_user(telegram_id=message.chat.id)
    if user:
        wallet_status = USERS_DB.find_wallet(telegram_id=message.chat.id)
        if not wallet_status:
            status = USERS_DB.add_wallet(telegram_id=message.chat.id)
            if not status:
                bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'])
                return
    charge_wallet['amount'] = str(amount)
    if settings['three_random_num_price'] == 1:
        charge_wallet['amount'] = utils.replace_last_three_with_random(str(amount))

    charge_wallet['id'] = random.randint(1000000, 9999999)

    # Send 0 to identify wallet balance charge
    bot.send_message(message.chat.id,
                     owner_info_template(settings['card_number'], settings['card_holder'], charge_wallet['amount']),
                     reply_markup=send_screenshot_markup(plan_id=charge_wallet['id']))
    


def update_info_subscription(message: Message, uuid,markup=None):
    value = uuid
    sub = utils.find_order_subscription_by_uuid(value)
    if not sub:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return
    if not markup:
        if sub.get('telegram_id', None):
            # Non-Order Subscription markup
            mrkup = user_info_non_sub_markup(sub['uuid'])
        else:
            # Ordered Subscription markup
            mrkup = user_info_markup(sub['uuid'])
    else:
        mrkup = markup
    server_id = sub['server_id']
    server = USERS_DB.find_server(id=server_id)
    if not server:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return
    server = server[0]
    URL = server['url'] + API_PATH
    user = api.find(URL, uuid=sub['uuid'])
    if not user:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                         reply_markup=main_menu_keyboard_markup())
        return
    user = utils.dict_process(URL, utils.users_to_dict([user]))[0]
    try:
        bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id,
                              text=user_info_template(sub['id'], server, user, MESSAGES['INFO_USER']),
                              reply_markup=mrkup)
    except:
        pass


# *********************************** Callback Query Area ***********************************
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call: CallbackQuery):
    try:
        bot.answer_callback_query(call.id, MESSAGES['WAIT'])
    except telebot.apihelper.ApiTelegramException:
        pass
    bot.clear_step_handler(call.message)
    if is_user_banned(call.message.chat.id):
        return
    # Split Callback Data to Key(Command) and UUID
    data = call.data.split(':', 1)
    key = data[0]
    value = data[1] if len(data) > 1 else ""

    # Backward/forward compatibility for callback prefixes.
    if key.startswith("smartkamavpn_"):
        key = f"velvet_{key[len('smartkamavpn_'):]}"

    global selected_server_id
    # ----------------------------------- YooKassa Payment Area -----------------------------------
    if key == 'select_payment_method':
        bot.send_message(call.message.chat.id, MESSAGES['SELECT_PAYMENT_METHOD'], reply_markup=payment_method_selection_markup())

    elif key == 'select_payment_method_specific':
        bot.send_message(call.message.chat.id, MESSAGES['SELECT_PAYMENT_METHOD'], reply_markup=payment_method_selection_markup(value))

    elif key == 'yookassa_payment':
        bot.delete_message(call.message.chat.id, call.message.message_id)
        if value and str(value).isdigit():
            create_yookassa_payment(call.message, int(value))
        else:
            bot.send_message(call.message.chat.id, MESSAGES['INCREASE_WALLET_BALANCE_AMOUNT'], reply_markup=cancel_markup())
            bot.register_next_step_handler(call.message, next_step_yookassa_amount)

    elif key == 'pally_payment':
        bot.delete_message(call.message.chat.id, call.message.message_id)
        if value and str(value).isdigit():
            create_pally_payment(call.message, int(value))
        else:
            bot.send_message(call.message.chat.id, MESSAGES['INCREASE_WALLET_BALANCE_AMOUNT'], reply_markup=cancel_markup())
            bot.register_next_step_handler(call.message, next_step_pally_amount)

    elif key == 'check_pally':
        payment_id = int(value)
        if USERS_DB.find_payment(id=payment_id):
            bot.answer_callback_query(call.id, MESSAGES['PALLY_PAYMENT_ALREADY_MARKED'], show_alert=True)
            return

        request_data = pending_pally_payments.get(str(value))
        if not request_data or int(request_data['telegram_id']) != int(call.message.chat.id):
            bot.answer_callback_query(call.id, MESSAGES['UNKNOWN_ERROR'], show_alert=True)
            return

        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = USERS_DB.add_payment(
            payment_id,
            call.message.chat.id,
            int(request_data['amount']),
            "Pally",
            "",
            created_at,
        )
        if not status:
            bot.answer_callback_query(call.id, MESSAGES['UNKNOWN_ERROR'], show_alert=True)
            return

        bot_users = USERS_DB.find_user(telegram_id=call.message.chat.id)
        bot_user = bot_users[0] if bot_users else None
        full_name = bot_user['full_name'] if bot_user and bot_user.get('full_name') else str(call.message.chat.id)

        for admin_id in ADMINS_ID:
            admin_bot.send_message(
                admin_id,
                (
                    "💸Новый платеж Pally\n"
                    f"ID: <code>{payment_id}</code>\n"
                    f"Пользователь: {html.escape(full_name)}\n"
                    f"Telegram ID: <code>{call.message.chat.id}</code>\n"
                    f"Сумма: {request_data['amount_rub']}₽"
                ),
                reply_markup=confirm_payment_by_admin(payment_id),
            )

        pending_pally_payments.pop(str(value), None)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, MESSAGES['PALLY_PAYMENT_MARKED'], reply_markup=main_menu_keyboard_markup())

    elif key == 'check_yookassa':
        result = check_yookassa_payment_status(value)
        if result:
            if result['status'] == 'succeeded':
                bot.delete_message(call.message.chat.id, call.message.message_id)
                bot.send_message(
                    call.message.chat.id,
                    f"{MESSAGES['YOOKASSA_PAYMENT_SUCCESS']}\n💰Сумма: {result['amount']}₽",
                    reply_markup=main_menu_keyboard_markup(),
                )
            elif result['status'] == 'canceled':
                bot.delete_message(call.message.chat.id, call.message.message_id)
                bot.send_message(
                    call.message.chat.id,
                    MESSAGES['YOOKASSA_PAYMENT_CANCELED'],
                    reply_markup=main_menu_keyboard_markup(),
                )
            else:
                bot.answer_callback_query(call.id, MESSAGES['YOOKASSA_PAYMENT_PENDING'], show_alert=True)
        else:
            bot.answer_callback_query(call.id, MESSAGES['UNKNOWN_ERROR'], show_alert=True)

    # ----------------------------------- Link Subscription Area -----------------------------------
    # Confirm Link Subscription
    if key == 'force_join_status':
        bot.delete_message(call.message.chat.id, call.message.message_id)
        join_status = is_user_in_channel(call.message.chat.id)

        if not join_status:
            return
        else:
            bot.send_message(call.message.chat.id, MESSAGES['JOIN_CHANNEL_SUCCESSFUL'])
            
    elif key == 'confirm_subscription':
        edit_status = USERS_DB.add_non_order_subscription(call.message.chat.id, value, )
        if edit_status:
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, MESSAGES['SUBSCRIPTION_CONFIRMED'],
                             reply_markup=main_menu_keyboard_markup())
        else:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                             reply_markup=main_menu_keyboard_markup())
    # Reject Link Subscription
    elif key == 'cancel_subscription':
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, MESSAGES['CANCEL_SUBSCRIPTION'],
                         reply_markup=main_menu_keyboard_markup())

    # ----------------------------------- Buy Plan Area -----------------------------------
    elif key == 'server_selected':
        # Legacy callback compatibility: explicit server selection removed.
        bot.edit_message_text(
            text=MESSAGES['BUY_TYPE_SELECT'],
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=subscription_type_markup(),
        )
        
    elif key == 'free_test_server_selected':
        if value == 'False':
            bot.send_message(call.message.chat.id, MESSAGES['SERVER_IS_FULL'], reply_markup=main_menu_keyboard_markup())
            return
        users = USERS_DB.find_user(telegram_id=call.message.chat.id)
        if users:
            user = users[0]
            if user['test_subscription']:
                bot.send_message(call.message.chat.id, MESSAGES['ALREADY_RECEIVED_FREE'],
                                reply_markup=main_menu_keyboard_markup())
                return
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, MESSAGES['REQUEST_SEND_NAME'], reply_markup=cancel_markup())
            bot.register_next_step_handler(call.message, next_step_send_name_for_get_free_test, value)
    # Send Asked Plan Info
    elif key == 'plan_selected':
        plan_rows = USERS_DB.find_plan(id=value)
        if not plan_rows:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                             reply_markup=main_menu_keyboard_markup())
            return
        plan = plan_rows[0]
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text=plan_info_template(plan),
                              reply_markup=confirm_buy_plan_markup(plan['id']))

    elif key == 'buy_type_selected':
        _ensure_single_server_tariff_plans()
        plans = _plans_for_buy_type(value)
        if not plans:
            bot.send_message(call.message.chat.id, MESSAGES['PLANS_NOT_FOUND'], reply_markup=main_menu_keyboard_markup())
            return
        buy_subscription_type[call.message.chat.id] = value
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=MESSAGES['PLANS_LIST'],
            reply_markup=plans_list_markup(plans),
        )

    # Confirm To Buy From Wallet
    elif key == 'confirm_buy_from_wallet':
        plan_rows = USERS_DB.find_plan(id=value)
        if not plan_rows:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                             reply_markup=main_menu_keyboard_markup())
            return
        plan = plan_rows[0]
        buy_from_wallet_confirm(call.message, plan)
    elif key == 'confirm_renewal_from_wallet':
        plan_rows = USERS_DB.find_plan(id=value)
        if not plan_rows:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                             reply_markup=main_menu_keyboard_markup())
            return
        plan = plan_rows[0]
        renewal_from_wallet_confirm(call.message)

    # Ask To Send Screenshot
    elif key == 'send_screenshot':
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, MESSAGES['REQUEST_SEND_SCREENSHOT'])
        bot.register_next_step_handler(call.message, next_step_send_screenshot, charge_wallet)

    #Answer to Admin After send Screenshot
    elif key == 'answer_to_admin':
        #bot.delete_message(call.message.chat.id,call.message.message_id)
        bot.send_message(call.message.chat.id, MESSAGES['ANSWER_TO_ADMIN'],
                        reply_markup=cancel_markup())
        bot.register_next_step_handler(call.message, next_step_answer_to_admin, value)

    #Send Ticket to Admin 
    elif key == 'send_ticket_to_support':
        bot.delete_message(call.message.chat.id,call.message.message_id)
        bot.send_message(call.message.chat.id, MESSAGES['SEND_TICKET_TO_ADMIN'],
                        reply_markup=cancel_markup())
        bot.register_next_step_handler(call.message, next_step_send_ticket_to_admin)

    # ----------------------------------- User Subscriptions Info Area -----------------------------------
    # Unlink non-order subscription
    elif key == 'unlink_subscription':
        delete_status = USERS_DB.delete_non_order_subscription(uuid=value)
        if delete_status:
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, MESSAGES['SUBSCRIPTION_UNLINKED'],
                             reply_markup=main_menu_keyboard_markup())
        else:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                             reply_markup=main_menu_keyboard_markup())

    elif key == 'update_info_subscription':
        update_info_subscription(call.message, value)

    # ----------------------------------- wallet Area -----------------------------------
    # INCREASE WALLET BALANCE
    elif key == 'increase_wallet_balance':
        bot.send_message(call.message.chat.id, MESSAGES['INCREASE_WALLET_BALANCE_AMOUNT'], reply_markup=cancel_markup())

        bot.register_next_step_handler(call.message, next_step_increase_wallet_balance)
    elif key == 'increase_wallet_balance_specific':
        bot.delete_message(call.message.chat.id, call.message.message_id)
        increase_wallet_balance_specific(call.message,value)
    elif key == 'renewal_subscription':
        settings = utils.all_configs_settings()
        if not settings['renewal_subscription_status']:
            bot.send_message(call.message.chat.id, MESSAGES['RENEWAL_SUBSCRIPTION_CLOSED'],
                             reply_markup=main_menu_keyboard_markup())
            return
        servers = USERS_DB.select_servers()
        server_id = 0
        user= []
        URL = "url"
        if servers:
            for server in servers:
                user = api.find(server['url'] + API_PATH, value)
                if user:
                    selected_server_id = server['id']
                    URL = server['url'] + API_PATH
                    break
        if not user:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                             reply_markup=main_menu_keyboard_markup())
            return
        user_info = utils.users_to_dict([user])
        if not user_info:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                             reply_markup=main_menu_keyboard_markup())
            return

        user_info_process = utils.dict_process(URL, user_info)
        if not user_info_process:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                             reply_markup=main_menu_keyboard_markup())
            return
        user_info_process = user_info_process[0]
        if settings['renewal_method'] == 2:
            if user_info_process['remaining_day'] > settings['advanced_renewal_days'] and user_info_process['usage']['remaining_usage_GB'] > settings['advanced_renewal_usage']:
                bot.send_message(call.message.chat.id, renewal_unvalable_template(settings),
                                 reply_markup=main_menu_keyboard_markup())
                return
        

        renew_subscription_dict[call.message.chat.id] = {
            'uuid': None,
            'plan_id': None,
        }
        raw_max_ips = user.get('max_ips') if isinstance(user, dict) else None
        renewal_type = _plan_type_from_max_ips(raw_max_ips)
        buy_subscription_type[call.message.chat.id] = renewal_type
        _ensure_single_server_tariff_plans()
        plans = _plans_for_buy_type(renewal_type, server_id=selected_server_id)
        if not plans:
            bot.send_message(call.message.chat.id, MESSAGES['PLANS_NOT_FOUND'],
                             reply_markup=main_menu_keyboard_markup())
            return
        renew_subscription_dict[call.message.chat.id]['uuid'] = value
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="🔄 Продление подписки\n\nВыберите тариф для продления:",
                reply_markup=plans_list_markup(plans, renewal=True, uuid=user_info_process['uuid'])
            )
        except telebot.apihelper.ApiTelegramException:
            bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=plans_list_markup(plans, renewal=True, uuid=user_info_process['uuid'])
            )

    elif key == 'renewal_plan_selected':
        plan_rows = USERS_DB.find_plan(id=value)
        if not plan_rows:
            bot.send_message(call.message.chat.id, MESSAGES['PLANS_NOT_FOUND'],
                             reply_markup=main_menu_keyboard_markup())
            return
        plan = plan_rows[0]
        renew_subscription_dict[call.message.chat.id]['plan_id'] = plan['id']
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text=plan_info_template(plan),
                              reply_markup=confirm_buy_plan_markup(plan['id'], renewal=True,uuid=renew_subscription_dict[call.message.chat.id]['uuid']))

    elif key == 'cancel_increase_wallet_balance':
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, MESSAGES['CANCEL_INCREASE_WALLET_BALANCE'],
                         reply_markup=main_menu_keyboard_markup())
    # ----------------------------------- User Configs Area -----------------------------------
    # User Configs - Main Menu
    elif key == 'configs_list':
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=sub_url_user_list_markup(value))
    # User Configs - Direct Link
    elif key == 'conf_dir':
        sub = utils.sub_links(value)
        if not sub:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        configs = utils.sub_parse(sub['sub_link'])
        if not configs:
            bot.send_message(call.message.chat.id, MESSAGES['ERROR_CONFIG_NOT_FOUND'])
            return
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=sub_user_list_markup(value,configs))
        
    # User Configs - Vless Configs Callback
    elif key == "conf_dir_vless":
        sub = utils.sub_links(value)
        if not sub:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        configs = utils.sub_parse(sub['sub_link'])
        if not configs:
            bot.send_message(call.message.chat.id, MESSAGES['ERROR_CONFIG_NOT_FOUND'])
            return
        if not configs['vless']:
            bot.send_message(call.message.chat.id, MESSAGES['ERROR_CONFIG_NOT_FOUND'])
            return
        msgs = configs_template(configs['vless'])
        for message in msgs:
            if message:
                bot.send_message(call.message.chat.id, f"{message}",
                                 reply_markup=main_menu_keyboard_markup())
    # User Configs - VMess Configs Callback
    elif key == "conf_dir_vmess":
        sub = utils.sub_links(value)
        if not sub:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        configs = utils.sub_parse(sub['sub_link'])
        if not configs:
            bot.send_message(call.message.chat.id, MESSAGES['ERROR_CONFIG_NOT_FOUND'])
            return
        if not configs['vmess']:
            bot.send_message(call.message.chat.id, MESSAGES['ERROR_CONFIG_NOT_FOUND'])
            return
        msgs = configs_template(configs['vmess'])
        for message in msgs:
            if message:
                bot.send_message(call.message.chat.id, f"{message}",
                                 reply_markup=main_menu_keyboard_markup())
    # User Configs - Trojan Configs Callback
    elif key == "conf_dir_trojan":
        sub = utils.sub_links(value)
        if not sub:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        configs = utils.sub_parse(sub['sub_link'])
        if not configs:
            bot.send_message(call.message.chat.id, MESSAGES['ERROR_CONFIG_NOT_FOUND'])
            return
        if not configs['trojan']:
            bot.send_message(call.message.chat.id, MESSAGES['ERROR_CONFIG_NOT_FOUND'])
            return
        msgs = configs_template(configs['trojan'])
        for message in msgs:
            if message:
                bot.send_message(call.message.chat.id, f"{message}",
                                 reply_markup=main_menu_keyboard_markup())

    # User Configs - Subscription Configs Callback
    elif key == "conf_sub_url":
        sub = utils.sub_links(value)
        if not sub:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        raw_sub_link = sub.get('sub_link_raw') or sub.get('sub_link')
        public_sub_link = sub.get('public_sub_link') or raw_sub_link
        qr_code = utils.txt_to_qr(raw_sub_link)
        if not qr_code:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        bot.send_photo(
            call.message.chat.id,
            photo=qr_code,
            caption=f"{KEY_MARKUP['CONFIGS_SUB']}\n<code>{public_sub_link}</code>",
            reply_markup=main_menu_keyboard_markup()
        )
    # User Configs - Base64 Subscription Configs Callback
    elif key == "conf_sub_url_b64":
        sub = utils.sub_links(value)
        if not sub:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        qr_code = utils.txt_to_qr(sub['sub_link_b64'])
        if not qr_code:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        bot.send_photo(
            call.message.chat.id,
            photo=qr_code,
            caption=f"{KEY_MARKUP['CONFIGS_SUB_B64']}\n<code>{sub['sub_link_b64']}</code>",
            reply_markup=main_menu_keyboard_markup()
        )
    # User Configs - Subscription Configs For Clash Callback
    elif key == "conf_clash":
        sub = utils.sub_links(value)
        if not sub:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        qr_code = utils.txt_to_qr(sub['clash_configs'])
        if not qr_code:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        bot.send_photo(
            call.message.chat.id,
            photo=qr_code,
            caption=f"{KEY_MARKUP['CONFIGS_CLASH']}\n<code>{sub['clash_configs']}</code>",
            reply_markup=main_menu_keyboard_markup()
        )
    # User Configs - Subscription Configs For Hiddify Callback
    elif key == "conf_hiddify":
        sub = utils.sub_links(value)
        if not sub:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        qr_code = utils.txt_to_qr(sub['hiddify_configs'])
        if not qr_code:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        bot.send_photo(
            call.message.chat.id,
            photo=qr_code,
            caption=f"{KEY_MARKUP['CONFIGS_HIDDIFY']}\n<code>{sub['hiddify_configs']}</code>",
            reply_markup=main_menu_keyboard_markup()
        )

    elif key == "conf_sub_auto":
        sub = utils.sub_links(value)
        if not sub:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        target_sub_link = sub.get('sub_link_auto_raw') or sub.get('sub_link_auto') or sub.get('sub_link')
        display_sub_link = sub.get('public_sub_link') or target_sub_link
        sub_data = None
        server_url = _get_server_api_url_by_uuid(value)
        if server_url:
            raw_user = api.find(server_url, uuid=value)
            user_info = utils.users_to_dict([raw_user]) if raw_user else None
            processed = utils.dict_process(server_url, user_info) if user_info else None
            if processed:
                sub_data = processed[0]
        qr_code = utils.txt_to_qr(target_sub_link)
        if not qr_code:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        bot.send_photo(
            call.message.chat.id,
            photo=qr_code,
            caption=f"{KEY_MARKUP['CONFIGS_SUB_AUTO']}\n<code>{display_sub_link}</code>",
            reply_markup=main_menu_keyboard_markup()
        )

    elif key == "conf_sub_sing_box":
        sub = utils.sub_links(value)
        if not sub:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        qr_code = utils.txt_to_qr(sub['sing_box'])
        if not qr_code:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        bot.send_photo(
            call.message.chat.id,
            photo=qr_code,
            caption=f"{KEY_MARKUP['CONFIGS_SING_BOX']}\n<code>{sub['sing_box']}</code>",
            reply_markup=main_menu_keyboard_markup()
        )

    elif key == "conf_sub_full_sing_box":
        sub = utils.sub_links(value)
        if not sub:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        qr_code = utils.txt_to_qr(sub['sing_box_full'])
        if not qr_code:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return
        bot.send_photo(
            call.message.chat.id,
            photo=qr_code,
            caption=f"{KEY_MARKUP['CONFIGS_FULL_SING_BOX']}\n<code>{sub['sing_box_full']}</code>",
            reply_markup=main_menu_keyboard_markup()
        )

    # manual
    elif key == "msg_manual":
        settings = utils.all_configs_settings()
        android_msg = settings['msg_manual_android'] if settings['msg_manual_android'] else MESSAGES['MANUAL_ANDROID']
        ios_msg = settings['msg_manual_ios'] if settings['msg_manual_ios'] else MESSAGES['MANUAL_IOS']
        win_msg = settings['msg_manual_windows'] if settings['msg_manual_windows'] else MESSAGES['MANUAL_WIN']
        mac_msg = settings['msg_manual_mac'] if settings['msg_manual_mac'] else MESSAGES['MANUAL_MAC']
        linux_msg = settings['msg_manual_linux'] if settings['msg_manual_linux'] else MESSAGES['MANUAL_LIN']
        if value == 'android':
            bot.send_message(call.message.chat.id, android_msg, reply_markup=main_menu_keyboard_markup())
        elif value == 'ios':
            bot.send_message(call.message.chat.id, ios_msg, reply_markup=main_menu_keyboard_markup())
        elif value == 'win':
            bot.send_message(call.message.chat.id, win_msg, reply_markup=main_menu_keyboard_markup())
        elif value == 'mac':
            bot.send_message(call.message.chat.id, mac_msg, reply_markup=main_menu_keyboard_markup())
        elif value == 'lin':
            bot.send_message(call.message.chat.id, linux_msg, reply_markup=main_menu_keyboard_markup())

    # ----------------------------------- Velvet UI Area -----------------------------------
    elif key == "velvet_title_menu":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        _send_velvet_main_menu(call.message.chat.id)

    elif key == "velvet_vpn_menu":
        subscriptions = _get_subscriptions_for_user(call.message.chat.id)
        text = MESSAGES['VELVET_VPN_MENU'] if subscriptions else MESSAGES['VELVET_NO_SUBS']
        bot.edit_message_text(
            text=text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=velvet_vpn_subscriptions_markup(subscriptions)
        )

    elif key == "velvet_renew_menu":
        subscriptions = _get_subscriptions_for_user(call.message.chat.id)
        if not subscriptions:
            bot.edit_message_text(
                text=MESSAGES['VELVET_NO_SUBS'],
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=velvet_vpn_subscriptions_markup([])
            )
            return
        bot.edit_message_text(
            text="🔄 Выберите подписку, которую хотите продлить:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=velvet_renew_subscriptions_markup(subscriptions)
        )

    elif key == "velvet_sub_open":
        if not _subscription_belongs_to_user(value, call.message.chat.id):
            bot.answer_callback_query(call.id, MESSAGES['SUBSCRIPTION_NOT_FOUND'], show_alert=True)
            return
        details = _render_subscription_details(value)
        if not details:
            bot.answer_callback_query(call.id, MESSAGES['SUBSCRIPTION_NOT_FOUND'], show_alert=True)
            return
        text, sub_id = details
        try:
            bot.edit_message_text(
                text=text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=velvet_subscription_actions_markup(value, sub_id),
                disable_web_page_preview=True,
            )
        except telebot.apihelper.ApiTelegramException:
            bot.send_message(
                call.message.chat.id,
                text=text,
                reply_markup=velvet_subscription_actions_markup(value, sub_id),
                disable_web_page_preview=True,
            )

    elif key == "velvet_setup":
        details = _render_subscription_details(value)
        if not details:
            bot.answer_callback_query(call.id, MESSAGES['SUBSCRIPTION_NOT_FOUND'], show_alert=True)
            return
        _, sub_id = details
        bot.edit_message_text(
            text=_build_setup_v2_text(value, sub_id),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=velvet_setup_markup(value),
            disable_web_page_preview=True,
        )

    elif key == "velvet_manual":
        bot.send_message(
            call.message.chat.id,
            MESSAGES['REQUEST_SELECT_OS_MANUAL'],
            reply_markup=users_bot_management_settings_panel_manual_markup()
        )

    elif key == "velvet_support":
        bot.send_message(call.message.chat.id, MESSAGES['SEND_TICKET_TO_ADMIN_TEMPLATE'], reply_markup=send_ticket_to_admin())

    elif key == "velvet_done":
        bot.send_message(call.message.chat.id, "✅Отлично! Если понадобится помощь, нажмите «🆘Помощь».", reply_markup=main_menu_keyboard_markup())

    elif key == "velvet_conf_happ":
        if not _subscription_belongs_to_user(value, call.message.chat.id):
            bot.answer_callback_query(call.id, MESSAGES['SUBSCRIPTION_NOT_FOUND'], show_alert=True)
            return

        server_url = _get_server_api_url_by_uuid(value)
        panel_base = server_url.replace(API_PATH, '') if server_url else None
        links = utils.sub_links(value, url=panel_base) if panel_base else utils.sub_links(value)
        source_url = (links or {}).get('sub_link_auto') or (links or {}).get('sub_link')
        if not source_url:
            bot.answer_callback_query(call.id, MESSAGES['SUBSCRIPTION_NOT_FOUND'], show_alert=True)
            return

        happ_sub_link = _add_url_query_params(source_url, {'app': '1', 'client': 'happ'})
        happ_deeplink = f"v2raytun://install-config?url={quote(happ_sub_link, safe='')}"
        qr_code = utils.txt_to_qr(happ_sub_link)
        if not qr_code:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'])
            return

        home_web_url = (links or {}).get('home_link')
        bot.send_photo(
            call.message.chat.id,
            photo=qr_code,
            caption=(
                "📱 Happ / V2RayTun\n\n"
                f"🔗 Ссылка подписки:\n<code>{html.escape(happ_sub_link)}</code>\n\n"
                f"⚡ Авто-импорт (deeplink):\n<code>{html.escape(happ_deeplink)}</code>"
            ),
            reply_markup=velvet_params_markup(value, home_web_url),
        )

    elif key == "velvet_params":
        server_url = _get_server_api_url_by_uuid(value)
        panel_base = server_url.replace(API_PATH, '') if server_url else None
        links = utils.sub_links(value, url=panel_base) if panel_base else utils.sub_links(value)
        # Native Hiddify route: https://<host>/<client_path>/<uuid>/?home=true
        home_web_url = (links or {}).get('home_link')
        params_text = (
            "\U0001f310 <b>Подписка SmartKamaVPN</b>\n\n"
            "Выберите клиент и получите подходящую ссылку/QR:\n"
            "• 📱 Happ / V2RayTun\n"
            "• 🟠 Hiddify\n"
            "• 🥷 Clash\n"
            "• 📦 Sing-box\n"
            "• ⚡ Авто-подключение\n"
            "• 🔗 Универсальная ссылка\n\n"
            "Сайт подписки:\n"
            f"<code>{html.escape(home_web_url or '')}</code>"
        )
        try:
            bot.edit_message_text(
                text=params_text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=velvet_params_markup(value, home_web_url),
                disable_web_page_preview=True,
            )
        except telebot.apihelper.ApiTelegramException:
            bot.send_message(
                call.message.chat.id,
                params_text,
                reply_markup=velvet_params_markup(value, home_web_url),
                disable_web_page_preview=True,
            )

    elif key == "velvet_devices":
        if '|' in value:
            page_str, uuid = value.split('|', 1)
            page = max(0, int(page_str))
        elif ':' in value:
            uuid, page_str = value.split(':', 1)
            page = max(0, int(page_str) - 1)
        else:
            uuid = value
            page = 0
        text, page, total_pages, page_item_indexes = _prepare_velvet_devices_screen(uuid, page)
        _safe_edit_message_text(
            text=text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=velvet_devices_markup(uuid, page, total_pages, page_item_indexes),
        )

    elif key in ("velvet_dev_block", "velvet_dev_del"):
        if not _device_actions_supported():
            bot.answer_callback_query(call.id, "Для текущего типа панели блокировка и удаление устройств недоступны", show_alert=True)
            if '|' in value:
                uuid = value.split('|', 1)[0]
                text, page, total_pages, page_item_indexes = _prepare_velvet_devices_screen(uuid, 0)
                _safe_edit_message_text(
                    text=text,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=velvet_devices_markup(uuid, page, total_pages, page_item_indexes),
                )
            return

        if '|' not in value:
            bot.answer_callback_query(call.id, MESSAGES['UNKNOWN_ERROR'], show_alert=True)
            return
        uuid, idx_str = value.split('|', 1)
        if not idx_str.isdigit():
            bot.answer_callback_query(call.id, MESSAGES['UNKNOWN_ERROR'], show_alert=True)
            return

        idx = int(idx_str)
        server_url = _get_server_api_url_by_uuid(uuid)
        raw_user = api.find(server_url, uuid=uuid) if server_url else None
        entries = _extract_device_entries(raw_user)
        if idx < 0 or idx >= len(entries):
            bot.answer_callback_query(call.id, "Устройство не найдено", show_alert=True)
            return

        target = entries[idx]
        if not _is_actionable_device_key(target.get('key')):
            bot.answer_callback_query(call.id, "Для этого устройства действие недоступно", show_alert=True)
            return
        action_ok = False
        if key == "velvet_dev_block":
            action_ok = api.block_device(server_url, uuid, target.get('key')) if server_url else False
            bot.answer_callback_query(call.id, "Устройство заблокировано" if action_ok else "Не удалось заблокировать", show_alert=not action_ok)
        else:
            action_ok = api.delete_device(server_url, uuid, target.get('key')) if server_url else False
            bot.answer_callback_query(call.id, "Устройство удалено" if action_ok else "Не удалось удалить", show_alert=not action_ok)

        page_size = 5
        target_page = idx // page_size
        text, page, total_pages, page_item_indexes = _prepare_velvet_devices_screen(uuid, target_page)
        _safe_edit_message_text(
            text=text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=velvet_devices_markup(uuid, page, total_pages, page_item_indexes),
        )

    elif key == "velvet_lte":
        bot.edit_message_text(
            text=MESSAGES['VELVET_LTE_TEXT'],
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=velvet_lte_packages_markup(value)
        )

    elif key == "velvet_lte_buy":
        if '|' in value:
            uuid, gb, price = value.split('|')
        else:
            uuid, gb, price = value.split(':')
        gb_int = int(gb)
        price_int = int(price)
        price_internal = price_int * 10
        wallet = USERS_DB.find_wallet(telegram_id=call.message.chat.id)
        balance = int(wallet[0]['balance']) if wallet else 0
        if balance < price_internal:
            needed = price_internal - balance
            bot.send_message(
                call.message.chat.id,
                MESSAGES['LACK_OF_WALLET_BALANCE'],
                reply_markup=wallet_info_specific_markup(needed)
            )
            return
        new_balance = balance - price_internal
        edit_ok = USERS_DB.edit_wallet(call.message.chat.id, balance=new_balance)
        if not edit_ok:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'], reply_markup=main_menu_keyboard_markup())
            return
        server_url = _get_server_api_url_by_uuid(uuid)
        if server_url:
            raw_user = api.find(server_url, uuid=uuid)
            if raw_user and isinstance(raw_user, dict):
                current_limit = float(raw_user.get('usage_limit_GB', 0) or 0)
                api.update(server_url, uuid, usage_limit_GB=current_limit + gb_int)
        bot.send_message(
            call.message.chat.id,
            MESSAGES['SKV_LTE_ACTIVATED'].format(gb=gb_int, price=price_int),
            reply_markup=main_menu_keyboard_markup()
        )

    elif key == "velvet_buy_sub":
        buy_subscription(call.message)

    elif key == "velvet_gift":
        bot.send_message(
            call.message.chat.id,
            MESSAGES['SKV_GIFT_MENU'],
            reply_markup=smartkamavpn_gift_menu_markup()
        )

    elif key == "velvet_gift_promo":
        bot.send_message(
            call.message.chat.id,
            MESSAGES['SKV_GIFT_PROMO_ASK_AMOUNT'],
            reply_markup=cancel_markup(),
        )
        bot.register_next_step_handler(call.message, next_step_gift_promo_amount)

    elif key == "velvet_gift_subscription":
        subscriptions = _get_subscriptions_for_user(call.message.chat.id)
        if not subscriptions:
            bot.send_message(call.message.chat.id, MESSAGES['VELVET_NO_SUBS'], reply_markup=main_menu_keyboard_markup())
            return
        bot.send_message(
            call.message.chat.id,
            MESSAGES['SKV_GIFT_SUB_PICK'],
            reply_markup=smartkamavpn_gift_subscription_markup(subscriptions),
        )

    elif key == "velvet_gift_sub_pick":
        if not _subscription_belongs_to_user(value, call.message.chat.id):
            bot.answer_callback_query(call.id, MESSAGES['SUBSCRIPTION_NOT_FOUND'], show_alert=True)
            return

        sub_record = utils.find_order_subscription_by_uuid(value) or {}
        user_raw = api.find(_get_server_api_url_by_uuid(value), uuid=value)
        sub_id = _resolve_display_sub_id(value, raw_user=user_raw, sub_record=sub_record)
        remaining = 0
        subscriptions = _get_subscriptions_for_user(call.message.chat.id)
        for sub in subscriptions:
            if sub.get('uuid') == value:
                remaining = int(sub.get('remaining_day', 0) or 0)
                break

        hours_left = _total_hours_left(remaining)
        expire_at = _format_expire_at(remaining)
        s_url = _get_server_api_url_by_uuid(value)
        p_base = s_url.replace(API_PATH, '') if s_url else None
        links = utils.sub_links(value, url=p_base) if p_base else utils.sub_links(value)
        raw_link = (links or {}).get('sub_link_auto') or (links or {}).get('sub_link')
        share_link = _shorten_url(raw_link) if raw_link else '-'

        bot.send_message(
            call.message.chat.id,
            MESSAGES['SKV_GIFT_SUB_CARD'].format(
                sub_id=sub_id,
                days=remaining,
                hours=hours_left,
                expire_at=expire_at,
                link=html.escape(share_link),
            ),
            reply_markup=main_menu_keyboard_markup(),
            disable_web_page_preview=True,
        )

    elif key == "velvet_bought_gifts":
        subscriptions = _get_subscriptions_for_user(call.message.chat.id)
        if not subscriptions:
            bot.send_message(call.message.chat.id, MESSAGES['VELVET_NO_SUBS'], reply_markup=main_menu_keyboard_markup())
            return
        lines = [MESSAGES['SKV_GIFT_BOUGHT_INTRO']]
        for sub in subscriptions:
            sub_uuid = sub.get('uuid')
            sub_id = sub.get('sub_id', '-')
            remaining = int(sub.get('remaining_day', 0))
            hours_left = _total_hours_left(remaining)
            time_left = _format_time_left(remaining)
            expire_at = _format_expire_at(remaining)
            s_url = _get_server_api_url_by_uuid(sub_uuid)
            p_base = s_url.replace(API_PATH, '') if s_url else None
            lnks = utils.sub_links(sub_uuid, url=p_base) if p_base else utils.sub_links(sub_uuid)
            if lnks:
                raw_link = lnks.get('sub_link_auto') or lnks.get('sub_link')
                short_gift = _shorten_url(raw_link) if raw_link else '-'
            else:
                short_gift = '-'
            status_icon = '✅' if sub.get('active') else '⏸️'
            lines.append(
                f"{status_icon} #{sub_id} — осталось {remaining} дн. ({hours_left} ч.)"
                f"\n⏳ {time_left}"
                f"\n🗓 До: {expire_at}"
                f"\n🔗 <code>{html.escape(short_gift)}</code>"
            )
        bot.send_message(
            call.message.chat.id,
            "\n\n".join(lines),
            reply_markup=main_menu_keyboard_markup(),
            disable_web_page_preview=True,
        )

    elif key == "velvet_info":
        settings = utils.all_configs_settings()
        support_username = settings.get('support_username') or '@support'
        channel_link = _build_channel_link(settings)
        status_link = _build_status_link(settings)
        if value == 'reviews':
            bot.send_message(call.message.chat.id, MESSAGES['VELVET_INFO_REVIEWS'])
        elif value == 'privacy':
            bot.send_message(call.message.chat.id, MESSAGES['VELVET_INFO_PRIVACY'])
        elif value == 'agreement':
            bot.send_message(call.message.chat.id, MESSAGES['VELVET_INFO_AGREEMENT'])
        elif value == 'pd':
            bot.send_message(call.message.chat.id, MESSAGES['VELVET_INFO_PD'])
        elif value == 'support':
            bot.send_message(call.message.chat.id, MESSAGES['VELVET_INFO_SUPPORT'].format(support=support_username))
        elif value == 'status':
            bot.send_message(call.message.chat.id, MESSAGES['VELVET_INFO_STATUS'].format(status_link=status_link))
        elif value == 'channel':
            bot.send_message(call.message.chat.id, MESSAGES['VELVET_INFO_CHANNEL'].format(channel_link=channel_link))





    # ----------------------------------- Back Area -----------------------------------
    # Back To User Menu
    elif key == "back_to_user_panel":
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=user_info_markup(value))
        

    # Back To Plans
    elif key == "back_to_plans":
        selected_type = buy_subscription_type.get(call.message.chat.id, 'individual')
        plans = _plans_for_buy_type(selected_type)
        if not plans:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                             reply_markup=main_menu_keyboard_markup())
            return
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text=MESSAGES['PLANS_LIST'], reply_markup=plans_list_markup(plans))

    # Back To Renewal Plans
    elif key == "back_to_renewal_plans":
        selected_type = buy_subscription_type.get(call.message.chat.id, 'individual')
        plans = _plans_for_buy_type(selected_type)
        if not plans:
            bot.send_message(call.message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                             reply_markup=main_menu_keyboard_markup())
            return
        # bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
        #                               reply_markup=plans_list_markup(plans, renewal=True,uuid=value))
        update_info_subscription(call.message, value,plans_list_markup(plans, renewal=True,uuid=value))
    
    elif key in ("back_to_servers", "back_to_buy_types"):
        bot.edit_message_text(
            text=MESSAGES['BUY_TYPE_SELECT'],
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=subscription_type_markup(),
        )
        

    # Delete Message
    elif key == "del_msg":
        bot.delete_message(call.message.chat.id, call.message.message_id)

    # Invalid Command
    else:
        bot.answer_callback_query(call.id, MESSAGES['ERROR_INVALID_COMMAND'])


# *********************************** Message Handler Area ***********************************
# Bot Start Message Handler
@bot.message_handler(commands=['start'])
def start_bot(message: Message):
    if is_user_banned(message.chat.id):
        return
    settings = utils.all_configs_settings()

    MESSAGES['WELCOME'] = MESSAGES['WELCOME'] if not settings['msg_user_start'] else settings['msg_user_start']
    
    if USERS_DB.find_user(telegram_id=message.chat.id):
        edit_name= USERS_DB.edit_user(telegram_id=message.chat.id,full_name=message.from_user.full_name)
        edit_username = USERS_DB.edit_user(telegram_id=message.chat.id,username=message.from_user.username)
        _send_velvet_main_menu(message.chat.id)
    else:
        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = USERS_DB.add_user(telegram_id=message.chat.id,username=message.from_user.username, full_name=message.from_user.full_name, created_at=created_at)
        if not status:
            bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'],
                             reply_markup=main_menu_keyboard_markup())
            return
        wallet_status = USERS_DB.find_wallet(telegram_id=message.chat.id)
        if not wallet_status:
            status = USERS_DB.add_wallet(telegram_id=message.chat.id)
            if not status:
                bot.send_message(message.chat.id, f"{MESSAGES['UNKNOWN_ERROR']}:Wallet",
                                 reply_markup=main_menu_keyboard_markup())
                return
            _send_velvet_main_menu(message.chat.id)

    join_status = is_user_in_channel(message.chat.id)
    if not join_status:
        return


@bot.message_handler(commands=['subscriptions'])
def subscriptions_command(message: Message):
    if is_user_banned(message.chat.id):
        return
    if not is_user_in_channel(message.chat.id):
        return
    _send_velvet_vpn_menu(message.chat.id)


@bot.message_handler(commands=['referral'])
def referral_command(message: Message):
    if is_user_banned(message.chat.id):
        return
    if not is_user_in_channel(message.chat.id):
        return
    username = bot.get_me().username
    ref_link = f"https://t.me/{username}?start=ref_{message.chat.id}"
    bot.send_message(message.chat.id, MESSAGES['VELVET_REFERRAL_TEXT'].format(ref_link=ref_link), reply_markup=velvet_referral_markup(ref_link))


@bot.message_handler(commands=['help'])
def help_command(message: Message):
    if is_user_banned(message.chat.id):
        return
    if not is_user_in_channel(message.chat.id):
        return
    settings = utils.all_configs_settings()
    bot.send_message(
        message.chat.id,
        MESSAGES['VELVET_HELP_TEXT'],
        reply_markup=velvet_help_markup(settings.get('support_username'))
    )


@bot.message_handler(commands=['about'])
def about_command(message: Message):
    if is_user_banned(message.chat.id):
        return
    if not is_user_in_channel(message.chat.id):
        return
    bot.send_message(message.chat.id, MESSAGES['VELVET_ABOUT_TEXT'], reply_markup=velvet_about_markup())


@bot.message_handler(func=lambda message: message.text == KEY_MARKUP['MAIN_MENU'])
def main_menu_button(message: Message):
    if is_user_banned(message.chat.id):
        return
    if not is_user_in_channel(message.chat.id):
        return
    _send_velvet_main_menu(message.chat.id)


@bot.message_handler(func=lambda message: message.text == KEY_MARKUP['INVITE_FRIEND'])
def invite_friend_button(message: Message):
    if is_user_banned(message.chat.id):
        return
    if not is_user_in_channel(message.chat.id):
        return
    username = bot.get_me().username
    ref_link = f"https://t.me/{username}?start=ref_{message.chat.id}"
    bot.send_message(message.chat.id, MESSAGES['VELVET_REFERRAL_TEXT'].format(ref_link=ref_link), reply_markup=velvet_referral_markup(ref_link))


@bot.message_handler(func=lambda message: message.text == KEY_MARKUP['HELP_MENU'])
def help_menu_button(message: Message):
    if is_user_banned(message.chat.id):
        return
    if not is_user_in_channel(message.chat.id):
        return
    settings = utils.all_configs_settings()
    bot.send_message(
        message.chat.id,
        MESSAGES['VELVET_HELP_TEXT'],
        reply_markup=velvet_help_markup(settings.get('support_username'))
    )


@bot.message_handler(func=lambda message: message.text == KEY_MARKUP['ABOUT_SERVICE'])
def about_service_button(message: Message):
    if is_user_banned(message.chat.id):
        return
    if not is_user_in_channel(message.chat.id):
        return
    bot.send_message(message.chat.id, MESSAGES['VELVET_ABOUT_TEXT'], reply_markup=velvet_about_markup())


# If user is not in users table, request /start
@bot.message_handler(func=lambda message: not USERS_DB.find_user(telegram_id=message.chat.id))
def not_in_users_table(message: Message):
    if is_user_banned(message.chat.id):
        return
    join_status = is_user_in_channel(message.chat.id)
    if not join_status:
        return
    bot.send_message(message.chat.id, MESSAGES['REQUEST_START'], reply_markup=main_menu_keyboard_markup())


# User Subscription Status Message Handler
@bot.message_handler(func=lambda message: message.text == KEY_MARKUP['SUBSCRIPTION_STATUS'])
def subscription_status(message: Message):
    if is_user_banned(message.chat.id):
        return
    join_status = is_user_in_channel(message.chat.id)
    if not join_status:
        return
    _send_velvet_vpn_menu(message.chat.id)


# User Buy Subscription Message Handler
@bot.message_handler(func=lambda message: message.text == KEY_MARKUP['BUY_SUBSCRIPTION'])
def buy_subscription(message: Message):
    if is_user_banned(message.chat.id):
        return
    join_status = is_user_in_channel(message.chat.id)
    if not join_status:
        return
    settings = utils.all_configs_settings()
    if not settings['buy_subscription_status']:
        bot.send_message(message.chat.id, MESSAGES['BUY_SUBSCRIPTION_CLOSED'], reply_markup=main_menu_keyboard_markup())
        return
    wallet = USERS_DB.find_wallet(telegram_id=message.chat.id)
    if not wallet:
        create_wallet_status = USERS_DB.add_wallet(message.chat.id)
        if not create_wallet_status: 
            bot.send_message(message.chat.id, MESSAGES['ERROR_UNKNOWN'])
            return
        wallet = USERS_DB.find_wallet(telegram_id=message.chat.id)
    _ensure_single_server_tariff_plans()
    server = _get_main_server()
    if not server:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'], reply_markup=main_menu_keyboard_markup())
        return

    if not _get_available_servers_with_capacity():
        bot.send_message(message.chat.id, MESSAGES['SERVER_IS_FULL'], reply_markup=main_menu_keyboard_markup())
        return
    bot.send_message(message.chat.id, MESSAGES['BUY_TYPE_SELECT'], reply_markup=subscription_type_markup())


# Config To QR Message Handler
@bot.message_handler(func=lambda message: message.text == KEY_MARKUP['TO_QR'])
def to_qr(message: Message):
    if is_user_banned(message.chat.id):
        return
    join_status = is_user_in_channel(message.chat.id)
    if not join_status:
        return
    bot.send_message(message.chat.id, MESSAGES['REQUEST_SEND_TO_QR'], reply_markup=cancel_markup())
    bot.register_next_step_handler(message, next_step_to_qr)


# Help Guide Message Handler
@bot.message_handler(func=lambda message: message.text == KEY_MARKUP['MANUAL'])
def help_guide(message: Message):
    if is_user_banned(message.chat.id):
        return
    join_status = is_user_in_channel(message.chat.id)
    if not join_status:
        return
    bot.send_message(message.chat.id, MESSAGES['MANUAL_HDR'],
                     reply_markup=users_bot_management_settings_panel_manual_markup())
    
# Help Guide Message Handler
@bot.message_handler(func=lambda message: message.text == KEY_MARKUP['FAQ'])
def faq(message: Message):
    if is_user_banned(message.chat.id):
        return
    join_status = is_user_in_channel(message.chat.id)
    if not join_status:
        return
    settings = utils.all_configs_settings()
    faq_msg = settings['msg_faq'] if settings['msg_faq'] else MESSAGES['UNKNOWN_ERROR']
    bot.send_message(message.chat.id, faq_msg, reply_markup=main_menu_keyboard_markup())


# Ticket To Support Message Handler
@bot.message_handler(func=lambda message: message.text == KEY_MARKUP['SEND_TICKET'])
def send_ticket(message: Message):
    if is_user_banned(message.chat.id):
        return
    join_status = is_user_in_channel(message.chat.id)
    if not join_status:
        return
    bot.send_message(message.chat.id, MESSAGES['SEND_TICKET_TO_ADMIN_TEMPLATE'], reply_markup=send_ticket_to_admin())


# Link Subscription Message Handler
@bot.message_handler(func=lambda message: message.text == KEY_MARKUP['LINK_SUBSCRIPTION'])
def link_subscription(message: Message):
    if is_user_banned(message.chat.id):
        return
    join_status = is_user_in_channel(message.chat.id)
    if not join_status:
        return
    bot.send_message(message.chat.id, MESSAGES['ENTER_SUBSCRIPTION_INFO'], reply_markup=cancel_markup())
    bot.register_next_step_handler(message, next_step_link_subscription)


# User Buy Subscription Message Handler
@bot.message_handler(func=lambda message: message.text == KEY_MARKUP['WALLET'])
def wallet_balance(message: Message):
    if is_user_banned(message.chat.id):
        return
    join_status = is_user_in_channel(message.chat.id)
    if not join_status:
        return
    user = USERS_DB.find_user(telegram_id=message.chat.id)
    if user:
        wallet_status = USERS_DB.find_wallet(telegram_id=message.chat.id)
        if not wallet_status:
            status = USERS_DB.add_wallet(telegram_id=message.chat.id)
            if not status:
                bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'])
                return

        wallet = USERS_DB.find_wallet(telegram_id=message.chat.id)
        wallet = wallet[0]
        telegram_user_data = wallet_info_template(wallet['balance'])

        bot.send_message(message.chat.id, telegram_user_data,
                         reply_markup=wallet_info_markup())
    else:
        bot.send_message(message.chat.id, MESSAGES['UNKNOWN_ERROR'])


@bot.message_handler(func=lambda message: message.text == KEY_MARKUP['GIFT_VPN'])
def gift_vpn_menu(message: Message):
    if is_user_banned(message.chat.id):
        return
    join_status = is_user_in_channel(message.chat.id)
    if not join_status:
        return
    bot.send_message(message.chat.id, MESSAGES['SKV_GIFT_MENU'], reply_markup=smartkamavpn_gift_menu_markup())


@bot.message_handler(func=lambda message: message.text == KEY_MARKUP['MTPROMO'])
def redeem_promo_menu(message: Message):
    if is_user_banned(message.chat.id):
        return
    join_status = is_user_in_channel(message.chat.id)
    if not join_status:
        return
    bot.send_message(message.chat.id, MESSAGES['SKV_GIFT_PROMO_REDEEM_ASK'], reply_markup=cancel_markup())
    bot.register_next_step_handler(message, next_step_redeem_gift_promo)


# User Buy Subscription Message Handler
@bot.message_handler(func=lambda message: message.text == KEY_MARKUP['FREE_TEST'])
def free_test(message: Message):
    if is_user_banned(message.chat.id):
        return
    join_status = is_user_in_channel(message.chat.id)
    if not join_status:
        return
    settings = utils.all_configs_settings()
    if not settings['test_subscription']:
        bot.send_message(message.chat.id, MESSAGES['FREE_TEST_NOT_AVAILABLE'], reply_markup=main_menu_keyboard_markup())
        return
    users = USERS_DB.find_user(telegram_id=message.chat.id)
    if users:
        user = users[0]
        if user['test_subscription']:
            bot.send_message(message.chat.id, MESSAGES['ALREADY_RECEIVED_FREE'],
                             reply_markup=main_menu_keyboard_markup())
            return
        else:
            # bot.send_message(message.chat.id, MESSAGES['REQUEST_SEND_NAME'], reply_markup=cancel_markup())
            # bot.register_next_step_handler(message, next_step_send_name_for_get_free_test)
            msg_wait = bot.send_message(message.chat.id, MESSAGES['WAIT'])
            servers = USERS_DB.select_servers()
            server_list = []
            if not servers:
                bot.send_message(message.chat.id, MESSAGES['SERVERS_NOT_FOUND'], reply_markup=main_menu_keyboard_markup())
                return
            for server in servers:
                user_index = 0
                #if server['status']:
                users_list = api.select(server['url'] + API_PATH)
                if users_list:
                    user_index = len(users_list)
                if server['user_limit'] > user_index:
                    server_list.append([server,True])
                else:
                    server_list.append([server,False])
            # bad request telbot api
            # bot.edit_message_text(chat_id=message.chat.id, message_id=msg_wait.message_id,
            #                                   text= MESSAGES['SERVERS_LIST'], reply_markup=servers_list_markup(server_list))
            bot.delete_message(message.chat.id, msg_wait.message_id)
            bot.send_message(message.chat.id, MESSAGES['SERVERS_LIST'], reply_markup=servers_list_markup(server_list, True))



# Cancel Message Handler
@bot.message_handler(func=lambda message: message.text == KEY_MARKUP['CANCEL'])
def cancel(message: Message):
    if is_user_banned(message.chat.id):
        return
    join_status = is_user_in_channel(message.chat.id)
    if not join_status:
        return
    bot.send_message(message.chat.id, MESSAGES['CANCELED'], reply_markup=main_menu_keyboard_markup())


# *********************************** Main Area ***********************************
def start():
    try:
        bot.remove_webhook()
    except Exception as e:
        logging.warning(f"Failed to remove user bot webhook: {e}")

    try:
        bot.set_my_commands([
            telebot.types.BotCommand("/start", BOT_COMMANDS['START']),
            telebot.types.BotCommand("/subscriptions", BOT_COMMANDS['SUBSCRIPTIONS']),
            telebot.types.BotCommand("/referral", BOT_COMMANDS['REFERRAL']),
            telebot.types.BotCommand("/help", BOT_COMMANDS['HELP']),
            telebot.types.BotCommand("/about", BOT_COMMANDS['ABOUT']),
        ])
    except telebot.apihelper.ApiTelegramException as e:
        if e.result.status_code == 401:
            logging.error("Invalid Telegram Bot Token!")
            return
        logging.warning(f"Failed to set user bot commands: {e}")
    except Exception as e:
        logging.warning(f"Failed to set user bot commands: {e}")
    # Welcome to Admin
    for admin in ADMINS_ID:
        try:
            bot.send_message(admin, MESSAGES['WELCOME_TO_ADMIN'])
        except Exception as e:
            logging.warning(f"Error in send message to admin {admin}: {e}")
    bot.enable_save_next_step_handlers()
    bot.load_next_step_handlers()
    while True:
        try:
            bot.infinity_polling()
        except Exception as e:
            logging.exception(f"User bot polling stopped: {e}")
            time.sleep(5)
