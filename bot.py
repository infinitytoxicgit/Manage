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

    # Captcha System
    "captcha_active": False,
    "captcha_mode": "button",  # "button" or "regulation"
    "captcha_time_val": 180,   # seconds (default 3 min)
    "captcha_time_label": "3 Minutes",
    "captcha_penalty": "Mute",  # "Mute", "Ban", "Kick"
    "captcha_delete_service": False,
    "captcha_custom_text": None,
    "captcha_topic_id": None,
    "captcha_tab": None,       # None, "time", "penalty", "custom"

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
    "welcome_text": "Hello {NAME}, welcome to {GROUPNAME}!",
    "welcome_media_id": None,
    "welcome_media_type": None,
    "welcome_buttons_raw": None,
    "welcome_topic_id": None,

    # Goodbye System
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

    # Security Modules
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

group_settings_cache = {}
admin_cache = {}
user_states = {}
link_drafts = {}
active_created_links = {}
last_welcome_messages = {}
last_goodbye_messages = {}
pending_captchas = {}  # {(chat_id, user_id): {"message_id": id, "expire_time": time, "penalty": str}}
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

# ----------------- CAPTCHA UI & TEXT ENGINE ----------------- #
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

    # Time Accordion Tab
    if tab == "time":
        keyboard.append([create_btn("» 🕒 Time (Minutes) 🕒 «", callback_data=f"cpt_tab_time_{chat_id}", style="primary")])
        # Time Grid Options: 15s, 30s, 1m, 2m, 3m, 5m, 10m, 15m, 20m, 30m
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

    # Penalty Accordion Tab
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

    # Customize Message Accordion Tab
    if tab == "custom":
        keyboard.append([create_btn("» ✍️ Customize message ✍️ «", callback_data=f"cpt_tab_custom_{chat_id}", style="primary")])
        keyboard.append([
            create_btn("📄 Text", callback_data=f"cpt_set_text_{chat_id}"),
            create_btn("👀 See", callback_data=f"cpt_see_text_{chat_id}")
        ])
    else:
        keyboard.append([create_btn("✍️ Customize message ✍️", callback_data=f"cpt_tab_custom_{chat_id}")])

    # Topic & Delete Service Message
    keyboard.append([create_btn("📁 Select a Topic 🆕", callback_data=f"cpt_topic_info_{chat_id}")])
    keyboard.append([create_btn(f"🗑 Delete service message {del_icon}", callback_data=f"cpt_tog_delsvc_{chat_id}")])
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

    if should_delete and msg:
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

    # CAPTCHA USER VERIFICATION BUTTONS (CLICKED BY NEW USERS)
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
        # Unmute User with full permissions
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
            await query.answer("✅ Verification successful! Welcome to the group.", show_alert=True)
            if cfg.get("captcha_delete_service"):
                await query.message.delete()
            else:
                await query.edit_message_text(f"✅ {user.mention_html()} verified successfully!", parse_mode="HTML")
        except Exception:
            pass
        return

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

    # 2. CAPTCHA MODULE ROUTING
    if data.startswith("cfg_view_captcha_"):
        cid = int(data.split("_")[3])
        user_states.pop((cid, user.id), None)
        cfg["captcha_tab"] = None
        save_config(cid, cfg)
        await fast_edit(query, get_captcha_text(cid), get_captcha_keyboard(cid))
        return

    if data.startswith("cpt_toggle_"):
        action = data.split("_")[2]
        cid = int(data.split("_")[3])
        cfg["captcha_active"] = (action == "on")
        cfg["captcha_tab"] = None
        save_config(cid, cfg)
        await fast_edit(query, get_captcha_text(cid), get_captcha_keyboard(cid))
        return

    if data.startswith("cpt_switch_mode_"):
        cid = int(data.split("_")[3])
        cfg["captcha_mode"] = "regulation" if cfg.get("captcha_mode") == "button" else "button"
        save_config(cid, cfg)
        await fast_edit(query, get_captcha_text(cid), get_captcha_keyboard(cid))
        return

    if data.startswith("cpt_tab_"):
        tab_name = data.split("_")[2]
        cid = int(data.split("_")[3])
        cfg["captcha_tab"] = None if cfg.get("captcha_tab") == tab_name else tab_name
        save_config(cid, cfg)
        await fast_edit(query, get_captcha_text(cid), get_captcha_keyboard(cid))
        return

    if data.startswith("cpt_set_t_"):
        parts = data.split("_")
        sec_val, cid = int(parts[3]), int(parts[4])
        cfg["captcha_time_val"] = sec_val
        if sec_val < 60:
            cfg["captcha_time_label"] = f"{sec_val} Seconds"
        else:
            cfg["captcha_time_label"] = f"{sec_val // 60} Minutes"
        save_config(cid, cfg)
        await fast_edit(query, get_captcha_text(cid), get_captcha_keyboard(cid))
        return

    if data.startswith("cpt_set_p_"):
        parts = data.split("_")
        pen_name, cid = parts[3], int(parts[4])
        cfg["captcha_penalty"] = pen_name
        save_config(cid, cfg)
        await fast_edit(query, get_captcha_text(cid), get_captcha_keyboard(cid))
        return

    if data.startswith("cpt_tog_delsvc_"):
        cid = int(data.split("_")[3])
        cfg["captcha_delete_service"] = not cfg.get("captcha_delete_service", False)
        save_config(cid, cfg)
        await fast_edit(query, get_captcha_text(cid), get_captcha_keyboard(cid))
        return

    if data.startswith("cpt_set_text_"):
        cid = int(data.split("_")[3])
        user_states[(cid, user.id)] = "awaiting_cpt_text"
        text = (
            f"{user.mention_html()}, send now the custom message for Captcha!\n\n"
            "You can use <b>HTML</b> and placeholders like {NAME}, {MENTION}, {GROUPNAME}."
        )
        keyboard = [
            [create_btn("🚫 Remove message", callback_data=f"cpt_rem_text_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"cfg_view_captcha_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("cpt_rem_text_"):
        cid = int(data.split("_")[3])
        cfg["captcha_custom_text"] = None
        save_config(cid, cfg)
        await query.answer("Custom Captcha text removed!")
        await fast_edit(query, get_captcha_text(cid), get_captcha_keyboard(cid))
        return

    if data.startswith("cpt_see_text_"):
        cid = int(data.split("_")[3])
        c_text = cfg.get("captcha_custom_text") or "Click the button below to confirm you are human."
        await query.answer(f"Captcha Text:\n{c_text[:200]}", show_alert=True)
        return

    if data.startswith("cpt_topic_info_"):
        cid = int(data.split("_")[3])
        text = (
            "📁 <b>Select a Topic</b>\n"
            "If you use \"Topics\" in your group, you can decide which topic the bot should send this type of message in.\n\n"
            "To do so, go to the chosen Topic and send this command:\n"
            "<code>/topic_captcha</code>\n\n"
            "<i>If you don't use \"Topics\", ignore this setting.</i>"
        )
        keyboard = [[create_btn("⬅️ Back", callback_data=f"cfg_view_captcha_{cid}")]]
        await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    # Fallback / Back to other sections
    if data.startswith("cfg_view_alphabets_") or data.startswith("cfg_view_welcome_") or data.startswith("cfg_view_goodbye_") or data.startswith("cfg_view_reg_") or data.startswith("cfg_view_flood_"):
        cid = int(data.split("_")[3])
        text = f"⚙️ <b>Module Settings</b>\nManage configuration directly from this panel."
        kb = [[create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]]
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

    if state == "awaiting_cpt_text":
        cfg["captcha_custom_text"] = text
        save_config(chat_id, cfg)
        kb = [[create_btn("⬅️ Back to Captcha", callback_data=f"cfg_view_captcha_{chat_id}")]]
        await msg.reply_text("✅ <b>Captcha custom message updated successfully!</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    return False

# ----------------- TOPIC BINDING COMMAND ----------------- #
async def topic_captcha_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message

    if chat.type == "private":
        await msg.reply_text("Yeh command group ke andar run karein.")
        return

    if not await is_user_admin(chat.id, user.id, context):
        await msg.reply_text("❌ Sirf admins topic bind kar sakte hain.")
        return

    # Check if chat actually has forum topics enabled
    is_forum = getattr(chat, 'is_forum', False)
    thread_id = msg.message_thread_id

    if not is_forum and not thread_id:
        text = "<i>There are no Topics in this group. You don't need to select a Topic.</i>"
        await msg.reply_text(text, parse_mode="HTML")
        return

    cfg = get_config(chat.id)
    cfg["captcha_topic_id"] = thread_id
    save_config(chat.id, cfg)
    await msg.reply_text(f"✅ Captcha bound to Topic Thread ID: <code>{thread_id}</code>.", parse_mode="HTML")

# ----------------- CAPTCHA ENFORCEMENT ON JOIN ----------------- #
async def captcha_new_member_enforcer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    cfg = get_config(chat.id)

    if not cfg.get("captcha_active"):
        return

    for member in update.message.new_chat_members:
        if member.id == context.bot.id or member.is_bot:
            continue

        # 1. Restrict user (Mute)
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=member.id,
                permissions=ChatPermissions(can_send_messages=False)
            )
        except Exception as e:
            logger.error(f"Failed to mute new user for captcha: {e}")

        # 2. Build Captcha Prompt
        mode = cfg.get("captcha_mode", "button")
        time_label = cfg.get("captcha_time_label", "3 Minutes")
        time_sec = cfg.get("captcha_time_val", 180)
        thread_id = cfg.get("captcha_topic_id")

        if mode == "button":
            cpt_text = (
                cfg.get("captcha_custom_text") or 
                f"👋 Hello {member.mention_html()}!\n\n"
                "Please press the button below within <b>{time_label}</b> to verify that you are not a robot and unlock sending messages."
            )
            cpt_text = cpt_text.replace("{time_label}", time_label)
            btn_label = "✅ I am not a robot"
        else:
            rules_txt = cfg.get("rules_text", "1. Be respectful\n2. No spam.")
            cpt_text = (
                f"👋 Hello {member.mention_html()}!\n\n"
                f"📜 <b>Group Regulations:</b>\n{rules_txt}\n\n"
                f"Please accept the group regulation within <b>{time_label}</b> to unlock sending messages."
            )
            btn_label = "✅ Accept Regulations"

        kb = [[create_btn(btn_label, callback_data=f"cptsolve_{member.id}_{chat.id}", style="success")]]

        try:
            sent = await chat.send_message(
                cpt_text,
                reply_markup=InlineKeyboardMarkup(kb),
                message_thread_id=thread_id,
                parse_mode="HTML"
            )
            pending_captchas[(chat.id, member.id)] = {
                "message_id": sent.message_id,
                "expire_time": time.time() + time_sec,
                "penalty": cfg.get("captcha_penalty", "Mute"),
                "del_service": cfg.get("captcha_delete_service", False)
            }
        except Exception as e:
            logger.error(f"Error sending captcha message: {e}")

# ----------------- CAPTCHA TIMEOUT MONITOR JOB ----------------- #
async def captcha_timeout_checker(context: ContextTypes.DEFAULT_TYPE):
    now = time.time()
    expired = []

    for (cid, uid), info in list(pending_captchas.items()):
        if now >= info["expire_time"]:
            expired.append(((cid, uid), info))

    for (cid, uid), info in expired:
        pending_captchas.pop((cid, uid), None)
        penalty = info["penalty"]

        # Delete Captcha Prompt if configured
        if info["del_service"]:
            try:
                await context.bot.delete_message(chat_id=cid, message_id=info["message_id"])
            except Exception:
                pass

        # Execute Penalty
        try:
            if penalty == "Ban":
                await context.bot.ban_chat_member(chat_id=cid, user_id=uid)
                await context.bot.send_message(chat_id=cid, text=f"🚫 User <a href='tg://user?id={uid}'>{uid}</a> banned for failing Captcha.", parse_mode="HTML")
            elif penalty == "Kick":
                await context.bot.unban_chat_member(chat_id=cid, user_id=uid)
                await context.bot.send_message(chat_id=cid, text=f"👞 User <a href='tg://user?id={uid}'>{uid}</a> kicked for failing Captcha.", parse_mode="HTML")
            elif penalty == "Mute":
                # Already muted
                await context.bot.send_message(chat_id=cid, text=f"🔇 User <a href='tg://user?id={uid}'>{uid}</a> remains muted for failing Captcha.", parse_mode="HTML")
        except Exception as e:
            logger.error(f"Timeout penalty error: {e}")

# ----------------- SYSTEM & COMMANDS ----------------- #
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

# ----------------- SECURITY & AUTO MODERATION ----------------- #
async def security_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    if await interactive_state_processor(update, context):
        return

# ----------------- MAIN INITIALIZER ----------------- #
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).build()

    # Recurring Job for Captcha Timeout Enforcement
    if app.job_queue:
        app.job_queue.run_repeating(captcha_timeout_checker, interval=5, first=5)

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("update", update_command))
    app.add_handler(CommandHandler("topic_captcha", topic_captcha_command))

    # Single Fast Router
    app.add_handler(CallbackQueryHandler(unified_callback_handler))

    # Handlers
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, captcha_new_member_enforcer))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^pip3?\s+install\s+"), auto_pip_installer))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, security_moderator))

    print("🛡 Group Help Security Bot running with complete Captcha System & SQLite persistence...")
    app.run_polling()

if __name__ == "__main__":
    main()
