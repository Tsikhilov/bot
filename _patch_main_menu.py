"""Patch _send_sk_main_menu to show subscription days."""
import sys

with open('UserBot/bot.py', 'r', encoding='utf-8') as f:
    code = f.read()

OLD_MARKER = '''    lines = [
        "🛡 <b>SmartKamaVPN</b>",
        "",
        "Привет! Рады видеть тебя снова 👋",
        "",
        f"┣ 📶 Статус: {sub_status_text}",
        f"┣ 💎 Баланс: {utils.rial_to_toman(balance)} руб.",
    ]
    channel_link = _build_channel_link(settings)
    if channel_link != "не указан":
        lines.append(f"┗ 📣 Новости: {channel_link}")
    else:
        lines[-1] = lines[-1].replace("┣ 💎", "┗ 💎")
    lines.append("")
    lines.append("✨ Подробности по трафику и сроку доступны в разделе подписок.")

    msg = "\\n".join(lines)
    bot.send_message(chat_id, msg, reply_markup=main_menu_keyboard_markup(), parse_mode="HTML")'''

NEW_CODE = '''    # Get subscription info with remaining days
    max_days = 0
    active_count = 0
    try:
        subs = _get_subscriptions_for_user(chat_id)
        total_subs = len(subs)
        for s in subs:
            if s.get('active'):
                active_count += 1
                rd = s.get('remaining_day', 0) or 0
                if rd > max_days:
                    max_days = rd
    except Exception:
        pass

    if active_count > 0:
        days_int = int(max_days)
        if days_int > 30:
            days_emoji = "🟢"
        elif days_int > 7:
            days_emoji = "🟡"
        else:
            days_emoji = "🔴"
        days_text = f"{days_int} дн." if days_int > 0 else "истекает сегодня"
        sub_line = f"┣ {days_emoji} Подписка: активна ({days_text})"
    elif total_subs > 0:
        sub_line = "┣ 🔴 Подписка: истекла"
    else:
        sub_line = "┣ ⚪ Подписка: не оформлена"

    lines = [
        "🛡 <b>SmartKamaVPN</b>",
        "━━━━━━━━━━━━━━━━━━",
        "",
        sub_line,
        f"┣ 💎 Баланс: {utils.rial_to_toman(balance)} руб.",
    ]
    channel_link = _build_channel_link(settings)
    if channel_link != "не указан":
        lines.append(f"┗ 📣 Канал: {channel_link}")
    else:
        lines[-1] = lines[-1].replace("┣ 💎", "┗ 💎")
    lines.append("")

    # Tips based on status
    if active_count == 0 and total_subs == 0:
        lines.append("🎯 Попробуй бесплатный тест или оформи подписку!")
    elif active_count == 0:
        lines.append("⏰ Подписка истекла — продли или оформи новую.")
    elif int(max_days) <= 7:
        lines.append(f"⚠️ Осталось {int(max_days)} дн. — не забудь продлить!")
    else:
        lines.append("✨ Всё работает! Приятного использования.")

    msg = "\\n".join(lines)
    bot.send_message(chat_id, msg, reply_markup=main_menu_keyboard_markup(), parse_mode="HTML")'''

if OLD_MARKER in code:
    code = code.replace(OLD_MARKER, NEW_CODE)
    with open('UserBot/bot.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print('OK: _send_sk_main_menu updated')
else:
    print('WARN: marker not found, showing context')
    # Find the function
    idx = code.find('def _send_sk_main_menu')
    if idx >= 0:
        snippet = code[idx:idx+1500]
        print(snippet[:500])
    else:
        print('Function not found at all!')
    sys.exit(1)
