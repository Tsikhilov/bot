# Hiddify Panel API v1 Client
# Panel: https://bot.smartkama.ru/XG2KXE1cOyMGJVEW/
# Docs: https://github.com/hiddify/hiddify-config/discussions/3209

import json
import logging
import uuid as _uuid_module
import datetime
import requests
from urllib.parse import urlparse
from config import API_PATH, PANEL_ADMIN_ID

_session = requests.Session()
_session.headers.update({
    'Content-Type': 'application/json',
    'Accept': 'application/json',
})


def _headers(admin_uuid=None):
    """Build auth headers for Hiddify API"""
    uid = admin_uuid or PANEL_ADMIN_ID or ""
    return {'Hiddify-API-Key': uid, 'Content-Type': 'application/json'}


def _admin_endpoint(url):
    """Return admin API base (url already contains /api/v1)"""
    return url + "/admin"


def select(url, endpoint="/user/"):
    """Get all users from Hiddify admin endpoint"""
    import Utils.utils as utils
    try:
        resp = _session.get(_admin_endpoint(url) + endpoint, headers=_headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return utils.dict_process(url, utils.users_to_dict(data))
    except Exception as e:
        logging.error("API select error: %s", e)
        return None


def find(url, uuid, endpoint="/user/"):
    """Find single user by UUID"""
    try:
        resp = _session.get(_admin_endpoint(url) + endpoint + str(uuid) + "/",
                            headers=_headers(), timeout=30)
        if resp.status_code == 200:
            return resp.json()
        # Fallback: search in full list
        all_resp = _session.get(_admin_endpoint(url) + endpoint,
                                headers=_headers(), timeout=30)
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
           endpoint="/user/"):
    """Create new user in Hiddify panel, returns new UUID or None"""
    new_uuid = str(_uuid_module.uuid4())
    admin_uuid = urlparse(url).path.split('/')[2] if not added_by_uuid else added_by_uuid
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
    try:
        resp = _session.post(_admin_endpoint(url) + endpoint,
                             data=json.dumps(data), headers=_headers(), timeout=30)
        if resp.status_code in (200, 201):
            return new_uuid
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
        resp = _session.patch(_admin_endpoint(url) + endpoint + str(uuid) + "/",
                              data=json.dumps(user), headers=_headers(), timeout=30)
        if resp.status_code in (200, 201, 204):
            return uuid
        # Fallback to POST for older panels
        resp2 = _session.post(_admin_endpoint(url) + endpoint,
                              data=json.dumps(user), headers=_headers(), timeout=30)
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
                               headers=_headers(), timeout=30)
        return resp.status_code in (200, 204)
    except Exception as e:
        logging.error("API delete error: %s", e)
        return False


def get_panel_status(url):
    """Get Hiddify panel server status"""
    try:
        resp = _session.get(url + "/admin/server_status/", headers=_headers(), timeout=15)
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
