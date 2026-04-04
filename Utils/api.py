# 3x-ui Panel API Client
# Panel: https://sub.smartkama.ru:55445/
# Docs: https://github.com/mhsanaei/3x-ui

import json
import logging
import uuid as _uuid_module
import datetime
import time
import requests
from config import (
    THREEXUI_USERNAME, THREEXUI_PASSWORD,
    THREEXUI_PANEL_URL, THREEXUI_WEB_BASE_PATH,
    THREEXUI_INBOUND_ID,
)

# ---------------------------------------------------------------------------
# Session и авторизация
# ---------------------------------------------------------------------------
_session = requests.Session()
_session.headers.update({'Accept': 'application/json'})
_logged_in = False


def _base_url():
    base = THREEXUI_PANEL_URL.rstrip('/')
    path = THREEXUI_WEB_BASE_PATH.strip('/')
    return f"{base}/{path}"


def _login():
    global _logged_in
    try:
        resp = _session.post(
            f"{_base_url()}/login",
            data={"username": THREEXUI_USERNAME, "password": THREEXUI_PASSWORD},
            timeout=15,
        )
        data = resp.json()
        if data.get("success"):
            _logged_in = True
            return True
        logging.error("3x-ui login failed: %s", data.get("msg"))
        return False
    except Exception as e:
        logging.error("3x-ui login error: %s", e)
        return False


def _api(method, path, **kwargs):
    """Authenticated request — re-logins on session expiry."""
    global _logged_in
    if not _logged_in:
        _login()
    url = f"{_base_url()}{path}"
    resp = _session.request(method, url, timeout=30, **kwargs)
    if resp.status_code == 401:
        _logged_in = False
        _login()
        resp = _session.request(method, url, timeout=30, **kwargs)
    return resp


# ---------------------------------------------------------------------------
# Конвертация форматов
# ---------------------------------------------------------------------------

def _gb_to_bytes(gb):
    return int(float(gb) * 1024 ** 3) if gb else 0


def _bytes_to_gb(b):
    return round(int(b) / 1024 ** 3, 3) if b else 0.0


def _days_to_expiry_ms(package_days, start_date=None):
    """Вычисляет Unix-timestamp в миллисекундах для даты истечения."""
    if not package_days:
        return 0
    if start_date:
        try:
            base = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        except Exception:
            base = datetime.datetime.utcnow()
    else:
        base = datetime.datetime.utcnow()
    expiry = base + datetime.timedelta(days=int(package_days))
    return int(expiry.timestamp() * 1000)


def _expiry_ms_to_days(expiry_ms):
    """Сколько дней осталось с текущего момента."""
    if not expiry_ms:
        return None
    remaining = (expiry_ms / 1000) - time.time()
    return max(0, int(remaining / 86400))


def _expiry_ms_to_start_date(expiry_ms, package_days):
    """Обратно вычисляет start_date из expiryTime и package_days."""
    if not expiry_ms or not package_days:
        return datetime.datetime.utcnow().strftime("%Y-%m-%d")
    start_ts = (expiry_ms / 1000) - int(package_days) * 86400
    return datetime.datetime.utcfromtimestamp(start_ts).strftime("%Y-%m-%d")


def _client_to_user(client, stats=None):
    """Преобразует 3x-ui client dict в формат, совместимый с Hiddify-логикой бота."""
    expiry_ms = client.get("expiryTime", 0)
    total_bytes = client.get("totalGB", 0)  # в API это уже байты (несмотря на имя)
    usage_limit_gb = _bytes_to_gb(total_bytes) if total_bytes else 0.0

    up = stats.get("up", 0) if stats else 0
    down = stats.get("down", 0) if stats else 0
    current_usage_gb = _bytes_to_gb(up + down)

    # package_days: сохраняем в comment как "days:<N>" если нет expiryTime
    comment = client.get("remark") or client.get("email") or ""
    package_days = None
    if expiry_ms:
        remaining = _expiry_ms_to_days(expiry_ms)
        package_days = remaining
    else:
        package_days = 36500  # бессрочный

    start_date = _expiry_ms_to_start_date(expiry_ms, package_days) if expiry_ms else \
        datetime.datetime.utcnow().strftime("%Y-%m-%d")

    return {
        "uuid": client.get("id"),
        "name": client.get("email", ""),
        "last_online": "1-01-01 00:00:00",
        "expiry_time": expiry_ms,
        "usage_limit_GB": usage_limit_gb,
        "package_days": package_days,
        "mode": "no_reset",
        "monthly": None,
        "start_date": start_date,
        "current_usage_GB": current_usage_gb,
        "last_reset_time": start_date,
        "comment": comment,
        "telegram_id": client.get("tgId") or None,
        "added_by": None,
        "max_ips": client.get("limitIp") or None,
        "enable": client.get("enable", True),
        "sub_id": client.get("subId", ""),
    }


def _get_inbound_clients(inbound_id=None):
    """Возвращает список клиентов из указанного inbound."""
    iid = inbound_id or THREEXUI_INBOUND_ID
    try:
        resp = _api("GET", "/panel/api/inbounds/list")
        if resp.status_code != 200:
            return []
        data = resp.json()
        if not data.get("success"):
            return []
        for inbound in data.get("obj", []):
            if str(inbound.get("id")) == str(iid):
                raw = inbound.get("settings", "{}")
                settings = json.loads(raw) if isinstance(raw, str) else raw
                return settings.get("clients", [])
        return []
    except Exception as e:
        logging.error("_get_inbound_clients error: %s", e)
        return []


def _get_client_stats(email):
    """Трафик клиента по email из 3x-ui."""
    try:
        resp = _api("GET", f"/panel/api/inbounds/getClientTraffics/{email}")
        if resp.status_code == 200:
            d = resp.json()
            if d.get("success"):
                return d.get("obj") or {}
    except Exception as e:
        logging.error("_get_client_stats error: %s", e)
    return {}


# ---------------------------------------------------------------------------
# Публичный API — та же сигнатура, что была в Hiddify-клиенте
# ---------------------------------------------------------------------------

def select(url=None, endpoint=None):
    """Получить всех клиентов из inbound."""
    import Utils.utils as utils
    try:
        clients = _get_inbound_clients()
        users = []
        for c in clients:
            stats = _get_client_stats(c.get("email", ""))
            users.append(_client_to_user(c, stats))
        return utils.dict_process(url or THREEXUI_PANEL_URL, users)
    except Exception as e:
        logging.error("API select error: %s", e)
        return None


def find(url=None, uuid=None, endpoint=None):
    """Найти клиента по UUID."""
    try:
        clients = _get_inbound_clients()
        for c in clients:
            if c.get("id") == str(uuid):
                stats = _get_client_stats(c.get("email", ""))
                return _client_to_user(c, stats)
        return None
    except Exception as e:
        logging.error("API find error: %s", e)
        return None


def insert(url=None, name=None, usage_limit_GB=0, package_days=30,
           last_reset_time=None, added_by_uuid=None, mode="no_reset",
           last_online="1-01-01 00:00:00", telegram_id=None,
           comment=None, current_usage_GB=0, start_date=None,
           max_ips=None, endpoint=None):
    """Создать нового клиента в 3x-ui inbound, вернуть UUID или None."""
    new_uuid = str(_uuid_module.uuid4())
    email = name or f"user_{new_uuid[:8]}"
    expiry_ms = _days_to_expiry_ms(package_days, start_date)

    client = {
        "id": new_uuid,
        "alterId": 0,
        "email": email,
        "limitIp": int(max_ips) if max_ips else 0,
        "totalGB": _gb_to_bytes(usage_limit_GB),
        "expiryTime": expiry_ms,
        "enable": True,
        "flow": "xtls-rprx-vision",
        "tgId": str(telegram_id) if telegram_id else "",
        "subId": new_uuid[:8],
    }
    payload = {"id": THREEXUI_INBOUND_ID, "settings": json.dumps({"clients": [client]})}
    try:
        resp = _api("POST", "/panel/api/inbounds/addClient", json=payload)
        data = resp.json()
        if data.get("success"):
            return new_uuid
        logging.error("API insert error: %s", data.get("msg"))
        return None
    except Exception as e:
        logging.error("API insert error: %s", e)
        return None


def update(url=None, uuid=None, endpoint=None, **kwargs):
    """Обновить поля клиента."""
    try:
        clients = _get_inbound_clients()
        target = next((c for c in clients if c.get("id") == str(uuid)), None)
        if not target:
            return None

        # Маппинг Hiddify-полей → 3x-ui поля
        if "usage_limit_GB" in kwargs:
            target["totalGB"] = _gb_to_bytes(kwargs["usage_limit_GB"])
        if "package_days" in kwargs:
            sd = kwargs.get("start_date") or datetime.datetime.utcnow().strftime("%Y-%m-%d")
            target["expiryTime"] = _days_to_expiry_ms(kwargs["package_days"], sd)
        if "start_date" in kwargs and "package_days" not in kwargs:
            pd = _expiry_ms_to_days(target.get("expiryTime", 0)) or 30
            target["expiryTime"] = _days_to_expiry_ms(pd, kwargs["start_date"])
        if "max_ips" in kwargs and kwargs["max_ips"] is not None:
            target["limitIp"] = int(kwargs["max_ips"])
        if "telegram_id" in kwargs:
            target["tgId"] = str(kwargs["telegram_id"]) if kwargs["telegram_id"] else ""
        if "enable" in kwargs:
            target["enable"] = bool(kwargs["enable"])

        payload = {"id": THREEXUI_INBOUND_ID, "settings": json.dumps({"clients": [target]})}
        resp = _api("POST", f"/panel/api/inbounds/updateClient/{uuid}", json=payload)
        data = resp.json()
        if data.get("success"):
            return uuid
        logging.error("API update error: %s", data.get("msg"))
        return None
    except Exception as e:
        logging.error("API update error: %s", e)
        return None


def delete(url=None, uuid=None, endpoint=None):
    """Удалить клиента из inbound."""
    try:
        resp = _api("POST", f"/panel/api/inbounds/{THREEXUI_INBOUND_ID}/delClient/{uuid}")
        data = resp.json()
        return bool(data.get("success"))
    except Exception as e:
        logging.error("API delete error: %s", e)
        return False


def get_panel_status(url=None):
    """Статус сервера 3x-ui."""
    try:
        resp = _api("GET", "/panel/api/server/status")
        if resp.status_code == 200:
            d = resp.json()
            if d.get("success"):
                return d.get("obj")
        return None
    except Exception as e:
        logging.error("API status error: %s", e)
        return None


def reset_user_usage(url=None, uuid=None, endpoint=None):
    """Сбросить трафик клиента."""
    try:
        clients = _get_inbound_clients()
        target = next((c for c in clients if c.get("id") == str(uuid)), None)
        if not target:
            return None
        email = target.get("email", "")
        resp = _api("POST", f"/panel/api/inbounds/resetClientTraffic/{email}")
        data = resp.json()
        return uuid if data.get("success") else None
    except Exception as e:
        logging.error("API reset_user_usage error: %s", e)
        return None


def reset_user_days(url=None, uuid=None, package_days=30, endpoint=None):
    """Продлить подписку клиента на package_days дней от сейчас."""
    return update(url, uuid,
                  package_days=package_days,
                  start_date=datetime.datetime.utcnow().strftime("%Y-%m-%d"))


# ---------------------------------------------------------------------------
# Заглушки для device_action (в 3x-ui нет отдельного device API)
# ---------------------------------------------------------------------------

def device_action(url=None, uuid=None, device_key=None, action="delete"):
    return update(url, uuid, max_ips=0) is not None


def block_device(url=None, uuid=None, device_key=None):
    return update(url, uuid, enable=False) is not None


def delete_device(url=None, uuid=None, device_key=None):
    return device_action(url, uuid, device_key, action="delete")
