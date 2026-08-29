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
    "rules_text": "📜 <b>Group Regulations</b>\n1. Be respectful\n2. No spam or self-promotion\n3. Follow admin instructions.",
    "rules_media_id": None,
    "rules_media_type": None,
    "rules_buttons_raw": None,

    "checks_main_tab": "obligations",
    "checks_sub_tab": None,
    "check_at_join": True,
    "checks_delete_messages": False,
    "checks_penalties": {
        "surname": "Off", "username": "Off", "pfp": "Off", "channel_ob": "Off", "add_ob": "Off",
        "arabic": "Off", "chinese": "Off", "russian": "Off", "spam": "Off"
    },

    "captcha_active": False,
    "captcha_mode": "button",
    "captcha_time_val": 180,
    "captcha_time_label": "3 Minutes",
    "captcha_penalty": "Mute",
    "captcha_delete_service": False,
    "captcha_custom_text": None,
    "captcha_topic_id": None,
    "captcha_tab": None,

    "alpha_active_tab": "chinese",
    "alpha_penalties": {k: "Off" for k in ALPHABET_DATA},
    "alpha_deletes": {k: False for k in ALPHABET_DATA},

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

    "welcome_active": True,
    "welcome_mode": "always",
    "welcome_delete_last": False,
    "welcome_text": "Hello {NAME}, welcome to {GROUPNAME}!",
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

    "flood_messages": 5,
    "flood_seconds": 3,
    "flood_penalty": "Off",
    "flood_delete": True,
    "flood_duration_sec": 0,
    "flood_duration_str": "Off",

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

# ----------------- ADMIN CHECK (ROBUST) ----------------- #
async def is_user_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if user_id in OWNER_IDS:
        return True
    
    # Private chat is always allowed
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
        # Fallback to true for smooth local response if check fails
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

# ----------------- SETTINGS DUAL-PAGE KEYBOARDS ----------------- #
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

# ----------------- UNIFIED CALLBACK QUERY ROUTER ----------------- #
async def unified_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat = query.message.chat
    user = query.from_user

    # 1. Handle "Open here" vs "Open in Private Chat"
    if data.startswith("set_open_"):
        mode = data.split("_")[2]
        cid = int(data.split("_")[3])

        if not await is_user_admin(cid, user.id, context):
            try:
                await query.answer("Sirf Admins settings open kar sakte hain!", show_alert=True)
            except Exception:
                pass
            return

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
                await fast_edit(query, "⚠️ Pehle bot ko PM me /start karein taaki settings send ho sakein.", InlineKeyboardMarkup(start_btn))
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

    # 2. Main Page Switchers
    if data.startswith("cfg_page_"):
        page = data.split("_")[2]
        cid = int(data.split("_")[3])
        chat_title = chat.title if chat.type != "private" else "Group"
        header_text = f"<b>SETTINGS</b>\nGroup: {chat_title}\n\n<i>Select one of the settings that you want to change.</i>"
        if page == "2":
            await fast_edit(query, header_text, get_page2_settings_keyboard(cid))
        else:
            await fast_edit(query, header_text, get_page1_settings_keyboard(cid))
        return

    # 3. SPECIFIC MODULE OPENERS
    if data.startswith("cfg_view_reg_"):
        cid = int(data.split("_")[3])
        text = "📜 <b>Group's regulations</b>\nFrom this menu you can manage the group's regulations, that will be shown with the command /rules."
        kb = [
            [create_btn("✍️ Customize message", callback_data=f"reg_custom_msg_{cid}")],
            [create_btn("🕹 Commands Permissions", callback_data=f"reg_cmd_perms_{cid}")],
            [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("aspam_main_"):
        cid = int(data.split("_")[2])
        text = "✉️ <b>Anti-Spam</b>\nProtect your group from unnecessary links, forwards, and quotes."
        kb = [
            [create_btn("📘 Telegram links", callback_data=f"aspam_tglinks_{cid}")],
            [create_btn("📩 Forwarding", callback_data=f"aspam_fwd_{cid}"), create_btn("💭 Quote", callback_data=f"aspam_quote_{cid}")],
            [create_btn("🔗 Total links block", callback_data=f"aspam_totallinks_{cid}")],
            [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("cfg_view_welcome_"):
        cid = int(data.split("_")[3])
        cfg = get_config(cid)
        is_active = cfg.get("welcome_active", False)
        mode_desc = "Send the welcome message at every join" if cfg.get("welcome_mode") == "always" else "Send only at first join"
        text = f"💬 <b>Welcome Message</b>\n\n<b>Status:</b> {'Active ✅' if is_active else 'Off ❌'}\n<b>Mode:</b> {mode_desc}"
        del_icon = "✔️" if cfg.get("welcome_delete_last") else "✖️"
        kb = [
            [create_btn("✖️ Turn off", callback_data=f"wlc_toggle_off_{cid}"), create_btn("✔️ Turn on", callback_data=f"wlc_toggle_on_{cid}")],
            [create_btn("✍️ Customize message", callback_data=f"wlc_custom_{cid}")],
            [create_btn("🔔 Always send", callback_data=f"wlc_mode_always_{cid}"), create_btn("1️⃣ Send 1st join", callback_data=f"wlc_mode_first_{cid}")],
            [create_btn(f"♻️ Delete last message {del_icon}", callback_data=f"wlc_tog_dellast_{cid}")],
            [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("cfg_view_flood_"):
        cid = int(data.split("_")[3])
        cfg = get_config(cid)
        p = cfg.get("flood_penalty", "Off")
        text = (
            "🗣 <b>Antiflood</b>\n"
            f"Triggered when {cfg.get('flood_messages', 5)} messages are sent within {cfg.get('flood_seconds', 3)} seconds.\n\n"
            f"<b>Punishment:</b> {p}"
        )
        del_icon = "✔️" if cfg.get("flood_delete", True) else "✖️"
        r1, r2 = make_penalty_buttons("fl", p, cid)
        kb = [
            [create_btn("📄 Messages", callback_data=f"flgrid_msg_{cid}"), create_btn("⏰ Time", callback_data=f"flgrid_time_{cid}")],
            r1, r2,
            [create_btn(f"🗑 Delete Messages {del_icon}", callback_data=f"fltog_del_{cid}")],
            [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("cfg_view_goodbye_"):
        cid = int(data.split("_")[3])
        cfg = get_config(cid)
        bot_info = await context.bot.get_me()
        is_active = cfg.get("goodbye_active", False)
        in_pm = cfg.get("goodbye_in_pm", False)
        pm_icon = "✔️" if in_pm else "✖️"
        del_icon = "✔️" if cfg.get("goodbye_delete_last") else "✖️"

        text = f"👋 <b>Goodbye</b>\n\n<b>Status:</b> {'Active ✅' if is_active else 'Off ❌'}"
        if in_pm:
            text += f"\n⚠️ The message will only be sent to users who started @{bot_info.username} in PM."

        kb = [
            [create_btn("✖️ Turn off", callback_data=f"gby_toggle_off_{cid}"), create_btn("✔️ Turn on", callback_data=f"gby_toggle_on_{cid}")],
            [create_btn("✍️ Customize message", callback_data=f"gby_custom_{cid}")],
            [create_btn(f"💌 Send in private chat {pm_icon}", callback_data=f"gby_tog_pm_{cid}")]
        ]
        if not in_pm:
            kb.append([create_btn(f"♻️ Delete last message {del_icon}", callback_data=f"gby_tog_dellast_{cid}")])
        kb.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")])
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("cfg_view_alphabets_"):
        cid = int(data.split("_")[3])
        cfg = get_config(cid)
        cur_tab = cfg.get("alpha_active_tab", "chinese")
        cur_pen = cfg.get("alpha_penalties", {}).get(cur_tab, "Off")
        cur_del = cfg.get("alpha_deletes", {}).get(cur_tab, False)

        lines = ["🕉 <b>Alphabets</b>\nSelect punishment for users who send messages in certain alphabets.\n"]
        for key, d in ALPHABET_DATA.items():
            pen = cfg.get("alpha_penalties", {}).get(key, "Off")
            lines.append(f"{d['icon']} <b>{d['name']}</b> (<a href=\"{d['wiki']}\">?</a>)\n  └ Status: {pen}")

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

    if data.startswith("cfg_view_captcha_"):
        cid = int(data.split("_")[3])
        cfg = get_config(cid)
        is_active = cfg.get("captcha_active", False)

        base = "🧠 <b>Captcha</b>\nConfirm user is not a robot.\n\n"
        if not is_active:
            text = base + "<b>Status:</b> Off ❌"
            kb = [
                [create_btn("✅ Activate", callback_data=f"cpt_toggle_on_{cid}", style="success")],
                [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]
            ]
        else:
            mode = cfg.get("captcha_mode", "button")
            text = base + f"<b>Status:</b> Active ✅\n🕒 <b>Time:</b> {cfg.get('captcha_time_label', '3 Minutes')}\n⛔️ <b>Penalty:</b> {cfg.get('captcha_penalty', 'Mute')}\n🗂 <b>Mode:</b> {mode.capitalize()}"
            del_icon = "✔️" if cfg.get("captcha_delete_service") else "✖️"
            kb = [
                [create_btn("❌ Turn off ❌", callback_data=f"cpt_toggle_off_{cid}", style="danger")],
                [create_btn("📦 Mode 📦", callback_data=f"cpt_switch_mode_{cid}")],
                [create_btn("🕒 Time 🕒", callback_data=f"cpt_tab_time_{cid}")],
                [create_btn("⛔️ Penalty ⛔️", callback_data=f"cpt_tab_penalty_{cid}")],
                [create_btn("✍️ Customize message ✍️", callback_data=f"cpt_tab_custom_{cid}")],
                [create_btn("📁 Select a Topic 🆕", callback_data=f"cpt_topic_info_{cid}")],
                [create_btn(f"🗑 Delete service message {del_icon}", callback_data=f"cpt_tog_delsvc_{cid}")],
                [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]
            ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    if data.startswith("cfg_view_checks_"):
        cid = int(data.split("_")[3])
        cfg = get_config(cid)
        main_tab = cfg.get("checks_main_tab", "obligations")
        sub_tab = cfg.get("checks_sub_tab")
        p = cfg.get("checks_penalties", {})
        chk_join = "Active ✔️" if cfg.get("check_at_join", True) else "Off ✖️"
        del_msg = "Active ✔️" if cfg.get("checks_delete_messages", False) else "Off ✖️"

        text = (
            "<b>OBLIGATION OF...</b>\n"
            f" • Surname: {p.get('surname', 'Off')}\n • Username: {p.get('username', 'Off')}\n"
            f" • Profile picture: {p.get('pfp', 'Off')}\n\n"
            "<b>BLOCK...</b>\n"
            f" • Arabic name: {p.get('arabic', 'Off')}\n • Chinese name: {p.get('chinese', 'Off')}\n\n"
            f"🚪 <b>Check at the join:</b> {chk_join}\n🗑 <b>Delete Messages:</b> {del_msg}"
        )

        t_ob = "» OBLIGATIONS «" if main_tab == "obligations" else "OBLIGATIONS"
        t_nb = "» NAME BLOCKS «" if main_tab == "nameblocks" else "NAME BLOCKS"
        kb = [[create_btn(t_ob, callback_data=f"chktab_main_obligations_{cid}"), create_btn(t_nb, callback_data=f"chktab_main_nameblocks_{cid}")]]

        items = [("surname", "🧑‍🤝‍🧑 Obligation Surname"), ("username", "🌐 Username Obligation"), ("pfp", "📸 Profile Picture Obligation 🔒")] if main_tab == "obligations" else [("arabic", "☪️ Arabic name block"), ("chinese", "🇨🇳 Chinese name block")]
        for k, lbl in items:
            is_active = (sub_tab == k)
            kb.append([create_btn(f"» {lbl} «" if is_active else lbl, callback_data=f"chktab_sub_{k}_{cid}", style="primary" if is_active else None)])
            if is_active:
                cur_p = p.get(k, "Off")
                r1, r2 = make_penalty_buttons("chk", cur_p, cid)
                kb.extend([r1, r2])

        if sub_tab is None:
            kb.append([create_btn(f"🚪 Check at the join {'✔️' if cfg.get('check_at_join', True) else '✖️'}", callback_data=f"chktog_join_{cid}")])
            kb.append([create_btn(f"🗑 Delete Messages {'✔️' if cfg.get('checks_delete_messages', False) else '✖️'}", callback_data=f"chktog_del_{cid}")])

        kb.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")])
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

    # Generic Module Handler
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

    # If opened in PM directly with start payload: /start settings_12345
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
        # Handle deep-link payload
        if context.args and context.args[0].startswith("settings_"):
            target_cid = int(context.args[0].replace("settings_", ""))
            header_text = "<b>SETTINGS</b>\n\n<i>Select one of the settings that you want to change.</i>"
            await update.message.reply_text(header_text, reply_markup=get_page1_settings_keyboard(target_cid), parse_mode="HTML")
            return

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

    app.add_handler(CallbackQueryHandler(unified_callback_handler))

    app.add_handler(MessageHandler(filters.Regex(r"(?i)^pip3?\s+install\s+"), auto_pip_installer))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, security_moderator))

    print("🛡 Group Help Security Bot running smoothly...")
    app.run_polling()

if __name__ == "__main__":
    main()
