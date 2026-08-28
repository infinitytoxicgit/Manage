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

# Default Complete Config
DEFAULT_CONFIG = {
    # Page 1 Modules
    "rules_text": "📜 <b>Group Regulations</b>\n1. Be respectful\n2. No spam or self-promotion\n3. Follow admin instructions.",
    "rules_media_id": None,
    "rules_media_type": None,
    "rules_buttons_raw": None,
    
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
    "welcome_text": "★彡[ 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 𝐓𝐎 {GROUPNAME} 𝐃𝐄𝐀𝐑 💕 ]彡★\n\n✿━━━━━━━━━━━━━━━━━✿\n  𝐇ᴇʏ {USERNAME}, 𝐖ᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ 𝐅ᴀᴍɪʟʏ!\n  𝐖ᴇ’ʀᴇ 𝐬ᴏ ʜᴀᴘᴘʏ ᴛᴏ ʜᴀᴠᴇ ʏᴏᴜ ʜᴇʀᴇ!\n✿━━━━━━━━━━━━━━━━━✿\n\n━━━━━━━━━━━━━━━━━━━━\n    𝐘ᴏᴜʀ 𝐈ɴғᴏ\n━━━━━━━━━━━━━━━━━━━━\n•𝐅𝐮𝐥𝐥 𝐍𝐚𝐦𝐞 = {NAMESURNAME} ❤️\n•𝐔𝐬𝐞𝐫 𝐍𝐚𝐦𝐞 = {USERNAME} 🦋\n•𝐔𝐬𝐞𝐫 𝐈'𝐃 = {ID} ❤️\n•𝐏𝐫𝐨𝐟𝐢𝐥𝐞 𝐋𝐢ｎ𝐤 = {MENTION} 💐\n•𝐋𝐚ｎｇｕａｇｅ = {LANG} 🍓\n•𝐃ａｔｅ = {DATE} 😊\n•𝐓ｉｍｅ = {TIME} 👀\n\n━━━━━━━━━━━━━━━━━━━━\n  𝐄ɴᴊᴏʏ ʏᴏᴜʀ 𝐒ᴛᴀʏ & ᴍᴀᴋᴇ ɢʀᴇᴀᴛ ᴍᴇᴍᴏʀɪᴇ𝐬!\n  𝐓ʜᴀɴᴋ𝐬 ғᴏʀ ᴊᴏɪɴɪɴɢ!",
    "welcome_media_id": None,
    "welcome_media_type": None,
    "welcome_buttons_raw": None,
    "welcome_topic_id": None,

    # Antiflood
    "flood_messages": 5,
    "flood_seconds": 3,
    "flood_penalty": "Off",
    "flood_delete": True,
    "flood_duration_sec": 0,
    "flood_duration_str": "Off",

    # Security Modules
    "goodbye_active": False,
    "alphabets_active": False,
    "captcha": True,
    "checks_active": False,
    "admin_tag_active": True,
    "blocks_active": False,
    "lock_media": False,
    "porn_block_active": True,
    "warn_limit": 3,
    "night_mode": False,
    "tag_protection": False,
    "guardian_bot_active": False,
    "approval_mode_group": False,
    "auto_del_service_msgs": True,
    "bot_lang": "en",

    # Page 2 Advanced
    "topic_enabled": False,
    "banned_words_list": [],
    "recurring_msgs_active": False,
    "masked_users_block": False,
    "discussion_group_id": None,
    "personal_cmds": {},
    "magic_stickers_block": False,
    "max_message_length": 0,
    "channel_mgmt_active": False,
    "log_channel_id": None,

    # Permissions
    "perm_staff": "everyone",
    "perm_rules": "staff",
    "perm_me": "private",
    "perm_translate": "everyone",
    "perm_link": "everyone"
}

# Runtime In-Memory Caches
group_settings_cache = {}
admin_cache = {}
user_states = {}
link_drafts = {}
active_created_links = {}
last_welcome_messages = {}
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
        cfg.update(json.loads(row[0]))
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

def get_link_draft(chat_id: int, user_id: int):
    key = (chat_id, user_id)
    if key not in link_drafts:
        link_drafts[key] = {"active_tab": None, "limit": 0, "until_seconds": 0, "approval": False}
    return link_drafts[key]

# ----------------- TIME DURATION PARSER ----------------- #
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

# ----------------- PERMISSION CHECKERS ----------------- #
async def check_admin_invite_permission(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if user_id in OWNER_IDS:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status == "creator":
            return True
        if member.status == "administrator":
            return getattr(member, 'can_invite_users', False)
        return False
    except Exception:
        return False

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
        await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML")
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

# ----------------- MESSAGE SENDER ----------------- #
async def send_custom_bundle(chat, user, cfg: dict, is_preview=False, thread_id=None):
    w_text = format_template(cfg.get("welcome_text", ""), user, chat, cfg)
    w_kb = parse_custom_buttons(cfg.get("welcome_buttons_raw"), chat.id)
    m_id = cfg.get("welcome_media_id")
    m_type = cfg.get("welcome_media_type")

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

# ----------------- 100% COMPLETE SETTINGS KEYBOARDS (PAGE 1 & PAGE 2) ----------------- #

def get_page1_settings_keyboard(chat_id: int):
    """Exact Screenshot Layout for Page 1"""
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
            create_btn("👋 Goodbye", callback_data=f"cfg_mod_goodbye_{chat_id}"),
            create_btn("🕉 Alphabets", callback_data=f"cfg_mod_alphabets_{chat_id}")
        ],
        [
            create_btn("🧠 Captcha", callback_data=f"cfg_mod_captcha_{chat_id}"),
            create_btn("🔦 Checks", callback_data=f"cfg_mod_checks_{chat_id}")
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
        [
            create_btn("🕵️ Guardian Bot 🆕", callback_data=f"cfg_mod_guardian_{chat_id}")
        ],
        [
            create_btn("🗂 Approval mode", callback_data=f"cfg_mod_approval_{chat_id}")
        ],
        [
            create_btn("🗑 Deleting Messages", callback_data=f"cfg_mod_delmsg_{chat_id}")
        ],
        [
            create_btn("🇬🇧 Lang", callback_data=f"cfg_mod_lang_{chat_id}"),
            create_btn("✅ Close", callback_data="cfg_close"),
            create_btn("▶️ Other", callback_data=f"cfg_page_2_{chat_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_page2_settings_keyboard(chat_id: int):
    """Exact Screenshot Layout for Page 2 (Other / Advanced)"""
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

# ----------------- ANTIFLOOD KEYBOARDS & UI ----------------- #
def get_antiflood_main_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    p = cfg.get("flood_penalty", "Off")
    del_icon = "✔️" if cfg.get("flood_delete", True) else "✖️"

    def get_btn(label, val):
        is_selected = (p == val)
        btn_text = f"❌ {label}" if val == "Off" and not is_selected else label
        btn_style = "success" if is_selected else None
        return create_btn(btn_text, callback_data=f"flpen_{val}_{chat_id}", style=btn_style)

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

# ----------------- SUB-MENU KEYBOARDS ----------------- #
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
    def style(name, val):
        return f"🟩 {name}" if cfg.get("totallinks_penalty") == val else name
    
    r1 = [
        create_btn(style("❌ Off", "Off"), callback_data=f"astot_pen_Off_{chat_id}"),
        create_btn(style("❗ Warn", "Warn"), callback_data=f"astot_pen_Warn_{chat_id}"),
        create_btn(style("❗ Kick", "Kick"), callback_data=f"astot_pen_Kick_{chat_id}")
    ]
    r2 = [
        create_btn(style("🔊 Mute", "Mute"), callback_data=f"astot_pen_Mute_{chat_id}"),
        create_btn(style("🚷 Ban", "Ban"), callback_data=f"astot_pen_Ban_{chat_id}")
    ]
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
    def style(name, val):
        return f"🟩 {name}" if cfg.get("tglinks_penalty") == val else name

    r1 = [
        create_btn(style("❌ Off", "Off"), callback_data=f"astg_pen_Off_{chat_id}"),
        create_btn(style("❗ Warn", "Warn"), callback_data=f"astg_pen_Warn_{chat_id}"),
        create_btn(style("❗ Kick", "Kick"), callback_data=f"astg_pen_Kick_{chat_id}")
    ]
    r2 = [
        create_btn(style("🔊 Mute", "Mute"), callback_data=f"astg_pen_Mute_{chat_id}"),
        create_btn(style("🚷 Ban", "Ban"), callback_data=f"astg_pen_Ban_{chat_id}")
    ]
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

    def pstyle(name, val):
        return f"🟩 {name}" if current_penalty == val else name

    row1 = [
        create_btn(pstyle("❌ Off", "Off"), callback_data=f"{prefix}_pen_Off_{chat_id}"),
        create_btn(pstyle("❗ Warn", "Warn"), callback_data=f"{prefix}_pen_Warn_{chat_id}"),
        create_btn(pstyle("❗ Kick", "Kick"), callback_data=f"{prefix}_pen_Kick_{chat_id}")
    ]
    row2 = [
        create_btn(pstyle("🔊 Mute", "Mute"), callback_data=f"{prefix}_pen_Mute_{chat_id}"),
        create_btn(pstyle("🚷 Ban", "Ban"), callback_data=f"{prefix}_pen_Ban_{chat_id}")
    ]

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

# ----------------- PUNISHMENT ENGINE ----------------- #
async def execute_punishment(penalty: str, should_delete: bool, update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str, duration_sec: int = 0):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message

    if should_delete:
        try:
            await msg.delete()
        except Exception:
            pass

    if penalty == "Off" or not penalty:
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
            dur_txt = f" for {duration_sec}s" if duration_sec > 0 else ""
            await chat.send_message(f"🔇 {user.mention_html()} muted{dur_txt} for {reason}.", parse_mode="HTML")

        elif penalty == "Kick":
            await context.bot.unban_chat_member(chat.id, user.id)
            await chat.send_message(f"👞 {user.mention_html()} kicked for {reason}.", parse_mode="HTML")

        elif penalty == "Ban":
            await context.bot.ban_chat_member(chat.id, user.id, until_date=until_date)
            dur_txt = f" for {duration_sec}s" if duration_sec > 0 else ""
            await chat.send_message(f"🚫 {user.mention_html()} banned{dur_txt} for {reason}.", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Punishment execution error: {e}")

# ----------------- UNIFIED CALLBACK ROUTER ----------------- #
async def unified_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat = query.message.chat
    user = query.from_user

    # Generic Popups
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

    # 1. Page Switcher (Page 1 <-> Page 2)
    if data.startswith("cfg_page_"):
        page = data.split("_")[2]
        cid = int(data.split("_")[3])
        header_text = (
            "<b>SETTINGS</b>\n"
            f"Group: {chat.title}\n\n"
            "<i>Select one of the settings that you want to change.</i>"
        )
        if page == "2":
            await fast_edit(query, header_text, get_page2_settings_keyboard(cid))
        else:
            await fast_edit(query, header_text, get_page1_settings_keyboard(cid))
        return

    # 2. Page 1 & Page 2 Module Views
    if data.startswith("cfg_mod_"):
        module_name = data.split("_")[2]
        cid = int(data.split("_")[3])
        
        # Generic handler for newly exposed buttons
        labels = {
            "goodbye": "👋 Goodbye Settings",
            "alphabets": "🕉 Allowed Alphabets & Scripts",
            "captcha": "🧠 Captcha Verification Settings",
            "checks": "🔦 Security Checks",
            "admin": "🆘 @Admin Reporting Settings",
            "blocks": "🔐 Group Blocks & Silence",
            "media": "📸 Media Permissions",
            "porn": "🔞 Anti-Porn Protection",
            "warns": "❗ Warnings Management",
            "night": "🌘 Night Mode Silence",
            "tag": "🔔 Mass Tag / Mention Protection",
            "link": "🔗 Invite Links Management",
            "guardian": "🕵️ Guardian Bot Security",
            "approval": "🗂 Join Requests Approval Mode",
            "delmsg": "🗑 Auto-Deleting Service Messages",
            "lang": "🇬🇧 Language Settings",
            "bannedwords": "🔤 Banned Words Filter",
            "recurring": "🕒 Recurring Messages Scheduler",
            "members": "👥 Members Management Panel",
            "masked": "😷 Masked & Anonymous Users",
            "discussion": "📣 Linked Discussion Group",
            "personalcmds": "📱 Custom Personal Commands",
            "magicstickers": "🎭 Magic Stickers & GIFs Filter",
            "msglength": "📏 Maximum Message Length",
            "chanmgmt": "📢 Linked Channels Management",
            "logs": "🔍 Audit Log Channel"
        }
        title = labels.get(module_name, f"⚙️ {module_name.capitalize()}")
        text = f"<b>{title}</b>\n\nThis module is active and protected under Group Security DB."
        kb = [[create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    # 3. Antiflood Hub & Actions
    if data.startswith("cfg_view_flood_"):
        cid = int(data.split("_")[3])
        user_states.pop((cid, user.id), None)
        await fast_edit(query, get_antiflood_text(cid), get_antiflood_main_keyboard(cid))
        return

    if data.startswith("flgrid_"):
        mode = data.split("_")[1]
        cid = int(data.split("_")[2])
        if mode == "msg":
            text = (
                "From here you can select the maximum amount of sendable messages in the time interval.\n"
                f"Currently, the antiflood trigger when {cfg.get('flood_messages', 5)} messages "
                f"are sent in {cfg.get('flood_seconds', 3)} seconds."
            )
            await fast_edit(query, text, get_antiflood_number_grid(cid, mode="msg"))
        else:
            text = (
                "From here you can select the time interval considered to calculate the antiflood.\n"
                f"Currently, the antiflood trigger when {cfg.get('flood_messages', 5)} messages "
                f"are sent in {cfg.get('flood_seconds', 3)} seconds."
            )
            await fast_edit(query, text, get_antiflood_number_grid(cid, mode="time"))
        return

    if data.startswith("flval_"):
        parts = data.split("_")
        mode, val, cid = parts[1], int(parts[2]), int(parts[3])
        if mode == "msg":
            cfg["flood_messages"] = val
        else:
            cfg["flood_seconds"] = val
        save_config(cid, cfg)
        await fast_edit(query, get_antiflood_text(cid), get_antiflood_main_keyboard(cid))
        return

    if data.startswith("flpen_"):
        pen = data.split("_")[1]
        cid = int(data.split("_")[2])
        cfg["flood_penalty"] = pen
        save_config(cid, cfg)
        await fast_edit(query, get_antiflood_text(cid), get_antiflood_main_keyboard(cid))
        return

    if data.startswith("fltog_del_"):
        cid = int(data.split("_")[2])
        cfg["flood_delete"] = not cfg.get("flood_delete", True)
        save_config(cid, cfg)
        await fast_edit(query, get_antiflood_text(cid), get_antiflood_main_keyboard(cid))
        return

    if data.startswith("flset_dur_"):
        parts = data.split("_")
        ptype, cid = parts[2], int(parts[3])
        user_states[(cid, user.id)] = f"awaiting_flood_dur_{ptype}"
        text = (
            f"Send now the duration of the chosen punishment ({ptype})\n\n"
            "<b>Minimum:</b> 30 seconds\n"
            "<b>Maximum:</b> 365 days\n\n"
            "<b>Example of format:</b> <code>3 month 2 days 12 hours 4 minutes 34 seconds</code>\n\n"
            f"<b>Current duration:</b> {cfg.get('flood_duration_str', 'Off')}"
        )
        keyboard = [
            [create_btn("0️⃣ Remove duration", callback_data=f"flrem_dur_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"cfg_view_flood_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("flrem_dur_"):
        cid = int(data.split("_")[2])
        cfg["flood_duration_sec"] = 0
        cfg["flood_duration_str"] = "Off"
        save_config(cid, cfg)
        await query.answer("Duration removed!")
        await fast_edit(query, get_antiflood_text(cid), get_antiflood_main_keyboard(cid))
        return

    # 4. Welcome System Hub & Actions
    if data.startswith("cfg_view_welcome_"):
        cid = int(data.split("_")[3])
        user_states.pop((cid, user.id), None)
        status_text = "Active ✅" if cfg.get("welcome_active") else "Off ❌"
        mode_desc = "Send the welcome message at every join of the users in the group" if cfg.get("welcome_mode") == "always" else "Send the welcome message only at the first join of the user in the group"

        text = (
            "💬 <b>Welcome Message</b>\n"
            "From this menu you can set a welcome message that will be sent when someone joins the group.\n\n"
            f"<b>Status:</b> {status_text}\n"
            f"<b>Mode:</b> {mode_desc}"
        )
        await fast_edit(query, text, get_welcome_main_keyboard(cid))
        return

    if data.startswith("wlc_toggle_"):
        action = data.split("_")[2]
        cid = int(data.split("_")[3])
        cfg["welcome_active"] = (action == "on")
        save_config(cid, cfg)
        status_text = "Active ✅" if cfg.get("welcome_active") else "Off ❌"
        mode_desc = "Send the welcome message at every join of the users in the group" if cfg.get("welcome_mode") == "always" else "Send the welcome message only at the first join of the user in the group"
        text = f"💬 <b>Welcome Message</b>\n\n<b>Status:</b> {status_text}\n<b>Mode:</b> {mode_desc}"
        await fast_edit(query, text, get_welcome_main_keyboard(cid))
        return

    if data.startswith("wlc_mode_"):
        mode = data.split("_")[2]
        cid = int(data.split("_")[3])
        cfg["welcome_mode"] = mode
        save_config(cid, cfg)
        status_text = "Active ✅" if cfg.get("welcome_active") else "Off ❌"
        mode_desc = "Send the welcome message at every join of the users in the group" if cfg.get("welcome_mode") == "always" else "Send the welcome message only at the first join of the user in the group"
        text = f"💬 <b>Welcome Message</b>\n\n<b>Status:</b> {status_text}\n<b>Mode:</b> {mode_desc}"
        await fast_edit(query, text, get_welcome_main_keyboard(cid))
        return

    if data.startswith("wlc_tog_dellast_"):
        cid = int(data.split("_")[3])
        cfg["welcome_delete_last"] = not cfg["welcome_delete_last"]
        save_config(cid, cfg)
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

    if data.startswith("wlc_set_text_"):
        cid = int(data.split("_")[3])
        user_states[(cid, user.id)] = "awaiting_wlc_text"
        text = f"{user.mention_html()}, send now the message you want to set!\n\nYou can use <b>HTML</b> and placeholders like {{NAME}}, {{USERNAME}}, {{GROUPNAME}}, etc."
        keyboard = [
            [create_btn("🚫 Remove message", callback_data=f"wlc_rem_text_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"wlc_custom_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("wlc_rem_text_"):
        cid = int(data.split("_")[3])
        cfg["welcome_text"] = None
        save_config(cid, cfg)
        await query.answer("Welcome text removed!")
        await fast_edit(query, "💬 <b>Welcome Message</b>", get_welcome_customize_keyboard(cid))
        return

    if data.startswith("wlc_set_media_"):
        cid = int(data.split("_")[3])
        user_states[(cid, user.id)] = "awaiting_wlc_media"
        text = "👉 <b>Send now the media (photos, videos, stickers...) you want to set.</b>"
        keyboard = [
            [create_btn("🚫 Remove message", callback_data=f"wlc_rem_media_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"wlc_custom_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("wlc_rem_media_"):
        cid = int(data.split("_")[3])
        cfg["welcome_media_id"] = None
        cfg["welcome_media_type"] = None
        save_config(cid, cfg)
        await query.answer("Welcome media removed!")
        await fast_edit(query, "💬 <b>Welcome Message</b>", get_welcome_customize_keyboard(cid))
        return

    if data.startswith("wlc_set_buttons_"):
        cid = int(data.split("_")[3])
        user_states[(cid, user.id)] = "awaiting_wlc_buttons"
        text = "👉 <b>Set buttons:</b> Send lines structured as <code>Title - @username</code> or <code>Title - link.com</code>"
        keyboard = [
            [create_btn("🚫 Remove Keyboard", callback_data=f"wlc_rem_buttons_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"wlc_custom_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("wlc_rem_buttons_"):
        cid = int(data.split("_")[3])
        cfg["welcome_buttons_raw"] = None
        save_config(cid, cfg)
        await query.answer("Welcome buttons removed!")
        await fast_edit(query, "💬 <b>Welcome Message</b>", get_welcome_customize_keyboard(cid))
        return

    if data.startswith("wlc_full_preview_"):
        cid = int(data.split("_")[3])
        try:
            await send_custom_bundle(chat, user, cfg, is_preview=True)
            await query.answer("Full preview sent!")
        except Exception as e:
            await query.answer(f"Preview error: {e}", show_alert=True)
        return

    # 5. Regulations Hub
    if data.startswith("cfg_view_reg_"):
        cid = int(data.split("_")[3])
        user_states.pop((cid, user.id), None)
        text = "📜 <b>Group's regulations</b>\nManage regulations shown with /rules."
        await fast_edit(query, text, get_regulations_keyboard(cid))
        return

    # 6. Anti-Spam Hub
    if data.startswith("aspam_main_"):
        cid = int(data.split("_")[2])
        text = "✉️ <b>Anti-Spam</b>\nProtect your group from unnecessary links, forwards, and quotes."
        await fast_edit(query, text, get_antispam_hub_keyboard(cid))
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

    if state.startswith("awaiting_flood_dur_"):
        ptype = state.split("_")[3]
        parsed_sec = parse_time_duration(text)
        if parsed_sec < 30 or parsed_sec > 31536000:
            await msg.reply_text("❌ Duration must be between 30 seconds and 365 days.\nTry again:")
            user_states[state_key] = state
            return True

        cfg["flood_duration_sec"] = parsed_sec
        cfg["flood_duration_str"] = text.strip()
        save_config(chat_id, cfg)
        kb = [[create_btn("⬅️ Back to Antiflood", callback_data=f"cfg_view_flood_{chat_id}")]]
        await msg.reply_text(f"✅ <b>Antiflood {ptype} duration set to {text}!</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    elif state == "awaiting_wlc_text":
        cfg["welcome_text"] = text
        save_config(chat_id, cfg)
        kb = [[create_btn("⬅️ Back", callback_data=f"wlc_custom_{chat_id}")]]
        await msg.reply_text("✅ <b>Message set.</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    elif state == "awaiting_wlc_media":
        if msg.photo:
            cfg["welcome_media_id"] = msg.photo[-1].file_id
            cfg["welcome_media_type"] = "photo"
        elif msg.video:
            cfg["welcome_media_id"] = msg.video.file_id
            cfg["welcome_media_type"] = "video"
        elif msg.sticker:
            cfg["welcome_media_id"] = msg.sticker.file_id
            cfg["welcome_media_type"] = "sticker"
        else:
            await msg.reply_text("❌ Kripya photo, video ya sticker send karein.")
            return True

        if msg.caption:
            cfg["welcome_text"] = msg.caption
        save_config(chat_id, cfg)
        kb = [[create_btn("⬅️ Back", callback_data=f"wlc_custom_{chat_id}")]]
        await msg.reply_text("✅ <b>Media set.</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    elif state == "awaiting_wlc_buttons":
        cfg["welcome_buttons_raw"] = text
        save_config(chat_id, cfg)
        kb = parse_custom_buttons(text, chat_id)
        btn_list = kb.inline_keyboard if kb else []
        final_kb = list(btn_list) + [[create_btn("⬅️ Back", callback_data=f"wlc_custom_{chat_id}")]]
        await msg.reply_text(f"<code>{html.escape(text)}</code>", reply_markup=InlineKeyboardMarkup(final_kb), parse_mode="HTML")
        return True

    return False

# ----------------- COMMANDS & DISPATCHERS ----------------- #
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_text("Sirf groups ke liye available hai.")
        return

    if not await is_user_admin(chat.id, user.id, context):
        await update.message.reply_text("❌ Sirf Admins `/settings` open kar sakte hain.")
        return

    header_text = (
        "<b>SETTINGS</b>\n"
        f"Group: {chat.title}\n\n"
        "<i>Select one of the settings that you want to change.</i>"
    )
    await update.message.reply_text(
        header_text,
        reply_markup=get_page1_settings_keyboard(chat.id),
        parse_mode="HTML"
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

# ----------------- NEW MEMBER JOIN DISPATCHER ----------------- #
async def new_member_welcome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    cfg = get_config(chat.id)

    if not cfg.get("welcome_active"):
        return

    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            continue

        if cfg.get("welcome_mode") == "first":
            if not is_first_join(chat.id, member.id):
                continue
        else:
            is_first_join(chat.id, member.id)

        if cfg.get("welcome_delete_last") and chat.id in last_welcome_messages:
            try:
                await context.bot.delete_message(chat_id=chat.id, message_id=last_welcome_messages[chat.id])
            except Exception:
                pass

        thread_id = cfg.get("welcome_topic_id")
        sent_msg = await send_custom_bundle(chat, member, cfg, is_preview=False, thread_id=thread_id)

        if sent_msg and cfg.get("welcome_delete_last"):
            last_welcome_messages[chat.id] = sent_msg.message_id

# ----------------- SECURITY & AUTO MODERATION ----------------- #
async def security_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    if await interactive_state_processor(update, context):
        return

    chat = update.effective_chat
    user = update.effective_user
    msg = update.message
    cfg = get_config(chat.id)

    if await is_user_admin(chat.id, user.id, context):
        return

    # Antiflood Tracker
    penalty = cfg.get("flood_penalty", "Off")
    if penalty != "Off" or cfg.get("flood_delete"):
        now = time.time()
        max_msgs = cfg.get("flood_messages", 5)
        window = cfg.get("flood_seconds", 3)

        user_floods = flood_tracker.setdefault((chat.id, user.id), [])
        user_floods = [t for t in user_floods if now - t <= window]
        user_floods.append(now)
        flood_tracker[(chat.id, user.id)] = user_floods

        if len(user_floods) >= max_msgs:
            flood_tracker.pop((chat.id, user.id), None)
            dur_sec = cfg.get("flood_duration_sec", 0)
            await execute_punishment(penalty, cfg.get("flood_delete", True), update, context, f"Flooding ({len(user_floods)} msgs in {window}s)", duration_sec=dur_sec)
            return

# ----------------- MAIN INITIALIZER ----------------- #
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("update", update_command))

    # Single Fast Router
    app.add_handler(CallbackQueryHandler(unified_callback_handler))

    # Handlers
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member_welcome_handler))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^pip3?\s+install\s+"), auto_pip_installer))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, security_moderator))

    print("🛡 Group Help Security Bot running with 100% complete dual-page matrix & persistent DB...")
    app.run_polling()

if __name__ == "__main__":
    main()
