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

    # CHECKS & OBLIGATIONS MODULE
    "checks_main_tab": "obligations", # "obligations" or "nameblocks"
    "checks_sub_tab": None,           # e.g., "username", "surname", "arabic", etc.
    "check_at_join": True,
    "checks_delete_messages": False,
    "checks_penalties": {
        # Obligations
        "surname": "Off",
        "username": "Off",
        "pfp": "Off",
        "channel_ob": "Off",
        "add_ob": "Off",
        # Name Blocks
        "arabic": "Off",
        "chinese": "Off",
        "russian": "Off",
        "spam": "Off"
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

    # Antiflood
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
        if "checks_penalties" not in cfg:
            cfg["checks_penalties"] = DEFAULT_CONFIG["checks_penalties"].copy()
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

# ----------------- CHECKS MODULE UI BUILDERS ----------------- #
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

    # Top Tabs
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

    # Obligations List
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

    # Name Blocks List
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

    # Bottom Settings & Navigation
    if sub_tab is None:
        chk_join_icon = "✔️" if cfg.get("check_at_join", True) else "✖️"
        del_msg_icon = "✔️" if cfg.get("checks_delete_messages", False) else "✖️"
        keyboard.append([create_btn(f"🚪 Check at the join {chk_join_icon}", callback_data=f"chktog_join_{chat_id}")])
        keyboard.append([create_btn(f"🗑 Delete Messages {del_msg_icon}", callback_data=f"chktog_del_{chat_id}")])

    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")])
    return InlineKeyboardMarkup(keyboard)

# ----------------- MAIN SETTINGS KEYBOARDS ----------------- #
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

# ----------------- UNIFIED CALLBACK ROUTER ----------------- #
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

    # 2. CHECKS & OBLIGATIONS MODULE ROUTING
    if data.startswith("cfg_view_checks_"):
        cid = int(data.split("_")[3])
        cfg["checks_sub_tab"] = None
        save_config(cid, cfg)
        await fast_edit(query, get_checks_text(cid), get_checks_keyboard(cid))
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

    # Fallback to page 1
    if data.startswith("cfg_view_"):
        cid = int(data.split("_")[-1])
        text = f"⚙️ <b>Module Settings</b>\nManage configuration directly from this panel."
        kb = [[create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
        return

# ----------------- LIVE CHECKS ENFORCER ----------------- #
async def run_user_checks(user, chat, context: ContextTypes.DEFAULT_TYPE, is_join=False, update=None):
    if await is_user_admin(chat.id, user.id, context):
        return True

    cfg = get_config(chat.id)
    p = cfg.get("checks_penalties", {})
    del_msg = cfg.get("checks_delete_messages", False)
    full_name = f"{user.first_name or ''} {user.last_name or ''}"

    # 1. OBLIGATIONS
    # Surname
    if p.get("surname", "Off") != "Off" and not user.last_name:
        await execute_punishment(p["surname"], del_msg, update, context, "Obligation Surname missing")
        return False

    # Username
    if p.get("username", "Off") != "Off" and not user.username:
        await execute_punishment(p["username"], del_msg, update, context, "Username Obligation missing")
        return False

    # Profile Picture
    if p.get("pfp", "Off") != "Off":
        try:
            photos = await context.bot.get_user_profile_photos(user.id, limit=1)
            if photos.total_count == 0:
                await execute_punishment(p["pfp"], del_msg, update, context, "Profile Picture Obligation missing")
                return False
        except Exception:
            pass

    # 2. NAME BLOCKS
    # Arabic Name
    if p.get("arabic", "Off") != "Off" and re.search(r"[\u0600-\u06FF]", full_name):
        await execute_punishment(p["arabic"], del_msg, update, context, "Arabic Name Block")
        return False

    # Chinese Name
    if p.get("chinese", "Off") != "Off" and re.search(r"[\u4E00-\u9FFF]", full_name):
        await execute_punishment(p["chinese"], del_msg, update, context, "Chinese Name Block")
        return False

    # Russian Name
    if p.get("russian", "Off") != "Off" and re.search(r"[\u0400-\u04FF]", full_name):
        await execute_punishment(p["russian"], del_msg, update, context, "Russian Name Block")
        return False

    # Spam Name
    if p.get("spam", "Off") != "Off":
        spam_keywords = ["crypto", "forex", "invest", "bonus", "t.me/", "http", "promo"]
        if any(w in full_name.lower() for w in spam_keywords):
            await execute_punishment(p["spam"], del_msg, update, context, "Spam Name Block")
            return False

    return True

# ----------------- NEW MEMBER JOIN CHECKS ----------------- #
async def new_member_checks_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    cfg = get_config(chat.id)

    if not cfg.get("check_at_join", True):
        return

    for member in update.message.new_chat_members:
        if member.id == context.bot.id or member.is_bot:
            continue
        await run_user_checks(member, chat, context, is_join=True, update=update)

# ----------------- SECURITY & AUTO MODERATION ----------------- #
async def security_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    chat = update.effective_chat
    user = update.effective_user

    if not await run_user_checks(user, chat, context, is_join=False, update=update):
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

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member_checks_handler))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^pip3?\s+install\s+"), auto_pip_installer))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, security_moderator))

    print("🛡 Group Help Security Bot running with complete Checks Module & SQLite Persistence...")
    app.run_polling()

if __name__ == "__main__":
    main()
