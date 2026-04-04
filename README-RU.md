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

Перед перезапуском сервиса можно выполнить end-to-end проверку API панели:

```bash
python3 scripts/selfcheck_api.py
```

Скрипт автоматически проверяет `create -> read -> delete` тестового пользователя через `/api/v2`.
При успехе выводит `SELF_CHECK_OK`.

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

