# Hiddify Panel API Client
# Panel: https://bot.smartkama.ru/XG2KXE1cOyMGJVEW/
# Docs: https://github.com/hiddify/hiddify-config/discussions/3209

import json
import logging
import uuid as _uuid_module
import datetime
import re
import requests
from urllib.parse import urlparse
from config import API_PATH, PANEL_ADMIN_ID, HIDDIFY_API_KEY

_session = requests.Session()
_session.headers.update({
    'Content-Type': 'application/json',
    'Accept': 'application/json',
})


def _headers(admin_uuid=None):
    """Build auth headers for Hiddify API"""
    uid = admin_uuid or HIDDIFY_API_KEY or PANEL_ADMIN_ID or ""
    return {'Hiddify-API-Key': uid, 'Content-Type': 'application/json'}


def _extract_admin_uuid(url):
    """Extract panel API key UUID from URL path."""
    try:
        parts = [p for p in urlparse(url).path.split('/') if p]
        uuid_pattern = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
        for p in parts:
            if uuid_pattern.match(p):
                return p
    except Exception:
        pass
    return HIDDIFY_API_KEY or PANEL_ADMIN_ID or ""


def _admin_endpoint(url):
    """Return admin API base (url already contains /api/v2)"""
    return url + "/admin"


def select(url, endpoint="/user/"):
    """Get all users from Hiddify admin endpoint"""
    import Utils.utils as utils
    try:
        resp = _session.get(_admin_endpoint(url) + endpoint, headers=_headers(_extract_admin_uuid(url)), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return utils.dict_process(url, utils.users_to_dict(data))
    except Exception as e:
        logging.error("API select error: %s", e)
        return None


def find(url, uuid, endpoint="/user/"):
    """Find single user by UUID"""
    try:
        auth_uuid = _extract_admin_uuid(url)
        resp = _session.get(_admin_endpoint(url) + endpoint + str(uuid) + "/",
                    headers=_headers(auth_uuid), timeout=30)
        if resp.status_code == 200:
            return resp.json()
        # Fallback: search in full list
        all_resp = _session.get(_admin_endpoint(url) + endpoint,
                    headers=_headers(auth_uuid), timeout=30)
        if all_resp.status_code == 200:
            for user in all_resp.json():
                if user.get('uuid') == str(uuid):
                    return user
        return None
    except Exception as e:
        logging.error("API find error: %s", e)
        return None


def insert(url, name, usage_limit_GB, package_days,
           last_reset_time=None, added_by_uuid=None, mode="no_reset",
           last_online="1-01-01 00:00:00", telegram_id=None,
           comment=None, current_usage_GB=0, start_date=None,
           max_ips=None,
           endpoint="/user/"):
    """Create new user in Hiddify panel, returns new UUID or None"""
    new_uuid = str(_uuid_module.uuid4())
    admin_uuid = added_by_uuid or _extract_admin_uuid(url)
    if not admin_uuid:
        logging.error("API insert error: admin UUID is empty for URL %s", url)
        return None
    last_reset_time = last_reset_time or datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = start_date or datetime.datetime.now().strftime("%Y-%m-%d")

    data = {
        "uuid": new_uuid,
        "name": name,
        "usage_limit_GB": float(usage_limit_GB),
        "package_days": int(package_days),
        "added_by_uuid": admin_uuid,
        "last_reset_time": last_reset_time,
        "start_date": start_date,
        "mode": mode,
        "last_online": last_online,
        "telegram_id": telegram_id,
        "comment": comment,
        "current_usage_GB": float(current_usage_GB),
    }
    if max_ips is not None:
        data["max_ips"] = int(max_ips)
    try:
        resp = _session.post(_admin_endpoint(url) + endpoint,
                     data=json.dumps(data), headers=_headers(admin_uuid), timeout=30)
        if resp.status_code in (200, 201):
            return new_uuid

        # Some panel versions reject unknown fields; retry without max_ips.
        if max_ips is not None and resp.status_code in (400, 422):
            fallback_data = dict(data)
            fallback_data.pop("max_ips", None)
            resp2 = _session.post(_admin_endpoint(url) + endpoint,
                          data=json.dumps(fallback_data), headers=_headers(admin_uuid), timeout=30)
            if resp2.status_code in (200, 201):
                return new_uuid
            logging.error("API insert fallback error %s: %s", resp2.status_code, resp2.text[:300])
            return None

        logging.error("API insert error %s: %s", resp.status_code, resp.text[:300])
        return None
    except Exception as e:
        logging.error("API insert error: %s", e)
        return None


def update(url, uuid, endpoint="/user/", **kwargs):
    """Update existing user fields via PATCH"""
    try:
        user = find(url, uuid)
        if not user:
            return None
        user.update(kwargs)
        auth_uuid = _extract_admin_uuid(url)
        resp = _session.patch(_admin_endpoint(url) + endpoint + str(uuid) + "/",
                      data=json.dumps(user), headers=_headers(auth_uuid), timeout=30)
        if resp.status_code in (200, 201, 204):
            return uuid
        # Fallback to POST for older panels
        resp2 = _session.post(_admin_endpoint(url) + endpoint,
                      data=json.dumps(user), headers=_headers(auth_uuid), timeout=30)
        if resp2.status_code in (200, 201):
            return uuid
        logging.error("API update error %s: %s", resp.status_code, resp.text[:300])
        return None
    except Exception as e:
        logging.error("API update error: %s", e)
        return None


def delete(url, uuid, endpoint="/user/"):
    """Delete user from Hiddify panel"""
    try:
        resp = _session.delete(_admin_endpoint(url) + endpoint + str(uuid) + "/",
                       headers=_headers(_extract_admin_uuid(url)), timeout=30)
        return resp.status_code in (200, 204)
    except Exception as e:
        logging.error("API delete error: %s", e)
        return False


def get_panel_status(url):
    """Get Hiddify panel server status"""
    try:
        resp = _session.get(url + "/admin/server_status/", headers=_headers(_extract_admin_uuid(url)), timeout=15)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        logging.error("API status error: %s", e)
        return None


def reset_user_usage(url, uuid, endpoint="/user/"):
    """Reset user traffic usage to zero"""
    return update(url, uuid, endpoint, current_usage_GB=0,
                  last_reset_time=datetime.datetime.now().strftime("%Y-%m-%d"))


def reset_user_days(url, uuid, package_days, endpoint="/user/"):
    """Reset user subscription days"""
    return update(url, uuid, endpoint, package_days=package_days,
                  start_date=datetime.datetime.now().strftime("%Y-%m-%d"))


def _device_action_candidates(base, user_uuid, action, device_key):
    action = (action or "").strip().lower()
    key = str(device_key or "").strip()
    escaped = requests.utils.quote(key, safe="") if key else ""

    candidates = [
        ("POST", f"{base}/user/{user_uuid}/device/{escaped}/{action}/", None),
        ("POST", f"{base}/user/{user_uuid}/devices/{escaped}/{action}/", None),
        ("POST", f"{base}/user/{user_uuid}/ip/{escaped}/{action}/", None),
        ("POST", f"{base}/user/{user_uuid}/ips/{escaped}/{action}/", None),
        ("POST", f"{base}/user/{user_uuid}/{action}_device/", {"device": key}),
        ("POST", f"{base}/user/{user_uuid}/{action}_device/", {"ip": key}),
        ("POST", f"{base}/user/{user_uuid}/device/{action}/", {"device": key}),
        ("POST", f"{base}/user/{user_uuid}/ip/{action}/", {"ip": key}),
    ]

    if action in ("delete", "remove", "revoke"):
        candidates.extend([
            ("DELETE", f"{base}/user/{user_uuid}/device/{escaped}/", None),
            ("DELETE", f"{base}/user/{user_uuid}/ip/{escaped}/", None),
            ("DELETE", f"{base}/user/{user_uuid}/ips/{escaped}/", None),
        ])

    return candidates


def _update_user_devices_snapshot(url, user_uuid, device_key=None, remove_only=False):
    """Best-effort fallback when panel has no direct device action endpoint."""
    user = find(url, user_uuid)
    if not isinstance(user, dict):
        return False

    changed = False
    key = str(device_key or "").strip()
    for field in ("ips", "connected_ips", "online_ips", "devices", "clients"):
        if field not in user:
            continue
        value = user.get(field)
        if isinstance(value, list):
            before = len(value)
            if key:
                value = [item for item in value if str(item) != key]
            elif remove_only:
                value = []
            if len(value) != before:
                user[field] = value
                changed = True
        elif isinstance(value, dict):
            before = len(value)
            if key and key in value:
                value.pop(key, None)
            elif remove_only:
                value = {}
            if len(value) != before:
                user[field] = value
                changed = True

    if not changed:
        return False

    auth_uuid = _extract_admin_uuid(url)
    try:
        resp = _session.patch(
            _admin_endpoint(url) + f"/user/{user_uuid}/",
            data=json.dumps(user),
            headers=_headers(auth_uuid),
            timeout=30,
        )
        if resp.status_code in (200, 201, 204):
            return True
    except Exception as e:
        logging.error("API device snapshot update error: %s", e)
    return False


def device_action(url, uuid, device_key, action="delete"):
    """Best-effort device action helper for Hiddify panels with different endpoint shapes."""
    try:
        auth_uuid = _extract_admin_uuid(url)
        base = _admin_endpoint(url)
        for method, endpoint, payload in _device_action_candidates(base, str(uuid), action, device_key):
            try:
                if method == "POST":
                    resp = _session.post(endpoint, data=json.dumps(payload) if payload is not None else None,
                                         headers=_headers(auth_uuid), timeout=20)
                else:
                    resp = _session.delete(endpoint, headers=_headers(auth_uuid), timeout=20)

                if resp.status_code in (200, 201, 202, 204):
                    return True
            except Exception:
                continue

        # Fallback: try to mutate user payload directly.
        return _update_user_devices_snapshot(url, str(uuid), device_key=device_key, remove_only=False)
    except Exception as e:
        logging.error("API device action error: %s", e)
        return False


def block_device(url, uuid, device_key):
    for action in ("block", "ban", "disable"):
        if device_action(url, uuid, device_key, action=action):
            return True
    return False


def delete_device(url, uuid, device_key):
    for action in ("delete", "remove", "revoke"):
        if device_action(url, uuid, device_key, action=action):
            return True
    return False
