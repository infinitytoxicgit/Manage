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
    "bengali": {"name": "Bengali", "icon": "🇧🇩", "wiki": "https://en.wikipedia.org/wiki/Bengali_alphabet", "regex": r"[\u0980-\u09FF]"}
}

DEFAULT_CONFIG = {
    # Regulations
    "rules_text": "📜 <b>Group Regulations</b>\n1. Be respectful\n2. No spam or self-promotion\n3. Follow admin instructions.",
    "rules_media_id": None,
    "rules_media_type": None,
    "rules_buttons_raw": None,

    # Checks & Obligations
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

    # Welcome System
    "welcome_active": True,
    "welcome_mode": "always",
    "welcome_delete_last": False,
    "welcome_text": "★彡[ 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 𝐓𝐎 {GROUPNAME} 𝐃𝐄𝐀𝐑 💕 ]彡★\n\n✿━━━━━━━━━━━━━━━━━✿\n  𝐇ᴇʏ {USERNAME}, 𝐖ᴇʟᴄᴏᴍᴇ ᴛ𝐨 ᴛʜᴇ 𝐅ᴀᴍɪʟʏ!\n  𝐖ᴇ’ʀᴇ 𝐬𝐨 ʜᴀ𝐩𝐩ʏ ᴛ𝐨 ʜᴀᴠᴇ 𝐲ᴏ𝐮 ʜᴇʀᴇ!\n✿━━━━━━━━━━━━━━━━━✿\n\n━━━━━━━━━━━━━━━━━━━━\n    𝐘ᴏ𝐮ʀ 𝐈ɴғᴏ\n━━━━━━━━━━━━━━━━━━━━\n•𝐅𝐮𝐥𝐥 𝐍𝐚𝐦𝐞 = {NAMESURNAME} ❤️\n•𝐔𝐬𝐞𝐫 𝐍𝐚𝐦𝐞 = {USERNAME} 🦋\n•𝐔𝐬𝐞𝐫 𝐈'𝐃 = {ID} ❤️\n•𝐏𝐫𝐨𝐟𝐢𝐥𝐞 𝐋𝐢𝐧𝐤 = {MENTION} 💐\n•𝐋𝐚𝐧𝐠𝐮𝐚𝐠𝐞 = {LANG} 🍓\n•𝐃ａ𝐭𝐞 = {DATE} 😊\n•𝐓ｉｍ𝐞 = {TIME} 👀\n\n━━━━━━━━━━━━━━━━━━━━\n  𝐄ɴᴊᴏʏ ʏᴏᴜʀ 𝐒ᴛᴀʏ & ᴍᴀᴋᴇ ɢʀᴇᴀ𝐭 ᴍᴇᴍᴏʀɪᴇ𝐬!\n  𝐓ʜᴀɴᴋ𝐬 ғ𝐨ʀ ᴊᴏɪɴɪɴɢ!",
    "welcome_media_id": None,
    "welcome_media_type": None,
    "welcome_buttons_raw": None,
    "welcome_topic_id": None,

    # Goodbye System
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

# ----------------- BUTTON CREATOR ----------------- #
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

# ----------------- ADMIN CHECK ----------------- #
async def is_user_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if user_id in OWNER_IDS:
        return True
    if chat_id > 0:
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
        return True

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

# ----------------- DUAL-PAGE KEYBOARDS ----------------- #
def get_page1_settings_keyboard(chat_id: int):
    keyboard = [
        [
            create_btn("📜 Regulation", callback_data=f"cfg_view_reg_{chat_id}"),
            create_btn("✉️ Anti-Spam", callback_data=f"aspam_main_{chat_id}")
        ],
        [
            create_btn("💬 Welcome", callback_data=f"cfg_view_welcome_{chat_id}"),
            create_btn("🗣 Anti-Flood", callback_data=f"cfg_view_flood_{chat_id}")
        ],
        [
            create_btn("👋 Goodbye", callback_data=f"cfg_view_goodbye_{chat_id}"),
            create_btn("🕉 Alphabets", callback_data=f"cfg_view_alphabets_{chat_id}")
        ],
        [
            create_btn("🧠 Captcha", callback_data=f"cfg_view_captcha_{chat_id}"),
            create_btn("🔦 Checks", callback_data=f"cfg_view_checks_{chat_id}")
        ],
        [
            create_btn("🆘 @Admin", callback_data=f"cfg_mod_admin_{chat_id}"),
            create_btn("🔐 Blocks", callback_data=f"cfg_mod_blocks_{chat_id}")
        ],
        [
            create_btn("📸 Media", callback_data=f"cfg_mod_media_{chat_id}"),
            create_btn("🔞 Porn", callback_data=f"cfg_mod_porn_{chat_id}")
        ],
        [
            create_btn("❗ Warns", callback_data=f"cfg_mod_warns_{chat_id}"),
            create_btn("🌘 Night", callback_data=f"cfg_mod_night_{chat_id}")
        ],
        [
            create_btn("🔔 Tag", callback_data=f"cfg_mod_tag_{chat_id}"),
            create_btn("🔗 Link", callback_data=f"cfg_mod_link_{chat_id}")
        ],
        [create_btn("🕵️ Guardian Bot 🆕", callback_data=f"cfg_mod_guardian_{chat_id}")],
        [create_btn("🗂 Approval mode", callback_data=f"cfg_mod_approval_{chat_id}")],
        [create_btn("🗑 Deleting Messages", callback_data=f"cfg_mod_delmsg_{chat_id}")],
        [
            create_btn("🇬🇧 Lang", callback_data=f"cfg_mod_lang_{chat_id}"),
            create_btn("✅ Close", callback_data="cfg_close"),
            create_btn("▶️ Other", callback_data=f"cfg_page_2_{chat_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_page2_settings_keyboard(chat_id: int):
    keyboard = [
        [create_btn("📁 Topic", callback_data=f"cfg_view_topic_{chat_id}")],
        [create_btn("🔤 Banned Words", callback_data=f"cfg_mod_bannedwords_{chat_id}")],
        [create_btn("🕒 Recurring messages", callback_data=f"cfg_mod_recurring_{chat_id}")],
        [create_btn("👥 Members Management", callback_data=f"cfg_mod_members_{chat_id}")],
        [create_btn("😷 Masked users", callback_data=f"cfg_mod_masked_{chat_id}")],
        [create_btn("📣 Discussion group 🆕", callback_data=f"cfg_mod_discussion_{chat_id}")],
        [create_btn("📱 Personal Commands", callback_data=f"cfg_mod_personalcmds_{chat_id}")],
        [create_btn("🎭 Magic Stickers&GIFs", callback_data=f"cfg_mod_magicstickers_{chat_id}")],
        [create_btn("📏 Message length", callback_data=f"cfg_mod_msglength_{chat_id}")],
        [create_btn("📢 Channels management 🆕", callback_data=f"cfg_mod_chanmgmt_{chat_id}")],
        [
            create_btn("📝 Permissions", callback_data=f"reg_cmd_perms_{chat_id}"),
            create_btn("🔍 Log Channel", callback_data=f"cfg_mod_logs_{chat_id}")
        ],
        [
            create_btn("◀️ Back", callback_data=f"cfg_page_1_{chat_id}"),
            create_btn("✅ Close", callback_data="cfg_close"),
            create_btn("🇬🇧 Lang", callback_data=f"cfg_mod_lang_{chat_id}")
        ]
    ]
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
            await chat.send_message(f"⚠️ {user.mention_html()}, please comply with the rule: <b>{reason}</b>.", parse_mode="HTML")
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
        logger.error(f"Punishment error: {e}")

# ----------------- UNIFIED CALLBACK QUERY ROUTER ----------------- #
async def unified_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat = query.message.chat
    user = query.from_user

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

    # /settings opening selector
    if data.startswith("set_open_"):
        mode = data.split("_")[2]
        cid = int(data.split("_")[3])
        chat_title = chat.title if chat.type != "private" else "Group"
        header_text = f"<b>SETTINGS</b>\nGroup: {chat_title}\n\n<i>Select one of the settings that you want to change.</i>"

        if mode == "here":
            await fast_edit(query, header_text, get_page1_settings_keyboard(cid))
        elif mode == "pm":
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
                start_btn = [[create_btn("🤖 Start Bot in PM", url=f"https://t.me/{bot_info.username}?start=settings_{cid}")]]
                await fast_edit(query, "⚠️ Pehle bot ko PM me /start karein.", InlineKeyboardMarkup(start_btn))
        return

    # Captcha User Action
    if data.startswith("cptsolve_"):
        parts = data.split("_")
        target_uid, cid = int(parts[1]), int(parts[2])
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

    # Extract Chat ID safely from callback data suffix
    match = re.search(r"(-?\d+)$", data)
    cid = int(match.group(1)) if match else chat.id

    if not await is_user_admin(cid, user.id, context):
        try:
            await query.answer("Sirf Admins settings badal sakte hain!", show_alert=True)
        except Exception:
            pass
        return

    cfg = get_config(cid)
    bot_info = await context.bot.get_me()

    # 1. Page Navigation
    if data.startswith("cfg_page_"):
        page = data.split("_")[2]
        chat_title = chat.title if chat.type != "private" else "Group"
        header_text = f"<b>SETTINGS</b>\nGroup: {chat_title}\n\n<i>Select one of the settings that you want to change.</i>"
        if page == "2":
            await fast_edit(query, header_text, get_page2_settings_keyboard(cid))
        else:
            await fast_edit(query, header_text, get_page1_settings_keyboard(cid))
        return

    # 2. 'SEE' PREVIEWS (WELCOME / GOODBYE / CAPTCHA)
    if data.startswith("wlc_see_text_"):
        w_text = format_template(cfg.get("welcome_text", "No text set."), user, chat, cfg)
        try:
            await chat.send_message(f"👁️ <b>Welcome Text Preview:</b>\n\n{w_text}", parse_mode="HTML")
            await query.answer("Preview sent!")
        except Exception:
            await chat.send_message(f"👁️ <b>Welcome Text Preview:</b>\n\n{w_text}")
            await query.answer("Preview sent.")
        return

    if data.startswith("wlc_see_media_"):
        m_id = cfg.get("welcome_media_id")
        m_type = cfg.get("welcome_media_type")
        if not m_id:
            await query.answer("No media configured.", show_alert=True)
            return
        try:
            if m_type == "photo":
                await chat.send_photo(photo=m_id, caption="📸 Welcome Media Preview")
            elif m_type == "video":
                await chat.send_video(video=m_id, caption="📸 Welcome Media Preview")
            elif m_type == "sticker":
                await chat.send_sticker(sticker=m_id)
            await query.answer("Media preview sent!")
        except Exception as e:
            await query.answer(f"Error: {e}", show_alert=True)
        return

    if data.startswith("wlc_see_buttons_"):
        kb = parse_custom_buttons(cfg.get("welcome_buttons_raw"), cid)
        if not kb:
            await query.answer("No buttons configured.", show_alert=True)
            return
        await chat.send_message("🔤 <b>Welcome Buttons Preview:</b>", reply_markup=kb, parse_mode="HTML")
        await query.answer("Buttons preview sent!")
        return

    if data.startswith("gby_see_text_"):
        g_text = format_template(cfg.get("goodbye_text", "No text set."), user, chat, cfg)
        try:
            await chat.send_message(f"👁️ <b>Goodbye Text Preview:</b>\n\n{g_text}", parse_mode="HTML")
            await query.answer("Preview sent!")
        except Exception:
            await chat.send_message(f"👁️ <b>Goodbye Text Preview:</b>\n\n{g_text}")
            await query.answer("Preview sent.")
        return

    if data.startswith("gby_see_media_"):
        m_id = cfg.get("goodbye_media_id")
        m_type = cfg.get("goodbye_media_type")
        if not m_id:
            await query.answer("No media configured.", show_alert=True)
            return
        try:
            if m_type == "photo":
                await chat.send_photo(photo=m_id, caption="📸 Goodbye Media Preview")
            elif m_type == "video":
                await chat.send_video(video=m_id, caption="📸 Goodbye Media Preview")
            elif m_type == "sticker":
                await chat.send_sticker(sticker=m_id)
            await query.answer("Media preview sent!")
        except Exception as e:
            await query.answer(f"Error: {e}", show_alert=True)
        return

    if data.startswith("gby_see_buttons_"):
        kb = parse_custom_buttons(cfg.get("goodbye_buttons_raw"), cid)
        if not kb:
            await query.answer("No buttons configured.", show_alert=True)
            return
        await chat.send_message("🔤 <b>Goodbye Buttons Preview:</b>", reply_markup=kb, parse_mode="HTML")
        await query.answer("Buttons preview sent!")
        return

    if data.startswith("cpt_see_text_"):
        c_text = cfg.get("captcha_custom_text") or "Click the button below to confirm you are human."
        await query.answer(f"Captcha Text:\n{c_text[:200]}", show_alert=True)
        return

    # 3. REGULATIONS HUB
    if data.startswith("cfg_view_reg_"):
        user_states.pop((cid, user.id), None)
        text = "📜 <b>Group's regulations</b>\nFrom this menu you can manage the group's regulations, that will be shown with the command /rules.\n\n<i>To edit who can use the /rules command, go to the \"Commands permissions\" section.</i>"
        kb = [
            [create_btn("✍️ Customize message", callback_data=f"reg_custom_msg_{cid}")],
            [create_btn("🕹 Commands Permissions", callback_data=f"reg_cmd_perms_{cid}")],
            [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("reg_custom_msg_"):
        text = "✍️ <b>Customize Regulations / Rules</b>\nConfigure message text, media attachment, and interactive buttons for /rules:"
        kb = [
            [create_btn("📝 Set Text Message", callback_data=f"reg_set_text_{cid}")],
            [create_btn("🖼️ Set Media (Photo/Video)", callback_data=f"reg_set_media_{cid}")],
            [create_btn("👉 Set Inline Buttons", callback_data=f"reg_set_buttons_{cid}")],
            [create_btn("👁️ Preview /rules", callback_data=f"reg_preview_{cid}")],
            [create_btn("⬅️ Back", callback_data=f"cfg_view_reg_{cid}")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("reg_set_text_"):
        user_states[(cid, user.id)] = "awaiting_reg_text"
        text = "👉 <b>Send now the message you want to set.</b>\n<i>You can send it already formatted or use HTML.</i>"
        kb = [
            [create_btn("🚫 Remove message", callback_data=f"reg_rem_text_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"cfg_view_reg_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("reg_rem_text_"):
        cfg["rules_text"] = "📜 Group Rules are not configured yet."
        save_config(cid, cfg)
        await fast_edit(query, "✍️ <b>Customize Regulations / Rules</b>", InlineKeyboardMarkup([[create_btn("⬅️ Back", callback_data=f"cfg_view_reg_{cid}")]]))
        return

    if data.startswith("reg_set_media_"):
        user_states[(cid, user.id)] = "awaiting_reg_media"
        text = "👉 <b>Send now the media (photos, videos, stickers...) you want to set.</b>"
        kb = [
            [create_btn("🚫 Remove media", callback_data=f"reg_rem_media_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"cfg_view_reg_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("reg_rem_media_"):
        cfg["rules_media_id"] = None
        cfg["rules_media_type"] = None
        save_config(cid, cfg)
        await fast_edit(query, "✍️ <b>Customize Regulations / Rules</b>", InlineKeyboardMarkup([[create_btn("⬅️ Back", callback_data=f"cfg_view_reg_{cid}")]]))
        return

    if data.startswith("reg_set_buttons_"):
        user_states[(cid, user.id)] = "awaiting_reg_buttons"
        text = "👉 <b>Set buttons:</b> Send structured as <code>Title - @username</code> or <code>Title - link.com</code>"
        kb = [
            [create_btn("🚫 Remove Keyboard", callback_data=f"reg_rem_buttons_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"cfg_view_reg_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("reg_rem_buttons_"):
        cfg["rules_buttons_raw"] = None
        save_config(cid, cfg)
        await fast_edit(query, "✍️ <b>Customize Regulations / Rules</b>", InlineKeyboardMarkup([[create_btn("⬅️ Back", callback_data=f"cfg_view_reg_{cid}")]]))
        return

    if data.startswith("reg_preview_"):
        await send_custom_bundle(chat, user, cfg, mode="rules", is_preview=True)
        await query.answer("Preview sent!")
        return

    if data.startswith("reg_cmd_perms_"):
        cmds = [("staff", "/staff"), ("rules", "/rules"), ("me", "/me"), ("translate", "/translate"), ("link", "/link")]
        modes = [("nobody", "✖️"), ("staff", "👮🏻"), ("everyone", "👥"), ("private", "🤖")]
        keyboard = []
        for cmd_key, label in cmds:
            row = [create_btn(label, callback_data=f"cmdlbl_{cmd_key}", style="primary")]
            cur_perm = cfg.get(f"perm_{cmd_key}", "everyone")
            for mode_key, icon in modes:
                style = "success" if cur_perm == mode_key else None
                row.append(create_btn(icon, callback_data=f"permset_{cmd_key}_{mode_key}_{cid}", style=style))
            keyboard.append(row)
        keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_view_reg_{cid}")])
        text = "🕹 <b>Commands Permissions</b>\nConfigure usage permissions for commands."
        await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("permset_"):
        parts = data.split("_")
        cmd_key, mode_key = parts[1], parts[2]
        cfg[f"perm_{cmd_key}"] = mode_key
        save_config(cid, cfg)
        cmds = [("staff", "/staff"), ("rules", "/rules"), ("me", "/me"), ("translate", "/translate"), ("link", "/link")]
        modes = [("nobody", "✖️"), ("staff", "👮🏻"), ("everyone", "👥"), ("private", "🤖")]
        keyboard = []
        for ck, label in cmds:
            row = [create_btn(label, callback_data=f"cmdlbl_{ck}", style="primary")]
            cur_perm = cfg.get(f"perm_{ck}", "everyone")
            for mk, icon in modes:
                style = "success" if cur_perm == mk else None
                row.append(create_btn(icon, callback_data=f"permset_{ck}_{mk}_{cid}", style=style))
            keyboard.append(row)
        keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_view_reg_{cid}")])
        await fast_edit(query, "🕹 <b>Commands Permissions</b>", InlineKeyboardMarkup(keyboard))
        return

    # 4. ANTI-SPAM MODULE
    if data.startswith("aspam_main_"):
        text = "✉️ <b>Anti-Spam</b>\nProtect your group from unnecessary links, forwards, and quotes."
        kb = [
            [create_btn("📘 Telegram links", callback_data=f"aspam_tglinks_{cid}")],
            [create_btn("📩 Forwarding", callback_data=f"aspam_fwd_{cid}"), create_btn("💭 Quote", callback_data=f"aspam_quote_{cid}")],
            [create_btn("🔗 Total links block", callback_data=f"aspam_totallinks_{cid}")],
            [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("aspam_totallinks_"):
        r1, r2 = make_penalty_buttons("astot_", cfg.get("totallinks_penalty", "Off"), cid)
        del_icon = "✔️" if cfg["totallinks_delete"] else "✖️"
        kb = [
            r1, r2,
            [create_btn(f"🗑 Delete Messages {del_icon}", callback_data=f"astottog_del_{cid}")],
            [create_btn("⬅️ Back", callback_data=f"aspam_main_{cid}"), create_btn("☀️ Exceptions", callback_data=f"asexc_main_{cid}")]
        ]
        text = f"🔗 <b>TOTAL LINKS BLOCK</b>\n<b>Penalty:</b> {cfg.get('totallinks_penalty')}\n<b>Deletion:</b> {del_icon}"
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("astot_pen_"):
        pen = data.split("_")[2]
        cfg["totallinks_penalty"] = pen
        save_config(cid, cfg)
        r1, r2 = make_penalty_buttons("astot_", pen, cid)
        del_icon = "✔️" if cfg["totallinks_delete"] else "✖️"
        kb = [r1, r2, [create_btn(f"🗑 Delete Messages {del_icon}", callback_data=f"astottog_del_{cid}")], [create_btn("⬅️ Back", callback_data=f"aspam_main_{cid}"), create_btn("☀️ Exceptions", callback_data=f"asexc_main_{cid}")]]
        await fast_edit(query, f"🔗 <b>TOTAL LINKS BLOCK</b>\n<b>Penalty:</b> {pen}", InlineKeyboardMarkup(kb))
        return

    if data.startswith("astottog_del_"):
        cfg["totallinks_delete"] = not cfg.get("totallinks_delete", False)
        save_config(cid, cfg)
        r1, r2 = make_penalty_buttons("astot_", cfg.get("totallinks_penalty", "Off"), cid)
        del_icon = "✔️" if cfg["totallinks_delete"] else "✖️"
        kb = [r1, r2, [create_btn(f"🗑 Delete Messages {del_icon}", callback_data=f"astottog_del_{cid}")], [create_btn("⬅️ Back", callback_data=f"aspam_main_{cid}"), create_btn("☀️ Exceptions", callback_data=f"asexc_main_{cid}")]]
        await fast_edit(query, f"🔗 <b>TOTAL LINKS BLOCK</b>", InlineKeyboardMarkup(kb))
        return

    if data.startswith("aspam_tglinks_"):
        r1, r2 = make_penalty_buttons("astg_", cfg.get("tglinks_penalty", "Off"), cid)
        del_icon = "Yes ✔️" if cfg.get("tglinks_delete") else "No ✖️"
        user_status = "✔️" if cfg.get("spam_usernames") else "✖️"
        bot_status = "✔️" if cfg.get("spam_bots") else "✖️"
        kb = [
            r1, r2,
            [create_btn(f"🗑 Delete Messages {del_icon}", callback_data=f"astgtog_del_{cid}")],
            [create_btn(f"🎯 Username Antispam {user_status}", callback_data=f"astgtog_user_{cid}")],
            [create_btn(f"🤖 Bots Antispam {bot_status}", callback_data=f"astgtog_bot_{cid}")],
            [create_btn("⬅️ Back", callback_data=f"aspam_main_{cid}"), create_btn("☀️ Exceptions", callback_data=f"asexc_main_{cid}")]
        ]
        await fast_edit(query, f"📘 <b>Telegram links</b>\n<b>Penalty:</b> {cfg.get('tglinks_penalty')}", InlineKeyboardMarkup(kb))
        return

    if data.startswith("astg_pen_"):
        pen = data.split("_")[2]
        cfg["tglinks_penalty"] = pen
        save_config(cid, cfg)
        r1, r2 = make_penalty_buttons("astg_", pen, cid)
        del_icon = "Yes ✔️" if cfg.get("tglinks_delete") else "No ✖️"
        kb = [r1, r2, [create_btn(f"🗑 Delete Messages {del_icon}", callback_data=f"astgtog_del_{cid}")], [create_btn("⬅️ Back", callback_data=f"aspam_main_{cid}"), create_btn("☀️ Exceptions", callback_data=f"asexc_main_{cid}")]]
        await fast_edit(query, f"📘 <b>Telegram links</b>\n<b>Penalty:</b> {pen}", InlineKeyboardMarkup(kb))
        return

    if data.startswith("astgtog_"):
        action = data.split("_")[1]
        if action == "del":
            cfg["tglinks_delete"] = not cfg.get("tglinks_delete", False)
        elif action == "user":
            cfg["spam_usernames"] = not cfg.get("spam_usernames", False)
        elif action == "bot":
            cfg["spam_bots"] = not cfg.get("spam_bots", False)
        save_config(cid, cfg)
        return await unified_callback_handler(update, context)

    # Forwarding & Quote Hub
    if data.startswith("aspam_fwd_") or data.startswith("asf") or data.startswith("aspam_quote_") or data.startswith("asq"):
        is_quote = "quote" in data or data.startswith("asq")
        prefix = "asq" if is_quote else "asf"
        mode = "quote" if is_quote else "fwd"

        if data.startswith(f"{prefix}tar_"):
            cfg[f"{mode}_target"] = data.split("_")[1]
        elif data.startswith(f"{prefix}_pen_"):
            target = cfg.get(f"{mode}_target", "groups")
            cfg[f"{mode}_{target}_penalty"] = data.split("_")[2]
        elif data.startswith(f"{prefix}tog_del_"):
            cfg[f"{mode}_delete"] = not cfg.get(f"{mode}_delete", False)
        save_config(cid, cfg)

        target = cfg.get(f"{mode}_target", "groups")
        current_penalty = cfg.get(f"{mode}_{target}_penalty", "Off")
        del_icon = "✔️" if cfg.get(f"{mode}_delete") else "✖️"
        row1, row2 = make_penalty_buttons(f"{prefix}_", current_penalty, cid)

        def tab(label, key):
            is_active = (target == key)
            lbl = f"» {label} «" if is_active else label
            return create_btn(lbl, callback_data=f"{prefix}tar_{key}_{cid}", style="primary" if is_active else None)

        kb = [
            [tab("📣 Channels", "channels"), tab("👥 Groups", "groups")],
            [tab("👤 Users", "users"), tab("🤖 Bots", "bots")],
            [create_btn("➖➖➖➖➖➖➖➖", callback_data="none")],
            row1, row2,
            [create_btn(f"🗑 Delete Messages {del_icon}", callback_data=f"{prefix}tog_del_{cid}")],
            [create_btn("⬅️ Back", callback_data=f"aspam_main_{cid}"), create_btn("☀️ Exceptions", callback_data=f"asexc_main_{cid}")]
        ]
        title = "💭 <b>Quote</b>" if is_quote else "📩 <b>Forwarding</b>"
        await fast_edit(query, title, InlineKeyboardMarkup(kb))
        return

    # Exceptions & Whitelist
    if data.startswith("asexc_"):
        action = data.split("_")[1]
        if action == "main":
            text = (
                "☀️ <b>Antispam Exception</b>\n"
                "Manage the Telegram's links/usernames of groups and channels that will not be treated as spam."
            )
            kb = [
                [create_btn("🔤 Show Whitelist", callback_data=f"asexc_show_{cid}")],
                [create_btn("➕ Add", callback_data=f"asexc_add_{cid}"), create_btn("➖ Remove", callback_data=f"asexc_rem_{cid}")],
                [create_btn("🌐 Global Whitelist", callback_data=f"asexc_globalmenu_{cid}")],
                [create_btn("⬅️ Back", callback_data=f"aspam_main_{cid}")]
            ]
            await fast_edit(query, text, InlineKeyboardMarkup(kb))
        elif action == "show":
            wl = get_whitelist(cid)
            items = "\n".join([f"• <code>{x}</code>" for x in sorted(wl)]) if wl else "The whitelist is currently empty."
            kb = [[create_btn("⬅️ Back", callback_data=f"asexc_main_{cid}")]]
            await fast_edit(query, f"🔤 <b>Links Block Whitelist ({len(wl)} items):</b>\n\n{items}", InlineKeyboardMarkup(kb))
        elif action == "add":
            user_states[(cid, user.id)] = "awaiting_whitelist_add"
            text = f"Ok {user.mention_html()}, now send one or more links to add to Whitelist."
            kb = [[create_btn("❌ Cancel", callback_data=f"asexc_main_{cid}", style="danger")]]
            await fast_edit(query, text, InlineKeyboardMarkup(kb))
        elif action == "rem":
            user_states[(cid, user.id)] = "awaiting_whitelist_remove"
            text = f"Ok {user.mention_html()}, now send one or more links to remove from Whitelist."
            kb = [[create_btn("❌ Cancel", callback_data=f"asexc_main_{cid}", style="danger")]]
            await fast_edit(query, text, InlineKeyboardMarkup(kb))
        elif action == "globalmenu":
            is_active = cfg.get("global_whitelist_active", True)
            status_text = "Active" if is_active else "Inactive"
            text = f"<b>Global Whitelist:</b>\nOfficial verified channels and groups ignored by spam detection.\n\n<b>Status:</b> {status_text}"
            kb = [
                [create_btn("✔ Turn on", callback_data=f"asexc_glbtoggle_on_{cid}", style="success" if is_active else None),
                 create_btn("✖ Turn off", callback_data=f"asexc_glbtoggle_off_{cid}", style="danger" if not is_active else None)],
                [create_btn("📖 Global Whitelist ↗", callback_data=f"asexc_viewglobal_{cid}")],
                [create_btn("⬅️ Back", callback_data=f"asexc_main_{cid}")]
            ]
            await fast_edit(query, text, InlineKeyboardMarkup(kb))
        elif action == "glbtoggle":
            sub_action = data.split("_")[2]
            cfg["global_whitelist_active"] = (sub_action == "on")
            save_config(cid, cfg)
            return await unified_callback_handler(update, context)
        elif action == "viewglobal":
            items = "\n".join([f"• <code>{x}</code>" for x in sorted(GLOBAL_WHITELIST_ITEMS)])
            kb = [[create_btn("⬅️ Back", callback_data=f"asexc_globalmenu_{cid}")]]
            await fast_edit(query, f"📖 <b>Global Whitelist ({len(GLOBAL_WHITELIST_ITEMS)} items):</b>\n\n{items}", InlineKeyboardMarkup(kb))
        return

    # 5. WELCOME
    if data.startswith("cfg_view_welcome_"):
        user_states.pop((cid, user.id), None)
        is_active = cfg.get("welcome_active", False)
        mode_desc = "Send the welcome message at every join" if cfg.get("welcome_mode") == "always" else "Send only at first join"
        text = f"💬 <b>Welcome Message</b>\n\n<b>Status:</b> {'Active ✅' if is_active else 'Off ❌'}\n<b>Mode:</b> {mode_desc}"
        del_icon = "✔️" if cfg.get("welcome_delete_last") else "✖️"
        kb = [
            [create_btn("✖️ Turn off", callback_data=f"wlc_toggle_off_{cid}", style="danger" if not is_active else None),
             create_btn("✔️ Turn on", callback_data=f"wlc_toggle_on_{cid}", style="success" if is_active else None)],
            [create_btn("✍️ Customize message", callback_data=f"wlc_custom_{cid}")],
            [create_btn("🔔 Always send", callback_data=f"wlc_mode_always_{cid}", style="primary" if cfg.get("welcome_mode")=="always" else None),
             create_btn("1️⃣ Send 1st join", callback_data=f"wlc_mode_first_{cid}", style="primary" if cfg.get("welcome_mode")=="first" else None)],
            [create_btn(f"♻️ Delete last message {del_icon}", callback_data=f"wlc_tog_dellast_{cid}")],
            [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("wlc_toggle_") or data.startswith("wlc_mode_") or data.startswith("wlc_tog_dellast_"):
        if "toggle_on" in data:
            cfg["welcome_active"] = True
        elif "toggle_off" in data:
            cfg["welcome_active"] = False
        elif "mode_always" in data:
            cfg["welcome_mode"] = "always"
        elif "mode_first" in data:
            cfg["welcome_mode"] = "first"
        elif "tog_dellast" in data:
            cfg["welcome_delete_last"] = not cfg.get("welcome_delete_last", False)
        save_config(cid, cfg)
        return await unified_callback_handler(update, context)

    if data.startswith("wlc_custom_"):
        has_text = "✅" if cfg.get("welcome_text") else "❌"
        has_media = "✅" if cfg.get("welcome_media_id") else "❌"
        has_buttons = "✅" if cfg.get("welcome_buttons_raw") else "❌"
        text = f"💬 <b>Welcome Message</b>\n\n📄 Text {has_text}\n📸 Media {has_media}\n🔤 Url Buttons {has_buttons}\n\n👉 Use the buttons below to choose what you want to set"
        kb = [
            [create_btn("📄 Text", callback_data=f"wlc_set_text_{cid}"), create_btn("👀 See", callback_data=f"wlc_see_text_{cid}")],
            [create_btn("📸 Media", callback_data=f"wlc_set_media_{cid}"), create_btn("👀 See", callback_data=f"wlc_see_media_{cid}")],
            [create_btn("🔤 Url Buttons", callback_data=f"wlc_set_buttons_{cid}"), create_btn("👀 See", callback_data=f"wlc_see_buttons_{cid}")],
            [create_btn("👀 Full preview", callback_data=f"wlc_full_preview_{cid}")],
            [create_btn("📁 Select a Topic 🆕", callback_data=f"wlc_topic_info_{cid}")],
            [create_btn("⬅️ Back", callback_data=f"cfg_view_welcome_{cid}")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("wlc_set_text_"):
        user_states[(cid, user.id)] = "awaiting_wlc_text"
        text = f"{user.mention_html()}, send now the message you want to set!"
        kb = [[create_btn("❌ Cancel", callback_data=f"wlc_custom_{cid}", style="danger")]]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("wlc_set_buttons_"):
        user_states[(cid, user.id)] = "awaiting_wlc_buttons"
        text = "👉 <b>Set buttons:</b> Send structured as <code>Title - @username</code>"
        kb = [[create_btn("❌ Cancel", callback_data=f"wlc_custom_{cid}", style="danger")]]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("wlc_full_preview_"):
        await send_custom_bundle(chat, user, cfg, mode="welcome", is_preview=True)
        await query.answer("Full preview sent!")
        return

    # 6. ANTI-FLOOD MODULE
    if data.startswith("cfg_view_flood_"):
        p = cfg.get("flood_penalty", "Off")
        text = (
            "🗣 <b>Antiflood</b>\n"
            f"Triggered when {cfg.get('flood_messages', 5)} messages are sent within {cfg.get('flood_seconds', 3)}s.\n\n"
            f"<b>Punishment:</b> {p}"
        )
        del_icon = "✔️" if cfg.get("flood_delete", True) else "✖️"
        r1, r2 = make_penalty_buttons("fl", p, cid)
        kb = [
            [create_btn("📄 Messages", callback_data=f"flgrid_msg_{cid}"), create_btn("⏰ Time", callback_data=f"flgrid_time_{cid}")],
            r1, r2,
            [create_btn(f"🗑 Delete Messages {del_icon}", callback_data=f"fltog_del_{cid}")]
        ]
        if p in ["Mute", "Ban", "Warn"]:
            kb.append([create_btn(f"⏰ Set {p.lower()} duration", callback_data=f"flset_dur_{p}_{cid}")])
        kb.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")])
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("flgrid_"):
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
        await fast_edit(query, f"Select amount:", InlineKeyboardMarkup(kb))
        return

    if data.startswith("flval_"):
        mode = data.split("_")[1]
        val = int(data.split("_")[2])
        if mode == "msg":
            cfg["flood_messages"] = val
        else:
            cfg["flood_seconds"] = val
        save_config(cid, cfg)
        return await unified_callback_handler(update, context)

    if data.startswith("flpen_"):
        cfg["flood_penalty"] = data.split("_")[1]
        save_config(cid, cfg)
        return await unified_callback_handler(update, context)

    if data.startswith("fltog_del_"):
        cfg["flood_delete"] = not cfg.get("flood_delete", True)
        save_config(cid, cfg)
        return await unified_callback_handler(update, context)

    if data.startswith("flset_dur_"):
        ptype = data.split("_")[2]
        user_states[(cid, user.id)] = f"awaiting_flood_dur_{ptype}"
        text = f"Send now the duration for {ptype} (e.g. <code>30 minutes</code>, <code>2 hours</code>):"
        kb = [[create_btn("❌ Cancel", callback_data=f"cfg_view_flood_{cid}", style="danger")]]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    # 7. GOODBYE
    if data.startswith("cfg_view_goodbye_") or data.startswith("gby_toggle_") or data.startswith("gby_tog_pm_") or data.startswith("gby_tog_dellast_"):
        if "toggle_on" in data:
            cfg["goodbye_active"] = True
        elif "toggle_off" in data:
            cfg["goodbye_active"] = False
        elif "tog_pm" in data:
            cfg["goodbye_in_pm"] = not cfg.get("goodbye_in_pm", False)
        elif "tog_dellast" in data:
            cfg["goodbye_delete_last"] = not cfg.get("goodbye_delete_last", False)
        save_config(cid, cfg)

        is_active = cfg.get("goodbye_active", False)
        in_pm = cfg.get("goodbye_in_pm", False)
        pm_icon = "✔️" if in_pm else "✖️"
        del_icon = "✔️" if cfg.get("goodbye_delete_last") else "✖️"
        text = f"👋 <b>Goodbye</b>\n\n<b>Status:</b> {'Active ✅' if is_active else 'Off ❌'}"
        if in_pm:
            text += f"\n⚠️ Sent only in PM."
        kb = [
            [create_btn("✖️ Turn off", callback_data=f"gby_toggle_off_{cid}", style="danger" if not is_active else None),
             create_btn("✔️ Turn on", callback_data=f"gby_toggle_on_{cid}", style="success" if is_active else None)],
            [create_btn("✍️ Customize message", callback_data=f"gby_custom_{cid}")],
            [create_btn(f"💌 Send in private chat {pm_icon}", callback_data=f"gby_tog_pm_{cid}")]
        ]
        if not in_pm:
            kb.append([create_btn(f"♻️ Delete last message {del_icon}", callback_data=f"gby_tog_dellast_{cid}")])
        kb.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")])
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("gby_custom_"):
        has_text = "✅" if cfg.get("goodbye_text") else "❌"
        has_media = "✅" if cfg.get("goodbye_media_id") else "❌"
        has_buttons = "✅" if cfg.get("goodbye_buttons_raw") else "❌"
        text = f"👋 <b>Goodbye</b>\n\n📄 Text {has_text}\n📸 Media {has_media}\n🔤 Url Buttons {has_buttons}"
        kb = [
            [create_btn("📄 Text", callback_data=f"gby_set_text_{cid}"), create_btn("👀 See", callback_data=f"gby_see_text_{cid}")],
            [create_btn("📸 Media", callback_data=f"gby_set_media_{cid}"), create_btn("👀 See", callback_data=f"gby_see_media_{cid}")],
            [create_btn("🔤 Url Buttons", callback_data=f"gby_set_buttons_{cid}"), create_btn("👀 See", callback_data=f"gby_see_buttons_{cid}")],
            [create_btn("👀 Full preview", callback_data=f"gby_full_preview_{cid}")],
            [create_btn("⬅️ Back", callback_data=f"cfg_view_goodbye_{cid}")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("gby_set_text_"):
        user_states[(cid, user.id)] = "awaiting_gby_text"
        text = f"{user.mention_html()}, send now the goodbye message!"
        kb = [[create_btn("❌ Cancel", callback_data=f"gby_custom_{cid}", style="danger")]]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("gby_full_preview_"):
        await send_custom_bundle(chat, user, cfg, mode="goodbye", is_preview=True)
        await query.answer("Full preview sent!")
        return

    # 8. ALPHABETS
    if data.startswith("cfg_view_alphabets_") or data.startswith("alptab_") or data.startswith("alppen_") or data.startswith("alptog_del_"):
        if data.startswith("alptab_"):
            cfg["alpha_active_tab"] = data.split("_")[1]
        elif data.startswith("alppen_"):
            cfg.setdefault("alpha_penalties", {})[cfg.get("alpha_active_tab", "chinese")] = data.split("_")[1]
        elif data.startswith("alptog_del_"):
            cur_tab = cfg.get("alpha_active_tab", "chinese")
            cfg.setdefault("alpha_deletes", {})[cur_tab] = not cfg.get("alpha_deletes", {}).get(cur_tab, False)
        save_config(cid, cfg)

        cur_tab = cfg.get("alpha_active_tab", "chinese")
        cur_pen = cfg.get("alpha_penalties", {}).get(cur_tab, "Off")
        cur_del = cfg.get("alpha_deletes", {}).get(cur_tab, False)

        lines = ["🕉 <b>Alphabets</b>\nSelect punishment for users who send messages in certain alphabets.\n"]
        for key, d in ALPHABET_DATA.items():
            pen = cfg.get("alpha_penalties", {}).get(key, "Off")
            lines.append(f"{d['icon']} <b>{d['name']}</b>: {pen}")

        kb = []
        lang_keys = list(ALPHABET_DATA.keys())
        for i in range(0, len(lang_keys), 2):
            row = []
            for k in lang_keys[i:i+2]:
                d = ALPHABET_DATA[k]
                lbl = f"» {d['icon']} {d['name'].upper()} «" if cur_tab == k else f"{d['icon']} {d['name'].upper()}"
                row.append(create_btn(lbl, callback_data=f"alptab_{k}_{cid}", style="primary" if cur_tab==k else None))
            kb.append(row)
        kb.append([create_btn("➖➖➖➖➖➖➖➖", callback_data="none")])
        r1, r2 = make_penalty_buttons("alp", cur_pen, cid)
        kb.extend([r1, r2])
        kb.append([create_btn(f"🗑 Delete Messages {'✔️' if cur_del else '✖️'}", callback_data=f"alptog_del_{cid}")])
        kb.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")])
        await fast_edit(query, "\n".join(lines), InlineKeyboardMarkup(kb))
        return

    # 9. CAPTCHA
    if data.startswith("cfg_view_captcha_") or data.startswith("cpt_toggle_") or data.startswith("cpt_switch_mode_") or data.startswith("cpt_tab_"):
        if "toggle_on" in data:
            cfg["captcha_active"] = True
        elif "toggle_off" in data:
            cfg["captcha_active"] = False
        elif "switch_mode" in data:
            cfg["captcha_mode"] = "regulation" if cfg.get("captcha_mode") == "button" else "button"
        elif data.startswith("cpt_tab_"):
            t_name = data.split("_")[2]
            cfg["captcha_tab"] = None if cfg.get("captcha_tab") == t_name else t_name
        save_config(cid, cfg)

        is_active = cfg.get("captcha_active", False)
        base = "🧠 <b>Captcha</b>\nBy activating the captcha, when a user enters the group he will not be able to send messages until he has confirmed that he is not a robot.\n\n"
        if not is_active:
            text = base + "<b>Status:</b> Off ❌"
            kb = [
                [create_btn("✅ Activate", callback_data=f"cpt_toggle_on_{cid}", style="success")],
                [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]
            ]
        else:
            mode = cfg.get("captcha_mode", "button")
            text = (
                base + f"<b>Status:</b> Active ✅\n"
                f"🕒 <b>Time:</b> {cfg.get('captcha_time_label', '3 Minutes')}\n"
                f"⛔️ <b>Penalty:</b> {cfg.get('captcha_penalty', 'Mute')}\n"
                f"🗂 <b>Mode:</b> {mode.capitalize()}\n"
                f"🗑 <b>Delete service message:</b> {'Active' if cfg.get('captcha_delete_service') else 'Off'}"
            )
            tab = cfg.get("captcha_tab")
            del_icon = "✔️" if cfg.get("captcha_delete_service") else "✖️"
            kb = [
                [create_btn("❌ Turn off ❌", callback_data=f"cpt_toggle_off_{cid}", style="danger")],
                [create_btn("📦 Mode 📦", callback_data=f"cpt_switch_mode_{cid}")]
            ]
            if tab == "time":
                kb.append([create_btn("» 🕒 Time «", callback_data=f"cpt_tab_time_{cid}", style="primary")])
                kb.append([create_btn("1 Min", callback_data=f"cpt_set_t_60_{cid}"), create_btn("3 Min", callback_data=f"cpt_set_t_180_{cid}"), create_btn("5 Min", callback_data=f"cpt_set_t_300_{cid}")])
            else:
                kb.append([create_btn("🕒 Time", callback_data=f"cpt_tab_time_{cid}")])

            if tab == "penalty":
                kb.append([create_btn("» ⛔️ Penalty «", callback_data=f"cpt_tab_penalty_{cid}", style="primary")])
                kb.append([create_btn("Mute", callback_data=f"cpt_set_p_Mute_{cid}"), create_btn("Ban", callback_data=f"cpt_set_p_Ban_{cid}")])
            else:
                kb.append([create_btn("⛔️ Penalty", callback_data=f"cpt_tab_penalty_{cid}")])

            kb.append([create_btn(f"🗑 Delete service message {del_icon}", callback_data=f"cpt_tog_delsvc_{cid}")])
            kb.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")])
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("cpt_set_t_"):
        sec = int(data.split("_")[3])
        cfg["captcha_time_val"] = sec
        cfg["captcha_time_label"] = f"{sec // 60} Minutes"
        save_config(cid, cfg)
        await query.answer("Time updated!")
        return

    if data.startswith("cpt_set_p_"):
        cfg["captcha_penalty"] = data.split("_")[3]
        save_config(cid, cfg)
        await query.answer("Penalty updated!")
        return

    # 10. CHECKS & OBLIGATIONS
    if data.startswith("cfg_view_checks_") or data.startswith("chktab_") or data.startswith("chkset_pen_") or data.startswith("chktog_"):
        if data.startswith("chktab_main_"):
            cfg["checks_main_tab"] = data.split("_")[2]
            cfg["checks_sub_tab"] = None
        elif data.startswith("chktab_sub_"):
            s = data.split("_")[2]
            cfg["checks_sub_tab"] = None if cfg.get("checks_sub_tab") == s else s
        elif data.startswith("chkset_pen_"):
            cur_sub = cfg.get("checks_sub_tab")
            if cur_sub:
                cfg.setdefault("checks_penalties", {})[cur_sub] = data.split("_")[2]
        elif data.startswith("chktog_join_"):
            cfg["check_at_join"] = not cfg.get("check_at_join", True)
        elif data.startswith("chktog_del_"):
            cfg["checks_delete_messages"] = not cfg.get("checks_delete_messages", False)
        save_config(cid, cfg)

        main_tab = cfg.get("checks_main_tab", "obligations")
        sub_tab = cfg.get("checks_sub_tab")
        p = cfg.get("checks_penalties", {})
        text = (
            "<b>OBLIGATION OF...</b>\n"
            f" • Surname: {p.get('surname', 'Off')}\n • Username: {p.get('username', 'Off')}\n"
            f" • Profile picture: {p.get('pfp', 'Off')}\n\n"
            "<b>BLOCK...</b>\n"
            f" • Arabic name: {p.get('arabic', 'Off')}\n • Chinese name: {p.get('chinese', 'Off')}\n"
        )
        t_ob = "» OBLIGATIONS «" if main_tab == "obligations" else "OBLIGATIONS"
        t_nb = "» NAME BLOCKS «" if main_tab == "nameblocks" else "NAME BLOCKS"
        kb = [[create_btn(t_ob, callback_data=f"chktab_main_obligations_{cid}", style="primary" if main_tab=="obligations" else None),
               create_btn(t_nb, callback_data=f"chktab_main_nameblocks_{cid}", style="primary" if main_tab=="nameblocks" else None)]]

        items = [("surname", "🧑‍🤝‍🧑 Obligation Surname"), ("username", "🌐 Username Obligation"), ("pfp", "📸 Profile Picture Obligation")] if main_tab == "obligations" else [("arabic", "☪️ Arabic name block"), ("chinese", "🇨🇳 Chinese name block")]
        for k, lbl in items:
            is_active = (sub_tab == k)
            kb.append([create_btn(f"» {lbl} «" if is_active else lbl, callback_data=f"chktab_sub_{k}_{cid}", style="primary" if is_active else None)])
            if is_active:
                r1, r2 = make_penalty_buttons("chk", p.get(k, "Off"), cid)
                kb.extend([r1, r2])

        if sub_tab is None:
            kb.append([create_btn(f"🚪 Check at the join {'✔️' if cfg.get('check_at_join', True) else '✖️'}", callback_data=f"chktog_join_{cid}")])
            kb.append([create_btn(f"🗑 Delete Messages {'✔️' if cfg.get('checks_delete_messages', False) else '✖️'}", callback_data=f"chktog_del_{cid}")])

        kb.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")])
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

# ----------------- TEXT & MEDIA CAPTURE ----------------- #
async def interactive_state_processor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message or not update.message.from_user:
        return False

    chat_id = update.effective_chat.id
    user_id = update.message.from_user.id
    state_key = (chat_id, user_id)

    if state_key not in user_states:
        return False

    state = user_states.pop(state_key)
    cfg = get_config(chat_id)
    msg = update.message
    text = msg.text or msg.caption or ""

    if state == "awaiting_wlc_text":
        cfg["welcome_text"] = text
        save_config(chat_id, cfg)
        kb = [[create_btn("⬅️ Back", callback_data=f"wlc_custom_{chat_id}")]]
        await msg.reply_text("✅ <b>Message set.</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    elif state == "awaiting_reg_text":
        cfg["rules_text"] = text
        save_config(chat_id, cfg)
        kb = [[create_btn("⬅️ Back", callback_data=f"cfg_view_reg_{chat_id}")]]
        await msg.reply_text("✅ <b>Message set.</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    elif state == "awaiting_gby_text":
        cfg["goodbye_text"] = text
        save_config(chat_id, cfg)
        kb = [[create_btn("⬅️ Back", callback_data=f"gby_custom_{chat_id}")]]
        await msg.reply_text("✅ <b>Message set.</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    elif state.startswith("awaiting_flood_dur_"):
        ptype = state.split("_")[3]
        parsed_sec = parse_time_duration(text)
        cfg["flood_duration_sec"] = parsed_sec
        cfg["flood_duration_str"] = text.strip()
        save_config(chat_id, cfg)
        kb = [[create_btn("⬅️ Back to Antiflood", callback_data=f"cfg_view_flood_{chat_id}")]]
        await msg.reply_text(f"✅ <b>Antiflood {ptype} duration set to {text}!</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    return False

# ----------------- COMMANDS ----------------- #
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        target_cid = int(context.args[0].replace("settings_", "")) if context.args and context.args[0].startswith("settings_") else user.id
        header_text = "<b>SETTINGS</b>\n\n<i>Select one of the settings that you want to change.</i>"
        await update.message.reply_text(header_text, reply_markup=get_page1_settings_keyboard(target_cid), parse_mode="HTML")
        return

    if not await is_user_admin(chat.id, user.id, context):
        await update.message.reply_text("❌ Sirf Admins `/settings` open kar sakte hain.")
        return

    bot_info = await context.bot.get_me()
    keyboard = [
        [create_btn("👥 Open here", callback_data=f"set_open_here_{chat.id}")],
        [create_btn("👤 Open in Private Chat", url=f"https://t.me/{bot_info.username}?start=settings_{chat.id}")]
    ]
    await update.message.reply_text(
        "Where do you want to open the settings menu?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.effective_chat.type == "private":
        if context.args and context.args[0].startswith("settings_"):
            target_cid = int(context.args[0].replace("settings_", ""))
            header_text = "<b>SETTINGS</b>\n\n<i>Select one of the settings that you want to change.</i>"
            await update.message.reply_text(header_text, reply_markup=get_page1_settings_keyboard(target_cid), parse_mode="HTML")
            return

        keyboard = [[create_btn("➕ Add Me to Your Group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
        await update.message.reply_text("🛡 Group Security Bot active! Add to group and send `/settings`.", reply_markup=InlineKeyboardMarkup(keyboard))

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    cfg = get_config(chat.id)
    await send_custom_bundle(chat, update.effective_user, cfg, mode="rules")

async def staff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    try:
        admins = await context.bot.get_chat_administrators(chat.id)
        staff_text = "👮🏻 <b>Group Staff:</b>\n\n"
        for adm in admins:
            status = "👑 Creator" if adm.status == "creator" else "🛡 Admin"
            staff_text += f"• {adm.user.mention_html()} — <i>{status}</i>\n"
        await update.message.reply_text(staff_text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error getting staff list: {e}")

async def me_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    warns = get_user_warns(chat.id, user.id)
    info = f"👤 <b>Your Info:</b>\n• Name: {user.mention_html()}\n• ID: <code>{user.id}</code>\n• Warns: <b>{warns}</b>"
    await update.message.reply_text(info, parse_mode="HTML")

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

    if await interactive_state_processor(update, context):
        return

# ----------------- MAIN INITIALIZER ----------------- #
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("rules", rules_command))
    app.add_handler(CommandHandler("staff", staff_command))
    app.add_handler(CommandHandler("me", me_command))
    app.add_handler(CommandHandler("update", update_command))

    app.add_handler(CallbackQueryHandler(unified_callback_handler))

    app.add_handler(MessageHandler(filters.Regex(r"(?i)^pip3?\s+install\s+"), auto_pip_installer))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, security_moderator))

    print("🛡 Group Help Security Bot running smoothly with all buttons and descriptions intact...")
    app.run_polling()

if __name__ == "__main__":
    main()
