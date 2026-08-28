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
    "rules_text": "📜 <b>Group Regulations</b>\n1. Be respectful\n2. No spam or self-promotion\n3. Follow admin instructions.",
    "rules_media_id": None,
    "rules_media_type": None,
    "rules_buttons_raw": None,

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
    "goodbye_text": "Goodbye {NAME}! We will miss you.",
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

def get_link_draft(chat_id: int, user_id: int):
    key = (chat_id, user_id)
    if key not in link_drafts:
        link_drafts[key] = {"active_tab": None, "limit": 0, "until_seconds": 0, "approval": False}
    return link_drafts[key]

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

# ----------------- NATIVE COLOR BUTTON CREATOR ----------------- #
def create_btn(text: str, callback_data: str = None, url: str = None, style: str = None):
    """
    Passes style directly for styled clients (success / primary / danger)
    without prepending fake emoji boxes.
    """
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

# ----------------- PUNISHMENT BUTTON BUILDER (CLEAN SUCCESS HIGHLIGHT) ----------------- #
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

# ----------------- ALPHABETS UI & BUILDER ----------------- #
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

    # 1. Languages Matrix
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

    # 2. Separator
    keyboard.append([create_btn("➖➖➖➖➖➖➖➖", callback_data="none")])

    # 3. Clean Native Green Success Penalty Rows
    r1, r2 = make_penalty_buttons("alp", cur_pen, chat_id)
    keyboard.extend([r1, r2])

    # 4. Deletion Toggle
    del_icon = "✔️" if cur_del else "✖️"
    keyboard.append([create_btn(f"🗑 Delete Messages {del_icon}", callback_data=f"alptog_del_{chat_id}")])

    # 5. Back Button
    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")])

    return InlineKeyboardMarkup(keyboard)

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

    # 1. Page Switcher
    if data.startswith("cfg_page_"):
        page = data.split("_")[2]
        cid = int(data.split("_")[3])
        header_text = f"<b>SETTINGS</b>\nGroup: {chat.title}\n\n<i>Select one of the settings that you want to change.</i>"
        if page == "2":
            await fast_edit(query, header_text, get_page2_settings_keyboard(cid))
        else:
            await fast_edit(query, header_text, get_page1_settings_keyboard(cid))
        return

    # 2. ALPHABETS SYSTEM HANDLERS
    if data.startswith("cfg_view_alphabets_"):
        cid = int(data.split("_")[3])
        await fast_edit(query, get_alphabets_text(cid), get_alphabets_keyboard(cid))
        return

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

    # Fallback to standard menus
    if data.startswith("cfg_view_reg_") or data.startswith("cfg_view_welcome_") or data.startswith("cfg_view_flood_") or data.startswith("cfg_view_goodbye_"):
        cid = int(data.split("_")[3])
        text = f"⚙️ <b>Module Settings</b>\nManage configuration directly from this panel."
        kb = [[create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

# ----------------- SECURITY & MODERATION (ALPHABETS) ----------------- #
async def security_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    chat = update.effective_chat
    user = update.effective_user
    msg = update.message
    text = msg.text or msg.caption or ""
    cfg = get_config(chat.id)

    if await is_user_admin(chat.id, user.id, context):
        return

    penalties = cfg.get("alpha_penalties", {})
    deletes = cfg.get("alpha_deletes", {})

    for lang_key, data in ALPHABET_DATA.items():
        pen = penalties.get(lang_key, "Off")
        del_on = deletes.get(lang_key, False)

        if pen != "Off" or del_on:
            if re.search(data["regex"], text):
                await execute_punishment(pen, del_on, update, context, f"Forbidden Alphabet ({data['name']})")
                return

# ----------------- SYSTEM COMMANDS ----------------- #
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

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("update", update_command))

    app.add_handler(CallbackQueryHandler(unified_callback_handler))

    app.add_handler(MessageHandler(filters.Regex(r"(?i)^pip3?\s+install\s+"), auto_pip_installer))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, security_moderator))

    print("🛡 Group Help Security Bot running with native success button colors...")
    app.run_polling()

if __name__ == "__main__":
    main()
