# Thanks to https://github.com/m-mjd/hiddybot_info_severs
import sqlite3
from urllib.parse import urlparse
import requests
from Database.dbManager import USERS_DB
from Utils import api
from config import API_PATH


def _to_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def scrape_data_from_json_url(url):
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()

        # Parse JSON data
        json_data = response.json()

        # Extract information from JSON using the shared function
        extracted_data = json_template(json_data)

        return extracted_data

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None


def json_template(data):
    system_stats = data.get('stats', {}).get('system', {})
    top5_stats = data.get('stats', {}).get('top5', {})
    usage_history = data.get('usage_history', {})
    bytes_recv = system_stats.get('bytes_recv')
    bytes_recv_cumulative = system_stats.get('bytes_recv_cumulative')
    bytes_sent = system_stats.get('bytes_sent')
    bytes_sent_cumulative = system_stats.get('bytes_sent_cumulative')
    cpu_percent = system_stats.get('cpu_percent')
    number_of_cores = system_stats.get('num_cpus')
    disk_total = system_stats.get('disk_total')
    disk_used = system_stats.get('disk_used')
    ram_total = system_stats.get('ram_total')
    ram_used = system_stats.get('ram_used')
    total_upload_server = system_stats.get('net_sent_cumulative_GB')
    total_download_server = system_stats.get('net_total_cumulative_GB')
    hiddify_used = system_stats.get('hiddify_used')
    load_avg_15min = system_stats.get('load_avg_15min')
    load_avg_1min = system_stats.get('load_avg_1min')
    load_avg_5min = system_stats.get('load_avg_5min')
    total_connections = system_stats.get('total_connections')
    total_unique_ips = system_stats.get('total_unique_ips')
    cpu_top5 = top5_stats.get('cpu', [])
    memory_top5 = top5_stats.get('memory', [])
    ram_top5 = top5_stats.get('ram', [])
    online_last_24h = usage_history.get('h24', {}).get('online')
    usage_last_24h = usage_history.get('h24', {}).get('usage')
    online_last_30_days = usage_history.get('last_30_days', {}).get('online')
    usage_last_30_days = usage_history.get('last_30_days', {}).get('usage')
    online_last_5min = usage_history.get('m5', {}).get('online')
    usage_last_5min = usage_history.get('m5', {}).get('usage')
    online_today = usage_history.get('today', {}).get('online')
    usage_today = usage_history.get('today', {}).get('usage')
    online_total = usage_history.get('total', {}).get('online')
    usage_total = usage_history.get('total', {}).get('usage')
    total_users = usage_history.get('total', {}).get('users')
    online_yesterday = usage_history.get('yesterday', {}).get('online')
    usage_yesterday = usage_history.get('yesterday', {}).get('usage')

    return {
        'bytes_recv': bytes_recv,
        'bytes_recv_cumulative': bytes_recv_cumulative,
        'bytes_sent': bytes_sent,
        'bytes_sent_cumulative': bytes_sent_cumulative,
        'cpu_percent': cpu_percent,
        'number_of_cores': number_of_cores,
        'disk_total': disk_total,
        'disk_used': disk_used,
        'ram_total': ram_total,
        'ram_used': ram_used,
        'total_upload_server': total_upload_server,
        'total_download_server': total_download_server,
        'hiddify_used': hiddify_used,
        'load_avg_15min': load_avg_15min,
        'load_avg_1min': load_avg_1min,
        'load_avg_5min': load_avg_5min,
        'total_connections': total_connections,
        'total_unique_ips': total_unique_ips,
        'cpu_top5': cpu_top5,
        'memory_top5': memory_top5,
        'ram_top5': ram_top5,
        'online_last_24h': online_last_24h,
        'usage_last_24h': usage_last_24h,
        'online_last_30_days': online_last_30_days,
        'usage_last_30_days': usage_last_30_days,
        'online_last_5min': online_last_5min,
        'usage_last_5min': usage_last_5min,
        'online_today': online_today,
        'usage_today': usage_today,
        'online_total': online_total,
        'usage_total': usage_total,
        'total_users': total_users,
        'online_yesterday': online_yesterday,
        'usage_yesterday': usage_yesterday,
    }



def server_status_template(result, server_name):
    lline = (32 * "-")
    
    bytes_recv = result.get('bytes_recv', 'N/A')
    bytes_recv_cumulative = result.get('bytes_recv_cumulative', 'N/A')
    bytes_sent = result.get('bytes_sent', 'N/A')
    bytes_sent_cumulative = result.get('bytes_sent_cumulative', 'N/A')
    cpu_percent = result.get('cpu_percent', 'N/A')
    number_of_cores = result.get('number_of_cores', 'N/A')
    disk_total = result.get('disk_total', 'N/A')
    disk_used = result.get('disk_used', 'N/A')
    ram_total = result.get('ram_total', 'N/A')
    ram_used = result.get('ram_used', 'N/A')
    total_upload_server = result.get('total_upload_server', 'N/A')
    total_download_server = result.get('total_download_server', 'N/A')
    online_last_24h = result.get('online_last_24h', 'N/A')
    usage_last_24h = result.get('usage_last_24h', 'N/A')
    usage_last_24h = f"{usage_last_24h / (1024 ** 3):.2f} GB" if usage_last_24h != 'N/A' else 'N/A'
    online_last_30_days = result.get('online_last_30_days', 'N/A')
    usage_last_30_days = result.get('usage_last_30_days', 'N/A')
    usage_last_30_days = f"{usage_last_30_days / (1024 ** 3):.2f} GB" if usage_last_30_days != 'N/A' else 'N/A'
    online_last_5min = result.get('online_last_5min', 'N/A')
    usage_last_5min = result.get('usage_last_5min', 'N/A')
    online_today = result.get('online_today', 'N/A')
    usage_today = result.get('usage_today', 'N/A')
    usage_today = f"{usage_today / (1024 ** 3):.2f} GB" if usage_today != 'N/A' else 'N/A'
    online_total = result.get('online_total', 'N/A')
    usage_total = result.get('usage_total', 'N/A')
    usage_total = f"{usage_total / (1024 ** 3):.2f} GB" if usage_total != 'N/A' else 'N/A'
    total_users = result.get('total_users', 'N/A')
    online_yesterday = result.get('online_yesterday', 'N/A')
    usage_yesterday = result.get('usage_yesterday', 'N/A')
    hiddify_used = result.get('hiddify_used', 'N/A')
    load_avg_15min = result.get('load_avg_15min', 'N/A')
    load_avg_1min = result.get('load_avg_1min', 'N/A')
    load_avg_5min = result.get('load_avg_5min', 'N/A')
    total_connections = result.get('total_connections', 'N/A')
    total_unique_ips = result.get('total_unique_ips', 'N/A')
    cpu_top5 = result.get('cpu_top5', 'N/A')
    memory_top5 = result.get('memory_top5', 'N/A')
    ram_top5 = result.get('ram_top5', 'N/A')
    # Calculate percentage for RAM and Disk
    ram_total_f = _to_float(ram_total)
    ram_used_f = _to_float(ram_used)
    disk_total_f = _to_float(disk_total)
    disk_used_f = _to_float(disk_used)
    total_upload_f = _to_float(total_upload_server)
    total_download_f = _to_float(total_download_server)
    bytes_recv_f = _to_float(bytes_recv)
    bytes_sent_f = _to_float(bytes_sent)

    ram_percent = (ram_used_f / ram_total_f) * 100 if ram_total_f > 0 else 0.0
    disk_percent = (disk_used_f / disk_total_f) * 100 if disk_total_f > 0 else 0.0

    # Format bytes with appropriate units
    formatted_bytes_recv = f"{bytes_recv_f / (1024 ** 2):.2f} МБ"
    formatted_bytes_sent = f"{bytes_sent_f / (1024 ** 2):.2f} МБ"

    # Add information for all servers
    return f"<b>Сервер: {server_name}</b>\n{lline}\n" \
                       f"<b>СИСТЕМА</b>\n"\
                       f"CPU: {cpu_percent}% - {number_of_cores} ядер\n" \
                       f"RAM: {ram_used_f:.2f} ГБ / {ram_total_f:.2f} ГБ ({ram_percent:.2f}%)\n" \
                       f"DISK: {disk_used_f:.2f} ГБ / {disk_total_f:.2f} ГБ ({disk_percent:.2f}%)\n\n" \
                       f"<b>СЕТЬ</b>\n"\
                       f"Всего пользователей: {total_users}\n" \
                       f"Трафик за сегодня: {usage_today}\n" \
                       f"Онлайн сейчас: {online_last_5min}\n" \
                       f"Сейчас принято: {formatted_bytes_recv}\n" \
                       f"Сейчас отправлено: {formatted_bytes_sent}\n" \
                       f"Онлайн сегодня: {online_today}\n" \
                       f"Онлайн за 30 дней: {online_last_30_days}\n" \
                       f"Трафик за 30 дней: {usage_last_30_days}\n"\
                       f"Всего скачано (сервер): {total_download_f:.2f} ГБ\n" \
                       f"Всего отправлено (сервер): {total_upload_f:.2f} ГБ\n" \

def get_server_status(server_row):
    server_name = server_row['title']
    server_url = server_row['url']

    # Prefer official API v2 status endpoint with auth header support.
    api_status = api.get_panel_status(server_url + API_PATH)
    if isinstance(api_status, dict) and api_status:
        cpu_percent = _to_float(api_status.get('cpu_percent', api_status.get('cpu', 0.0)))
        ram_percent = _to_float(api_status.get('ram_percent', api_status.get('memory', 0.0)))
        disk_percent = _to_float(api_status.get('disk_percent', api_status.get('disk', 0.0)))
        online_users = api_status.get('online_users', api_status.get('online', 'неизвестно'))
        total_users = api_status.get('total_users', api_status.get('users', 'неизвестно'))
        return (
            f"<b>Сервер: {server_name}</b>\n"
            f"--------------------------------\n"
            f"<b>Состояние по API</b>\n"
            f"CPU: {cpu_percent:.2f}%\n"
            f"RAM: {ram_percent:.2f}%\n"
            f"DISK: {disk_percent:.2f}%\n"
            f"Онлайн пользователей: {online_users}\n"
            f"Всего пользователей: {total_users}"
        )

    # Fallback to legacy stats endpoint.
    data = scrape_data_from_json_url(f"{server_url}/admin/get_data/")
    if not data:
        return f"❌Не удается получить статус сервера: {server_name}\nПроверьте доступность панели и API."
    txt = server_status_template(data, server_name)
    return txt
    