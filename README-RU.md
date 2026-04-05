# SmartKamaVPN Telegram Bot

Telegram бот для управления VPN-подписками на базе Hiddify 12.1.0b5 с интеграцией ЮKassa.

## Возможности

- 🌍 **Поддержка нескольких серверов**
- 💳 **Интеграция с ЮKassa** - прием платежей онлайн
- 💰 **Система кошельков** - пользователи могут пополнять баланс
- 📊 **Управление подписками** - создание, продление, отслеживание
- 🎁 **Бесплатный тестовый период**
- 🔔 **Уведомления** - напоминания об истечении подписки
- 📱 **QR-коды** - быстрое подключение
- 📖 **Руководства** - инструкции для разных ОС
- 🛡️ **Админ-панель** - полное управление

## Требования

- Python 3.8+
- Hiddify Panel 12.1.0b5+
- ЮKassa аккаунт (опционально)

## Установка

### Автоматическая установка

```bash
bash <(curl -Ls https://raw.githubusercontent.com/Tsikhilov/SmartKamaVPN/main/install.sh)
```

### Ручная установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/Tsikhilov/SmartKamaVPN.git
cd SmartKamaVPN-Bot
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Настройте бота:
```bash
python3 config.py
```

4. Запустите бота:
```bash
python3 smartkamavpnTelegramBot.py
```

## Прод-проверка API (рекомендуется)

Перед перезапуском сервиса проверка теперь выбирается по активному провайдеру панели:

- `panel_provider=3xui` -> `scripts/selfcheck_api.py`
- `panel_provider=marzban` -> `scripts/selfcheck_marzban_api.py`

Ручной запуск:

```bash
python3 scripts/selfcheck_api.py
python3 scripts/selfcheck_marzban_api.py
```

Для Marzban доступен опциональный write-smoke (создание/чтение/обновление/сброс/удаление тестового пользователя):

```bash
MARZBAN_SELFCHECK_WRITE=1 python3 scripts/selfcheck_marzban_api.py
```

## Переключение провайдера панели (под ключ)

На сервере можно безопасно посмотреть текущий провайдер и Marzban-параметры:

```bash
python3 scripts/server_set_panel_provider.py --show
```

Переключить провайдер:

```bash
python3 scripts/server_set_panel_provider.py --provider 3xui
python3 scripts/server_set_panel_provider.py --provider marzban --marzban-panel-url https://example.com
```

`--provider marzban` сохраняет уже существующие Marzban-поля, если новые значения явно не переданы.
Если в БД поля пустые, скрипт попробует взять `MARZBAN_*` из окружения.

Через PowerShell-инструменты деплоя:

```powershell
. .\scripts\prod_tools.ps1
Get-ProdPanelProvider
Set-ProdPanelProvider -Provider marzban -MarzbanPanelUrl "https://example.com"

# Полный контур: deploy -> switch provider -> selfchecks -> guard -> autotune
Invoke-ProdMarzbanTurnkey -MarzbanPanelUrl "https://example.com" -SubId "01dcf49b"
```

## Guard-скрипт для прода (диагностика + автофикс + smoke)

Для проверки подписок, shortlink, Reality-параметров и сервисов в один шаг:

```bash
python3 scripts/server_ops_guard.py --mode all
```

Отдельные режимы:

```bash
# Только диагностика
python3 scripts/server_ops_guard.py --mode diagnose

# Автоисправление типовых проблем + повторная диагностика
python3 scripts/server_ops_guard.py --mode autofix

# Короткий smoke-тест /sub и /s
python3 scripts/server_ops_guard.py --mode smoke
```

Если нужно явно проверить конкретную подписку:

```bash
python3 scripts/server_ops_guard.py --mode all --sub-id ec0a9260
```

По умолчанию скрипт использует:
- x-ui DB: `/etc/x-ui/x-ui.db`
- bot DB: `/opt/SmartKamaVPN/Database/smartkamavpn.db`
- домен подписок: `sub.smartkama.ru`

## Снижение пинга протоколов

Для уменьшения задержек на проде используйте связку из двух шагов:

```bash
# 1) Тюнинг TCP стека (fq + bbr + tcp_fastopen)
python3 scripts/server_tune_network.py

# 2) Применение latency-aware профилей (выбор самых быстрых Reality SNI)
python3 scripts/server_apply_nl_profiles.py
```

После применения рекомендуется проверить целостность контура:

```bash
python3 scripts/server_ops_guard.py --mode all
```

## One-click автотюнинг прода (WARP + профили + guard)

Запуск полного безопасного автотюнинга:

```bash
python3 scripts/server_autotune_stack.py --full
```

Что делает `--full`:
- применяет TCP тюнинг (`server_tune_network.py`)
- применяет latency-aware профили (`server_apply_nl_profiles.py`)
- обновляет `xrayTemplateConfig` для селективного WARP-роутинга по проблемным зарубежным доменам
- отключает `tgBotEnable` при конфликте polling (если токен панели совпадает с токеном админ-бота)
- перезапускает x-ui при изменениях
- запускает guard (`server_ops_guard.py --mode all`)

Важно:
- в этой сборке x-ui `balancerTag`/`balancers` из шаблона не материализуются в runtime-конфиг и могут уронить Xray.
- поэтому используется только безопасный селективный `outboundTag=warp`.

## Планировщик автотюнинга (systemd timer)

Установить периодический автотюнинг 2 раза в сутки:

```bash
python3 scripts/server_install_autotune_timer.py --on-calendar "*-*-* 04,16:00:00"
```

Проверить таймер:

```bash
systemctl status smartkama-autotune.timer --no-pager
systemctl list-timers smartkama-autotune.timer --no-pager
```

## Telegram панели (ограничение)

Если включить Telegram-бот панели (`tgBotEnable=true`) и использовать тот же токен, что у основного админ-бота SmartKama,
возникнет конфликт `getUpdates 409` (два poller на одном токене).

Рекомендуется:
- либо держать `tgBotEnable=false`,
- либо выдать панели отдельный Telegram bot token.

## Нативная русификация Hiddify (без прокси-версии страницы)

Для применения полного набора (переводы `ru.json`, fallback для `en.json`, no-cache для `i18n`, cron-переапплай после обновлений):

```powershell
pwsh -NoProfile -File .\scripts\deploy_hiddify_native_ru.ps1
```

Локальный запуск на сервере (если уже скопирован `scripts/hiddify_native_ru.py`):

```bash
python3 /opt/SmartKamaVPN/scripts/hiddify_native_ru.py --apply --force-en-ru --nginx-reload --install-cron
```

Проверка русификации и кэша i18n:

```bash
python3 scripts/selfcheck_hiddify_ru.py --uuid <subscription_uuid>
```

Если UUID не передан, скрипт проверит только i18n JSON и заголовки no-cache.

## Настройка ЮKassa

1. Получите Shop ID и Secret Key в личном кабинете ЮKassa
2. Добавьте настройки в базу данных через админ-панель бота
3. Настройте webhook для получения уведомлений о платежах

## Структура проекта

```
SmartKamaVPN-Bot/
├── AdminBot/           # Бот для администраторов
├── UserBot/            # Бот для пользователей
├── Database/           # Модули работы с БД
├── Utils/              # Утилиты и API
├── Shared/             # Общие модули
├── config.py           # Конфигурация
├── smartkamavpnTelegramBot.py  # Главный файл
└── requirements.txt    # Зависимости
```

## Команды

### Администраторские команды
- `/start` - Начать работу
- `/users` - Список пользователей
- `/plans` - Управление тарифами
- `/servers` - Управление серверами
- `/payments` - Управление платежами
- `/settings` - Настройки бота

### Пользовательские команды
- `/start` - Начать работу
- `/status` - Статус подписки
- `/buy` - Купить подписку
- `/wallet` - Баланс кошелька
- `/support` - Поддержка

## Лицензия

MIT License

## Поддержка

Telegram: @SmartKamaVPSupport

