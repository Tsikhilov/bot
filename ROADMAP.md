# SmartKamaVPN Bot — Roadmap улучшений

> **Инструкция для Copilot:** при каждом новом сеансе читать этот файл, брать первую задачу со статусом `TODO` и выполнять её. После выполнения менять статус на `DONE` и деплоить.

---

## Правила работы

- Деплой: `Publish-ProdBot` из `scripts/prod_tools.ps1`
- Проверка: `callback_coverage=OK`, оба сервиса `active`
- Правильный DB: `/opt/SmartKamaVPN/Database/smartkamavpn.db`
- Deeplink-схемы: `hiddify://import?url=`, `singbox://import-remote-profile?url=&name=SmartKamaVPN`, `clash://install-config?url=`, `v2raytun://install-config?url=`

---

## Блок 1 — Подписки и приложения (Sing-box / SmartKamaVPN)

### `DONE` 1.1 — Включить видимость всех форматов подписки в DB
- Все `visible_conf_*` флаги = 1 в `/opt/SmartKamaVPN/Database/smartkamavpn.db`

### `DONE` 1.2 — Переписать `smartkamavpn_sub_page` 
- Показывает QR-код + список приложений + `sk_params_markup`
- Использует `_get_server_api_url_by_uuid` + проверку `_subscription_belongs_to_user`

### `DONE` 1.3 — Хэндлер `smartkamavpn_conf_hiddify`
- Deeplink: `hiddify://import?url=…`
- Ссылки на магазины приложений (iOS / Android / Desktop)
- Markup: `_conf_deeplink_markup`

### `DONE` 1.4 — Хэндлер `smartkamavpn_conf_singbox`
- Deeplink: `singbox://import-remote-profile?url=…&name=SmartKamaVPN`
- Ссылки на магазины (iOS / Android / Desktop)

### `DONE` 1.5 — Хэндлер `smartkamavpn_conf_clash`
- Deeplink: `clash://install-config?url=…`
- Ссылки: Stash (iOS), ClashMeta (Android), Mihomo (Desktop)

### `DONE` 1.6 — Обновить `sk_params_markup`
- Clash → `smartkamavpn_conf_clash`
- Sing-box → `smartkamavpn_conf_singbox`
- Hiddify → `smartkamavpn_conf_hiddify`

### `DONE` 1.7 — Обновить `sub_url_user_list_markup`
- Hiddify → `smartkamavpn_conf_hiddify`
- Sing-box → `smartkamavpn_conf_singbox`

### `DONE` 1.8 — Убрать дубль кнопки QR из `sk_setup_markup`
- Удалена кнопка `conf_sub_auto` — дублировала «Подписка и приложения»

---

## Блок 2 — UX текстов и сообщений

### `DONE` 2.1 — Обновить `SK_SETUP_TEXT` в messages.json
- Убрать упоминание «Показать QR-код подписки» (кнопки больше нет)
- Обновить список шагов: «Подписка и приложения → выбери приложение → авто-импорт»
- Файл: `UserBot/Json/messages.json`, ключ `SK_SETUP_TEXT`

### `DONE` 2.2 — Добавить `SK_CONF_BACK_TO_APPS` сообщение
- Текст на кнопке «◀️ К выбору приложения» — вынести в messages.json для локализации

### `DONE` 2.3 — Улучшить caption в `smartkamavpn_sub_page`
- Добавить краткую инструкцию «Нажмите кнопку приложения → откроется авто-импорт»
- Убрать дублирующийся QR-hint (он уже виден как фото)

---

## Блок 3 — Sing-box специфика

### `DONE` 3.1 — Проверить наличие `sing_box_configs` ключа в `utils.sub_links()`
- Текущий код использует `links.get('sing_box_configs')` — убедиться что ключ реально возвращается панелью
- Файл: `Utils/utils.py`, функция `sub_links()`
- Сделать: добавить fallback `sub_link_auto` если `sing_box_configs` пустой

### `DONE` 3.2 — Sing-box: добавить параметр `name` в deeplink
- Текущий deeplink: `singbox://import-remote-profile?url={url}&name=SmartKamaVPN`
- Улучшение: добавить `name={sub_id}` вместо `SmartKamaVPN` — персонализация
- Файл: `UserBot/bot.py`, хэндлер `smartkamavpn_conf_singbox`

### `DONE` 3.3 — Sing-box: показать тип конфига в caption
- Если сервер возвращает `sing_box_configs` → указать «Полная конфигурация»
- Если fallback на `sub_link_auto` → указать «Универсальная подписка»

---

## Блок 4 — Happ / V2RayTun

### `DONE` 4.1 — Проверить deeplink Happ на iOS
- Текущий deeplink: `v2raytun://install-config?url={url}`
- Убедиться что Happ (iOS) и V2RayTun (Android) используют одну и ту же схему
- Если разные → добавить отдельные кнопки iOS / Android

### `DONE` 4.2 — Добавить кнопку прямого импорта через `hiddify://`  
- Happ поддерживает `hiddify://import?url=` так же как Hiddify App
- Рассмотреть объединение кнопок или добавление второго варианта

---

## Блок 5 — Навигация и UX

### `DONE` 5.1 — Добавить кнопку «🔄 Обновить» в `sk_subscription_actions_markup`
- При нажатии: повторно вызывает `smartkamavpn_sub_open:{uuid}` (перечитывает данные)
- Убирает необходимость выходить и заходить снова для актуализации трафика

### `DONE` 5.2 — Отображать статус подписки иконкой в `sk_vpn_subscriptions_markup`
- Активная → ✅ вместо 🔹
- Истекает скоро (< 3 дней) → ⚠️
- Неактивная / заморожена → ❌
- Файл: `UserBot/markups.py`, функция `sk_vpn_subscriptions_markup`

### `DONE` 5.3 — В `smartkamavpn_sub_open` показывать трафик с прогресс-баром
- `▓▓▓▓▓░░░░░ 50%` — текстовый прогресс-бар использования трафика
- Уже есть `used_gb / limit_gb` — добавить визуализацию

### `DONE` 5.4 — Кнопка «📋 Скопировать ссылку» в `_conf_deeplink_markup`  
- После deeplink кнопки добавить `answer_callback_query` с текстом ссылки
- Или отдельное `send_message` с `<code>…</code>` ссылкой для тапа-и-копирования

---

## Блок 6 — Безопасность и качество

### `DONE` 6.1 — Добавить rate limiting на conf-хэндлеры
- `smartkamavpn_conf_*` могут вызываться быстро → добавить cooldown 3 сек per user
- Через `bot.answer_callback_query` с `show_alert=False` если спам

### `DONE` 6.2 — Логировать выбор приложения
- При нажатии `smartkamavpn_conf_hiddify`, `_singbox`, `_clash` → писать в лог
- `logging.info("user %s chose app %s for sub %s", chat_id, key, value)`

### `DONE` 6.3 — Обработка ошибки если `qr_code` is None во всех conf-хэндлерах
- Сейчас: возвращает `MESSAGES['UNKNOWN_ERROR']`  
- Улучшение: если QR не сгенерировался, всё равно показать ссылку и deeplink без фото

---

## Блок 7 — Административная панель

### `DONE` 7.1 — В AdminBot добавить кнопку «Тест deeplink»
- Позволяет администратору отправить тестовый deeplink себе в ЛС
- Для проверки что `hiddify://`, `singbox://`, `clash://` работают на реальных устройствах

### `DONE` 7.2 — Статистика использования форматов подписки
- Считать через лог или новую таблицу DB: сколько раз нажаты hiddify/singbox/clash/happ
- Показывать в AdminBot → «📊 Статистика» → «Форматы подписок»

---

## Статусы
- `TODO` — ещё не сделано
- `IN_PROGRESS` — в работе прямо сейчас
- `DONE` — выполнено и задеплоено
- `SKIP` — пропущено (обоснование рядом)

