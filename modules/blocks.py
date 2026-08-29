import re
import time
from telegram import Update, InlineKeyboardMarkup, ChatPermissions
from database import get_config, save_config
from utils import create_btn, fast_edit, parse_time_duration

# Custom Smart Duration Parser
def parse_block_duration(text: str) -> tuple:
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

# --- 1. MAIN BLOCKS MENU ---
def get_blocks_main_keyboard(cid: int):
    keyboard = [
        [create_btn("📛 Blacklist", callback_data=f"blk_menu_bl_{cid}")],
        [create_btn("🧝 Join block", callback_data=f"blk_menu_join_{cid}")],
        [create_btn("🚪 Leave block", callback_data=f"blk_menu_leave_{cid}")],
        [create_btn("🏃 Join-Leave block", callback_data=f"blk_menu_joinleave_{cid}")],
        [create_btn("👥 Multiple joins block", callback_data=f"blk_menu_multijoin_{cid}")],
        [create_btn("🤖 Block adding bots", callback_data=f"blk_menu_addbots_{cid}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_blocks_main_text():
    return "🔐 <b>Blocks</b>"

# --- 2. BLACKLIST / BLOCKLIST MENU ---
def get_blacklist_keyboard(cid: int):
    cfg = get_config(cid)
    status = cfg.get("blk_blocklist_mode", "ban")  # ban, mute, off
    
    if status == "ban":
        toggle_btn = create_btn("✅ Ban", callback_data=f"blktog_blmode_mute_{cid}", style="success")
    elif status == "mute":
        toggle_btn = create_btn("✅ Mute", callback_data=f"blktog_blmode_off_{cid}", style="success")
    else:
        toggle_btn = create_btn("❌", callback_data=f"blktog_blmode_ban_{cid}", style="danger")

    keyboard = [
        [create_btn("➕ Create Blacklist ↗️", url="https://t.me/telegram")],
        [create_btn("🚷 Blocklist ↗️", url="https://t.me/telegram"), toggle_btn],
        [create_btn("⬅️ Back", callback_data=f"cfg_mod_blocks_{cid}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_blacklist_text(cid: int):
    cfg = get_config(cid)
    status = cfg.get("blk_blocklist_mode", "ban")

    if status == "ban":
        status_line = "🚷 <b>Blocklist ➔ Active (Ban) ✅</b>"
        light_line = "💡 <b>Status: Active (Ban) ✅</b>\n └ Blocklisted users will be banned when they join the group."
    elif status == "mute":
        status_line = "🚷 <b>Blocklist ➔ Active (Mute) ✅</b>"
        light_line = "💡 <b>Status: Active (Mute) ✅</b>\n └ Blocklisted users will be muted when they join the group and they can be approved by administrators."
    else:
        status_line = "🚷 <b>Blocklist ➔ Deactivated ❌</b>"
        light_line = "💡 <b>Status: Deactivated ❌</b>"

    return (
        "📛 <b>Blacklist</b>\n"
        "From this menu you can manage lists of users, who will automatically be banned when they join the group.\n"
        "You can create a BlackList or use those created by other users.\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"{status_line}\n"
        "The Blocklist is a global blacklist created and managed by the <b>Staff of the Bot</b>.\n"
        "Information 💬\n\n"
        "⚠️ <b>ATTENTION: Users in this list have caused serious damage to other groups, therefore WE DO NOT RECOMMEND DEACTIVATING IT!</b>\n\n"
        f"{light_line}"
    )

# --- 3. JOIN BLOCK MENU ---
def get_joinblock_keyboard(cid: int):
    cfg = get_config(cid)
    p = cfg.get("blk_join_penalty", "Off")
    del_icon = "🟢" if cfg.get("blk_join_delmsg", False) else "✖️"

    r1 = [
        create_btn("❌ Off", callback_data=f"blkpen_join_Off_{cid}", style="success" if p == "Off" else None),
        create_btn("! Kick", callback_data=f"blkpen_join_Kick_{cid}", style="success" if p == "Kick" else None)
    ]
    r2 = [
        create_btn("🔊 Mute", callback_data=f"blkpen_join_Mute_{cid}", style="success" if p == "Mute" else None),
        create_btn("🚫 Ban", callback_data=f"blkpen_join_Ban_{cid}", style="success" if p == "Ban" else None)
    ]
    
    keyboard = [r1, r2]
    if p in ["Mute", "Ban"]:
        keyboard.append([create_btn(f"🚫⏰ Set {p.lower()} duration", callback_data=f"blkset_dur_join_{p}_{cid}")])

    keyboard.extend([
        [create_btn(f"♻️ Delete join message {del_icon}", callback_data=f"blktog_joindel_{cid}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_mod_blocks_{cid}")]
    ])
    return InlineKeyboardMarkup(keyboard)

def get_joinblock_text(cid: int):
    cfg = get_config(cid)
    p = cfg.get("blk_join_penalty", "Off")
    dur_str = cfg.get("blk_join_dur_str", "")
    disp = f"{p} {dur_str}".strip() if p in ["Mute", "Ban"] and dur_str else p
    return (
        "🧝 <b>Join block</b>\n"
        "Give a penalty to users or bots that try to join the group.\n\n"
        f"<b>Status:</b> {disp}"
    )

# --- 4. LEAVE BLOCK MENU ---
def get_leaveblock_keyboard(cid: int):
    cfg = get_config(cid)
    p = cfg.get("blk_leave_penalty", "Ban")

    r1 = [
        create_btn("❌ Off", callback_data=f"blkpen_leave_Off_{cid}", style="success" if p == "Off" else None),
        create_btn("🚫 Ban", callback_data=f"blkpen_leave_Ban_{cid}", style="success" if p == "Ban" else None)
    ]
    keyboard = [r1]
    if p == "Ban":
        keyboard.append([create_btn("🚫⏰ Set ban duration", callback_data=f"blkset_dur_leave_Ban_{cid}")])
    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_mod_blocks_{cid}")])
    return InlineKeyboardMarkup(keyboard)

def get_leaveblock_text(cid: int):
    cfg = get_config(cid)
    p = cfg.get("blk_leave_penalty", "Ban")
    dur_str = cfg.get("blk_leave_dur_str", "")
    disp = f"{p} {dur_str}".strip() if p == "Ban" and dur_str else p
    return (
        "🚪 <b>Leave block</b>\n"
        "Ban for users who leave the group.\n\n"
        f"<b>Status:</b> {disp}"
    )

# --- 5. JOIN-LEAVE BLOCK MENU ---
def get_joinleave_keyboard(cid: int):
    cfg = get_config(cid)
    p = cfg.get("blk_joinleave_penalty", "Ban")

    r1 = [
        create_btn("❌ Off", callback_data=f"blkpen_jl_Off_{cid}", style="success" if p == "Off" else None),
        create_btn("🚫 Ban", callback_data=f"blkpen_jl_Ban_{cid}", style="success" if p == "Ban" else None)
    ]
    keyboard = [r1]
    if p == "Ban":
        keyboard.append([create_btn("🚫⏰ Set ban duration", callback_data=f"blkset_dur_jl_Ban_{cid}")])
    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_mod_blocks_{cid}")])
    return InlineKeyboardMarkup(keyboard)

def get_joinleave_text(cid: int):
    cfg = get_config(cid)
    p = cfg.get("blk_joinleave_penalty", "Ban")
    dur_str = cfg.get("blk_jl_dur_str", "")
    disp = f"{p} {dur_str}".strip() if p == "Ban" and dur_str else p
    return (
        "🏃 <b>Join-Leave block</b>\n"
        "Penalty for users who join and immediately leave the group within a short time.\n\n"
        f"<b>Status:</b> {disp}"
    )

# --- 6. MULTIPLE JOINS BLOCK (ANTI-RAID FLOOD) ---
def get_multijoin_main_keyboard(cid: int):
    cfg = get_config(cid)
    p = cfg.get("blk_multi_penalty", "Kick")
    
    r1 = [
        create_btn("❌ Off", callback_data=f"blkpen_multi_Off_{cid}", style="success" if p == "Off" else None),
        create_btn("! Kick", callback_data=f"blkpen_multi_Kick_{cid}", style="success" if p == "Kick" else None)
    ]
    r2 = [
        create_btn("🔊 Mute", callback_data=f"blkpen_multi_Mute_{cid}", style="success" if p == "Mute" else None),
        create_btn("🚫 Ban", callback_data=f"blkpen_multi_Ban_{cid}", style="success" if p == "Ban" else None)
    ]

    keyboard = [
        [create_btn("👥 Users", callback_data=f"blkgrid_musr_{cid}"), create_btn("⏰ Time", callback_data=f"blkgrid_mtime_{cid}")],
        r1, r2
    ]
    if p in ["Mute", "Ban"]:
        keyboard.append([create_btn(f"🚫⏰ Set {p.lower()} duration", callback_data=f"blkset_dur_multi_{p}_{cid}")])
    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_mod_blocks_{cid}")])
    return InlineKeyboardMarkup(keyboard)

def get_multijoin_main_text(cid: int):
    cfg = get_config(cid)
    users_cnt = cfg.get("blk_multi_users", 4)
    seconds_cnt = cfg.get("blk_multi_seconds", 2)
    p = cfg.get("blk_multi_penalty", "Kick")
    return (
        "👥 <b>Multiple joins block</b>\n"
        "From this menu you can set a protection against massive raid joins.\n\n"
        f"Currently, the multiple join block is triggered if <b>{users_cnt} of users</b> come in <b>{seconds_cnt} of seconds</b>.\n\n"
        f"<b>Status:</b> {p}"
    )

def get_multijoin_grid_keyboard(cid: int, mode: str):
    prefix = f"blkval_{mode}_"
    numbers = [2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20, 25] if mode == "musr" else [1, 2, 3, 4, 5, 6, 8, 10, 15, 20, 25, 30]
    
    kb = []
    row = []
    for n in numbers:
        row.append(create_btn(str(n), callback_data=f"{prefix}{n}_{cid}"))
        if len(row) == 4:
            kb.append(row)
            row = []
    kb.append([create_btn("⬅️ Back", callback_data=f"blk_menu_multijoin_{cid}")])
    return InlineKeyboardMarkup(kb)

# --- 7. BLOCK ADDING BOTS ---
def get_addbots_keyboard(cid: int):
    cfg = get_config(cid)
    status = cfg.get("blk_addbots_active", False)
    toggle_btn = create_btn("🟢 Active" if status else "🔴 Off", callback_data=f"blktog_addbots_{cid}", style="success" if status else "danger")
    keyboard = [
        [toggle_btn],
        [create_btn("⬅️ Back", callback_data=f"cfg_mod_blocks_{cid}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_addbots_text(cid: int):
    cfg = get_config(cid)
    status = "Active ✅" if cfg.get("blk_addbots_active", False) else "Off ❌"
    return (
        "🤖 <b>Block adding bots</b>\n"
        "Prevent non-admin members from adding bots to the group.\n\n"
        f"<b>Status:</b> {status}"
    )

# --- 8. CALLBACK ROUTER ---
async def handle_blocks_callbacks(query, data: str, cid: int, user, user_states):
    cfg = get_config(cid)

    # Main Blocks Menu
    if data.startswith("cfg_mod_blocks_") or data.startswith("cfg_view_blocks_") or data.startswith("blk_main_"):
        user_states.pop((cid, user.id), None)
        await fast_edit(query, get_blocks_main_text(), get_blocks_main_keyboard(cid))

    # Blacklist Section
    elif data.startswith("blk_menu_bl_"):
        await fast_edit(query, get_blacklist_text(cid), get_blacklist_keyboard(cid))
    elif data.startswith("blktog_blmode_"):
        mode = data.split("_")[2]
        cfg["blk_blocklist_mode"] = mode
        save_config(cid, cfg)
        await fast_edit(query, get_blacklist_text(cid), get_blacklist_keyboard(cid))

    # Join Block Section
    elif data.startswith("blk_menu_join_"):
        await fast_edit(query, get_joinblock_text(cid), get_joinblock_keyboard(cid))
    elif data.startswith("blkpen_join_"):
        cfg["blk_join_penalty"] = data.split("_")[2]
        save_config(cid, cfg)
        await fast_edit(query, get_joinblock_text(cid), get_joinblock_keyboard(cid))
    elif data.startswith("blktog_joindel_"):
        cfg["blk_join_delmsg"] = not cfg.get("blk_join_delmsg", False)
        save_config(cid, cfg)
        await fast_edit(query, get_joinblock_text(cid), get_joinblock_keyboard(cid))

    # Leave Block Section
    elif data.startswith("blk_menu_leave_"):
        await fast_edit(query, get_leaveblock_text(cid), get_leaveblock_keyboard(cid))
    elif data.startswith("blkpen_leave_"):
        cfg["blk_leave_penalty"] = data.split("_")[2]
        save_config(cid, cfg)
        await fast_edit(query, get_leaveblock_text(cid), get_leaveblock_keyboard(cid))

    # Join-Leave Block Section
    elif data.startswith("blk_menu_joinleave_"):
        await fast_edit(query, get_joinleave_text(cid), get_joinleave_keyboard(cid))
    elif data.startswith("blkpen_jl_"):
        cfg["blk_joinleave_penalty"] = data.split("_")[2]
        save_config(cid, cfg)
        await fast_edit(query, get_joinleave_text(cid), get_joinleave_keyboard(cid))

    # Multiple Joins Section
    elif data.startswith("blk_menu_multijoin_"):
        await fast_edit(query, get_multijoin_main_text(cid), get_multijoin_main_keyboard(cid))
    elif data.startswith("blkpen_multi_"):
        cfg["blk_multi_penalty"] = data.split("_")[2]
        save_config(cid, cfg)
        await fast_edit(query, get_multijoin_main_text(cid), get_multijoin_main_keyboard(cid))
    elif data.startswith("blkgrid_"):
        mode = data.split("_")[1]
        t_str = "maximum number of joins in the group, allowed in the time interval.\n⚠️ <i>It is not recommended to set this value to more than 5 users.</i>" if mode == "musr" else "time interval of joins in the group."
        msg_text = f"Here you can select the {t_str}\n\nCurrently, the multiple join block is triggered if {cfg.get('blk_multi_users', 4)} of users come in {cfg.get('blk_multi_seconds', 2)} of seconds."
        await fast_edit(query, msg_text, get_multijoin_grid_keyboard(cid, mode))
    elif data.startswith("blkval_"):
        parts = data.split("_")
        mode, val = parts[1], int(parts[2])
        if mode == "musr":
            cfg["blk_multi_users"] = val
        else:
            cfg["blk_multi_seconds"] = val
        save_config(cid, cfg)
        await fast_edit(query, get_multijoin_main_text(cid), get_multijoin_main_keyboard(cid))

    # Block Adding Bots
    elif data.startswith("blk_menu_addbots_"):
        await fast_edit(query, get_addbots_text(cid), get_addbots_keyboard(cid))
    elif data.startswith("blktog_addbots_"):
        cfg["blk_addbots_active"] = not cfg.get("blk_addbots_active", False)
        save_config(cid, cfg)
        await fast_edit(query, get_addbots_text(cid), get_addbots_keyboard(cid))

    # Duration Set Prompt (Exact Screenshot Style)
    elif data.startswith("blkset_dur_"):
        parts = data.split("_")
        target_mod, ptype = parts[2], parts[3]
        user_states[(cid, user.id)] = f"awaiting_blk_dur_{target_mod}_{ptype}_{query.message.message_id}"
        
        dur_key = f"blk_{target_mod}_dur_str"
        current_dur = cfg.get(dur_key, "Off")
        text = (
            f"Send now the duration of the chosen punishment ({ptype})\n\n"
            f"<b>Minimum:</b> 30 seconds\n<b>Maximum:</b> 365 days\n\n"
            f"<b>Example of format:</b> 3 month 2 days 12 hours 4 minutes 34 seconds\n\n"
            f"<b>Current duration:</b> {current_dur or 'Off'}"
        )
        kb = [
            [create_btn("❌ Cancel", callback_data=f"blk_menu_{target_mod}_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))

# --- 9. TEXT STATE HANDLER FOR DURATION INPUT ---
async def handle_blocks_text_state(update: Update, context, user_states):
    msg = update.message
    if not msg or not msg.from_user:
        return False
        
    chat_id = update.effective_chat.id
    user_id = msg.from_user.id
    state_key = (chat_id, user_id)

    if state_key not in user_states:
        return False

    state = user_states.get(state_key)
    if not state or not state.startswith("awaiting_blk_dur_"):
        return False

    text = msg.text or ""
    cfg = get_config(chat_id)
    parts = state.split("_")
    target_mod = parts[3]
    panel_msg_id = int(parts[-1]) if parts[-1].isdigit() else None

    parsed_sec, dur_str = parse_block_duration(text)
    if parsed_sec < 30:
        kb = [[create_btn("❌ Cancel", callback_data=f"blk_menu_{target_mod}_{chat_id}", style="danger")]]
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
    cfg[f"blk_{target_mod}_dur_sec"] = parsed_sec
    cfg[f"blk_{target_mod}_dur_str"] = dur_str or text.strip()
    save_config(chat_id, cfg)

    try:
        await msg.delete()
    except Exception:
        pass

    # Exact confirmation screen
    kb = [[create_btn("⬅️ Back", callback_data=f"blk_menu_{target_mod}_{chat_id}")]]
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
