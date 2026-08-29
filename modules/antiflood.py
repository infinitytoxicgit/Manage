import re
from database import get_config, save_config
from utils import create_btn, make_penalty_buttons, fast_edit, InlineKeyboardMarkup, parse_time_duration

def get_antiflood_main_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    p = cfg.get("flood_penalty", "Off")
    del_icon = "✔️" if cfg.get("flood_delete", True) else "✖️"
    r1, r2 = make_penalty_buttons("fl", p, chat_id)

    keyboard = [
        [create_btn("📄 Messages", callback_data=f"flgrid_msg_{chat_id}"), create_btn("⏰ Time", callback_data=f"flgrid_time_{chat_id}")],
        r1, r2,
        [create_btn(f"🗑 Delete Messages {del_icon}", callback_data=f"fltog_del_{chat_id}")]
    ]
    if p in ["Mute", "Ban", "Warn"]:
        keyboard.append([create_btn(f"⏰ Set {p.lower()} duration", callback_data=f"flset_dur_{p}_{chat_id}")])
    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")] )
    return InlineKeyboardMarkup(keyboard)

def get_antiflood_text(chat_id: int):
    cfg = get_config(chat_id)
    p = cfg.get("flood_penalty", "Off")
    punishment_display = "Deletion" if (p == "Off" and cfg.get("flood_delete")) else p
    dur_str = cfg.get("flood_duration_str", "Off")

    return (
        "🗣 <b>Antiflood</b>\n"
        "From this menu you can set a punishment for those who send many messages in a short time.\n\n"
        f"Currently the antiflood is triggered when {cfg.get('flood_messages', 5)} messages "
        f"are sent within {cfg.get('flood_seconds', 3)} seconds.\n\n"
        f"<b>Punishment:</b> {punishment_display}\n"
        f"<b>Duration:</b> {dur_str}"
    )

async def handle_antiflood_callbacks(query, data: str, cid: int, user, user_states):
    cfg = get_config(cid)

    if data.startswith("cfg_view_flood_"):
        user_states.pop((cid, user.id), None)
        await fast_edit(query, get_antiflood_text(cid), get_antiflood_main_keyboard(cid))

    elif data.startswith("flgrid_"):
        mode = data.split("_")[1]
        numbers = [2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20]
        prefix = f"flval_{mode}_"
        kb = []
        row = []
        for n in numbers:
            row.append(create_btn(str(n), callback_data=f"{prefix}{n}_{cid}"))
            if len(row) == 4:
                kb.append(row)
                row = []
        kb.append([create_btn("⬅️ Back", callback_data=f"cfg_view_flood_{cid}")])
        title = "select the maximum amount of sendable messages" if mode=="msg" else "select the time interval considered to calculate the antiflood"
        await fast_edit(query, f"From here you can {title}.", InlineKeyboardMarkup(kb))

    elif data.startswith("flval_"):
        mode, val = data.split("_")[1], int(data.split("_")[2])
        if mode == "msg":
            cfg["flood_messages"] = val
        else:
            cfg["flood_seconds"] = val
        save_config(cid, cfg)
        await handle_antiflood_callbacks(query, f"cfg_view_flood_{cid}", cid, user, user_states)

    elif data.startswith("flpen_"):
        cfg["flood_penalty"] = data.split("_")[1]
        save_config(cid, cfg)
        await handle_antiflood_callbacks(query, f"cfg_view_flood_{cid}", cid, user, user_states)

    elif data.startswith("fltog_del_"):
        cfg["flood_delete"] = not cfg.get("flood_delete", True)
        save_config(cid, cfg)
        await handle_antiflood_callbacks(query, f"cfg_view_flood_{cid}", cid, user, user_states)

    elif data.startswith("flset_dur_"):
        ptype = data.split("_")[2]
        user_states[(cid, user.id)] = f"awaiting_flood_dur_{ptype}"
        dur_str = cfg.get("flood_duration_str", "Off")
        text = (
            f"Send now the duration of the chosen punishment ({ptype})\n\n"
            f"<b>Minimum:</b> 30 seconds\n<b>Maximum:</b> 365 days\n\n"
            f"<b>Example of format:</b> 10 min, 3 months, 2 years, 30s\n\n"
            f"<b>Current duration:</b> {dur_str}"
        )
        kb = [
            [create_btn("0️⃣ Remove duration", callback_data=f"flrem_dur_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"cfg_view_flood_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))

    elif data.startswith("flrem_dur_"):
        cfg["flood_duration_sec"] = 0
        cfg["flood_duration_str"] = "Off"
        save_config(cid, cfg)
        await query.answer("Duration removed!")
        await handle_antiflood_callbacks(query, f"cfg_view_flood_{cid}", cid, user, user_states)

# Dedicated text handler for Antiflood duration inputs
async def handle_antiflood_text_state(update, context, user_states):
    msg = update.message
    if not msg or not msg.from_user:
        return False
    chat_id = update.effective_chat.id
    user_id = msg.from_user.id
    state_key = (chat_id, user_id)

    if state_key not in user_states:
        return False

    state = user_states.get(state_key)
    if not state or not state.startswith("awaiting_flood_dur_"):
        return False

    text = msg.text or msg.caption or ""
    raw_t = text.strip().lower()

    # Common spelling fixes for units (e.g. mis, mi -> min, sec -> s)
    raw_t = re.sub(r'\bmis\b', 'min', raw_t)
    raw_t = re.sub(r'\bmisecs\b', 'secs', raw_t)

    valid_units = ['sec', 'second', 'secs', 'seconds', 'min', 'mins', 'minute', 'minutes', 'hr', 'hrs', 'hour', 'hours', 'day', 'days', 'month', 'months', 'yr', 'yrs', 'year', 'years', 's', 'm', 'h', 'd', 'mo', 'y']
    has_valid_unit = any(unit in raw_t for unit in valid_units)

    parsed_sec = parse_time_duration(raw_t)
    if parsed_sec <= 0 or not has_valid_unit:
        match_num = re.search(r'\d+', raw_t)
        if match_num and has_valid_unit:
            val = int(match_num.group())
            if 's' in raw_t: parsed_sec = val
            elif 'm' in raw_t: parsed_sec = val * 60
            elif 'h' in raw_t: parsed_sec = val * 3600
            elif 'd' in raw_t: parsed_sec = val * 86400
            elif 'mo' in raw_t: parsed_sec = val * 2592000
            elif 'y' in raw_t: parsed_sec = val * 31536000

    # Agar format galat hai ya 30 seconds se kam hai
    if parsed_sec < 30 or not has_valid_unit:
        err_msg = await msg.reply_text(
            "❌ <b>Invalid duration format!</b>\n"
            "Minimum duration is 30 seconds.\n"
            "<i>Example:</i> <code>10 min</code>, <code>3 months</code>, <code>2 years</code>, <code>30s</code>\n\n"
            "Please try again:",
            parse_mode="HTML"
        )
        try:
            await msg.delete()
        except Exception:
            pass
        return True

    # Sahi time milne par state clear karo aur permanent database me save karo
    user_states.pop(state_key, None)
    cfg = get_config(chat_id)
    cfg["flood_duration_sec"] = parsed_sec
    cfg["flood_duration_str"] = text.strip()
    save_config(chat_id, cfg)

    try:
        await msg.delete()
    except Exception:
        pass

    if msg.reply_to_message:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg.reply_to_message.message_id,
                text=get_antiflood_text(chat_id),
                reply_markup=get_antiflood_main_keyboard(chat_id),
                parse_mode="HTML"
            )
            return True
        except Exception:
            pass

    await msg.reply_text(
        get_antiflood_text(chat_id),
        reply_markup=get_antiflood_main_keyboard(chat_id),
        parse_mode="HTML"
    )
    return True
