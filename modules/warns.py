import re
import time
from telegram import Update, InlineKeyboardMarkup, ChatPermissions
from database import get_config, save_config, get_user_warns, set_user_warns
from utils import create_btn, fast_edit, is_user_admin

# Custom Smart Duration Parser
def parse_warn_duration(text: str) -> tuple:
    raw = text.strip().lower()
    raw = re.sub(r'\bmis\b|\bmi\b', 'min', raw)
    
    matches = re.findall(r'(\d+)\s*([a-zA-Z]+)', raw)
    if not matches:
        match_single = re.match(r'^(\d+)([a-zA-Z]+)$', raw)
        if match_single:
            matches = [(match_single.group(1), match_single.group(2))]
        else:
            return 0, ""

    total_seconds = 0
    formatted_parts = []

    for val_str, unit in matches:
        val = int(val_str)
        unit = unit.lower()
        if unit in ['s', 'sec', 'secs', 'second', 'seconds']:
            total_seconds += val
            formatted_parts.append(f"{val} Seconds")
        elif unit in ['m', 'min', 'mins', 'minute', 'minutes']:
            total_seconds += val * 60
            formatted_parts.append(f"{val} Minutes")
        elif unit in ['h', 'hr', 'hrs', 'hour', 'hours']:
            total_seconds += val * 3600
            formatted_parts.append(f"{val} Hours")
        elif unit in ['d', 'day', 'days']:
            total_seconds += val * 86400
            formatted_parts.append(f"{val} Days")
        elif unit in ['mo', 'month', 'months']:
            total_seconds += val * 2592000
            formatted_parts.append(f"{val} Months")
        elif unit in ['y', 'yr', 'yrs', 'year', 'years']:
            total_seconds += val * 31536000
            formatted_parts.append(f"{val} Years")

    return total_seconds, " ".join(formatted_parts)

# --- 1. MAIN WARNS MENU ---
def get_warns_main_keyboard(cid: int):
    cfg = get_config(cid)
    p = cfg.get("warn_penalty", "Ban")
    max_w = cfg.get("warn_max_count", 3)

    r1 = [
        create_btn("✖️ Off", callback_data=f"wrnpen_Off_{cid}", style="success" if p == "Off" else None),
        create_btn("❗️ Kick", callback_data=f"wrnpen_Kick_{cid}", style="success" if p == "Kick" else None)
    ]
    r2 = [
        create_btn("🔇 Mute", callback_data=f"wrnpen_Mute_{cid}", style="success" if p == "Mute" else None),
        create_btn("🚷 Ban", callback_data=f"wrnpen_Ban_{cid}", style="success" if p == "Ban" else None)
    ]

    keyboard = [
        [create_btn("📑 Warned List", callback_data=f"wrn_list_{cid}")],
        r1, r2
    ]

    # Duration button if Mute or Ban is selected
    if p == "Mute":
        keyboard.append([create_btn("🔇⏰ Set mute duration", callback_data=f"wrnset_dur_Mute_{cid}")])
    elif p == "Ban":
        keyboard.append([create_btn("🚷⏰ Set ban duration", callback_data=f"wrnset_dur_Ban_{cid}")])

    # Max Warns Row (2, 3, 4, 5, 6)
    limit_row = []
    for num in [2, 3, 4, 5, 6]:
        lbl = f"{num} ✅" if num == max_w else str(num)
        limit_row.append(create_btn(lbl, callback_data=f"wrnlim_{num}_{cid}"))
    keyboard.append(limit_row)

    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")])
    return InlineKeyboardMarkup(keyboard)

def get_warns_main_text(cid: int):
    cfg = get_config(cid)
    p = cfg.get("warn_penalty", "Ban")
    max_w = cfg.get("warn_max_count", 3)
    return (
        "❗️ <b>User warnings</b>\n"
        "The warning system allows you to give warnings to users for incorrect behavior in the group, "
        "before actually punishing them.\n\n"
        "From this menu you can set:\n"
        "• the <u>punishment</u> for users who exceed the maximum of warnings allowed\n"
        "• the <u>maximum number</u> of warns allowed\n\n"
        f"<b>Punishment:</b> {p}\n"
        f"<b>Max Warns allowed:</b> {max_w}"
    )

# --- 2. WARNED LIST & RESET FLOW ---
def get_warned_list_keyboard(cid: int):
    keyboard = [
        [create_btn("☑️ Free all", callback_data=f"wrn_free_prompt_{cid}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_mod_warns_{cid}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_warned_list_text(cid: int):
    cfg = get_config(cid)
    max_w = cfg.get("warn_max_count", 3)
    return f"<b>WARNED USERS (MAX {max_w})</b>"

def get_free_confirm_keyboard(cid: int):
    keyboard = [
        [create_btn("✅ Confirm", callback_data=f"wrn_free_confirm_{cid}")],
        [create_btn("❌ Cancel", callback_data=f"wrn_list_{cid}", style="danger")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- 3. CALLBACK ROUTER ---
async def handle_warns_callbacks(query, data: str, cid: int, user, user_states):
    cfg = get_config(cid)

    # Main Warns Dashboard
    if data.startswith("cfg_mod_warns_") or data.startswith("cfg_view_warns_") or data.startswith("wrn_main_"):
        user_states.pop((cid, user.id), None)
        await fast_edit(query, get_warns_main_text(cid), get_warns_main_keyboard(cid))

    # Penalty Type Selector
    elif data.startswith("wrnpen_"):
        pen = data.split("_")[1]
        cfg["warn_penalty"] = pen
        save_config(cid, cfg)
        await fast_edit(query, get_warns_main_text(cid), get_warns_main_keyboard(cid))

    # Max Limit Selector
    elif data.startswith("wrnlim_"):
        lim = int(data.split("_")[1])
        cfg["warn_max_count"] = lim
        save_config(cid, cfg)
        await fast_edit(query, get_warns_main_text(cid), get_warns_main_keyboard(cid))

    # Warned List Menu
    elif data.startswith("wrn_list_"):
        await fast_edit(query, get_warned_list_text(cid), get_warned_list_keyboard(cid))

    # Free All Prompt
    elif data.startswith("wrn_free_prompt_"):
        await fast_edit(query, "You want to reset all the warnings?", get_free_confirm_keyboard(cid))

    # Free All Confirmed Action
    elif data.startswith("wrn_free_confirm_"):
        cfg["warns_db"] = {}
        save_config(cid, cfg)
        kb = [[create_btn("⬅️ Back", callback_data=f"cfg_mod_warns_{cid}")]]
        await fast_edit(query, "All the warnings were removed.", InlineKeyboardMarkup(kb))

    # Duration Set Prompt
    elif data.startswith("wrnset_dur_"):
        ptype = data.split("_")[2]
        user_states[(cid, user.id)] = f"awaiting_wrn_dur_{ptype}_{query.message.message_id}"
        
        dur_str = cfg.get(f"warn_{ptype.lower()}_dur_str", "Off")
        text = (
            f"Send now the duration of the chosen punishment ({ptype})\n\n"
            f"<b>Minimum:</b> 30 seconds\n<b>Maximum:</b> 365 days\n\n"
            f"<b>Example of format:</b> 3 month 2 days 12 hours 4 minutes 34 seconds\n\n"
            f"<b>Current duration:</b> {dur_str or 'Off'}"
        )
        kb = [
            [create_btn("❌ Cancel", callback_data=f"cfg_mod_warns_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))

# --- 4. TEXT STATE HANDLER FOR DURATION INPUT ---
async def handle_warns_text_state(update: Update, context, user_states):
    msg = update.message
    if not msg or not msg.from_user:
        return False
        
    chat_id = update.effective_chat.id
    user_id = msg.from_user.id
    state_key = (chat_id, user_id)

    if state_key not in user_states:
        return False

    state = user_states.get(state_key)
    if not state or not state.startswith("awaiting_wrn_dur_"):
        return False

    text = msg.text or ""
    cfg = get_config(chat_id)
    parts = state.split("_")
    ptype = parts[3]
    panel_msg_id = int(parts[-1]) if parts[-1].isdigit() else None

    parsed_sec, dur_str = parse_warn_duration(text)
    if parsed_sec < 30:
        kb = [[create_btn("❌ Cancel", callback_data=f"cfg_mod_warns_{chat_id}", style="danger")]]
        await msg.reply_text(
            "❌ <b>Invalid duration format!</b>\n"
            "Minimum duration is 30 seconds.\n"
            "<i>Example:</i> <code>10 min</code>, <code>3 month 2 days</code>, <code>30s</code>\n\n"
            "Please try again:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )
        return True

    user_states.pop(state_key, None)
    cfg[f"warn_{ptype.lower()}_dur_sec"] = parsed_sec
    cfg[f"warn_{ptype.lower()}_dur_str"] = dur_str or text.strip()
    save_config(chat_id, cfg)

    try:
        await msg.delete()
    except Exception:
        pass

    # Exact confirmation screen with Back button
    kb = [[create_btn("⬅️ Back", callback_data=f"cfg_mod_warns_{chat_id}")]]
    if panel_msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=panel_msg_id,
                text="The punishment period has been set.",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return True
        except Exception:
            pass

    await msg.reply_text("The punishment period has been set.", reply_markup=InlineKeyboardMarkup(kb))
    return True

# --- 5. WARN PUNISHMENT EXECUTOR ---
async def execute_warn_action(context, chat_id: int, user, reason: str = ""):
    cfg = get_config(chat_id)
    max_warns = cfg.get("warn_max_count", 3)
    penalty = cfg.get("warn_penalty", "Ban")

    current_warns = get_user_warns(chat_id, user.id) + 1
    
    if current_warns < max_warns:
        set_user_warns(chat_id, user.id, current_warns)
        reason_txt = f" for {reason}" if reason else ""
        await context.bot.send_message(
            chat_id, 
            f"⚠️ {user.mention_html()} has been warned ({current_warns}/{max_warns}){reason_txt}.",
            parse_mode="HTML"
        )
        return

    # User exceeded max warns
    set_user_warns(chat_id, user.id, 0)
    dur_sec = cfg.get(f"warn_{penalty.lower()}_dur_sec", 0)
    until_time = int(time.time() + dur_sec) if dur_sec > 0 else 0

    try:
        if penalty == "Kick":
            await context.bot.ban_chat_member(chat_id, user.id)
            await context.bot.unban_chat_member(chat_id, user.id)
            await context.bot.send_message(chat_id, f"⚡ {user.mention_html()} kicked (Exceeded {max_warns} warnings).", parse_mode="HTML")

        elif penalty == "Mute":
            permissions = ChatPermissions(can_send_messages=False)
            if until_time > 0:
                await context.bot.restrict_chat_member(chat_id, user.id, permissions=permissions, until_date=until_time)
                await context.bot.send_message(chat_id, f"🔇 {user.mention_html()} muted for <b>{dur_sec}s</b> (Exceeded {max_warns} warnings).", parse_mode="HTML")
            else:
                await context.bot.restrict_chat_member(chat_id, user.id, permissions=permissions)
                await context.bot.send_message(chat_id, f"🔇 {user.mention_html()} muted permanently (Exceeded {max_warns} warnings).", parse_mode="HTML")

        elif penalty == "Ban":
            if until_time > 0:
                await context.bot.ban_chat_member(chat_id, user.id, until_date=until_time)
                await context.bot.send_message(chat_id, f"🚫 {user.mention_html()} banned for <b>{dur_sec}s</b> (Exceeded {max_warns} warnings).", parse_mode="HTML")
            else:
                await context.bot.ban_chat_member(chat_id, user.id)
                await context.bot.send_message(chat_id, f"🚫 {user.mention_html()} banned permanently (Exceeded {max_warns} warnings).", parse_mode="HTML")
    except Exception as e:
        print(f"Error executing warn penalty: {e}")
