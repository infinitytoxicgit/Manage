import re
import time
from telegram import Update, InlineKeyboardMarkup, ChatPermissions
from database import get_config, save_config, get_user_warns, set_user_warns
from utils import create_btn, fast_edit, is_user_admin

# Media Definitions per Page
PAGE_1_ITEMS = [
    ("story", "📲", "Story"),
    ("photo", "📸", "Photo"),
    ("video", "🎞", "Video"),
    ("album", "🖼", "Album"),
    ("livephoto", "✨", "Live Photo"),
    ("gif", "🎥", "GIF"),
    ("sticker", "🃏", "Sticker"),
    ("anim_sticker", "🎭", "Animated stickers"),
    ("file", "💾", "File")
]

PAGE_2_ITEMS = [
    ("voice", "🎤", "Voice"),
    ("audio", "🎧", "Audio"),
    ("round_video", "👁‍🗨", "Round Video"),
    ("anim_games", "🎲", "Animated Games"),
    ("anim_emoji", "😀", "Animated Emoji"),
    ("prem_emoji", "👾", "Premium Emoji"),
    ("polls", "📊", "Polls"),
    ("checklist", "📋", "Checklist"),
    ("contacts", "☎️", "Contacts")
]

PAGE_3_ITEMS = [
    ("uppercase", "🆎", "Uppercase"),
    ("location", "📍", "Location"),
    ("games", "🎮", "Games"),
    ("payments", "💶", "Payments"),
    ("spoiler", "🗯", "Spoiler"),
    ("spoiler_media", "🌌", "Spoiler Media"),
    ("giveaway", "🎁", "Giveaway"),
    ("inline_bot", "🤖", "Inline Bot"),
    ("guest_bot", "🛸", "Guest Bot"),
    ("rich_msg", "🔣", "Rich message")
]

# Smart Duration Parser
def parse_media_duration(text: str) -> tuple:
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

# UI Builder
def get_media_block_text(cid: int, page: int):
    cfg = get_config(cid)
    items = PAGE_1_ITEMS if page == 1 else (PAGE_2_ITEMS if page == 2 else PAGE_3_ITEMS)
    
    status_icons = {
        "Off": "☑️ Off",
        "Warn": "❕ Warn",
        "Kick": "❗️ Kick",
        "Mute": "🔇 Mute",
        "Ban": "🚷 Ban",
        "Del": "🗑 Deletion"
    }

    lines = [
        "📸 <b>Media Block</b>\n",
        "❕ = Warn | ❗️ = Kick",
        "🔇 = Mute | 🚷 = Ban",
        "🗑 = Deletion",
        "☑️ = Off",
        "______________________________\n"
    ]

    for key, icon, name in items:
        val = cfg.get(f"med_{key}", "Off")
        val_str = status_icons.get(val, "☑️ Off")
        lines.append(f"{icon} {name} = {val_str}")

    return "\n".join(lines)

def get_media_block_keyboard(cid: int, page: int):
    cfg = get_config(cid)
    items = PAGE_1_ITEMS if page == 1 else (PAGE_2_ITEMS if page == 2 else PAGE_3_ITEMS)
    
    keyboard = []
    
    for key, icon, _ in items:
        curr = cfg.get(f"med_{key}", "Off")
        row = [
            create_btn(icon, callback_data="none", style="primary"),
            create_btn("☑️", callback_data=f"medset_{key}_Off_{page}_{cid}", style="success" if curr == "Off" else None),
            create_btn("❕", callback_data=f"medset_{key}_Warn_{page}_{cid}", style="success" if curr == "Warn" else None),
            create_btn("❗️", callback_data=f"medset_{key}_Kick_{page}_{cid}", style="success" if curr == "Kick" else None),
            create_btn("🔇", callback_data=f"medset_{key}_Mute_{page}_{cid}", style="success" if curr == "Mute" else None),
            create_btn("🚷", callback_data=f"medset_{key}_Ban_{page}_{cid}", style="success" if curr == "Ban" else None),
            create_btn("🗑", callback_data=f"medset_{key}_Del_{page}_{cid}", style="success" if curr == "Del" else None)
        ]
        keyboard.append(row)

    # Page Switchers
    p1_lbl = "•1•" if page == 1 else "1"
    p2_lbl = "•2•" if page == 2 else "2"
    p3_lbl = "•3•" if page == 3 else "3"

    nav_row = [
        create_btn(p1_lbl, callback_data=f"medpage_1_{cid}"),
        create_btn(p2_lbl, callback_data=f"medpage_2_{cid}"),
        create_btn(p3_lbl, callback_data=f"medpage_3_{cid}")
    ]
    keyboard.append(nav_row)

    # Bottom Actions
    bottom_row = [
        create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}"),
        create_btn("🔇⏰🚷", callback_data=f"med_dur_prompt_{page}_{cid}")
    ]
    keyboard.append(bottom_row)

    return InlineKeyboardMarkup(keyboard)

# Callback Router
async def handle_media_callbacks(query, data: str, cid: int, user, user_states):
    cfg = get_config(cid)

    # Main Entry
    if data.startswith("cfg_mod_media_") or data.startswith("cfg_view_media_") or data.startswith("med_main_"):
        user_states.pop((cid, user.id), None)
        await fast_edit(query, get_media_block_text(cid, 1), get_media_block_keyboard(cid, 1))

    # Page Switcher
    elif data.startswith("medpage_"):
        page = int(data.split("_")[1])
        await fast_edit(query, get_media_block_text(cid, page), get_media_block_keyboard(cid, page))

    # Set Punishment Mode per Item
    elif data.startswith("medset_"):
        parts = data.split("_")
        key, mode, page = parts[1], parts[2], int(parts[3])
        cfg[f"med_{key}"] = mode
        save_config(cid, cfg)
        await fast_edit(query, get_media_block_text(cid, page), get_media_block_keyboard(cid, page))

    # Duration Setting Prompt
    elif data.startswith("med_dur_prompt_"):
        page = int(data.split("_")[3])
        user_states[(cid, user.id)] = f"awaiting_med_dur_{page}_{query.message.message_id}"
        
        dur_str = cfg.get("med_duration_str", "Off")
        text = (
            "Send now the duration of the chosen punishment (Ban/Mute/Warn)\n\n"
            "<b>Minimum:</b> 30 seconds\n<b>Maximum:</b> 365 days\n\n"
            "<b>Example of format:</b> 3 month 2 days 12 hours 4 minutes 34 seconds\n\n"
            f"<b>Current duration:</b> {dur_str}"
        )
        kb = [
            [create_btn("❌ Cancel", callback_data=f"medpage_{page}_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))

# Text Handler for Duration Input
async def handle_media_text_state(update: Update, context, user_states):
    msg = update.message
    if not msg or not msg.from_user:
        return False

    chat_id = update.effective_chat.id
    user_id = msg.from_user.id
    state_key = (chat_id, user_id)

    if state_key not in user_states:
        return False

    state = user_states.get(state_key)
    if not state or not state.startswith("awaiting_med_dur_"):
        return False

    text = msg.text or ""
    cfg = get_config(chat_id)
    parts = state.split("_")
    page = int(parts[3])
    panel_msg_id = int(parts[-1]) if parts[-1].isdigit() else None

    parsed_sec, dur_str = parse_media_duration(text)
    if parsed_sec < 30:
        kb = [[create_btn("❌ Cancel", callback_data=f"medpage_{page}_{chat_id}", style="danger")]]
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
    cfg["med_duration_sec"] = parsed_sec
    cfg["med_duration_str"] = dur_str or text.strip()
    save_config(chat_id, cfg)

    try:
        await msg.delete()
    except Exception:
        pass

    # Exact Confirmation screen with working Back button
    kb = [[create_btn("⬅️ Back", callback_data=f"medpage_{page}_{chat_id}")]]
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

# Penalty Executor
async def execute_media_penalty(context, chat_id: int, user, penalty: str, duration_sec: int, reason: str):
    if penalty == "Off" or not penalty:
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
        print(f"Error executing media penalty: {e}")

# Live Group Message Scanner
async def inspect_media_message(update: Update, context) -> bool:
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not msg or not chat or not user or chat.type == "private":
        return False

    if await is_user_admin(chat.id, user.id, context):
        return False

    cfg = get_config(chat.id)
    detected_type = None

    # Detect Message Type
    if msg.story:
        detected_type = "story"
    elif msg.photo:
        detected_type = "photo"
    elif msg.video:
        detected_type = "video"
    elif msg.animation:
        detected_type = "gif"
    elif msg.sticker:
        detected_type = "anim_sticker" if (msg.sticker.is_animated or msg.sticker.is_video) else "sticker"
    elif msg.voice:
        detected_type = "voice"
    elif msg.audio:
        detected_type = "audio"
    elif msg.video_note:
        detected_type = "round_video"
    elif msg.dice:
        detected_type = "anim_games"
    elif msg.poll:
        detected_type = "polls"
    elif msg.contact:
        detected_type = "contacts"
    elif msg.location or msg.venue:
        detected_type = "location"
    elif msg.game:
        detected_type = "games"
    elif msg.document:
        detected_type = "file"
    elif msg.has_media_spoiler:
        detected_type = "spoiler_media"
    elif msg.via_bot:
        detected_type = "inline_bot"
    elif msg.text:
        # Uppercase Check
        letters = [c for c in msg.text if c.isalpha()]
        if len(letters) >= 8 and (sum(1 for c in letters if c.isupper()) / len(letters)) > 0.75:
            detected_type = "uppercase"

    if not detected_type:
        return False

    penalty = cfg.get(f"med_{detected_type}", "Off")
    if penalty == "Off":
        return False

    if penalty == "Del":
        try:
            await msg.delete()
        except Exception:
            pass
        return True

    try:
        await msg.delete()
    except Exception:
        pass

    dur = cfg.get("med_duration_sec", 0)
    await execute_media_penalty(context, chat.id, user, penalty, dur, f"Sending {detected_type}")
    return True
