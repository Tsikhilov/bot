# SmartKamaVPN-Bot

Telegram VPN management system: AdminBot + UserBot + cron-задачи. Панель: 3x-ui (миграция с Marzban). Два сервера: NL (основной) и RU (Reality-only).

## КРИТИЧНО: Callback parsing

```
AdminBot:  call.data.split(':')    — БЕЗ лимита → data[0]=key, data[1]=value
UserBot:   call.data.split(':', 1) — лимит 1   → data[0]=key, data[1]=всё_после_первого_двоеточия
```

**AdminBot**: callback_data НЕ ДОЛЖНА содержать больше одного `:`. Если нужно передать несколько значений — кодируй через `_` или `-`, НЕ через `:`. Пример: `server_autotune_run:full` (правильно), `server_autotune_run:full:5` (СЛОМАЕТСЯ).

**UserBot**: можно передавать `set_operator:mts:uuid123` — `value` будет `mts:uuid123`, парсить вручную через `value.split(":", 1)`.

## Структура проекта

```
config.py              — env vars, токены, настройки панели
Database/dbManager.py  — SQLite, 16 таблиц, класс USERS_DB
AdminBot/bot.py        — бот администратора (TELEGRAM_TOKEN)
UserBot/bot.py         — бот пользователя (CLIENT_TOKEN)
Utils/api.py           — унифицированный API для 3x-ui / Marzban
Utils/utils.py         — хелперы, sub_links(), all_configs_settings()
Utils/marzban_api.py   — Marzban-специфичный API
Utils/serverInfo.py    — get_server_status(server) → HTML текст
Utils/yookassa.py      — оплата YooKassa
Utils/cryptopay.py     — оплата CryptoPay
Cronjob/               — cron-задачи (backup, reminder, anomaly, cleanup, payment_check, status_channel, backupBot)
crontab.py             — CLI: python3 crontab.py --backup / --reminder / etc.
scripts/               — серверные скрипты (autotune, install, diag)
```

## База данных (SQLite)

16 таблиц: `users`, `plans`, `orders`, `order_subscriptions`, `non_order_subscriptions`, `str_config`, `int_config`, `bool_config`, `wallet`, `payments`, `yookassa_payments`, `crypto_payments`, `gift_promo_codes`, `servers`, `device_connections`, `referrals`.

**Паттерн методов**: `select_*()`, `find_*(**kwargs)`, `add_*()`, `edit_*()`, `delete_*()`.

**Внимание**: метод `select_order_subscription()` — без 's' в конце!

## Конфигурация (str_config / int_config / bool_config)

Динамические настройки хранятся в трёх таблицах. Паттерн: `USERS_DB.add_str_config(key, value)` + `USERS_DB.edit_str_config(key, value=value)`.

Ключи str_config: `status_channel_id`, `user_operator_{telegram_id}`, `support_username`, и др.

## Оплата

3 системы: карта (ручная проверка), YooKassa (автомат), CryptoPay (автомат). Кошелёк пользователя: `atomic_deduct_wallet()`, `atomic_credit_wallet()`.

## Панели

`PANEL_PROVIDER` в config.py: `"3xui"` (по умолчанию) или `"marzban"`. API-слой в `Utils/api.py` абстрагирует обе панели.

## JSON шаблоны

`AdminBot/Json/buttons.json`, `messages.json` — мультиязычные строки (RU/EN). Доступ: `KEY_MARKUP['KEY']`, `MESSAGES['KEY']`.

## Autotune

`scripts/server_autotune_stack.py` — 12 стадий автонастройки. Запуск из AdminBot через subprocess (бот на том же сервере). Режимы: `--full`, `--run-guard --guard-mode all`, `--apply-network`.

## Подписки (sub_links)

`Utils/utils.py:sub_links(uuid, url=None, telegram_id=None)` — возвращает dict с ключами: `sub_link`, `clash_configs`, `hiddify_configs`, `sing_box`, `home_link`, и др. Поддержка `?op=` для оператора связи.

## Shortlink

`scripts/shortlink_redirect.py` на localhost:9101. Поддерживает `?op=mts|beeline|tele2|megafon|yota` для сортировки протоколов по оператору.
