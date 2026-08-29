import re
import html
import datetime
import urllib.parse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.error import BadRequest
from config import OWNER_IDS
from database import get_config, get_user_warns, set_user_warns

admin_cache = {}

def create_btn(text: str, callback_data: str = None, url: str = None, style: str = None):
    try:
        if url:
            return InlineKeyboardButton(text=text, url=url)
        if style:
            return InlineKeyboardButton(text=text, callback_data=callback_data, style=style)
    except TypeError:
        pass
    if url:
        return InlineKeyboardButton(text=text, url=url)
    return InlineKeyboardButton(text=text, callback_data=callback_data)

def make_penalty_buttons(prefix: str, current_penalty: str, chat_id: int):
    def get_btn(label, val):
        is_selected = (current_penalty == val)
        btn_style = "success" if is_selected else None
        return create_btn(label, callback_data=f"{prefix}pen_{val}_{chat_id}", style=btn_style)

    row1 = [get_btn("❌ Off", "Off"), get_btn("! Warn", "Warn"), get_btn("! Kick", "Kick")]
    row2 = [get_btn("🔊 Mute", "Mute"), get_btn("🚷 Ban", "Ban")]
    return row1, row2

async def is_user_admin(chat_id: int, user_id: int, context) -> bool:
    if user_id in OWNER_IDS or chat_id > 0:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return True

async def fast_edit(query, text: str, keyboard: InlineKeyboardMarkup):
    try:
        await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            try:
                await query.edit_message_reply_markup(reply_markup=keyboard)
            except Exception:
                pass

def parse_time_duration(text: str) -> int:
    text = text.lower().strip()
    patterns = {
        "year": 31536000, "y": 31536000,
        "month": 2592000, "mo": 2592000,
        "week": 604800, "w": 604800,
        "day": 86400, "d": 86400,
        "hour": 3600, "h": 3600,
        "minute": 60, "min": 60, "m": 60,
        "second": 1, "sec": 1, "s": 1
    }
    total_sec = 0
    matches = re.findall(r"(\d+)\s*([a-zA-Z]+)", text)
    if matches:
        for val, unit in matches:
            val = int(val)
            for k, sec in patterns.items():
                if unit.startswith(k):
                    total_sec += val * sec
                    break
    elif text.isdigit():
        total_sec = int(text)

    return total_sec

def format_template(text: str, user, chat, cfg: dict):
    if not text:
        return ""
    now = datetime.datetime.now()
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    mention_link = f'<a href="tg://user?id={user.id}">{html.escape(first_name)}</a>'
    user_handle = f"@{user.username}" if user.username else mention_link
    group_title = html.escape(chat.title) if chat and chat.title else "Group"
    rules_content = cfg.get("rules_text", "")

    replacements = {
        "{ID}": str(user.id), "{NAME}": html.escape(first_name), "{SURNAME}": html.escape(last_name),
        "{NAMESURNAME}": html.escape(full_name), "{LANG}": html.escape(user.language_code or "en"),
        "{DATE}": now.strftime("%d/%m/%Y"), "{TIME}": now.strftime("%H:%M:%S"), "{WEEKDAY}": now.strftime("%A"),
        "{MENTION}": mention_link, "{USERNAME}": user_handle, "{GROUPNAME}": group_title, "{RULES}": rules_content
    }

    formatted = text
    for placeholder, val in replacements.items():
        formatted = formatted.replace(placeholder, str(val))
    return re.sub(r"&(?!amp;|lt;|gt;|quot;|#\d+;)", "&amp;", formatted)

def parse_custom_buttons(raw_data: str, chat_id: int):
    if not raw_data:
        return None
    keyboard = []
    for line in raw_data.strip().splitlines():
        row = []
        for part in line.split("&&"):
            if "-" not in part:
                continue
            title, action = part.split("-", 1)
            title, action = title.strip(), action.strip()
            if action.lower() == "rules":
                row.append(create_btn(title, callback_data=f"show_rules_popup_{chat_id}"))
            elif action.lower().startswith("popup:"):
                txt = action.split(":", 1)[1].strip()
                row.append(create_btn(title, callback_data=f"popalert_{txt[:40]}"))
            elif action.lower().startswith("share:"):
                share_txt = action.split(":", 1)[1].strip()
                row.append(create_btn(title, url=f"https://t.me/share/url?url={urllib.parse.quote(share_txt)}"))
            elif action.lower().startswith("copy:"):
                copy_txt = action.split(":", 1)[1].strip()
                row.append(create_btn(title, callback_data=f"popcopy_{copy_txt[:40]}"))
            else:
                link = f"https://t.me/{action[1:]}" if action.startswith("@") else (action if action.startswith(("http://", "https://")) else f"https://{action}")
                row.append(create_btn(f"{title} ↗", url=link))
        if row:
            keyboard.append(row)
    return InlineKeyboardMarkup(keyboard) if keyboard else None

async def send_custom_bundle(chat, user, cfg: dict, mode="welcome", is_preview=False, thread_id=None):
    text_key = f"{mode}_text"
    kb_key = f"{mode}_buttons_raw"
    mid_key = f"{mode}_media_id"
    mtype_key = f"{mode}_media_type"

    w_text = format_template(cfg.get(text_key, ""), user, chat, cfg)
    w_kb = parse_custom_buttons(cfg.get(kb_key), chat.id)
    m_id = cfg.get(mid_key)
    m_type = cfg.get(mtype_key)

    if m_id and m_type in ["photo", "video"] and len(w_text) <= 1000:
        try:
            if m_type == "photo":
                return await chat.send_photo(photo=m_id, caption=w_text, reply_markup=w_kb, parse_mode="HTML", message_thread_id=thread_id)
            elif m_type == "video":
                return await chat.send_video(video=m_id, caption=w_text, reply_markup=w_kb, parse_mode="HTML", message_thread_id=thread_id)
        except Exception:
            pass

    if m_id:
        try:
            if m_type == "photo":
                await chat.send_photo(photo=m_id, message_thread_id=thread_id)
            elif m_type == "video":
                await chat.send_video(video=m_id, message_thread_id=thread_id)
            elif m_type == "sticker":
                await chat.send_sticker(sticker=m_id, message_thread_id=thread_id)
        except Exception:
            pass

    if w_text:
        try:
            return await chat.send_message(w_text, reply_markup=w_kb, parse_mode="HTML", message_thread_id=thread_id)
        except Exception:
            return await chat.send_message(w_text, reply_markup=w_kb, message_thread_id=thread_id)
    elif w_kb:
        return await chat.send_message("👉 <b>Buttons:</b>", reply_markup=w_kb, parse_mode="HTML", message_thread_id=thread_id)
    return None

async def execute_punishment(penalty: str, should_delete: bool, update, context, reason: str, duration_sec: int = 0):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message

    if should_delete and msg:
        try:
            await msg.delete()
        except Exception:
            pass

    if penalty == "Off" or not penalty:
        return

    if penalty == "Advise":
        try:
            await chat.send_message(f"⚠️ {user.mention_html()}, please comply with the rule: <b>{reason}</b>.", parse_mode="HTML")
        except Exception:
            pass
        return

    until_date = datetime.datetime.now() + datetime.timedelta(seconds=duration_sec) if duration_sec > 0 else None

    try:
        if penalty == "Warn":
            current_warns = get_user_warns(chat.id, user.id) + 1
            limit = get_config(chat.id).get("warn_limit", 3)
            if current_warns >= limit:
                set_user_warns(chat.id, user.id, 0)
                await context.bot.ban_chat_member(chat.id, user.id, until_date=until_date)
                await chat.send_message(f"🚫 {user.mention_html()} banned ({limit}/{limit} warns) for {reason}.", parse_mode="HTML")
            else:
                set_user_warns(chat.id, user.id, current_warns)
                await chat.send_message(f"⚠️ {user.mention_html()} warned ({current_warns}/{limit}) for {reason}!", parse_mode="HTML")
        elif penalty == "Mute":
            await context.bot.restrict_chat_member(chat.id, user.id, permissions=ChatPermissions(can_send_messages=False), until_date=until_date)
            await chat.send_message(f"🔇 {user.mention_html()} muted for {reason}.", parse_mode="HTML")
        elif penalty == "Kick":
            await context.bot.unban_chat_member(chat.id, user.id)
            await chat.send_message(f"👞 {user.mention_html()} kicked for {reason}.", parse_mode="HTML")
        elif penalty == "Ban":
            await context.bot.ban_chat_member(chat.id, user.id, until_date=until_date)
            await chat.send_message(f"🚫 {user.mention_html()} banned for {reason}.", parse_mode="HTML")
    except Exception:
        pass
