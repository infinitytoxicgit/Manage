import re
import time
from telegram import Update, InlineKeyboardMarkup, ChatPermissions
from database import get_config, save_config, get_user_warns, set_user_warns
from utils import create_btn, fast_edit

# Custom Duration Parser for Anti-Spam
def parse_duration_smart(text: str) -> int:
    raw = text.strip().lower()
    matches = re.findall(r'(\d+)\s*([a-zA-Z]+)', raw)
    if not matches:
        return 0

    total_seconds = 0
    matched_any = False
    for val_str, unit in matches:
        val = int(val_str)
        unit = unit.lower()
        if unit in ['s', 'sec', 'secs', 'second', 'seconds']:
            total_seconds += val
            matched_any = True
        elif unit in ['m', 'min', 'mins', 'minute', 'minutes', 'mis']:
            total_seconds += val * 60
            matched_any = True
        elif unit in ['h', 'hr', 'hrs', 'hour', 'hours']:
            total_seconds += val * 3600
            matched_any = True
        elif unit in ['d', 'day', 'days']:
            total_seconds += val * 86400
            matched_any = True
        elif unit in ['mo', 'month', 'months']:
            total_seconds += val * 2592000
            matched_any = True
        elif unit in ['y', 'yr', 'yrs', 'year', 'years']:
            total_seconds += val * 31536000
            matched_any = True

    return total_seconds if matched_any else 0

# Visual helper for penalty buttons with active indicator colors
def build_penalty_matrix(prefix: str, current_val: str, cid: int):
    val = current_val or "Off"
    
    btn_off = f"❌ Off" if val != "Off" else "🔴 [ Off ]"
    btn_warn = f"! Warn" if val != "Warn" else "⚠️ [ Warn ]"
    btn_kick = f"! Kick" if val != "Kick" else "⚡ [ Kick ]"
    btn_mute = f"🔇 Mute" if val != "Mute" else "🔇 [ Mute ]"
    btn_ban = f"🚫 Ban" if val != "Ban" else "⛔ [ Ban ]"

    r1 = [
        create_btn(btn_off, callback_data=f"{prefix}Off_{cid}"),
        create_btn(btn_warn, callback_data=f"{prefix}Warn_{cid}"),
        create_btn(btn_kick, callback_data=f"{prefix}Kick_{cid}")
    ]
    r2 = [
        create_btn(btn_mute, callback_data=f"{prefix}Mute_{cid}"),
        create_btn(btn_ban, callback_data=f"{prefix}Ban_{cid}")
    ]
    return r1, r2

# --- 1. MAIN ANTI-SPAM MENU ---
def get_antispam_main_keyboard(cid: int):
    keyboard = [
        [create_btn("📖 Telegram links", callback_data=f"as_tglinks_{cid}")],
        [create_btn("📩 Forwarding", callback_data=f"as_fwd_grp_{cid}"), create_btn("💭 Quote", callback_data=f"as_quote_grp_{cid}")],
        [create_btn("🔗 Total links block", callback_data=f"as_totlinks_{cid}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_antispam_main_text():
    return (
        "📩 <b>Anti-Spam</b>\n"
        "In this menu you can decide whether to protect your groups from unnecessary links, "
        "forwards, and quotes."
    )

# --- 2. TELEGRAM LINKS MENU ---
def get_tglinks_keyboard(cid: int):
    cfg = get_config(cid)
    p = cfg.get("as_tg_penalty", "Off")
    del_icon = "🟢 Yes" if cfg.get("as_tg_delete", False) else "🔴 No"
    user_icon = "🟢 Yes" if cfg.get("as_tg_username", False) else "🔴 No"
    bot_icon = "🟢 Yes" if cfg.get("as_tg_bots", False) else "🔴 No"

    r1, r2 = build_penalty_matrix("astgpen_", p, cid)
    keyboard = [r1, r2]
    
    if p in ["Warn", "Mute", "Ban"]:
        keyboard.append([create_btn(f"⏰ Set {p} duration", callback_data=f"astgset_dur_{p}_{cid}")])

    keyboard.extend([
        [create_btn(f"🗑 Delete Messages: {del_icon}", callback_data=f"astgtog_del_{cid}")],
        [create_btn(f"🎯 Username Antispam: {user_icon}", callback_data=f"astgtog_usr_{cid}")],
        [create_btn(f"🤖 Bots Antispam: {bot_icon}", callback_data=f"astgtog_bot_{cid}")],
        [create_btn("⬅️ Back", callback_data=f"as_main_{cid}"), create_btn("☀️ Exceptions", callback_data=f"as_exc_{cid}")]
    ])
    return InlineKeyboardMarkup(keyboard)

def get_tglinks_text(cid: int):
    cfg = get_config(cid)
    p = cfg.get("as_tg_penalty", "Off")
    dur_str = cfg.get("as_tg_duration_str", "")
    penalty_display = f"{p} {dur_str}".strip() if p in ["Warn", "Mute", "Ban"] and dur_str else p
    del_str = "Yes 🟢" if cfg.get("as_tg_delete", False) else "No 🔴"

    return (
        "📖 <b>Telegram links</b>\n"
        "From this menu you can set a punishment for users who send messages that contain Telegram links.\n\n"
        "🎯 <b>Username Antispam:</b> this option triggers the antispam when a username considered spam is sent.\n\n"
        "🤖 <b>Bots Antispam:</b> this option triggers the antispam when a Bot link is sent.\n\n"
        f"<b>Penalty:</b> <code>{penalty_display}</code>\n"
        f"<b>Deletion:</b> {del_str}"
    )

# --- 3. TOTAL LINKS BLOCK MENU ---
def get_totlinks_keyboard(cid: int):
    cfg = get_config(cid)
    p = cfg.get("as_tot_penalty", "Off")
    del_icon = "🟢 Yes" if cfg.get("as_tot_delete", False) else "🔴 No"
    
    r1, r2 = build_penalty_matrix("astotpen_", p, cid)
    keyboard = [r1, r2]

    if p in ["Warn", "Mute", "Ban"]:
        keyboard.append([create_btn(f"⏰ Set {p} duration", callback_data=f"astotset_dur_{p}_{cid}")])

    keyboard.extend([
        [create_btn(f"🗑 Delete Messages: {del_icon}", callback_data=f"astottog_del_{cid}")],
        [create_btn("⬅️ Back", callback_data=f"as_main_{cid}"), create_btn("☀️ Exceptions", callback_data=f"as_exc_{cid}")]
    ])
    return InlineKeyboardMarkup(keyboard)

def get_totlinks_text(cid: int):
    cfg = get_config(cid)
    p = cfg.get("as_tot_penalty", "Off")
    dur_str = cfg.get("as_tot_duration_str", "")
    penalty_display = f"{p} {dur_str}".strip() if p in ["Warn", "Mute", "Ban"] and dur_str else p
    del_str = "Yes 🟢" if cfg.get("as_tot_delete", False) else "No 🔴"

    return (
        "🔗 <b>Total links block</b>\n"
        "Select punishment for users who send any external web link.\n\n"
        f"<b>Penalty:</b> <code>{penalty_display}</code>\n"
        f"<b>Deletion:</b> {del_str}"
    )

# --- 4. QUOTE / FORWARDING MENU ---
def get_sub_category_keyboard(cid: int, mode_type: str, selected_cat: str):
    cfg = get_config(cid)
    key_prefix = f"as_{mode_type}_{selected_cat}"
    p = cfg.get(f"{key_prefix}_pen", "Off")
    del_icon = "🟢 Yes" if cfg.get(f"{key_prefix}_del", False) else "🔴 No"

    def mark(cat_key, label):
        return f"🟢 [ {label} ]" if selected_cat == cat_key else label

    cat_row1 = [
        create_btn(mark("chan", "📣 Channels"), callback_data=f"as_{mode_type}_chan_{cid}"),
        create_btn(mark("grp", "👥 Groups"), callback_data=f"as_{mode_type}_grp_{cid}")
    ]
    cat_row2 = [
        create_btn(mark("usr", "👤 Users"), callback_data=f"as_{mode_type}_usr_{cid}"),
        create_btn(mark("bot", "🤖 Bots"), callback_data=f"as_{mode_type}_bot_{cid}")
    ]

    r1, r2 = build_penalty_matrix(f"assub_{mode_type}_{selected_cat}_", p, cid)
    keyboard = [
        cat_row1,
        cat_row2,
        [create_btn("─────────────", callback_data="none")],
        r1, r2,
        [create_btn(f"🗑 Delete Messages: {del_icon}", callback_data=f"asdel_{mode_type}_{selected_cat}_{cid}")],
        [create_btn("⬅️ Back", callback_data=f"as_main_{cid}"), create_btn("☀️ Exceptions", callback_data=f"as_exc_{cid}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_sub_category_text(cid: int, mode_type: str):
    cfg = get_config(cid)
    title = "Quote" if mode_type == "quote" else "Forwarding"
    
    chan_p = cfg.get(f"as_{mode_type}_chan_pen", "Off")
    grp_p = cfg.get(f"as_{mode_type}_grp_pen", "Off")
    usr_p = cfg.get(f"as_{mode_type}_usr_pen", "Off")
    bot_p = cfg.get(f"as_{mode_type}_bot_pen", "Off")

    return (
        f"💭 <b>{title}</b>\n"
        f"Select punishment for users who send messages containing {title.lower()}s from external chats.\n\n"
        f"📣 <b>Channels</b>\n └ <code>{chan_p}</code>\n"
        f"👥 <b>Groups</b>\n └ <code>{grp_p}</code>\n"
        f"👤 <b>Users</b>\n └ <code>{usr_p}</code>\n"
        f"🤖 <b>Bots</b>\n └ <code>{bot_p}</code>"
    )

# --- 5. EXCEPTIONS & WHITELIST MENU ---
def get_exceptions_keyboard(cid: int):
    keyboard = [
        [create_btn("🔤 Show Whitelist", callback_data=f"asexc_show_{cid}")],
        [create_btn("➕ Add", callback_data=f"asexc_add_{cid}"), create_btn("➖ Remove", callback_data=f"asexc_rem_{cid}")],
        [create_btn("🌐 Global Whitelist", callback_data=f"asexc_global_{cid}")],
        [create_btn("⬅️ Back", callback_data=f"as_main_{cid}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_exceptions_text():
    return (
        "<b>Antispam Exception</b>\n"
        "Manage the Telegram's links/usernames of groups and channels that will not be treated as spam.\n\n"
        "<i>The group links are automatically in the antispam exception.</i>"
    )

def get_global_whitelist_keyboard(cid: int):
    cfg = get_config(cid)
    is_active = cfg.get("as_global_whitelist", True)
    on_btn = "🟢 [ Active ]" if is_active else "✔️ Turn on"
    off_btn = "🔴 [ Off ]" if not is_active else "✖️ Turn off"
    
    keyboard = [
        [create_btn(on_btn, callback_data=f"asexc_g_on_{cid}"), create_btn(off_btn, callback_data=f"asexc_g_off_{cid}")],
        [create_btn("📖 Global Whitelist ↗️", url="https://t.me/telegram")],
        [create_btn("⬅️ Back", callback_data=f"as_exc_{cid}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_global_whitelist_text(cid: int):
    cfg = get_config(cid)
    status = "Active 🟢" if cfg.get("as_global_whitelist", True) else "Disabled 🔴"
    return (
        "<b>Global Whitelist:</b>\n"
        "It's a list, created by our staff, of channels and groups that offer serious content, "
        "well organized and managed, non-profit and therefore not to be considered spam.\n"
        "The channels and groups in this list will be ignored by the spam detection in the group.\n\n"
        "You can consult the list by pressing the button below.\n\n"
        f"<b>Status:</b> {status}"
    )

# --- 6. UNIFIED CALLBACK HANDLER (NO FREEZING) ---
async def handle_antispam_callbacks(query, data: str, cid: int, user, user_states):
    cfg = get_config(cid)

    # 1. Main Antispam Dashboard
    if data.startswith("as_main_") or data.startswith("cfg_view_antispam_") or data.startswith("cfg_view_spam_") or data.startswith("aspam_main_"):
        user_states.pop((cid, user.id), None)
        await fast_edit(query, get_antispam_main_text(), get_antispam_main_keyboard(cid))
    
    # 2. Telegram Links Section
    elif data.startswith("as_tglinks_"):
        await fast_edit(query, get_tglinks_text(cid), get_tglinks_keyboard(cid))
    elif data.startswith("astgpen_"):
        pen = data.split("_")[1]
        cfg["as_tg_penalty"] = pen
        save_config(cid, cfg)
        await fast_edit(query, get_tglinks_text(cid), get_tglinks_keyboard(cid))
    elif data.startswith("astgtog_del_"):
        cfg["as_tg_delete"] = not cfg.get("as_tg_delete", False)
        save_config(cid, cfg)
        await fast_edit(query, get_tglinks_text(cid), get_tglinks_keyboard(cid))
    elif data.startswith("astgtog_usr_"):
        cfg["as_tg_username"] = not cfg.get("as_tg_username", False)
        save_config(cid, cfg)
        await fast_edit(query, get_tglinks_text(cid), get_tglinks_keyboard(cid))
    elif data.startswith("astgtog_bot_"):
        cfg["as_tg_bots"] = not cfg.get("as_tg_bots", False)
        save_config(cid, cfg)
        await fast_edit(query, get_tglinks_text(cid), get_tglinks_keyboard(cid))
    elif data.startswith("astgset_dur_"):
        ptype = data.split("_")[2]
        user_states[(cid, user.id)] = f"awaiting_as_tg_dur_{ptype}"
        dur_str = cfg.get("as_tg_duration_str", "Off")
        text = (
            f"Send now the duration of the chosen punishment ({ptype})\n\n"
            f"<b>Minimum:</b> 30 seconds\n<b>Maximum:</b> 365 days\n\n"
            f"<b>Example of format:</b> 10 min, 3 months, 2 years, 30s\n\n"
            f"<b>Current duration:</b> {dur_str}"
        )
        kb = [
            [create_btn("0️⃣ Remove duration", callback_data=f"astgrem_dur_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"as_tglinks_{cid}")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
    elif data.startswith("astgrem_dur_"):
        cfg["as_tg_duration_sec"] = 0
        cfg["as_tg_duration_str"] = "Off"
        save_config(cid, cfg)
        await query.answer("Duration removed!")
        await fast_edit(query, get_tglinks_text(cid), get_tglinks_keyboard(cid))

    # 3. Total Links Block Section
    elif data.startswith("as_totlinks_"):
        await fast_edit(query, get_totlinks_text(cid), get_totlinks_keyboard(cid))
    elif data.startswith("astotpen_"):
        pen = data.split("_")[1]
        cfg["as_tot_penalty"] = pen
        save_config(cid, cfg)
        await fast_edit(query, get_totlinks_text(cid), get_totlinks_keyboard(cid))
    elif data.startswith("astottog_del_"):
        cfg["as_tot_delete"] = not cfg.get("as_tot_delete", False)
        save_config(cid, cfg)
        await fast_edit(query, get_totlinks_text(cid), get_totlinks_keyboard(cid))
    elif data.startswith("astotset_dur_"):
        ptype = data.split("_")[2]
        user_states[(cid, user.id)] = f"awaiting_as_tot_dur_{ptype}"
        dur_str = cfg.get("as_tot_duration_str", "Off")
        text = (
            f"Send now the duration of the chosen punishment ({ptype})\n\n"
            f"<b>Minimum:</b> 30 seconds\n<b>Maximum:</b> 365 days\n\n"
            f"<b>Example of format:</b> 10 min, 3 months, 2 years, 30s\n\n"
            f"<b>Current duration:</b> {dur_str}"
        )
        kb = [
            [create_btn("0️⃣ Remove duration", callback_data=f"astotrem_dur_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"as_totlinks_{cid}")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
    elif data.startswith("astotrem_dur_"):
        cfg["as_tot_duration_sec"] = 0
        cfg["as_tot_duration_str"] = "Off"
        save_config(cid, cfg)
        await query.answer("Duration removed!")
        await fast_edit(query, get_totlinks_text(cid), get_totlinks_keyboard(cid))

    # 4. Quote / Forwarding Sub-Categories
    elif data.startswith("as_quote_") or data.startswith("as_fwd_"):
        parts = data.split("_")
        mode_type = parts[1]
        selected_cat = parts[2] if len(parts) > 2 and parts[2] in ["chan", "grp", "usr", "bot"] else "grp"
        await fast_edit(query, get_sub_category_text(cid, mode_type), get_sub_category_keyboard(cid, mode_type, selected_cat))
    elif data.startswith("assub_"):
        parts = data.split("_")
        mode_type, selected_cat, pen_val = parts[1], parts[2], parts[3]
        cfg[f"as_{mode_type}_{selected_cat}_pen"] = pen_val
        save_config(cid, cfg)
        await fast_edit(query, get_sub_category_text(cid, mode_type), get_sub_category_keyboard(cid, mode_type, selected_cat))
    elif data.startswith("asdel_"):
        parts = data.split("_")
        mode_type, selected_cat = parts[1], parts[2]
        curr = cfg.get(f"as_{mode_type}_{selected_cat}_del", False)
        cfg[f"as_{mode_type}_{selected_cat}_del"] = not curr
        save_config(cid, cfg)
        await fast_edit(query, get_sub_category_text(cid, mode_type), get_sub_category_keyboard(cid, mode_type, selected_cat))

    # 5. Exceptions & Whitelists
    elif data.startswith("as_exc_") or data.startswith("asexc_main_"):
        await fast_edit(query, get_exceptions_text(), get_exceptions_keyboard(cid))
    elif data.startswith("asexc_show_"):
        wl = cfg.get("as_whitelist", [])
        wl_text = "\n".join([f"• <code>{x}</code>" for x in wl]) if wl else "<i>Whitelist is empty.</i>"
        await query.answer(f"Whitelist:\n{wl_text}", show_alert=True)
    elif data.startswith("asexc_add_"):
        user_states[(cid, user.id)] = "awaiting_as_wl_add"
        kb = [[create_btn("❌ Cancel", callback_data=f"as_exc_{cid}")] ]
        await fast_edit(query, "Send the username or link to add to the whitelist:\n\nExample: <code>@examplechannel</code>", InlineKeyboardMarkup(kb))
    elif data.startswith("asexc_rem_"):
        user_states[(cid, user.id)] = "awaiting_as_wl_rem"
        kb = [[create_btn("❌ Cancel", callback_data=f"as_exc_{cid}")] ]
        await fast_edit(query, "Send the username or link to remove from whitelist:", InlineKeyboardMarkup(kb))
    elif data.startswith("asexc_global_"):
        await fast_edit(query, get_global_whitelist_text(cid), get_global_whitelist_keyboard(cid))
    elif data.startswith("asexc_g_on_"):
        cfg["as_global_whitelist"] = True
        save_config(cid, cfg)
        await fast_edit(query, get_global_whitelist_text(cid), get_global_whitelist_keyboard(cid))
    elif data.startswith("asexc_g_off_"):
        cfg["as_global_whitelist"] = False
        save_config(cid, cfg)
        await fast_edit(query, get_global_whitelist_text(cid), get_global_whitelist_keyboard(cid))

# --- 7. TEXT STATE PROCESSOR ---
async def handle_antispam_text_state(update, context, user_states):
    msg = update.message
    if not msg or not msg.from_user:
        return False
        
    chat_id = update.effective_chat.id
    user_id = msg.from_user.id
    state_key = (chat_id, user_id)

    if state_key not in user_states:
        return False

    state = user_states.get(state_key)
    if not state or not (state.startswith("awaiting_as_tg_dur_") or state.startswith("awaiting_as_tot_dur_") or state.startswith("awaiting_as_wl_")):
        return False

    text = msg.text or ""
    cfg = get_config(chat_id)

    # Telegram links duration
    if state.startswith("awaiting_as_tg_dur_"):
        parsed_sec = parse_duration_smart(text)
        if parsed_sec < 30:
            kb = [[create_btn("❌ Cancel", callback_data=f"as_tglinks_{chat_id}")] ]
            await msg.reply_text(
                "❌ <b>Invalid duration format!</b>\nMinimum duration is 30 seconds.\n<i>Example:</i> <code>10 min</code>, <code>3 months</code>, <code>2 years</code>, <code>30s</code>\n\nPlease try again:",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="HTML"
            )
            return True

        user_states.pop(state_key, None)
        cfg["as_tg_duration_sec"] = parsed_sec
        cfg["as_tg_duration_str"] = text.strip()
        save_config(chat_id, cfg)

        try:
            await msg.delete()
        except Exception:
            pass

        await msg.reply_text(
            f"✅ <b>Telegram links duration set to: {text.strip()}</b>\n\n" + get_tglinks_text(chat_id),
            reply_markup=get_tglinks_keyboard(chat_id),
            parse_mode="HTML"
        )
        return True

    # Total links duration
    elif state.startswith("awaiting_as_tot_dur_"):
        parsed_sec = parse_duration_smart(text)
        if parsed_sec < 30:
            kb = [[create_btn("❌ Cancel", callback_data=f"as_totlinks_{chat_id}")] ]
            await msg.reply_text(
                "❌ <b>Invalid duration format!</b>\nMinimum duration is 30 seconds.\n<i>Example:</i> <code>10 min</code>, <code>3 months</code>, <code>2 years</code>, <code>30s</code>\n\nPlease try again:",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="HTML"
            )
            return True

        user_states.pop(state_key, None)
        cfg["as_tot_duration_sec"] = parsed_sec
        cfg["as_tot_duration_str"] = text.strip()
        save_config(chat_id, cfg)

        try:
            await msg.delete()
        except Exception:
            pass

        await msg.reply_text(
            f"✅ <b>Total links duration set to: {text.strip()}</b>\n\n" + get_totlinks_text(chat_id),
            reply_markup=get_totlinks_keyboard(chat_id),
            parse_mode="HTML"
        )
        return True

    # Whitelist Add
    elif state == "awaiting_as_wl_add":
        user_states.pop(state_key, None)
        wl = cfg.get("as_whitelist", [])
        clean_item = text.strip().replace("https://t.me/", "@")
        if clean_item not in wl:
            wl.append(clean_item)
            cfg["as_whitelist"] = wl
            save_config(chat_id, cfg)
        await msg.reply_text(f"✅ <code>{clean_item}</code> added to Whitelist!", reply_markup=get_exceptions_keyboard(chat_id), parse_mode="HTML")
        return True

    # Whitelist Remove
    elif state == "awaiting_as_wl_rem":
        user_states.pop(state_key, None)
        wl = cfg.get("as_whitelist", [])
        clean_item = text.strip().replace("https://t.me/", "@")
        if clean_item in wl:
            wl.remove(clean_item)
            cfg["as_whitelist"] = wl
            save_config(chat_id, cfg)
            await msg.reply_text(f"🗑 <code>{clean_item}</code> removed from Whitelist!", reply_markup=get_exceptions_keyboard(chat_id), parse_mode="HTML")
        else:
            await msg.reply_text(f"❌ <code>{clean_item}</code> Whitelist me nahi mila.", reply_markup=get_exceptions_keyboard(chat_id), parse_mode="HTML")
        return True

    return False

# --- 8. PUNISHMENT EXECUTOR ---
async def execute_antispam_penalty(context, chat_id: int, user, penalty: str, duration_sec: int, reason: str):
    if penalty == "Off" or not penalty or penalty == "pen":
        return

    until_time = int(time.time() + duration_sec) if duration_sec > 0 else 0

    try:
        if penalty == "Mute":
            permissions = ChatPermissions(can_send_messages=False)
            if until_time > 0:
                await context.bot.restrict_chat_member(chat_id, user.id, permissions=permissions, until_date=until_time)
                await context.bot.send_message(chat_id, f"🔇 {user.mention_html()} muted for <b>{duration_sec}s</b> ({reason}).", parse_mode="HTML")
            else:
                await context.bot.restrict_chat_member(chat_id, user.id, permissions=permissions)
                await context.bot.send_message(chat_id, f"🔇 {user.mention_html()} muted permanently ({reason}).", parse_mode="HTML")

        elif penalty == "Ban":
            if until_time > 0:
                await context.bot.ban_chat_member(chat_id, user.id, until_date=until_time)
                await context.bot.send_message(chat_id, f"🚫 {user.mention_html()} banned for <b>{duration_sec}s</b> ({reason}).", parse_mode="HTML")
            else:
                await context.bot.ban_chat_member(chat_id, user.id)
                await context.bot.send_message(chat_id, f"🚫 {user.mention_html()} banned permanently ({reason}).", parse_mode="HTML")

        elif penalty == "Kick":
            await context.bot.ban_chat_member(chat_id, user.id)
            await context.bot.unban_chat_member(chat_id, user.id)
            await context.bot.send_message(chat_id, f"⚡ {user.mention_html()} kicked ({reason}).", parse_mode="HTML")

        elif penalty == "Warn":
            warns = get_user_warns(chat_id, user.id) + 1
            set_user_warns(chat_id, user.id, warns)
            await context.bot.send_message(chat_id, f"⚠️ {user.mention_html()} warned ({warns}/3) for {reason}.", parse_mode="HTML")
            if warns >= 3:
                set_user_warns(chat_id, user.id, 0)
                await context.bot.ban_chat_member(chat_id, user.id)
                await context.bot.send_message(chat_id, f"⛔ {user.mention_html()} banned (Exceeded max warnings).", parse_mode="HTML")

    except Exception as e:
        print(f"Error executing antispam penalty: {e}")

# --- 9. MESSAGE SCANNER ---
async def inspect_antispam_message(update: Update, context) -> bool:
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not msg or not chat or not user or chat.type == "private":
        return False

    from utils import is_user_admin
    if await is_user_admin(chat.id, user.id, context):
        return False

    cfg = get_config(chat.id)
    text = (msg.text or msg.caption or "")
    entities = msg.entities or msg.caption_entities or []

    # Whitelist Check
    whitelist = cfg.get("as_whitelist", [])
    for item in whitelist:
        if item.lower() in text.lower():
            return False

    # Total Links Check
    tot_penalty = cfg.get("as_tot_penalty", "Off")
    if tot_penalty not in ["Off", "pen"]:
        has_url = any(e.type in ["url", "text_link"] for e in entities) or re.search(r'https?://[^\s]+', text)
        if has_url:
            if cfg.get("as_tot_delete", False):
                try:
                    await msg.delete()
                except Exception:
                    pass
            dur = cfg.get("as_tot_duration_sec", 0)
            await execute_antispam_penalty(context, chat.id, user, tot_penalty, dur, "Sending external link")
            return True

    # Telegram Links Check
    tg_penalty = cfg.get("as_tg_penalty", "Off")
    if tg_penalty not in ["Off", "pen"]:
        has_tg = "t.me/" in text or "telegram.me/" in text or (cfg.get("as_tg_username", False) and "@" in text)
        if has_tg:
            if cfg.get("as_tg_delete", False):
                try:
                    await msg.delete()
                except Exception:
                    pass
            dur = cfg.get("as_tg_duration_sec", 0)
            await execute_antispam_penalty(context, chat.id, user, tg_penalty, dur, "Sending Telegram link/username")
            return True

    # Forwarding Check
    if msg.forward_from_chat or msg.forward_from:
        fwd_cat = "chan" if (msg.forward_from_chat and msg.forward_from_chat.type == "channel") else "grp"
        fwd_pen = cfg.get(f"as_fwd_{fwd_cat}_pen", "Off")
        if fwd_pen not in ["Off", "pen"]:
            if cfg.get(f"as_fwd_{fwd_cat}_del", False):
                try:
                    await msg.delete()
                except Exception:
                    pass
            await execute_antispam_penalty(context, chat.id, user, fwd_pen, 0, f"Forwarding from {fwd_cat}")
            return True

    return False
