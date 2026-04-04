#!/usr/bin/env python3
import html
import json
import os
import re
import sqlite3
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, parse_qsl, quote, unquote, urlencode, urlparse, urlunparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "Database", "smartkamavpn.db")
HOST = "127.0.0.1"
PORT = 9101


UUID_RE = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
UUID_PATTERN = re.compile(UUID_RE)
PBK_PATTERN = re.compile(r"[?&]pbk=([^&#\s]+)", re.IGNORECASE)
SID_PATTERN = re.compile(r"[?&]sid=([^&#\s]*)", re.IGNORECASE)

AMS_PROFILE_NAMES = [
    "🔒 AMSTERDAM - ПРЯМОЙ ОБХОД",
    "🔒 AMSTERDAM - БЕЛЫЙ СПИСОК 1",
    "🔒 AMSTERDAM - ПОЛНЫЙ ТУННЕЛЬ",
    "🔒 AMSTERDAM - УНИВЕРСАЛЬНЫЙ LTE",
]

LOCAL_PROFILE_NAMES = [
    "⚡ ЛОКАЛЬНЫЙ - ПРЯМОЙ ОБХОД",
    "⚡ ЛОКАЛЬНЫЙ - СТАБИЛЬНЫЙ H2",
    "⚡ ЛОКАЛЬНЫЙ - HTTPUPGRADE",
]


def is_subscription_target(target_url):
    parsed = urlparse(target_url)
    if parsed.scheme not in ("http", "https"):
        return False
    path = parsed.path or ""
    return path.endswith("/all.txt") or "/sub/" in path or path.endswith("/sub")


def is_browser_client(headers):
    ua = (headers.get("User-Agent") or "").lower()
    browser_hints = ("mozilla", "chrome", "safari", "webkit", "telegram")
    return any(h in ua for h in browser_hints)


def is_app_client(headers):
    ua = (headers.get("User-Agent") or "").lower()
    app_hints = (
        "happ",
        "hiddify",
        "v2ray",
        "v2raytun",
        "sing-box",
        "singbox",
        "clash",
        "mihomo",
        "nekobox",
    )
    return any(h in ua for h in app_hints)


def build_install_page(target_url, token, meta):
    encoded = quote(target_url, safe="")

    escaped_target = html.escape(target_url, quote=True)
    deeplink_hiddify = f"hiddify://install-config?url={encoded}"
    deeplink_v2raytun = f"v2raytun://install-config?url={encoded}"
    deeplink_mtpromo = f"mtpromo://install-config?url={encoded}"
    deeplink_clash = f"clash://install-config?url={encoded}"
    deeplink_clash_meta = f"clashmeta://install-config?url={encoded}"
    raw_link = f"/s/{quote(token, safe='')}?raw=1"

    escaped_hiddify = html.escape(deeplink_hiddify, quote=True)
    escaped_v2raytun = html.escape(deeplink_v2raytun, quote=True)
    escaped_mtpromo = html.escape(deeplink_mtpromo, quote=True)
    escaped_clash = html.escape(deeplink_clash, quote=True)
    escaped_clash_meta = html.escape(deeplink_clash_meta, quote=True)
    escaped_raw_link = html.escape(raw_link, quote=True)

    remaining_days = meta.get("rd", "-")
    remaining_hours = meta.get("rh", "-")
    remaining_minutes = meta.get("rm", "-")
    usage_current = meta.get("uc", "-")
    usage_limit = meta.get("ul", "-")

    escaped_remaining = html.escape(f"{remaining_days} д. {remaining_hours} ч. {remaining_minutes} мин.", quote=True)
    escaped_usage = html.escape(f"{usage_current} / {usage_limit} ГБ", quote=True)

    js_sub_url = json.dumps(target_url)
    js_hiddify_link = json.dumps(deeplink_hiddify)

    return f"""<!doctype html>
<html lang=\"ru\">
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>SmartKamaVPN Установка</title>
    <style>
        :root {{
            --bg: #0b1220;
            --card: #121a2b;
            --text: #e6edf8;
            --muted: #9eb0cf;
            --accent: #3cb179;
            --accent2: #2a8cff;
            --border: #26334d;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif;
            color: var(--text);
            background: radial-gradient(circle at top right, #1a2742 0%, var(--bg) 55%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 16px;
        }}
        .card {{
            width: min(680px, 100%);
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 18px 48px rgba(0,0,0,.35);
        }}
        h1 {{ margin: 0 0 12px; font-size: 22px; }}
        p {{ margin: 0 0 12px; color: var(--muted); line-height: 1.5; }}
        .row {{ display: grid; gap: 10px; margin-top: 14px; }}
        .btn {{
            display: inline-block;
            text-decoration: none;
            color: #fff;
            padding: 12px 14px;
            border-radius: 10px;
            border: 1px solid transparent;
            font-weight: 600;
            text-align: center;
        }}
        .hiddify {{ background: var(--accent); }}
        .clash {{ background: var(--accent2); }}
        .secondary {{ background: #1a2438; border-color: var(--border); }}
        .url {{
            margin-top: 12px;
            padding: 10px;
            border-radius: 8px;
            border: 1px solid var(--border);
            background: #0f1728;
            color: #c9d8ef;
            word-break: break-all;
            font-size: 13px;
        }}
        .status {{ color: #9bd4b6; margin-top: 8px; font-size: 13px; }}
        .meta {{
            margin-top: 12px;
            padding: 12px;
            border-radius: 10px;
            border: 1px solid var(--border);
            background: #0f1728;
            color: #d8e5f7;
            font-size: 14px;
            line-height: 1.5;
        }}
    </style>
</head>
<body>
    <main class=\"card\">
        <h1>Открыть VPN-подписку</h1>
        <p>Пробуем автоматически открыть Hiddify. Если не сработало, используйте кнопки ниже.</p>
        <div class=\"meta\">
            ⏳ Осталось: {escaped_remaining}<br/>
            📊 Трафик: {escaped_usage}
        </div>
        <div class=\"row\">
            <a class=\"btn hiddify\" href=\"{escaped_hiddify}\">Открыть в Hiddify</a>
            <a class=\"btn hiddify\" href=\"{escaped_v2raytun}\">Открыть в V2RayTun</a>
            <a class=\"btn hiddify\" href=\"{escaped_mtpromo}\">Открыть в MTPromo</a>
            <a class=\"btn clash\" href=\"{escaped_clash}\">Открыть в Clash</a>
            <a class=\"btn clash\" href=\"{escaped_clash_meta}\">Открыть в Clash Meta</a>
            <a class=\"btn secondary\" href=\"{escaped_raw_link}\">Показать исходную ссылку подписки</a>
            <button class=\"btn secondary\" id=\"copyBtn\" type=\"button\">Скопировать ссылку подписки</button>
        </div>
        <div class=\"status\" id=\"status\">Пробуем запустить приложение...</div>
        <div class=\"url\" id=\"subUrl\">{escaped_target}</div>
    </main>
    <script>
        (function () {{
            const subUrl = {js_sub_url};
            const hiddifyLink = {js_hiddify_link};
            const status = document.getElementById('status');
            const copyBtn = document.getElementById('copyBtn');

            copyBtn.addEventListener('click', async function () {{
                try {{
                    await navigator.clipboard.writeText(subUrl);
                    status.textContent = 'Ссылка подписки скопирована.';
                }} catch (e) {{
                    status.textContent = 'Не удалось скопировать. Скопируйте вручную.';
                }}
            }});

            setTimeout(function () {{
                window.location.href = hiddifyLink;
            }}, 120);
        }})();
    </script>
</body>
</html>
""".encode("utf-8")


_RU_INJECT_JS = """
<script>
(function(){
  var MAX_TRIES = 80;
  var tries = 0;
    var textMap = {
        'Welcome': 'Добро пожаловать',
        'Choose your preferred language:': 'Выберите предпочитаемый язык:',
        'Import To App': 'Импорт в приложение',
        'Copy Link': 'Скопировать ссылку',
        'Open Telegram': 'Открыть Telegram',
        'Setup Guide': 'Инструкция по настройке',
        'Remaining time': 'Оставшееся время',
        'Days': 'Дни',
        'Hours': 'Часы',
        'Minutes': 'Минуты',
        'Total': 'Всего',
        'Used': 'Использовано',
        'Remaining': 'Осталось',
        'Account': 'Аккаунт',
        'Profile': 'Профиль',
        'Download QR': 'Скачать QR',
        'Download': 'Скачать',
        'Copy': 'Скопировать',
        'Open': 'Открыть',
        'Subscription': 'Подписка',
        'No Time Limit': 'Без ограничения по времени',
        'No Data Limit': 'Без лимита трафика',
        'Remaining Traffic': 'Оставшийся трафик',
        'Remaining Time': 'Оставшееся время',
        'Support': 'Поддержка',
        'View More': 'Показать больше',
        'Home': 'Главная',
        'Devices': 'Устройства',
        'Settings': 'Параметры',
        'Dashboard': 'Панель управления',
        'Traffic': 'Трафик',
        'Data': 'Данные',
        'Time': 'Время',
        'Expiration': 'Окончание',
        'Admin': 'Администратор',
        'User': 'Пользователь',
        'Active': 'Активно',
        'Inactive': 'Неактивно',
        'Disabled': 'Отключено',
        'Enable': 'Включить',
        'Disable': 'Отключить',
        'Delete': 'Удалить',
        'Edit': 'Редактировать',
        'Save': 'Сохранить',
        'Cancel': 'Отмена',
        'Confirm': 'Подтвердить',
        'Loading': 'Загрузка',
        'Error': 'Ошибка',
        'Success': 'Успешно',
        'Warning': 'Предупреждение',
        'Info': 'Информация',
        'Yes': 'Да',
        'No': 'Нет',
        'OK': 'ОК',
        'Close': 'Закрыть',
        'Back': 'Назад',
        'Next': 'Далее',
        'Previous': 'Назад',
        'First': 'Первая',
        'Last': 'Последняя',
        'Page': 'Страница',
        'Search': 'Поиск',
        'Filter': 'Фильтр',
        'Sort': 'Сортировка',
        'Export': 'Экспорт',
        'Import': 'Импорт',
        'Share': 'Поделиться',
        'Logout': 'Выход',
        'Login': 'Вход',
        'Register': 'Регистрация',
        'Password': 'Пароль',
        'Username': 'Имя пользователя',
        'Email': 'Электронная почта',
        'Phone': 'Телефон',
        'Address': 'Адрес',
        'Name': 'Имя',
        'Language': 'Язык',
        'Theme': 'Тема'
    };

    function translateNodeText(root){
        try {
            var walker = document.createTreeWalker(root || document.body, NodeFilter.SHOW_TEXT, null);
            var n;
            while ((n = walker.nextNode())) {
                var val = (n.nodeValue || '').trim();
                if (!val) continue;
                if (textMap[val]) {
                    n.nodeValue = n.nodeValue.replace(val, textMap[val]);
                    continue;
                }

                // Dynamic fragments (with variables) that are not exact dictionary keys.
                if (val.indexOf('Welcome, ') === 0) {
                    n.nodeValue = n.nodeValue.replace('Welcome, ', 'Добро пожаловать, ');
                    continue;
                }
                if (val.indexOf('Used Traffic: ') === 0) {
                    n.nodeValue = n.nodeValue.replace('Used Traffic: ', 'Использовано трафика: ');
                    continue;
                }
            }
        } catch(e) {}
    }

    function translateAttrs(){
        try {
            ['button','a','span','div','h1','h2','h3','p','label'].forEach(function(sel){
                document.querySelectorAll(sel).forEach(function(el){
                    var t = (el.innerText || '').trim();
                    if (textMap[t] && el.childElementCount === 0) {
                        el.innerText = textMap[t];
                    }
                });
            });
            document.querySelectorAll('[placeholder]').forEach(function(el){
                var p = (el.getAttribute('placeholder') || '').trim();
                if (textMap[p]) el.setAttribute('placeholder', textMap[p]);
            });
            document.querySelectorAll('[title]').forEach(function(el){
                var t = (el.getAttribute('title') || '').trim();
                if (textMap[t]) el.setAttribute('title', textMap[t]);
            });
        } catch(e) {}
    }

    function applyFallbackRU(){
        translateNodeText(document.body);
        translateAttrs();
    }

  function trySetLang(){
    tries++;
    // Attempt 1: patch i18next instance exposed by React
        if(window.__i18n_patched){
            applyFallbackRU();
            return;
        }
    var candidates = [];
    // look for i18next on window
    Object.keys(window).forEach(function(k){
      try{
        var v=window[k];
        if(v && typeof v.changeLanguage==='function' && typeof v.language==='string'){
          candidates.push(v);
        }
      }catch(e){}
    });
    if(candidates.length){
      candidates.forEach(function(i18n){
        if(i18n.language!=='ru') i18n.changeLanguage('ru').catch(function(){});
      });
      window.__i18n_patched=true;
            applyFallbackRU();
      return;
    }
    // Attempt 2: try React fiber tree to find i18n context
    var root=document.getElementById('root');
    if(root){
      var fk=Object.keys(root).find(function(k){return k.startsWith('__reactFiber')||k.startsWith('__reactInternalInstance');});
      if(fk){
        var node=root[fk];
        var depth=0;
        while(node && depth<200){
          var mi=node.memoizedProps||node.pendingProps||{};
          if(mi && mi.i18n && typeof mi.i18n.changeLanguage==='function'){
            if(mi.i18n.language!=='ru') mi.i18n.changeLanguage('ru').catch(function(){});
            window.__i18n_patched=true;
                        applyFallbackRU();
            return;
          }
          node=node.return||null;
          depth++;
        }
      }
    }
    if(tries<MAX_TRIES) setTimeout(trySetLang, 100);
        applyFallbackRU();
  }

    // Keep UI translated even when React rerenders asynchronously.
    var mo = new MutationObserver(function(){ applyFallbackRU(); });
    document.addEventListener('DOMContentLoaded', function(){
        applyFallbackRU();
        try {
            mo.observe(document.documentElement, { childList: true, subtree: true, characterData: true });
        } catch(e) {}
    });

  setTimeout(trySetLang, 200);
})();
</script>
""".encode("utf-8")

def _build_home_url(target_url):
    """Given a sub/?asn=unknown style URL build the ?home=true counterpart."""
    parsed = urlparse(target_url)
    parts = [p for p in parsed.path.split("/") if p]
    # Find UUID segment
    uuid_idx = None
    for i, p in enumerate(parts):
        if UUID_PATTERN.fullmatch(p):
            uuid_idx = i
            break
    if uuid_idx is None:
        return None
    # Rebuild path: /<client_path>/<uuid>/
    home_path = "/" + "/".join(parts[:uuid_idx + 1]) + "/"
    home_url = urlunparse((parsed.scheme, parsed.netloc, home_path, "", "home=true", ""))
    return home_url


def proxy_home_page(target_url):
    """Fetch the Hiddify home page, inject Russian language switcher, return bytes."""
    home_url = _build_home_url(target_url)
    if not home_url:
        return None
    try:
        req = urllib.request.Request(
            home_url,
            headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
                "Accept": "text/html,*/*",
                "Accept-Language": "ru-RU,ru;q=0.9",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            page_bytes = resp.read()
    except Exception:
        return None

    # Keep relative JS/CSS/image paths valid when page is served from /s/<token>?home=1.
    try:
        base_tag = f'<base href="{home_url}">'.encode('utf-8')
        if b'<head>' in page_bytes:
            page_bytes = page_bytes.replace(b'<head>', b'<head>' + base_tag, 1)
        elif b'</head>' in page_bytes:
            page_bytes = page_bytes.replace(b'</head>', base_tag + b'</head>', 1)
    except Exception:
        pass

    # Inject the language-switch script before </body>
    inject_point = b"</body>"
    if inject_point in page_bytes:
        page_bytes = page_bytes.replace(inject_point, _RU_INJECT_JS + inject_point, 1)
    else:
        page_bytes = page_bytes + _RU_INJECT_JS

    # Patch page title
    page_bytes = page_bytes.replace(b"<title>Hiddify | Panel</title>", b"<title>SmartKamaVPN</title>")

    return page_bytes


def proxy_subscription_source(target_url):
    try:
        req = urllib.request.Request(
            target_url,
            headers={
                "User-Agent": "SmartKamaShortlink/1.0",
                "Accept": "text/plain,*/*",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "text/plain; charset=utf-8")
            passthrough_headers = {}
            for h in (
                "profile-title",
                "subscription-userinfo",
                "profile-web-page-url",
                "support-url",
                "profile-update-interval",
                "content-disposition",
            ):
                v = resp.headers.get(h)
                if v:
                    passthrough_headers[h] = v
            return data, content_type, passthrough_headers
    except Exception:
        return None, None, {}


def _extract_uuid(target_url, text):
    path_match = re.search(rf"/(?:[^/]+)/({UUID_RE})/", target_url)
    if path_match:
        return path_match.group(1)
    text_match = re.search(rf"vless://({UUID_RE})@", text, flags=re.IGNORECASE)
    if text_match:
        return text_match.group(1)
    return None


def _extract_reality_keys(text):
    pbk_match = PBK_PATTERN.search(text)
    sid_match = SID_PATTERN.search(text)
    if not pbk_match:
        return None, None
    pbk = pbk_match.group(1)
    sid = sid_match.group(1) if sid_match else "f9"
    sid = sid or "f9"
    return pbk, sid


def _append_amsterdam_profiles(target_url, payload):
    if not payload:
        return payload

    try:
        text = payload.decode("utf-8", errors="ignore")
    except Exception:
        return payload

    user_uuid = _extract_uuid(target_url, text)
    pbk, sid = _extract_reality_keys(text)
    if not user_uuid or not pbk:
        return payload

    # Strip previously injected profiles to keep deterministic ordering.
    base_lines = []
    for raw_line in text.splitlines():
        line = (raw_line or "").strip()
        if not line:
            continue
        frag_decoded = ""
        if "#" in line:
            frag_decoded = unquote(line.split("#", 1)[1])
        if (
            "AMSTERDAM - " in frag_decoded
            or "ЛОКАЛЬНЫЙ - " in frag_decoded
            or "амстердам" in frag_decoded.lower()
            or "%d0%b0%d0%bc%d1%81%d1%82%d0%b5%d1%80%d0%b4%d0%b0%d0%bc" in line.lower()
        ):
            continue
        base_lines.append(line)

    # Prefer cloning already working templates from the current subscription.
    reality_template = None
    tls_h2_template = None
    httpupgrade_template = None
    for raw_line in text.splitlines():
        line = (raw_line or "").strip()
        if not line.startswith("vless://"):
            continue
        uri_no_frag = line.split("#", 1)[0]
        if reality_template is None and "security=reality" in uri_no_frag and "pbk=" in uri_no_frag:
            reality_template = line.split("#", 1)[0]
        if tls_h2_template is None and "security=tls" in uri_no_frag and "alpn=h2" in uri_no_frag:
            tls_h2_template = uri_no_frag
        if httpupgrade_template is None and "type=httpupgrade" in uri_no_frag and "security=tls" in uri_no_frag:
            httpupgrade_template = uri_no_frag

    host = (urlparse(target_url).hostname or "bot.smartkama.ru").strip()

    def _fallback_reality_uri():
        return (
            f"vless://{user_uuid}@{host}:443"
            f"?type=tcp&security=reality&pbk={pbk}&fp=chrome&sni=yandex.ru"
            f"&sid={sid}&flow=xtls-rprx-vision"
        )

    local_templates = [
        reality_template or _fallback_reality_uri(),
        tls_h2_template or reality_template or _fallback_reality_uri(),
        httpupgrade_template or reality_template or _fallback_reality_uri(),
    ]

    injected = []
    for template, name in zip(local_templates, LOCAL_PROFILE_NAMES):
        fragment = quote(name, safe="")
        injected.append(f"{template}#{fragment}")

    for name in AMS_PROFILE_NAMES:
        fragment = quote(name, safe="")
        injected.append(f"{(reality_template or _fallback_reality_uri())}#{fragment}")

    merged_lines = base_lines + injected
    return ("\n".join(merged_lines) + "\n").encode("utf-8")


def ensure_table(conn):
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


def find_target(token):
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_table(conn)
        row = conn.execute("SELECT target_url FROM short_links WHERE token=?", (token,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def update_target(token, target_url):
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_table(conn)
        conn.execute("UPDATE short_links SET target_url=? WHERE token=?", (target_url, token))
        conn.commit()
    finally:
        conn.close()


def _load_client_proxy_path():
    env_path = (os.getenv("HIDDIFY_CLIENT_PROXY_PATH") or "").strip("/")
    if env_path:
        return env_path

    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_table(conn)
        row = conn.execute("SELECT value FROM str_config WHERE key='hiddify_client_proxy_path' LIMIT 1").fetchone()
        if row and row[0]:
            return str(row[0]).strip("/")
    except Exception:
        return None
    finally:
        conn.close()
    return None


def _rewrite_subscription_path(url, client_path):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return url

    parts = [p for p in (parsed.path or "").split("/") if p]
    if len(parts) < 3:
        return url
    if parts[0] == client_path:
        return url

    import re
    if not re.fullmatch(UUID_RE, parts[1]):
        return url

    subpath = "/".join(parts[2:])
    sub_target = (
        subpath == "all.txt"
        or subpath == "sub"
        or subpath.startswith("sub/")
        or subpath.startswith("clash/")
        or subpath.startswith("full-singbox")
        or subpath.startswith("singbox")
    )
    if not sub_target:
        return url

    new_path = "/" + "/".join([client_path, parts[1]] + parts[2:])
    return urlunparse((parsed.scheme, parsed.netloc, new_path, parsed.params, parsed.query, parsed.fragment))


def _normalize_target_url(target_url):
    client_path = _load_client_proxy_path()
    if not client_path:
        return target_url

    parsed = urlparse(target_url)
    if parsed.scheme in ("http", "https"):
        return _rewrite_subscription_path(target_url, client_path)

    # Normalize deep-link wrappers like hiddify://install-config?url=<http...>
    if parsed.scheme in ("hiddify", "v2raytun", "mtpromo", "clash", "clashmeta"):
        q = dict(parse_qsl(parsed.query, keep_blank_values=True))
        raw_inner = q.get("url")
        if not raw_inner:
            return target_url
        fixed_inner = _rewrite_subscription_path(raw_inner, client_path)
        if fixed_inner == raw_inner:
            return target_url
        q["url"] = fixed_inner
        new_query = urlencode(q, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    return target_url


def find_meta(token):
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_table(conn)
        row = conn.execute(
            """
            SELECT remaining_days, remaining_hours, remaining_minutes, usage_current, usage_limit
            FROM short_links_meta WHERE token=?
            """,
            (token,),
        ).fetchone()
        if not row:
            return None
        return {
            "rd": row[0],
            "rh": row[1],
            "rm": row[2],
            "uc": row[3],
            "ul": row[4],
        }
    finally:
        conn.close()


class Handler(BaseHTTPRequestHandler):
    def _handle_redirect(self, send_body=True):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path.startswith("/s/"):
            token = path.split("/s/", 1)[1].strip("/")
            if token:
                target = find_target(token)
                if target:
                    normalized_target = _normalize_target_url(target)
                    if normalized_target != target:
                        try:
                            update_target(token, normalized_target)
                        except Exception:
                            pass
                        target = normalized_target

                    force_app_redirect = (query.get("app") or [""])[0] == "1"
                    force_web_page = (query.get("web") or [""])[0] == "1"
                    if is_subscription_target(target):
                        if (query.get("raw") or [""])[0] == "1":
                            payload, content_type, upstream_headers = proxy_subscription_source(target)
                            if payload is not None:
                                payload = _append_amsterdam_profiles(target, payload)
                                self.send_response(200)
                                self.send_header("Content-Type", content_type or "text/plain; charset=utf-8")
                                for hk, hv in (upstream_headers or {}).items():
                                    self.send_header(hk, hv)
                                self.send_header("Cache-Control", "no-store")
                                self.end_headers()
                                if send_body:
                                    self.wfile.write(payload)
                                return

                        if force_app_redirect:
                            payload, content_type, upstream_headers = proxy_subscription_source(target)
                            if payload is not None:
                                payload = _append_amsterdam_profiles(target, payload)
                                self.send_response(200)
                                self.send_header("Content-Type", content_type or "text/plain; charset=utf-8")
                                for hk, hv in (upstream_headers or {}).items():
                                    self.send_header(hk, hv)
                                self.send_header("Cache-Control", "no-store")
                                self.end_headers()
                                if send_body:
                                    self.wfile.write(payload)
                                return

                        # Default behavior for subscription links is direct redirect for app import reliability.
                        if is_app_client(self.headers) or not force_web_page:
                            self.send_response(302)
                            self.send_header("Location", target)
                            self.send_header("Cache-Control", "no-store")
                            self.end_headers()
                            return

                        self.send_response(200)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        if send_body:
                            meta = find_meta(token) or {
                                "rd": (query.get("rd") or ["-"])[0],
                                "rh": (query.get("rh") or ["-"])[0],
                                "rm": (query.get("rm") or ["-"])[0],
                                "uc": (query.get("uc") or ["-"])[0],
                                "ul": (query.get("ul") or ["-"])[0],
                            }
                            self.wfile.write(build_install_page(target, token, meta))
                    else:
                        self.send_response(302)
                        self.send_header("Location", target)
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                    return
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        if send_body:
            self.wfile.write(b"Not found")

    def do_GET(self):
        self._handle_redirect(send_body=True)

    def do_HEAD(self):
        self._handle_redirect(send_body=False)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Handler)
    server.serve_forever()
