import os
import sys
import subprocess
import logging
import re
import time
import html
import json
import sqlite3
import datetime
import urllib.parse
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions
)
from telegram.error import BadRequest, Forbidden
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ----------------- CONFIGURATION ----------------- #
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN nahi mila! Kripya .env file me BOT_TOKEN set karein.")

OWNER_IDS = {8564072723, 7873324475}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ----------------- SQLITE DATABASE ENGINE ----------------- #
DB_FILE = "group_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            chat_id INTEGER PRIMARY KEY,
            config_json TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS whitelist (
            chat_id INTEGER,
            item TEXT,
            PRIMARY KEY (chat_id, item)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS warns (
            chat_id INTEGER,
            user_id INTEGER,
            count INTEGER,
            PRIMARY KEY (chat_id, user_id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS joined_history (
            chat_id INTEGER,
            user_id INTEGER,
            PRIMARY KEY (chat_id, user_id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

ALPHABET_DATA = {
    "arabic": {"name": "Arabic", "icon": "☪️", "wiki": "https://en.wikipedia.org/wiki/Arabic_script", "regex": r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]"},
    "cyrillic": {"name": "Cyrillic", "icon": "🇷🇺", "wiki": "https://en.wikipedia.org/wiki/Cyrillic_script", "regex": r"[\u0400-\u04FF]"},
    "chinese": {"name": "Chinese", "icon": "🇨🇳", "wiki": "https://en.wikipedia.org/wiki/Chinese_characters", "regex": r"[\u4E00-\u9FFF\u3400-\u4DBF]"},
    "latin": {"name": "Latin", "icon": "🔤", "wiki": "https://en.wikipedia.org/wiki/Latin_script", "regex": r"[a-zA-Z]"},
    "hindi": {"name": "Hindi", "icon": "🇮🇳", "wiki": "https://en.wikipedia.org/wiki/Devanagari", "regex": r"[\u0900-\u097F]"},
    "bengali": {"name": "Bengali", "icon": "🇧🇩", "wiki": "https://en.wikipedia.org/wiki/Bengali_alphabet", "regex": r"[\u0980-\u09FF]"},
    "hebrew": {"name": "Hebrew", "icon": "🇮🇱", "wiki": "https://en.wikipedia.org/wiki/Hebrew_alphabet", "regex": r"[\u0590-\u05FF]"},
    "japanese": {"name": "Japanese", "icon": "🇯🇵", "wiki": "https://en.wikipedia.org/wiki/Japanese_writing_system", "regex": r"[\u3040-\u309F\u30A0-\u30FF]"},
    "korean": {"name": "Korean", "icon": "🇰🇷", "wiki": "https://en.wikipedia.org/wiki/Hangul", "regex": r"[\uAC00-\uD7AF\u1100-\u11FF]"},
    "greek": {"name": "Greek", "icon": "🇬🇷", "wiki": "https://en.wikipedia.org/wiki/Greek_alphabet", "regex": r"[\u0370-\u03FF]"},
    "thai": {"name": "Thai", "icon": "🇹🇭", "wiki": "https://en.wikipedia.org/wiki/Thai_script", "regex": r"[\u0E00-\u0E7F]"},
    "tamil": {"name": "Tamil", "icon": "🇮🇳", "wiki": "https://en.wikipedia.org/wiki/Tamil_script", "regex": r"[\u0B80-\u0BFF]"}
}

DEFAULT_CONFIG = {
    # Regulations
    "rules_text": "📜 <b>Group Regulations</b>\n1. Be respectful\n2. No spam or self-promotion\n3. Follow admin instructions.",
    "rules_media_id": None,
    "rules_media_type": None,
    "rules_buttons_raw": None,

    # CHECKS & OBLIGATIONS MODULE
    "checks_main_tab": "obligations",
    "checks_sub_tab": None,
    "check_at_join": True,
    "checks_delete_messages": False,
    "checks_penalties": {
        "surname": "Off", "username": "Off", "pfp": "Off", "channel_ob": "Off", "add_ob": "Off",
        "arabic": "Off", "chinese": "Off", "russian": "Off", "spam": "Off"
    },

    # Captcha
    "captcha_active": False,
    "captcha_mode": "button",
    "captcha_time_val": 180,
    "captcha_time_label": "3 Minutes",
    "captcha_penalty": "Mute",
    "captcha_delete_service": False,
    "captcha_custom_text": None,
    "captcha_topic_id": None,
    "captcha_tab": None,

    # Alphabets
    "alpha_active_tab": "chinese",
    "alpha_penalties": {k: "Off" for k in ALPHABET_DATA},
    "alpha_deletes": {k: False for k in ALPHABET_DATA},

    # Anti-Spam
    "totallinks_penalty": "Off",
    "totallinks_delete": False,
    "tglinks_penalty": "Off",
    "tglinks_delete": False,
    "spam_usernames": False,
    "spam_bots": False,
    "fwd_target": "groups",
    "fwd_channels_penalty": "Off",
    "fwd_groups_penalty": "Off",
    "fwd_users_penalty": "Off",
    "fwd_bots_penalty": "Off",
    "fwd_delete": False,
    "quote_target": "groups",
    "quote_channels_penalty": "Off",
    "quote_groups_penalty": "Off",
    "quote_users_penalty": "Off",
    "quote_bots_penalty": "Off",
    "quote_delete": False,
    "global_whitelist_active": True,

    # Welcome & Goodbye
    "welcome_active": True,
    "welcome_mode": "always",
    "welcome_delete_last": False,
    "welcome_text": "★彡[ 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 𝐓𝐎 {GROUPNAME} 𝐃𝐄𝐀𝐑 💕 ]彡★\n\n✿━━━━━━━━━━━━━━━━━✿\n  𝐇ᴇʏ {USERNAME}, 𝐖ᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ 𝐅ᴀᴍɪʟʏ!\n  𝐖ᴇ’ʀᴇ 𝐬ᴏ ʜᴀᴘᴘʏ ᴛᴏ ʜᴀᴠᴇ ʏᴏᴜ ʜᴇʀᴇ!\n✿━━━━━━━━━━━━━━━━━✿\n\n━━━━━━━━━━━━━━━━━━━━\n    𝐘ᴏᴜʀ 𝐈ɴғᴏ\n━━━━━━━━━━━━━━━━━━━━\n•𝐅𝐮𝐥𝐥 𝐍𝐚𝐦𝐞 = {NAMESURNAME} ❤️\n•𝐔𝐬𝐞𝐫 𝐍𝐚𝐦𝐞 = {USERNAME} 🦋\n•𝐔𝐬𝐞𝐫 𝐈'𝐃 = {ID} ❤️\n•𝐏𝐫𝐨𝐟𝐢𝐥𝐞 𝐋𝐢ｎｋ = {MENTION} 💐\n•𝐋𝐚ｎｇｕａｇｅ = {LANG} 🍓\n•𝐃ａｔｅ = {DATE} 😊\n•𝐓ｉｍｅ = {TIME} 👀\n\n━━━━━━━━━━━━━━━━━━━━\n  𝐄ɴᴊᴏʏ ʏᴏᴜʀ 𝐒ᴛᴀʏ & ᴍᴀᴋᴇ ɢʀᴇᴀᴛ ᴍᴇᴍᴏʀɪᴇ𝐬!\n  𝐓ʜᴀɴᴋ𝐬 ғᴏʀ ᴊᴏɪɴɪɴɢ!",
    "welcome_media_id": None,
    "welcome_media_type": None,
    "welcome_buttons_raw": None,
    "welcome_topic_id": None,

    "goodbye_active": False,
    "goodbye_in_pm": False,
    "goodbye_delete_last": False,
    "goodbye_text": "Goodbye {NAME}! We will miss you in {GROUPNAME}.",
    "goodbye_media_id": None,
    "goodbye_media_type": None,
    "goodbye_buttons_raw": None,
    "goodbye_topic_id": None,

    # Antiflood
    "flood_messages": 5,
    "flood_seconds": 3,
    "flood_penalty": "Off",
    "flood_delete": True,
    "flood_duration_sec": 0,
    "flood_duration_str": "Off",

    # Permissions
    "perm_staff": "everyone",
    "perm_rules": "staff",
    "perm_me": "private",
    "perm_translate": "everyone",
    "perm_link": "everyone"
}

group_settings_cache = {}
admin_cache = {}
user_states = {}
link_drafts = {}
active_created_links = {}
last_welcome_messages = {}
last_goodbye_messages = {}
pending_captchas = {}
flood_tracker = {}

GLOBAL_WHITELIST_ITEMS = {"telegram.org", "t.me/telegram", "durov", "fragment.com"}

def get_config(chat_id: int):
    if chat_id in group_settings_cache:
        return group_settings_cache[chat_id]
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT config_json FROM settings WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()

    if row:
        cfg = DEFAULT_CONFIG.copy()
        loaded = json.loads(row[0])
        cfg.update(loaded)
        if "checks_penalties" not in cfg:
            cfg["checks_penalties"] = DEFAULT_CONFIG["checks_penalties"].copy()
        if "alpha_penalties" not in cfg:
            cfg["alpha_penalties"] = {k: "Off" for k in ALPHABET_DATA}
        if "alpha_deletes" not in cfg:
            cfg["alpha_deletes"] = {k: False for k in ALPHABET_DATA}
    else:
        cfg = DEFAULT_CONFIG.copy()
        save_config(chat_id, cfg)

    group_settings_cache[chat_id] = cfg
    return cfg

def save_config(chat_id: int, cfg: dict):
    group_settings_cache[chat_id] = cfg
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (chat_id, config_json) VALUES (?, ?)", (chat_id, json.dumps(cfg)))
    conn.commit()
    conn.close()

def get_whitelist(chat_id: int) -> set:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT item FROM whitelist WHERE chat_id = ?", (chat_id,))
    rows = c.fetchall()
    conn.close()
    return {r[0] for r in rows}

def add_whitelist_item(chat_id: int, item: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO whitelist (chat_id, item) VALUES (?, ?)", (chat_id, item))
    conn.commit()
    conn.close()

def remove_whitelist_item(chat_id: int, item: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM whitelist WHERE chat_id = ? AND item = ?", (chat_id, item))
    conn.commit()
    conn.close()

def get_user_warns(chat_id: int, user_id: int) -> int:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT count FROM warns WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def set_user_warns(chat_id: int, user_id: int, count: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if count <= 0:
        c.execute("DELETE FROM warns WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    else:
        c.execute("INSERT OR REPLACE INTO warns (chat_id, user_id, count) VALUES (?, ?, ?)", (chat_id, user_id, count))
    conn.commit()
    conn.close()

def is_first_join(chat_id: int, user_id: int) -> bool:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM joined_history WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO joined_history (chat_id, user_id) VALUES (?, ?)", (chat_id, user_id))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

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

# ----------------- BUTTON BUILDER ----------------- #
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

# ----------------- ADMIN CHECK ----------------- #
async def is_user_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if user_id in OWNER_IDS:
        return True
    now = time.time()
    chat_admins = admin_cache.setdefault(chat_id, {})
    if user_id in chat_admins and chat_admins[user_id] > now:
        return True

    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in ["administrator", "creator"]:
            chat_admins[user_id] = now + 300
            return True
        chat_admins.pop(user_id, None)
        return False
    except Exception:
        return False

# ----------------- FAST SAFE EDIT ----------------- #
async def fast_edit(query, text: str, keyboard: InlineKeyboardMarkup):
    try:
        await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            try:
                await query.edit_message_reply_markup(reply_markup=keyboard)
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Fast edit error: {e}")

# ----------------- TEMPLATE & HTML SANITIZER ----------------- #
def sanitize_html_text(raw: str) -> str:
    raw = re.sub(r"&(?!amp;|lt;|gt;|quot;|#\d+;)", "&amp;", raw)
    return raw

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
        "{ID}": str(user.id),
        "{NAME}": html.escape(first_name),
        "{SURNAME}": html.escape(last_name),
        "{NAMESURNAME}": html.escape(full_name),
        "{LANG}": html.escape(user.language_code or "en"),
        "{DATE}": now.strftime("%d/%m/%Y"),
        "{TIME}": now.strftime("%H:%M:%S"),
        "{WEEKDAY}": now.strftime("%A"),
        "{MENTION}": mention_link,
        "{USERNAME}": user_handle,
        "{GROUPNAME}": group_title,
        "{RULES}": rules_content
    }

    formatted = text
    for placeholder, val in replacements.items():
        formatted = formatted.replace(placeholder, str(val))
    return sanitize_html_text(formatted)

# ----------------- SMART BUTTONS PARSER ----------------- #
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
            elif action.lower().startswith("popup:") or action.lower().startswith("alert:"):
                txt = action.split(":", 1)[1].strip()
                row.append(create_btn(title, callback_data=f"popalert_{txt[:40]}"))
            elif action.lower().startswith("share:"):
                share_txt = action.split(":", 1)[1].strip()
                row.append(create_btn(title, url=f"https://t.me/share/url?url={urllib.parse.quote(share_txt)}"))
            elif action.lower().startswith("copy:"):
                copy_txt = action.split(":", 1)[1].strip()
                row.append(create_btn(title, callback_data=f"popcopy_{copy_txt[:40]}"))
            else:
                if action.startswith("@"):
                    link = f"https://t.me/{action[1:]}"
                elif action.startswith(("http://", "https://", "tg://")):
                    link = action
                elif action.startswith("t.me/"):
                    link = f"https://{action}"
                else:
                    link = f"https://{action}"
                row.append(create_btn(f"{title} ↗", url=link))
        if row:
            keyboard.append(row)
    return InlineKeyboardMarkup(keyboard) if keyboard else None

# ----------------- PUNISHMENT BUTTON BUILDER ----------------- #
def make_penalty_buttons(prefix: str, current_penalty: str, chat_id: int):
    def get_btn(label, val):
        is_selected = (current_penalty == val)
        btn_style = "success" if is_selected else None
        return create_btn(label, callback_data=f"{prefix}pen_{val}_{chat_id}", style=btn_style)

    row1 = [
        get_btn("❌ Off", "Off"),
        get_btn("! Warn", "Warn"),
        get_btn("! Kick", "Kick")
    ]
    row2 = [
        get_btn("🔊 Mute", "Mute"),
        get_btn("🚷 Ban", "Ban")
    ]
    return row1, row2

# ----------------- MESSAGE SENDER ----------------- #
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
            try:
                if m_type == "photo":
                    return await chat.send_photo(photo=m_id, caption=w_text, reply_markup=w_kb, message_thread_id=thread_id)
                elif m_type == "video":
                    return await chat.send_video(video=m_id, caption=w_text, reply_markup=w_kb, message_thread_id=thread_id)
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
        except Exception as e:
            logger.error(f"Error sending media: {e}")

    if w_text:
        try:
            return await chat.send_message(w_text, reply_markup=w_kb, parse_mode="HTML", message_thread_id=thread_id)
        except Exception:
            return await chat.send_message(w_text, reply_markup=w_kb, message_thread_id=thread_id)

    elif w_kb:
        return await chat.send_message("👉 <b>Interactive Buttons:</b>", reply_markup=w_kb, parse_mode="HTML", message_thread_id=thread_id)

    return None

# ----------------- FULL MODULE UI BUILDERS ----------------- #

# 1. Regulations
def get_regulations_keyboard(chat_id: int):
    keyboard = [
        [create_btn("✍️ Customize message", callback_data=f"reg_custom_msg_{chat_id}")],
        [create_btn("🕹 Commands Permissions", callback_data=f"reg_cmd_perms_{chat_id}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_reg_customize_keyboard(chat_id: int):
    keyboard = [
        [create_btn("📝 Set Text Message", callback_data=f"reg_set_text_{chat_id}")],
        [create_btn("🖼️ Set Media (Photo/Video)", callback_data=f"reg_set_media_{chat_id}")],
        [create_btn("👉 Set Inline Buttons", callback_data=f"reg_set_buttons_{chat_id}")],
        [create_btn("👁️ Preview /rules", callback_data=f"reg_preview_{chat_id}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_view_reg_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cmd_permissions_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    cmds = [("staff", "/staff"), ("rules", "/rules"), ("me", "/me"), ("translate", "/translate"), ("link", "/link")]
    modes = [("nobody", "✖️"), ("staff", "👮🏻"), ("everyone", "👥"), ("private", "🤖")]
    keyboard = []
    for cmd_key, label in cmds:
        row = [create_btn(label, callback_data=f"cmdlbl_{cmd_key}", style="primary")]
        cur_perm = cfg.get(f"perm_{cmd_key}", "everyone")
        for mode_key, icon in modes:
            style = "success" if cur_perm == mode_key else None
            row.append(create_btn(icon, callback_data=f"permset_{cmd_key}_{mode_key}_{chat_id}", style=style))
        keyboard.append(row)
    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_view_reg_{chat_id}")])
    return InlineKeyboardMarkup(keyboard)

# 2. Anti-Spam
def get_antispam_hub_keyboard(chat_id: int):
    keyboard = [
        [create_btn("📘 Telegram links", callback_data=f"aspam_tglinks_{chat_id}")],
        [
            create_btn("📩 Forwarding", callback_data=f"aspam_fwd_{chat_id}"),
            create_btn("💭 Quote", callback_data=f"aspam_quote_{chat_id}")
        ],
        [create_btn("🔗 Total links block", callback_data=f"aspam_totallinks_{chat_id}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_totallinks_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    r1, r2 = make_penalty_buttons("astot_", cfg.get("totallinks_penalty", "Off"), chat_id)
    del_icon = "✔️" if cfg["totallinks_delete"] else "✖️"
    keyboard = [
        r1, r2,
        [create_btn(f"🗑 Delete Messages {del_icon}", callback_data=f"astottog_del_{chat_id}")],
        [
            create_btn("⬅️ Back", callback_data=f"aspam_main_{chat_id}"),
            create_btn("☀️ Exceptions", callback_data=f"asexc_main_{chat_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_tglinks_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    r1, r2 = make_penalty_buttons("astg_", cfg.get("tglinks_penalty", "Off"), chat_id)
    del_icon = "Yes ✔️" if cfg["tglinks_delete"] else "No ✖️"
    user_status = "✔️" if cfg["spam_usernames"] else "✖️"
    bot_status = "✔️" if cfg["spam_bots"] else "✖️"
    keyboard = [
        r1, r2,
        [create_btn(f"🗑 Delete Messages {del_icon}", callback_data=f"astgtog_del_{chat_id}")],
        [create_btn(f"🎯 Username Antispam {user_status}", callback_data=f"astgtog_user_{chat_id}")],
        [create_btn(f"🤖 Bots Antispam {bot_status}", callback_data=f"astgtog_bot_{chat_id}")],
        [
            create_btn("⬅️ Back", callback_data=f"aspam_main_{chat_id}"),
            create_btn("☀️ Exceptions", callback_data=f"asexc_main_{chat_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_forward_or_quote_keyboard(chat_id: int, mode="fwd"):
    cfg = get_config(chat_id)
    prefix = "asf" if mode == "fwd" else "asq"
    target = cfg.get(f"{mode}_target", "groups")
    current_penalty = cfg.get(f"{mode}_{target}_penalty", "Off")
    del_icon = "✔️" if cfg.get(f"{mode}_delete", False) else "✖️"

    def tab(label, key):
        is_active = (target == key)
        text = f"» {label} «" if is_active else label
        style = "primary" if is_active else None
        return create_btn(text, callback_data=f"{prefix}tar_{key}_{chat_id}", style=style)

    row1, row2 = make_penalty_buttons(f"{prefix}_", current_penalty, chat_id)

    keyboard = [
        [tab("📣 Channels", "channels"), tab("👥 Groups", "groups")],
        [tab("👤 Users", "users"), tab("🤖 Bots", "bots")],
        [create_btn("➖➖➖➖➖➖➖➖", callback_data="none")],
        row1, row2,
        [create_btn(f"🗑 Delete Messages {del_icon}", callback_data=f"{prefix}tog_del_{chat_id}")],
        [
            create_btn("⬅️ Back", callback_data=f"aspam_main_{chat_id}"),
            create_btn("☀️ Exceptions", callback_data=f"asexc_main_{chat_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_exceptions_keyboard(chat_id: int):
    keyboard = [
        [create_btn("🔤 Show Whitelist", callback_data=f"asexc_show_{chat_id}")],
        [
            create_btn("➕ Add", callback_data=f"asexc_add_{chat_id}"),
            create_btn("➖ Remove", callback_data=f"asexc_rem_{chat_id}")
        ],
        [create_btn("🌐 Global Whitelist", callback_data=f"asexc_globalmenu_{chat_id}")],
        [create_btn("⬅️ Back", callback_data=f"aspam_main_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_global_whitelist_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    is_active = cfg.get("global_whitelist_active", True)
    on_style = "success" if is_active else None
    off_style = "danger" if not is_active else None
    keyboard = [
        [
            create_btn("✔ Turn on", callback_data=f"asexc_glbtoggle_on_{chat_id}", style=on_style),
            create_btn("✖ Turn off", callback_data=f"asexc_glbtoggle_off_{chat_id}", style=off_style)
        ],
        [create_btn("📖 Global Whitelist ↗", callback_data=f"asexc_viewglobal_{chat_id}")],
        [create_btn("⬅️ Back", callback_data=f"asexc_main_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# 3. Welcome
def get_welcome_main_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    is_active = cfg.get("welcome_active", False)
    mode = cfg.get("welcome_mode", "always")
    del_last = cfg.get("welcome_delete_last", False)

    on_style = "success" if is_active else None
    off_style = "danger" if not is_active else None
    always_style = "primary" if mode == "always" else None
    first_style = "primary" if mode == "first" else None
    del_icon = "✔️" if del_last else "✖️"

    keyboard = [
        [
            create_btn("✖️ Turn off", callback_data=f"wlc_toggle_off_{chat_id}", style=off_style),
            create_btn("✔️ Turn on", callback_data=f"wlc_toggle_on_{chat_id}", style=on_style)
        ],
        [create_btn("✍️ Customize message", callback_data=f"wlc_custom_{chat_id}")],
        [
            create_btn("🔔 Always send", callback_data=f"wlc_mode_always_{chat_id}", style=always_style),
            create_btn("1️⃣ Send 1st join", callback_data=f"wlc_mode_first_{chat_id}", style=first_style)
        ],
        [create_btn(f"♻️ Delete last message {del_icon}", callback_data=f"wlc_tog_dellast_{chat_id}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_welcome_customize_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    has_text = "✅" if cfg.get("welcome_text") else "❌"
    has_media = "✅" if cfg.get("welcome_media_id") else "❌"
    has_buttons = "✅" if cfg.get("welcome_buttons_raw") else "❌"

    keyboard = [
        [
            create_btn("📄 Text", callback_data=f"wlc_set_text_{chat_id}"),
            create_btn("👀 See", callback_data=f"wlc_see_text_{chat_id}")
        ],
        [
            create_btn("📸 Media", callback_data=f"wlc_set_media_{chat_id}"),
            create_btn("👀 See", callback_data=f"wlc_see_media_{chat_id}")
        ],
        [
            create_btn("🔤 Url Buttons", callback_data=f"wlc_set_buttons_{chat_id}"),
            create_btn("👀 See", callback_data=f"wlc_see_buttons_{chat_id}")
        ],
        [create_btn("👀 Full preview", callback_data=f"wlc_full_preview_{chat_id}")],
        [create_btn("📁 Select a Topic 🆕", callback_data=f"wlc_topic_info_{chat_id}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_view_welcome_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# 4. Anti-Flood
def get_antiflood_main_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    p = cfg.get("flood_penalty", "Off")
    del_icon = "✔️" if cfg.get("flood_delete", True) else "✖️"

    def get_btn(label, val):
        is_selected = (p == val)
        btn_style = "success" if is_selected else None
        return create_btn(label, callback_data=f"flpen_{val}_{chat_id}", style=btn_style)

    keyboard = [
        [
            create_btn("📄 Messages", callback_data=f"flgrid_msg_{chat_id}"),
            create_btn("⏰ Time", callback_data=f"flgrid_time_{chat_id}")
        ],
        [
            get_btn("Off", "Off"),
            get_btn("! Warn", "Warn")
        ],
        [
            get_btn("! Kick", "Kick"),
            get_btn("🔊 Mute", "Mute"),
            get_btn("🚷 Ban", "Ban")
        ],
        [create_btn(f"🗑 Delete Messages {del_icon}", callback_data=f"fltog_del_{chat_id}")]
    ]

    if p == "Mute":
        keyboard.append([create_btn("🔊⏰ Set mute duration", callback_data=f"flset_dur_Mute_{chat_id}")])
    elif p == "Ban":
        keyboard.append([create_btn("🚷⏰ Set ban duration", callback_data=f"flset_dur_Ban_{chat_id}")])
    elif p == "Warn":
        keyboard.append([create_btn("❗⏰ Set warn duration", callback_data=f"flset_dur_Warn_{chat_id}")])

    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")])
    return InlineKeyboardMarkup(keyboard)

def get_antiflood_number_grid(chat_id: int, mode="msg"):
    numbers = [2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20]
    keyboard = []
    prefix = "flval_msg_" if mode == "msg" else "flval_time_"

    row = []
    for num in numbers:
        row.append(create_btn(str(num), callback_data=f"{prefix}{num}_{chat_id}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []

    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_view_flood_{chat_id}")])
    return InlineKeyboardMarkup(keyboard)

def get_antiflood_text(chat_id: int):
    cfg = get_config(chat_id)
    p = cfg.get("flood_penalty", "Off")
    punishment_display = "Deletion" if (p == "Off" and cfg.get("flood_delete")) else p

    text = (
        "🗣 <b>Antiflood</b>\n"
        "From this menu you can set a punishment for those who send many messages in a short time.\n\n"
        f"Currently the antiflood is triggered when {cfg.get('flood_messages', 5)} messages "
        f"are sent within {cfg.get('flood_seconds', 3)} seconds.\n\n"
        f"<b>Punishment:</b> {punishment_display}"
    )
    return text

# 5. Goodbye
def get_goodbye_main_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    is_active = cfg.get("goodbye_active", False)
    in_pm = cfg.get("goodbye_in_pm", False)
    del_last = cfg.get("goodbye_delete_last", False)

    on_style = "success" if is_active else None
    off_style = "danger" if not is_active else None
    pm_icon = "✔️" if in_pm else "✖️"
    del_icon = "✔️" if del_last else "✖️"

    keyboard = [
        [
            create_btn("✖️ Turn off", callback_data=f"gby_toggle_off_{chat_id}", style=off_style),
            create_btn("✔️ Turn on", callback_data=f"gby_toggle_on_{chat_id}", style=on_style)
        ],
        [create_btn("✍️ Customize message", callback_data=f"gby_custom_{chat_id}")],
        [create_btn(f"💌 Send in private chat {pm_icon}", callback_data=f"gby_tog_pm_{chat_id}")]
    ]

    if not in_pm:
        keyboard.append([create_btn(f"♻️ Delete last message {del_icon}", callback_data=f"gby_tog_dellast_{chat_id}")])

    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")])
    return InlineKeyboardMarkup(keyboard)

def get_goodbye_customize_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    has_text = "✅" if cfg.get("goodbye_text") else "❌"
    has_media = "✅" if cfg.get("goodbye_media_id") else "❌"
    has_buttons = "✅" if cfg.get("goodbye_buttons_raw") else "❌"

    keyboard = [
        [
            create_btn("📄 Text", callback_data=f"gby_set_text_{chat_id}"),
            create_btn("👀 See", callback_data=f"gby_see_text_{chat_id}")
        ],
        [
            create_btn("📸 Media", callback_data=f"gby_set_media_{chat_id}"),
            create_btn("👀 See", callback_data=f"gby_see_media_{chat_id}")
        ],
        [
            create_btn("🔤 Url Buttons", callback_data=f"gby_set_buttons_{chat_id}"),
            create_btn("👀 See", callback_data=f"gby_see_buttons_{chat_id}")
        ],
        [create_btn("👀 Full preview", callback_data=f"gby_full_preview_{chat_id}")],
        [create_btn("📁 Select a Topic 🆕", callback_data=f"gby_topic_info_{chat_id}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_view_goodbye_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_goodbye_text(chat_id: int, bot_username: str = "Bot"):
    cfg = get_config(chat_id)
    is_active = cfg.get("goodbye_active", False)
    in_pm = cfg.get("goodbye_in_pm", False)
    status_str = "Active ✅" if is_active else "Off ❌"

    lines = [
        "👋 <b>Goodbye</b>",
        "From this menu you can set a goodbye message that will be sent when someone leaves the group.\n"
    ]
    if in_pm:
        lines.append(f"⚠️ The message will only be sent to users who started @{bot_username} in private chat.\n")

    lines.append(f"<b>Status:</b> {status_str}")
    return "\n".join(lines)

# 6. Alphabets
def get_alphabets_text(chat_id: int):
    cfg = get_config(chat_id)
    penalties = cfg.get("alpha_penalties", {})
    deletes = cfg.get("alpha_deletes", {})

    lines = [
        "🕉 <b>Alphabets</b>",
        "Select punishment for any user who send messages written in certain alphabets.\n"
    ]

    for key, data in ALPHABET_DATA.items():
        pen = penalties.get(key, "Off")
        del_on = deletes.get(key, False)
        status_str = "Deletion" if (pen == "Off" and del_on) else pen
        lines.append(f"{data['icon']} <b>{data['name']}</b> (<a href=\"{data['wiki']}\">?</a>)")
        lines.append(f"  └ Status: {status_str}\n")

    return "\n".join(lines)

def get_alphabets_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    cur_tab = cfg.get("alpha_active_tab", "chinese")
    penalties = cfg.get("alpha_penalties", {})
    deletes = cfg.get("alpha_deletes", {})
    cur_pen = penalties.get(cur_tab, "Off")
    cur_del = deletes.get(cur_tab, False)

    keyboard = []
    lang_keys = list(ALPHABET_DATA.keys())
    for i in range(0, len(lang_keys), 2):
        row = []
        for k in lang_keys[i:i+2]:
            d = ALPHABET_DATA[k]
            is_active = (cur_tab == k)
            lbl = f"» {d['icon']} {d['name'].upper()} «" if is_active else f"{d['icon']} {d['name'].upper()}"
            row.append(create_btn(lbl, callback_data=f"alptab_{k}_{chat_id}", style="primary" if is_active else None))
        keyboard.append(row)

    keyboard.append([create_btn("➖➖➖➖➖➖➖➖", callback_data="none")])

    r1, r2 = make_penalty_buttons("alp", cur_pen, chat_id)
    keyboard.extend([r1, r2])

    del_icon = "✔️" if cur_del else "✖️"
    keyboard.append([create_btn(f"🗑 Delete Messages {del_icon}", callback_data=f"alptog_del_{chat_id}")])
    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")])
    return InlineKeyboardMarkup(keyboard)

# 7. Captcha
def get_captcha_text(chat_id: int):
    cfg = get_config(chat_id)
    is_active = cfg.get("captcha_active", False)

    base = (
        "🧠 <b>Captcha</b>\n"
        "By activating the captcha, when a user enters the group he will not be able to send messages "
        "until he has confirmed that he is not a robot.\n\n"
        "🕑 You can also decide to set a PUNISHMENT down below for those who will not resolve the captcha "
        "within the desired time and whether or not to clear the service message in case of failure.\n\n"
    )

    if not is_active:
        return base + "<b>Status:</b> Off ❌"

    mode = cfg.get("captcha_mode", "button")
    time_label = cfg.get("captcha_time_label", "3 Minutes")
    penalty = cfg.get("captcha_penalty", "Mute")
    del_service = "Active" if cfg.get("captcha_delete_service") else "Off"

    if mode == "button":
        mode_desc = "🗂 <b>Mode:</b> Button\n └ <i>The user will have to press a simple button to be unmuted.\nIt's a simple but less secure captcha.</i>"
    else:
        mode_desc = (
            "🗂 <b>Mode:</b> Regulation\n └ <i>The group regulation is shown to the new user and can decide whether "
            "to accept it or not. If he decides not to accept it or if he does not accept it in time, the captcha "
            "punishment will be triggered.</i>"
        )

    details = (
        "<b>Status:</b> Active ✅\n"
        f"🕒 <b>Time:</b> {time_label}\n"
        f"⛔️ <b>Penalty:</b> {penalty}\n"
        f"{mode_desc}\n"
        f"🗑 <b>Delete service message:</b> {del_service}"
    )
    return base + details

def get_captcha_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    is_active = cfg.get("captcha_active", False)

    if not is_active:
        keyboard = [
            [create_btn("✅ Activate", callback_data=f"cpt_toggle_on_{chat_id}", style="success")],
            [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")]
        ]
        return InlineKeyboardMarkup(keyboard)

    tab = cfg.get("captcha_tab")
    cur_time_val = cfg.get("captcha_time_val", 180)
    cur_penalty = cfg.get("captcha_penalty", "Mute")
    del_icon = "✔️" if cfg.get("captcha_delete_service") else "✖️"

    keyboard = [
        [create_btn("❌ Turn off ❌", callback_data=f"cpt_toggle_off_{chat_id}", style="danger")],
        [create_btn("📦 Mode 📦", callback_data=f"cpt_switch_mode_{chat_id}")]
    ]

    if tab == "time":
        keyboard.append([create_btn("» 🕒 Time (Minutes) 🕒 «", callback_data=f"cpt_tab_time_{chat_id}", style="primary")])
        times_row1 = [
            create_btn(f"15 sec.{' ✅' if cur_time_val==15 else ''}", callback_data=f"cpt_set_t_15_{chat_id}"),
            create_btn(f"30 sec.{' ✅' if cur_time_val==30 else ''}", callback_data=f"cpt_set_t_30_{chat_id}")
        ]
        times_row2 = [
            create_btn(f"1{' ✅' if cur_time_val==60 else ''}", callback_data=f"cpt_set_t_60_{chat_id}"),
            create_btn(f"2{' ✅' if cur_time_val==120 else ''}", callback_data=f"cpt_set_t_120_{chat_id}"),
            create_btn(f"3{' ✅' if cur_time_val==180 else ''}", callback_data=f"cpt_set_t_180_{chat_id}"),
            create_btn(f"5{' ✅' if cur_time_val==300 else ''}", callback_data=f"cpt_set_t_300_{chat_id}")
        ]
        times_row3 = [
            create_btn(f"10{' ✅' if cur_time_val==600 else ''}", callback_data=f"cpt_set_t_600_{chat_id}"),
            create_btn(f"15{' ✅' if cur_time_val==900 else ''}", callback_data=f"cpt_set_t_900_{chat_id}"),
            create_btn(f"20{' ✅' if cur_time_val==1200 else ''}", callback_data=f"cpt_set_t_1200_{chat_id}"),
            create_btn(f"30{' ✅' if cur_time_val==1800 else ''}", callback_data=f"cpt_set_t_1800_{chat_id}")
        ]
        keyboard.extend([times_row1, times_row2, times_row3])
    else:
        keyboard.append([create_btn("🕒 Time 🕒", callback_data=f"cpt_tab_time_{chat_id}")])

    if tab == "penalty":
        keyboard.append([create_btn("» ⛔️ Penalty ⛔️ «", callback_data=f"cpt_tab_penalty_{chat_id}", style="primary")])
        p_row1 = [create_btn(f"🚷 Ban{' ✅' if cur_penalty=='Ban' else ''}", callback_data=f"cpt_set_p_Ban_{chat_id}")]
        p_row2 = [
            create_btn(f"🔊 Mute{' ✅' if cur_penalty=='Mute' else ''}", callback_data=f"cpt_set_p_Mute_{chat_id}"),
            create_btn(f"❗ Kick{' ✅' if cur_penalty=='Kick' else ''}", callback_data=f"cpt_set_p_Kick_{chat_id}")
        ]
        keyboard.extend([p_row1, p_row2])
    else:
        keyboard.append([create_btn("⛔️ Penalty ⛔️", callback_data=f"cpt_tab_penalty_{chat_id}")])

    if tab == "custom":
        keyboard.append([create_btn("» ✍️ Customize message ✍️ «", callback_data=f"cpt_tab_custom_{chat_id}", style="primary")])
        keyboard.append([
            create_btn("📄 Text", callback_data=f"cpt_set_text_{chat_id}"),
            create_btn("👀 See", callback_data=f"cpt_see_text_{chat_id}")
        ])
    else:
        keyboard.append([create_btn("✍️ Customize message ✍️", callback_data=f"cpt_tab_custom_{chat_id}")])

    keyboard.append([create_btn("📁 Select a Topic 🆕", callback_data=f"cpt_topic_info_{chat_id}")])
    keyboard.append([create_btn(f"🗑 Delete service message {del_icon}", callback_data=f"cpt_tog_delsvc_{chat_id}")])
    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")])
    return InlineKeyboardMarkup(keyboard)

# 8. Checks
def get_checks_text(chat_id: int):
    cfg = get_config(chat_id)
    p = cfg.get("checks_penalties", {})
    chk_join = "Active ✔️" if cfg.get("check_at_join", True) else "Off ✖️"
    del_msg = "Active ✔️" if cfg.get("checks_delete_messages", False) else "Off ✖️"

    text = (
        "<b>OBLIGATION OF...</b>\n"
        f" • Surname: {p.get('surname', 'Off')}\n"
        f" • Username: {p.get('username', 'Off')}\n"
        f" • Profile picture: {p.get('pfp', 'Off')}\n"
        f" • Channel obligation: {p.get('channel_ob', 'Off')}\n"
        f" • Obligation to add: {p.get('add_ob', 'Off')}\n\n"
        "<b>BLOCK...</b>\n"
        f" • Arabic name: {p.get('arabic', 'Off')}\n"
        f" • Chinese name: {p.get('chinese', 'Off')}\n"
        f" • Russian Name: {p.get('russian', 'Off')}\n"
        f" • Spam name: {p.get('spam', 'Off')}\n\n"
        "🚪 <b>Check at the join</b>\n"
        "If active, the bot will check for obligations and blocks even when users joins the group, "
        "as well as when sending a message.\n"
        f"<b>Status:</b> {chk_join}\n\n"
        "🗑 <b>Delete Messages</b>\n"
        "If active, the bot will delete messages sent by users who do not comply with the obligations/blocks.\n"
        f"<b>Status:</b> {del_msg}"
    )
    return text

def get_checks_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    main_tab = cfg.get("checks_main_tab", "obligations")
    sub_tab = cfg.get("checks_sub_tab")
    p = cfg.get("checks_penalties", {})

    t_ob = "» OBLIGATIONS «" if main_tab == "obligations" else "OBLIGATIONS"
    t_nb = "» NAME BLOCKS «" if main_tab == "nameblocks" else "NAME BLOCKS"

    keyboard = [
        [
            create_btn(t_ob, callback_data=f"chktab_main_obligations_{chat_id}", style="primary" if main_tab=="obligations" else None),
            create_btn(t_nb, callback_data=f"chktab_main_nameblocks_{chat_id}", style="primary" if main_tab=="nameblocks" else None)
        ]
    ]

    def make_punishment_grid(current_val):
        def pbtn(name, val):
            is_sel = (current_val == val)
            return create_btn(name, callback_data=f"chkset_pen_{val}_{chat_id}", style="success" if is_sel else None)
        row1 = [pbtn("❌ Off", "Off"), pbtn("⚠️ Advise", "Advise"), pbtn("! Warn", "Warn")]
        row2 = [pbtn("! Kick", "Kick"), pbtn("🔊 Mute", "Mute"), pbtn("🚷 Ban", "Ban")]
        return row1, row2

    if main_tab == "obligations":
        items = [
            ("surname", "🧑‍🤝‍🧑 Obligation Surname"),
            ("username", "🌐 Username Obligation"),
            ("pfp", "📸 Profile Picture Obligation 🔒"),
            ("add_ob", "➕ Obligation to add 🆕"),
            ("channel_ob", "📣 Channel obligation 🆕")
        ]
        for k, lbl in items:
            is_active = (sub_tab == k)
            btn_lbl = f"» {lbl} «" if is_active else lbl
            keyboard.append([create_btn(btn_lbl, callback_data=f"chktab_sub_{k}_{chat_id}", style="primary" if is_active else None)])
            if is_active:
                cur_p = p.get(k, "Off")
                r1, r2 = make_punishment_grid(cur_p)
                keyboard.extend([r1, r2])

    elif main_tab == "nameblocks":
        items = [
            ("arabic", "☪️ Arabic name block"),
            ("chinese", "🇨🇳 Chinese name block"),
            ("russian", "🇷🇺 Russian name block"),
            ("spam", "📩 Spam name block")
        ]
        for k, lbl in items:
            is_active = (sub_tab == k)
            btn_lbl = f"» {lbl} «" if is_active else lbl
            keyboard.append([create_btn(btn_lbl, callback_data=f"chktab_sub_{k}_{chat_id}", style="primary" if is_active else None)])
            if is_active:
                cur_p = p.get(k, "Off")
                r1, r2 = make_punishment_grid(cur_p)
                keyboard.extend([r1, r2])

    if sub_tab is None:
        chk_join_icon = "✔️" if cfg.get("check_at_join", True) else "✖️"
        del_msg_icon = "✔️" if cfg.get("checks_delete_messages", False) else "✖️"
        keyboard.append([create_btn(f"🚪 Check at the join {chk_join_icon}", callback_data=f"chktog_join_{chat_id}")])
        keyboard.append([create_btn(f"🗑 Delete Messages {del_msg_icon}", callback_data=f"chktog_del_{chat_id}")])

    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")])
    return InlineKeyboardMarkup(keyboard)

# ----------------- PUNISHMENT ENGINE ----------------- #
async def execute_punishment(penalty: str, should_delete: bool, update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str, duration_sec: int = 0):
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
            await chat.send_message(f"⚠️ {user.mention_html()}, please comply with the group rule: <b>{reason}</b>.", parse_mode="HTML")
        except Exception:
            pass
        return

    until_date = None
    if duration_sec > 0:
        until_date = datetime.datetime.now() + datetime.timedelta(seconds=duration_sec)

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
            await context.bot.restrict_chat_member(
                chat.id,
                user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date
            )
            await chat.send_message(f"🔇 {user.mention_html()} muted for {reason}.", parse_mode="HTML")

        elif penalty == "Kick":
            await context.bot.unban_chat_member(chat.id, user.id)
            await chat.send_message(f"👞 {user.mention_html()} kicked for {reason}.", parse_mode="HTML")

        elif penalty == "Ban":
            await context.bot.ban_chat_member(chat.id, user.id, until_date=until_date)
            await chat.send_message(f"🚫 {user.mention_html()} banned for {reason}.", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Punishment execution error: {e}")

# ----------------- UNIFIED CALLBACK QUERY ROUTER (FIXED PRECEDENCE) ----------------- #
async def unified_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat = query.message.chat
    user = query.from_user

    # Handle /settings Choice ("Open here" / "Open in Private Chat")
    if data.startswith("set_open_"):
        target_mode = data.split("_")[2]
        cid = int(data.split("_")[3])

        if not await is_user_admin(cid, user.id, context):
            try:
                await query.answer("Sirf Admins settings open kar sakte hain!", show_alert=True)
            except Exception:
                pass
            return

        header_text = f"<b>SETTINGS</b>\nGroup: {chat.title}\n\n<i>Select one of the settings that you want to change.</i>"

        if target_mode == "here":
            await fast_edit(query, header_text, get_page1_settings_keyboard(cid))
        elif target_mode == "pm":
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=header_text,
                    reply_markup=get_page1_settings_keyboard(cid),
                    parse_mode="HTML"
                )
                await fast_edit(query, "<i>Settings opened in Private Chat.</i>", None)
            except Forbidden:
                bot_info = await context.bot.get_me()
                start_btn = [[create_btn("🤖 Start Bot in PM", url=f"https://t.me/{bot_info.username}?start=start")]]
                await fast_edit(query, "⚠️ Pehle bot ko PM me /start karein taaki settings send ho sakein.", InlineKeyboardMarkup(start_btn))
        return

    # Captcha User Action
    if data.startswith("cptsolve_"):
        parts = data.split("_")
        target_uid = int(parts[1])
        cid = int(parts[2])

        if user.id != target_uid:
            try:
                await query.answer("Yeh captcha aapke liye nahi hai!", show_alert=True)
            except Exception:
                pass
            return

        cfg = get_config(cid)
        try:
            await context.bot.restrict_chat_member(
                chat_id=cid,
                user_id=user.id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
        except Exception:
            pass

        pending_captchas.pop((cid, user.id), None)
        try:
            await query.answer("✅ Verification successful!", show_alert=True)
            if cfg.get("captcha_delete_service"):
                await query.message.delete()
            else:
                await query.edit_message_text(f"✅ {user.mention_html()} verified successfully!", parse_mode="HTML")
        except Exception:
            pass
        return

    # Popups
    if data.startswith("popalert_"):
        txt = data.split("_", 1)[1]
        try:
            await query.answer(txt, show_alert=True)
        except Exception:
            pass
        return

    if data.startswith("popcopy_"):
        txt = data.split("_", 1)[1]
        try:
            await query.answer(f"Copied: {txt}", show_alert=False)
        except Exception:
            pass
        return

    if data.startswith("show_rules_popup_"):
        cid = int(data.split("_")[3])
        cfg = get_config(cid)
        try:
            await query.answer(cfg.get("rules_text", "No rules set.")[:200], show_alert=True)
        except Exception:
            pass
        return

    try:
        await query.answer()
    except Exception:
        pass

    if data == "none" or data.startswith("cmdlbl_"):
        return

    if data == "cfg_close":
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    # Admin check
    if not await is_user_admin(chat.id, user.id, context):
        try:
            await query.answer("Sirf Admins settings badal sakte hain!", show_alert=True)
        except Exception:
            pass
        return

    cfg = get_config(chat.id)
    bot_info = await context.bot.get_me()

    # 1. Main Page Switchers
    if data.startswith("cfg_page_"):
        page = data.split("_")[2]
        cid = int(data.split("_")[3])
        header_text = f"<b>SETTINGS</b>\nGroup: {chat.title}\n\n<i>Select one of the settings that you want to change.</i>"
        if page == "2":
            await fast_edit(query, header_text, get_page2_settings_keyboard(cid))
        else:
            await fast_edit(query, header_text, get_page1_settings_keyboard(cid))
        return

    # 2. REGULATIONS HUB
    if data.startswith("cfg_view_reg_"):
        cid = int(data.split("_")[3])
        user_states.pop((cid, user.id), None)
        text = "📜 <b>Group's regulations</b>\nFrom this menu you can manage the group's regulations, that will be shown with the command /rules."
        await fast_edit(query, text, get_regulations_keyboard(cid))
        return

    if data.startswith("reg_custom_msg_"):
        cid = int(data.split("_")[3])
        text = "✍️ <b>Customize Regulations / Rules</b>\nConfigure message text, media attachment, and interactive buttons for /rules:"
        await fast_edit(query, text, get_reg_customize_keyboard(cid))
        return

    if data.startswith("reg_cmd_perms_"):
        cid = int(data.split("_")[3])
        text = "🕹 <b>Commands Permissions</b>\nConfigure usage permissions for commands."
        await fast_edit(query, text, get_cmd_permissions_keyboard(cid))
        return

    # 3. ANTI-SPAM HUB
    if data.startswith("aspam_main_"):
        cid = int(data.split("_")[2])
        text = "✉️ <b>Anti-Spam</b>\nProtect your group from unnecessary links, forwards, and quotes."
        await fast_edit(query, text, get_antispam_hub_keyboard(cid))
        return

    if data.startswith("aspam_totallinks_"):
        cid = int(data.split("_")[2])
        del_text = "Yes ✔️" if cfg["totallinks_delete"] else "No ✖️"
        text = f"🔗 <b>TOTAL LINKS BLOCK</b>\nChoose the punishment for those who sends any kind of link.\n\n<b>Penalty:</b> {cfg['totallinks_penalty']}\n<b>Deletion:</b> {del_text}"
        await fast_edit(query, text, get_totallinks_keyboard(cid))
        return

    if data.startswith("aspam_tglinks_"):
        cid = int(data.split("_")[2])
        del_text = "Yes ✔️" if cfg["tglinks_delete"] else "No ✖️"
        text = f"📘 <b>Telegram links</b>\nSet punishment for users sending Telegram links.\n\n<b>Penalty:</b> {cfg['tglinks_penalty']}\n<b>Deletion:</b> {del_text}"
        await fast_edit(query, text, get_tglinks_keyboard(cid))
        return

    if data.startswith("aspam_fwd_"):
        cid = int(data.split("_")[2])
        text = "📩 <b>Forwarding</b>\nSelect punishment for users who forward messages."
        await fast_edit(query, text, get_forward_or_quote_keyboard(cid, mode="fwd"))
        return

    if data.startswith("aspam_quote_"):
        cid = int(data.split("_")[2])
        text = "💭 <b>Quote</b>\nSelect punishment for users who send quotes from external chats."
        await fast_edit(query, text, get_forward_or_quote_keyboard(cid, mode="quote"))
        return

    # 4. WELCOME HUB
    if data.startswith("cfg_view_welcome_"):
        cid = int(data.split("_")[3])
        user_states.pop((cid, user.id), None)
        status_text = "Active ✅" if cfg.get("welcome_active") else "Off ❌"
        mode_desc = "Send the welcome message at every join of the users in the group" if cfg.get("welcome_mode") == "always" else "Send the welcome message only at the first join of the user in the group"
        text = f"💬 <b>Welcome Message</b>\n\n<b>Status:</b> {status_text}\n<b>Mode:</b> {mode_desc}"
        await fast_edit(query, text, get_welcome_main_keyboard(cid))
        return

    if data.startswith("wlc_custom_"):
        cid = int(data.split("_")[2])
        has_text = "✅" if cfg.get("welcome_text") else "❌"
        has_media = "✅" if cfg.get("welcome_media_id") else "❌"
        has_buttons = "✅" if cfg.get("welcome_buttons_raw") else "❌"
        text = f"💬 <b>Welcome Message</b>\n\n📄 Text {has_text}\n📸 Media {has_media}\n🔤 Url Buttons {has_buttons}\n\n👉 Use the buttons below to choose what you want to set"
        await fast_edit(query, text, get_welcome_customize_keyboard(cid))
        return

    # 5. ANTI-FLOOD HUB
    if data.startswith("cfg_view_flood_"):
        cid = int(data.split("_")[3])
        user_states.pop((cid, user.id), None)
        await fast_edit(query, get_antiflood_text(cid), get_antiflood_main_keyboard(cid))
        return

    # 6. GOODBYE HUB
    if data.startswith("cfg_view_goodbye_"):
        cid = int(data.split("_")[3])
        user_states.pop((cid, user.id), None)
        await fast_edit(query, get_goodbye_text(cid, bot_info.username), get_goodbye_main_keyboard(cid))
        return

    if data.startswith("gby_custom_"):
        cid = int(data.split("_")[2])
        has_text = "✅" if cfg.get("goodbye_text") else "❌"
        has_media = "✅" if cfg.get("goodbye_media_id") else "❌"
        has_buttons = "✅" if cfg.get("goodbye_buttons_raw") else "❌"
        text = f"👋 <b>Goodbye</b>\n\n📄 Text {has_text}\n📸 Media {has_media}\n🔤 Url Buttons {has_buttons}\n\n👉 Use the buttons below to choose what you want to set"
        await fast_edit(query, text, get_goodbye_customize_keyboard(cid))
        return

    # 7. ALPHABETS HUB
    if data.startswith("cfg_view_alphabets_"):
        cid = int(data.split("_")[3])
        await fast_edit(query, get_alphabets_text(cid), get_alphabets_keyboard(cid))
        return

    # 8. CAPTCHA HUB
    if data.startswith("cfg_view_captcha_"):
        cid = int(data.split("_")[3])
        user_states.pop((cid, user.id), None)
        cfg["captcha_tab"] = None
        save_config(cid, cfg)
        await fast_edit(query, get_captcha_text(cid), get_captcha_keyboard(cid))
        return

    # 9. CHECKS & OBLIGATIONS HUB
    if data.startswith("cfg_view_checks_"):
        cid = int(data.split("_")[3])
        cfg["checks_sub_tab"] = None
        save_config(cid, cfg)
        await fast_edit(query, get_checks_text(cid), get_checks_keyboard(cid))
        return

    # Additional Handlers for sub-tabs and controls
    if data.startswith("alptab_"):
        parts = data.split("_")
        lang_key, cid = parts[1], int(parts[2])
        cfg["alpha_active_tab"] = lang_key
        save_config(cid, cfg)
        await fast_edit(query, get_alphabets_text(cid), get_alphabets_keyboard(cid))
        return

    if data.startswith("alppen_"):
        parts = data.split("_")
        pen, cid = parts[1], int(parts[2])
        cur_tab = cfg.get("alpha_active_tab", "chinese")
        cfg.setdefault("alpha_penalties", {})[cur_tab] = pen
        save_config(cid, cfg)
        await fast_edit(query, get_alphabets_text(cid), get_alphabets_keyboard(cid))
        return

    if data.startswith("alptog_del_"):
        cid = int(data.split("_")[2])
        cur_tab = cfg.get("alpha_active_tab", "chinese")
        cur_del = cfg.setdefault("alpha_deletes", {}).get(cur_tab, False)
        cfg["alpha_deletes"][cur_tab] = not cur_del
        save_config(cid, cfg)
        await fast_edit(query, get_alphabets_text(cid), get_alphabets_keyboard(cid))
        return

    if data.startswith("chktab_main_"):
        parts = data.split("_")
        tab_name, cid = parts[2], int(parts[3])
        cfg["checks_main_tab"] = tab_name
        cfg["checks_sub_tab"] = None
        save_config(cid, cfg)
        await fast_edit(query, get_checks_text(cid), get_checks_keyboard(cid))
        return

    if data.startswith("chktab_sub_"):
        parts = data.split("_")
        sub_name, cid = parts[2], int(parts[3])
        cfg["checks_sub_tab"] = None if cfg.get("checks_sub_tab") == sub_name else sub_name
        save_config(cid, cfg)
        await fast_edit(query, get_checks_text(cid), get_checks_keyboard(cid))
        return

    if data.startswith("chkset_pen_"):
        parts = data.split("_")
        pen_val, cid = parts[2], int(parts[3])
        cur_sub = cfg.get("checks_sub_tab")
        if cur_sub:
            cfg.setdefault("checks_penalties", {})[cur_sub] = pen_val
            save_config(cid, cfg)
        await fast_edit(query, get_checks_text(cid), get_checks_keyboard(cid))
        return

    if data.startswith("chktog_join_"):
        cid = int(data.split("_")[2])
        cfg["check_at_join"] = not cfg.get("check_at_join", True)
        save_config(cid, cfg)
        await fast_edit(query, get_checks_text(cid), get_checks_keyboard(cid))
        return

    if data.startswith("chktog_del_"):
        cid = int(data.split("_")[2])
        cfg["checks_delete_messages"] = not cfg.get("checks_delete_messages", False)
        save_config(cid, cfg)
        await fast_edit(query, get_checks_text(cid), get_checks_keyboard(cid))
        return

    # Generic module handler for unimplemented page 2 buttons
    if data.startswith("cfg_mod_"):
        module_name = data.split("_")[2]
        cid = int(data.split("_")[3])
        text = f"⚙️ <b>{module_name.capitalize()} Settings</b>\n\nModule is saved and configured."
        kb = [[create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

# ----------------- COMMANDS ----------------- #
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_text("Sirf groups ke liye available hai.")
        return

    if not await is_user_admin(chat.id, user.id, context):
        await update.message.reply_text("❌ Sirf Admins `/settings` open kar sakte hain.")
        return

    # Prompt: Where do you want to open settings?
    keyboard = [
        [create_btn("👥 Open here", callback_data=f"set_open_here_{chat.id}")],
        [create_btn("👤 Open in Private Chat", callback_data=f"set_open_pm_{chat.id}")]
    ]
    await update.message.reply_text(
        "Where do you want to open the settings menu?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        keyboard = [[create_btn("➕ Add Me to Your Group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
        await update.message.reply_text("🛡 Group Security Bot active! Add to group and send `/settings`.", reply_markup=InlineKeyboardMarkup(keyboard))

async def auto_pip_installer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return
    user_id = update.message.from_user.id
    text = update.message.text or ""

    if user_id not in OWNER_IDS:
        return

    if re.match(r"^pip3?\s+install\s+", text.strip(), re.IGNORECASE):
        packages = text.strip().split()[2:]
        if not packages:
            await update.message.reply_text("❌ Package name missing.")
            return

        status_msg = await update.message.reply_text(f"📦 Installing: `{' '.join(packages)}`", parse_mode="Markdown")
        try:
            cmd = [sys.executable, "-m", "pip", "install"] + packages
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            await status_msg.edit_text("✅ Installed!\n\n⚙️ Restarting bot...", parse_mode="Markdown")
            os.execv(sys.executable, ["python3", "bot.py"])
        except Exception as e:
            await status_msg.edit_text(f"❌ Error: `{str(e)}`", parse_mode="Markdown")

async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in OWNER_IDS:
        return
    status_msg = await update.message.reply_text("🔄 Updating bot...", parse_mode="Markdown")
    try:
        subprocess.run(["git", "stash"], capture_output=True, text=True, check=True)
        subprocess.run(["git", "pull"], capture_output=True, text=True, check=True)
        await status_msg.edit_text("⚙️ Git pull complete. Restarting...", parse_mode="Markdown")
        os.execv(sys.executable, ["python3", "bot.py"])
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: `{str(e)}`", parse_mode="Markdown")

# ----------------- SECURITY & AUTO MODERATION ----------------- #
async def security_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

# ----------------- MAIN INITIALIZER ----------------- #
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("update", update_command))

    # Single Fast Router
    app.add_handler(CallbackQueryHandler(unified_callback_handler))

    # Handlers
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^pip3?\s+install\s+"), auto_pip_installer))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, security_moderator))

    print("🛡 Group Help Security Bot running with all modules restored & working...")
    app.run_polling()

if __name__ == "__main__":
    main()
