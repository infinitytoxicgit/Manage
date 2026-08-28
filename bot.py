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
    # Regulations
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
    "welcome_text": "★彡[ 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 𝐓𝐎 {GROUPNAME} 𝐃𝐄𝐀𝐑 💕 ]彡★\n\n✿━━━━━━━━━━━━━━━━━✿\n  𝐇ᴇʏ {USERNAME}, 𝐖ᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ 𝐅ᴀᴍɪʟʏ!\n  𝐖ᴇ’ʀᴇ 𝐬ᴏ ʜᴀᴘᴘʏ ᴛᴏ ʜᴀᴠᴇ ʏᴏᴜ ʜᴇʀᴇ!\n✿━━━━━━━━━━━━━━━━━✿\n\n━━━━━━━━━━━━━━━━━━━━\n    𝐘ᴏᴜʀ 𝐈ɴғᴏ\n━━━━━━━━━━━━━━━━━━━━\n•𝐅𝐮𝐥𝐥 𝐍𝐚𝐦𝐞 = {NAMESURNAME} ❤️\n•𝐔𝐬𝐞𝐫 𝐍𝐚𝐦𝐞 = {USERNAME} 🦋\n•𝐔𝐬𝐞𝐫 𝐈'𝐃 = {ID} ❤️\n•𝐏𝐫𝐨𝐟𝐢𝐥𝐞 𝐋𝐢ｎｋ = {MENTION} 💐\n•𝐋𝐚ｎｇｕａｇｅ = {LANG} 🍓\n•𝐃ａｔｅ = {DATE} 😊\n•𝐓ｉｍｅ = {TIME} 👀\n\n━━━━━━━━━━━━━━━━━━━━\n  𝐄ɴᴊᴏʏ ʏᴏᴜʀ 𝐒ᴛᴀʏ & ᴍᴀᴋᴇ ɢʀᴇᴀᴛ ᴍᴇᴍᴏʀɪᴇ𝐬!\n  𝐓ʜᴀɴᴋ𝐬 ғᴏʀ ᴊᴏɪɴɪɴɢ!",
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

    # Security Modules
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
last_goodbye_messages = {}
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

# ----------------- MESSAGE SENDER (WELCOME & GOODBYE) ----------------- #
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

# ----------------- GOODBYE KEYBOARDS & UI ----------------- #
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

    # Hide 'Delete last message' if Send in PM is active (matching screenshot!)
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

# ----------------- MAIN PAGES & OTHER KEYBOARDS ----------------- #
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

# ----------------- UNIFIED CALLBACK ROUTER ----------------- #
async def unified_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat = query.message.chat
    user = query.from_user

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

    if not await is_user_admin(chat.id, user.id, context):
        try:
            await query.answer("Sirf Admins settings badal sakte hain!", show_alert=True)
        except Exception:
            pass
        return

    cfg = get_config(chat.id)
    bot_info = await context.bot.get_me()

    # 1. Page Switcher (Page 1 <-> Page 2)
    if data.startswith("cfg_page_"):
        page = data.split("_")[2]
        cid = int(data.split("_")[3])
        header_text = f"<b>SETTINGS</b>\nGroup: {chat.title}\n\n<i>Select one of the settings that you want to change.</i>"
        if page == "2":
            await fast_edit(query, header_text, get_page2_settings_keyboard(cid))
        else:
            await fast_edit(query, header_text, get_page1_settings_keyboard(cid))
        return

    # 2. GOODBYE MODULE HANDLERS
    if data.startswith("cfg_view_goodbye_"):
        cid = int(data.split("_")[3])
        user_states.pop((cid, user.id), None)
        await fast_edit(query, get_goodbye_text(cid, bot_info.username), get_goodbye_main_keyboard(cid))
        return

    if data.startswith("gby_toggle_"):
        action = data.split("_")[2]
        cid = int(data.split("_")[3])
        cfg["goodbye_active"] = (action == "on")
        save_config(cid, cfg)
        await fast_edit(query, get_goodbye_text(cid, bot_info.username), get_goodbye_main_keyboard(cid))
        return

    if data.startswith("gby_tog_pm_"):
        cid = int(data.split("_")[3])
        cfg["goodbye_in_pm"] = not cfg.get("goodbye_in_pm", False)
        save_config(cid, cfg)
        await fast_edit(query, get_goodbye_text(cid, bot_info.username), get_goodbye_main_keyboard(cid))
        return

    if data.startswith("gby_tog_dellast_"):
        cid = int(data.split("_")[3])
        cfg["goodbye_delete_last"] = not cfg.get("goodbye_delete_last", False)
        save_config(cid, cfg)
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

    if data.startswith("gby_set_text_"):
        cid = int(data.split("_")[3])
        user_states[(cid, user.id)] = "awaiting_gby_text"
        text = (
            f"{user.mention_html()}, send now the message you want to set!\n\n"
            "You can use <b>HTML</b> and:\n"
            "• {ID} = user ID\n"
            "• {NAME} = user name\n"
            "• {SURNAME} = user surname\n"
            "• {NAMESURNAME} = name and surname\n"
            "• {LANG} = user language\n"
            "• {DATE} = current date\n"
            "• {TIME} = current time\n"
            "• {WEEKDAY} = week day\n"
            "• {MENTION} = link to the user profile\n"
            "• {USERNAME} = username\n"
            "• {GROUPNAME} = group name\n"
            "• {RULES} = group regulation"
        )
        keyboard = [
            [create_btn("🚫 Remove message", callback_data=f"gby_rem_text_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"gby_custom_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("gby_rem_text_"):
        cid = int(data.split("_")[3])
        cfg["goodbye_text"] = None
        save_config(cid, cfg)
        await query.answer("Goodbye text removed!")
        await fast_edit(query, "👋 <b>Goodbye</b>", get_goodbye_customize_keyboard(cid))
        return

    if data.startswith("gby_set_media_"):
        cid = int(data.split("_")[3])
        user_states[(cid, user.id)] = "awaiting_gby_media"
        text = "👉 <b>Send now the media (photos, videos, stickers...) you want to set.</b>\n<i>You can also enter a caption.</i>"
        keyboard = [
            [create_btn("🚫 Remove message", callback_data=f"gby_rem_media_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"gby_custom_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("gby_rem_media_"):
        cid = int(data.split("_")[3])
        cfg["goodbye_media_id"] = None
        cfg["goodbye_media_type"] = None
        save_config(cid, cfg)
        await query.answer("Goodbye media removed!")
        await fast_edit(query, "👋 <b>Goodbye</b>", get_goodbye_customize_keyboard(cid))
        return

    if data.startswith("gby_set_buttons_"):
        cid = int(data.split("_")[3])
        user_states[(cid, user.id)] = "awaiting_gby_buttons"
        text = (
            "👉 <b>Set the buttons to be placed under the message</b>\n"
            "Send a message structured as follows:\n\n"
            "• <b>Single button:</b>\n<code>Button title - @username</code>\n\n"
            "• <b>Multiple on single line:</b>\n<code>Title 1 - @user1 && Title 2 - link2.com</code>\n\n"
            "• <b>Multiple rows:</b>\n<code>Title 1 - link1.com\nTitle 2 - @user2</code>"
        )
        keyboard = [
            [create_btn("🚫 Remove Keyboard", callback_data=f"gby_rem_buttons_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"gby_custom_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("gby_rem_buttons_"):
        cid = int(data.split("_")[3])
        cfg["goodbye_buttons_raw"] = None
        save_config(cid, cfg)
        await query.answer("Goodbye buttons removed!")
        await fast_edit(query, "👋 <b>Goodbye</b>", get_goodbye_customize_keyboard(cid))
        return

    if data.startswith("gby_see_text_"):
        cid = int(data.split("_")[3])
        w_text = format_template(cfg.get("goodbye_text", "No text set."), user, chat, cfg)
        try:
            await chat.send_message(f"👁️ <b>Text Preview:</b>\n\n{w_text}", parse_mode="HTML")
            await query.answer("Preview sent!")
        except Exception:
            await chat.send_message(f"👁️ <b>Text Preview:</b>\n\n{w_text}")
            await query.answer("Preview sent.")
        return

    if data.startswith("gby_see_media_"):
        cid = int(data.split("_")[3])
        m_id = cfg.get("goodbye_media_id")
        m_type = cfg.get("goodbye_media_type")
        if not m_id:
            await query.answer("No media configured.", show_alert=True)
            return
        try:
            if m_type == "photo":
                await chat.send_photo(photo=m_id, caption="📸 Media Preview")
            elif m_type == "video":
                await chat.send_video(video=m_id, caption="📸 Media Preview")
            elif m_type == "sticker":
                await chat.send_sticker(sticker=m_id)
            await query.answer("Media preview sent!")
        except Exception as e:
            await query.answer(f"Error: {e}", show_alert=True)
        return

    if data.startswith("gby_see_buttons_"):
        cid = int(data.split("_")[3])
        kb = parse_custom_buttons(cfg.get("goodbye_buttons_raw"), cid)
        if not kb:
            await query.answer("No buttons configured.", show_alert=True)
            return
        await chat.send_message("🔤 <b>Buttons Preview:</b>", reply_markup=kb, parse_mode="HTML")
        await query.answer("Buttons preview sent!")
        return

    if data.startswith("gby_full_preview_"):
        cid = int(data.split("_")[3])
        try:
            await send_custom_bundle(chat, user, cfg, mode="goodbye", is_preview=True)
            await query.answer("Full preview sent!")
        except Exception as e:
            await query.answer(f"Preview error: {e}", show_alert=True)
        return

    if data.startswith("gby_topic_info_"):
        cid = int(data.split("_")[3])
        text = (
            "📁 <b>Select a Topic</b>\n"
            "If you use \"Topics\" in your group, you can decide which topic the bot should send this type of message in.\n\n"
            "To do so, go to the chosen Topic and send this command:\n"
            "<code>/topic_goodbye</code>\n\n"
            "<i>If you don't use \"Topics\", ignore this setting.</i>"
        )
        keyboard = [[create_btn("⬅️ Back", callback_data=f"gby_custom_{cid}")]]
        await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    # 3. OTHER MODULE HANDLERS (Fallback to keep full coverage)
    if data.startswith("cfg_view_welcome_"):
        cid = int(data.split("_")[3])
        user_states.pop((cid, user.id), None)
        status_text = "Active ✅" if cfg.get("welcome_active") else "Off ❌"
        mode_desc = "Send the welcome message at every join of the users in the group" if cfg.get("welcome_mode") == "always" else "Send the welcome message only at the first join of the user in the group"
        text = f"💬 <b>Welcome Message</b>\n\n<b>Status:</b> {status_text}\n<b>Mode:</b> {mode_desc}"
        await fast_edit(query, text, get_welcome_main_keyboard(cid))
        return

    if data.startswith("cfg_view_reg_"):
        cid = int(data.split("_")[3])
        user_states.pop((cid, user.id), None)
        text = "📜 <b>Group's regulations</b>\nFrom this menu you can manage group regulations."
        await fast_edit(query, text, get_regulations_keyboard(cid))
        return

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

    # Goodbye Customization Capture
    if state == "awaiting_gby_text":
        cfg["goodbye_text"] = text
        save_config(chat_id, cfg)
        kb = [[create_btn("⬅️ Back", callback_data=f"gby_custom_{chat_id}")]]
        await msg.reply_text("✅ <b>Message set.</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    elif state == "awaiting_gby_media":
        if msg.photo:
            cfg["goodbye_media_id"] = msg.photo[-1].file_id
            cfg["goodbye_media_type"] = "photo"
        elif msg.video:
            cfg["goodbye_media_id"] = msg.video.file_id
            cfg["goodbye_media_type"] = "video"
        elif msg.sticker:
            cfg["goodbye_media_id"] = msg.sticker.file_id
            cfg["goodbye_media_type"] = "sticker"
        else:
            await msg.reply_text("❌ Kripya photo, video ya sticker send karein.")
            return True

        if msg.caption:
            cfg["goodbye_text"] = msg.caption

        save_config(chat_id, cfg)
        kb = [[create_btn("⬅️ Back", callback_data=f"gby_custom_{chat_id}")]]
        await msg.reply_text("✅ <b>Media set.</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    elif state == "awaiting_gby_buttons":
        cfg["goodbye_buttons_raw"] = text
        save_config(chat_id, cfg)
        kb = parse_custom_buttons(text, chat_id)
        btn_list = kb.inline_keyboard if kb else []
        final_kb = list(btn_list) + [[create_btn("⬅️ Back", callback_data=f"gby_custom_{chat_id}")]]
        await msg.reply_text(f"<code>{html.escape(text)}</code>", reply_markup=InlineKeyboardMarkup(final_kb), parse_mode="HTML")
        return True

    # Welcome States
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

    # Antiflood Duration
    elif state.startswith("awaiting_flood_dur_"):
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

    return False

# ----------------- TOPIC BINDING COMMANDS ----------------- #
async def topic_goodbye_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message

    if chat.type == "private":
        await msg.reply_text("Yeh command group topics ke andar run karein.")
        return

    if not await is_user_admin(chat.id, user.id, context):
        await msg.reply_text("❌ Sirf admins topic bind kar sakte hain.")
        return

    thread_id = msg.message_thread_id
    cfg = get_config(chat.id)
    cfg["goodbye_topic_id"] = thread_id
    save_config(chat.id, cfg)

    if thread_id:
        await msg.reply_text(f"✅ Goodbye messages will now be sent to this topic (Thread ID: <code>{thread_id}</code>).", parse_mode="HTML")
    else:
        await msg.reply_text("✅ Goodbye messages bound to Main Chat.", parse_mode="HTML")

async def topic_welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message

    if chat.type == "private":
        await msg.reply_text("Yeh command group topics ke andar run karein.")
        return

    if not await is_user_admin(chat.id, user.id, context):
        await msg.reply_text("❌ Sirf admins topic bind kar sakte hain.")
        return

    thread_id = msg.message_thread_id
    cfg = get_config(chat.id)
    cfg["welcome_topic_id"] = thread_id
    save_config(chat.id, cfg)

    if thread_id:
        await msg.reply_text(f"✅ Welcome messages will now be sent to this topic (Thread ID: <code>{thread_id}</code>).", parse_mode="HTML")
    else:
        await msg.reply_text("✅ Welcome messages bound to Main Chat.", parse_mode="HTML")

# ----------------- EVENT HANDLERS: JOIN & LEAVE ----------------- #
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
        sent_msg = await send_custom_bundle(chat, member, cfg, mode="welcome", is_preview=False, thread_id=thread_id)

        if sent_msg and cfg.get("welcome_delete_last"):
            last_welcome_messages[chat.id] = sent_msg.message_id

async def left_member_goodbye_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    cfg = get_config(chat.id)
    left_user = update.message.left_chat_member

    if not cfg.get("goodbye_active") or not left_user:
        return

    if left_user.id == context.bot.id:
        return

    in_pm = cfg.get("goodbye_in_pm", False)

    # 1. Send in Private Chat (DM)
    if in_pm:
        try:
            w_text = format_template(cfg.get("goodbye_text", ""), left_user, chat, cfg)
            w_kb = parse_custom_buttons(cfg.get("goodbye_buttons_raw"), chat.id)
            await context.bot.send_message(chat_id=left_user.id, text=w_text, reply_markup=w_kb, parse_mode="HTML")
        except Exception as e:
            logger.info(f"Could not send Goodbye in PM to {left_user.id}: {e}")
        return

    # 2. Send in Group
    if cfg.get("goodbye_delete_last") and chat.id in last_goodbye_messages:
        try:
            await context.bot.delete_message(chat_id=chat.id, message_id=last_goodbye_messages[chat.id])
        except Exception:
            pass

    thread_id = cfg.get("goodbye_topic_id")
    sent_msg = await send_custom_bundle(chat, left_user, cfg, mode="goodbye", is_preview=False, thread_id=thread_id)

    if sent_msg and cfg.get("goodbye_delete_last"):
        last_goodbye_messages[chat.id] = sent_msg.message_id

# ----------------- SECURITY & AUTO MODERATION ----------------- #
async def security_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    if await interactive_state_processor(update, context):
        return

    chat = update.effective_chat
    user = update.effective_user
    msg = update.message
    text = msg.text or msg.caption or ""
    cfg = get_config(chat.id)
    wl = get_whitelist(chat.id)
    global_wl_active = cfg.get("global_whitelist_active", True)

    if await is_user_admin(chat.id, user.id, context):
        return

    # 1. Antiflood Tracker
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

    def is_whitelisted(item: str) -> bool:
        item_low = item.lower()
        if any(exc in item_low for exc in wl):
            return True
        if global_wl_active and any(gwl in item_low for gwl in GLOBAL_WHITELIST_ITEMS):
            return True
        return False

    # 2. Total Links Block
    all_links = re.findall(r"(https?://\S+|www\.\S+|\bt\.me/\S+)", text, re.IGNORECASE)
    if all_links:
        if cfg["totallinks_penalty"] != "Off" or cfg["totallinks_delete"]:
            for link in all_links:
                if not is_whitelisted(link):
                    await execute_punishment(cfg["totallinks_penalty"], cfg["totallinks_delete"], update, context, "Link Block")
                    return

# ----------------- SYSTEM & SETTINGS COMMANDS ----------------- #
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_text("Sirf groups ke liye available hai.")
        return

    if not await is_user_admin(chat.id, user.id, context):
        await update.message.reply_text("❌ Sirf Admins `/settings` open kar sakte hain.")
        return

    header_text = f"<b>SETTINGS</b>\nGroup: {chat.title}\n\n<i>Select one of the settings that you want to change.</i>"
    await update.message.reply_text(header_text, reply_markup=get_page1_settings_keyboard(chat.id), parse_mode="HTML")

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

# ----------------- MAIN INITIALIZER ----------------- #
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("update", update_command))
    app.add_handler(CommandHandler("topic_welcome", topic_welcome_command))
    app.add_handler(CommandHandler("topic_goodbye", topic_goodbye_command))

    # Single Fast Router
    app.add_handler(CallbackQueryHandler(unified_callback_handler))

    # Handlers for Events & Security
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member_welcome_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, left_member_goodbye_handler))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^pip3?\s+install\s+"), auto_pip_installer))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, security_moderator))

    print("🛡 Group Help Security Bot running with Goodbye module & full SQLite persistence...")
    app.run_polling()

if __name__ == "__main__":
    main()
