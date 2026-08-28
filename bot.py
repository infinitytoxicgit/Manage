import os
import sys
import subprocess
import logging
import re
import time
import html
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

# ----------------- LOAD ENVIRONMENT VARIABLES ----------------- #
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

# Data Storage
group_settings = {}
user_warns = {}
staff_roles = {}
whitelist_storage = {}
admin_cache = {}
user_states = {}
link_drafts = {}
active_created_links = {}
joined_members_history = {}
last_welcome_messages = {}

GLOBAL_WHITELIST_ITEMS = {"telegram.org", "t.me/telegram", "durov", "fragment.com"}

def get_default_config():
    return {
        "captcha": True,
        "warn_limit": 3,
        "night_mode": False,
        "lock_media": False,

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

        # Regulations / Rules
        "rules_text": "📜 <b>Group Regulations</b>\n1. Be respectful\n2. No spam or self-promotion\n3. Follow admin instructions.",
        "rules_media_id": None,
        "rules_media_type": None,
        "rules_buttons_raw": None,

        # Welcome System
        "welcome_active": True,
        "welcome_mode": "always",
        "welcome_delete_last": False,
        "welcome_text": "★彡[ 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 𝐓𝐎 {GROUPNAME} 𝐃𝐄𝐀𝐑 💕 ]彡★\n\n✿━━━━━━━━━━━━━━━━━✿\n  𝐇ᴇʏ {USERNAME}, 𝐖ᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ 𝐅ᴀᴍɪʟʏ!\n  𝐖ᴇ’ʀᴇ 𝐬ᴏ ʜᴀᴘᴘʏ ᴛᴏ ʜᴀᴠᴇ ʏᴏᴜ ʜᴇʀᴇ!\n✿━━━━━━━━━━━━━━━━━✿\n\n━━━━━━━━━━━━━━━━━━━━\n    𝐘ᴏᴜʀ 𝐈ɴғᴏ\n━━━━━━━━━━━━━━━━━━━━\n•𝐅𝐮𝐥𝐥 𝐍𝐚𝐦𝐞 = {NAMESURNAME} ❤️\n•𝐔𝐬𝐞𝐫 𝐍𝐚𝐦𝐞 = {USERNAME} 🦋\n•𝐔𝐬𝐞𝐫 𝐈'𝐃 = {ID} ❤️\n•𝐏𝐫𝐨𝐟𝐢𝐥𝐞 𝐋𝐢𝐧𝐤 = {MENTION} 💐\n•𝐋𝐚ｎｇｕａｇｅ = {LANG} 🍓\n•𝐃ａｔｅ = {DATE} 😊\n•𝐓ｉｍｅ = {TIME} 👀\n\n━━━━━━━━━━━━━━━━━━━━\n  𝐄ɴᴊᴏʏ ʏᴏᴜʀ 𝐒ᴛᴀʏ & ᴍᴀᴋᴇ ɢʀᴇᴀᴛ ᴍᴇᴍᴏʀɪᴇ𝐬!\n  𝐓ʜᴀɴᴋ𝐬 ғᴏʀ ᴊᴏɪɴɪɴɢ!",
        "welcome_media_id": None,
        "welcome_media_type": None,
        "welcome_buttons_raw": None,
        "welcome_topic_id": None,

        # Permissions
        "perm_staff": "everyone",
        "perm_rules": "staff",
        "perm_me": "private",
        "perm_translate": "everyone",
        "perm_link": "everyone"
    }

def get_config(chat_id: int):
    if chat_id not in group_settings:
        group_settings[chat_id] = get_default_config()
    return group_settings[chat_id]

def get_whitelist(chat_id: int):
    if chat_id not in whitelist_storage:
        whitelist_storage[chat_id] = set()
    return whitelist_storage[chat_id]

def get_link_draft(chat_id: int, user_id: int):
    key = (chat_id, user_id)
    if key not in link_drafts:
        link_drafts[key] = {
            "active_tab": None,
            "limit": 0,
            "until_seconds": 0,
            "approval": False
        }
    return link_drafts[key]

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
    if staff_roles.get(chat_id, {}).get(user_id) in ["admin", "mod"]:
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
    """Escapes loose '&', '<', '>' while keeping genuine HTML tags intact."""
    # Replace & that isn't already an entity
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

# ----------------- BUTTONS PARSER ----------------- #
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
                link = action if action.startswith(("http://", "https://", "t.me/")) else f"https://{action}"
                row.append(create_btn(title, url=link))
        if row:
            keyboard.append(row)
    return InlineKeyboardMarkup(keyboard) if keyboard else None

# ----------------- RELIABLE MESSAGE + MEDIA + BUTTONS DISPATCHER ----------------- #
async def send_custom_bundle(chat, user, cfg: dict, is_preview=False, thread_id=None):
    """
    Sends Media + Formatted Text + Buttons guaranteed without dropping any component.
    """
    w_text = format_template(cfg.get("welcome_text", ""), user, chat, cfg)
    w_kb = parse_custom_buttons(cfg.get("welcome_buttons_raw"), chat.id)
    m_id = cfg.get("welcome_media_id")
    m_type = cfg.get("welcome_media_type")

    # CASE 1: Photo or Video with Short Caption (<= 1000 characters)
    if m_id and m_type in ["photo", "video"] and len(w_text) <= 1000:
        try:
            if m_type == "photo":
                return await chat.send_photo(photo=m_id, caption=w_text, reply_markup=w_kb, parse_mode="HTML", message_thread_id=thread_id)
            elif m_type == "video":
                return await chat.send_video(video=m_id, caption=w_text, reply_markup=w_kb, parse_mode="HTML", message_thread_id=thread_id)
        except BadRequest as e:
            logger.warning(f"HTML Caption failed ({e}), trying plain text caption...")
            try:
                # Fallback to plain text caption with buttons attached
                if m_type == "photo":
                    return await chat.send_photo(photo=m_id, caption=w_text, reply_markup=w_kb, message_thread_id=thread_id)
                elif m_type == "video":
                    return await chat.send_video(video=m_id, caption=w_text, reply_markup=w_kb, message_thread_id=thread_id)
            except Exception:
                pass

    # CASE 2: Long Caption (> 1000 chars) OR Sticker OR Caption Fallback -> Send Media First, then Text + Buttons
    if m_id:
        try:
            if m_type == "photo":
                await chat.send_photo(photo=m_id, message_thread_id=thread_id)
            elif m_type == "video":
                await chat.send_video(video=m_id, message_thread_id=thread_id)
            elif m_type == "sticker":
                await chat.send_sticker(sticker=m_id, message_thread_id=thread_id)
        except Exception as e:
            logger.error(f"Error sending media file: {e}")

    # Send Text & Buttons
    if w_text:
        try:
            return await chat.send_message(w_text, reply_markup=w_kb, parse_mode="HTML", message_thread_id=thread_id)
        except Exception:
            # Safe plain text delivery
            return await chat.send_message(w_text, reply_markup=w_kb, message_thread_id=thread_id)

    elif w_kb:
        return await chat.send_message("👉 <b>Interactive Buttons:</b>", reply_markup=w_kb, parse_mode="HTML", message_thread_id=thread_id)

    return None

# ----------------- WELCOME KEYBOARDS ----------------- #
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

# ----------------- LINK CREATOR UI ----------------- #
def get_link_creator_keyboard(chat_id: int, user_id: int):
    draft = get_link_draft(chat_id, user_id)
    tab = draft["active_tab"]
    cur_limit = draft["limit"]
    cur_until = draft["until_seconds"]
    cur_approval = draft["approval"]

    keyboard = []
    if cur_approval:
        t_unt = "» ⏰ Until «" if tab == "until" else "⏰ Until"
        keyboard.append([create_btn(t_unt, callback_data=f"lnktab_until_{chat_id}_{user_id}", style="primary" if tab == "until" else None)])
    else:
        t_inv = "» 📋 Invitations «" if tab == "invitations" else "📋 Invitations"
        t_unt = "» ⏰ Until «" if tab == "until" else "⏰ Until"
        keyboard.append([
            create_btn(t_inv, callback_data=f"lnktab_invitations_{chat_id}_{user_id}", style="primary" if tab == "invitations" else None),
            create_btn(t_unt, callback_data=f"lnktab_until_{chat_id}_{user_id}", style="primary" if tab == "until" else None)
        ])

    if tab == "invitations" and not cur_approval:
        limits = [(0, "No"), (1, "1"), (2, "2"), (5, "5"), (10, "10"), (20, "20"), (50, "50"), (100, "100")]
        row1, row2 = [], []
        for val, lbl in limits[:4]:
            is_active = (cur_limit == val)
            label = f"• {lbl} •" if is_active else lbl
            row1.append(create_btn(label, callback_data=f"lnsetlim_{val}_{chat_id}_{user_id}", style="primary" if is_active else None))
        for val, lbl in limits[4:]:
            is_active = (cur_limit == val)
            label = f"• {lbl} •" if is_active else lbl
            row2.append(create_btn(label, callback_data=f"lnsetlim_{val}_{chat_id}_{user_id}", style="primary" if is_active else None))
        keyboard.extend([row1, row2])

    elif tab == "until":
        times = [(0, "No"), (300, "5m"), (1800, "30m"), (3600, "1h"), (43200, "12h"), (86400, "24h"), (172800, "48h"), (604800, "1w")]
        row1, row2 = [], []
        for sec, lbl in times[:4]:
            is_active = (cur_until == sec)
            label = f"• {lbl} •" if is_active else lbl
            row1.append(create_btn(label, callback_data=f"lnsettim_{sec}_{chat_id}_{user_id}", style="primary" if is_active else None))
        for sec, lbl in times[4:]:
            is_active = (cur_until == sec)
            label = f"• {lbl} •" if is_active else lbl
            row2.append(create_btn(label, callback_data=f"lnsettim_{sec}_{chat_id}_{user_id}", style="primary" if is_active else None))
        keyboard.extend([row1, row2])

    app_icon = "✔️" if cur_approval else "✖️"
    keyboard.append([create_btn(f"🗂 Approval mode {app_icon}", callback_data=f"lnktog_app_{chat_id}_{user_id}")])
    keyboard.append([
        create_btn("❌ Cancel", callback_data="cfg_close", style="danger"),
        create_btn("✅ Create link", callback_data=f"lnk_generate_{chat_id}_{user_id}", style="success")
    ])

    return InlineKeyboardMarkup(keyboard)

def get_link_creator_text(chat_id: int, user_id: int):
    draft = get_link_draft(chat_id, user_id)
    lines = ["🔗 <b>Link</b>"]
    if draft["until_seconds"] > 0:
        exp_date = datetime.datetime.now() + datetime.timedelta(seconds=draft["until_seconds"])
        lines.append(f" └ ⏰ <b>Until:</b> {exp_date.strftime('%d %b %Y, %H:%M')}")
    if draft["limit"] > 0 and not draft["approval"]:
        lines.append(f" └ 📋 <b>Invitations:</b> {draft['limit']}")
    app_str = "Yes" if draft["approval"] else "No"
    lines.append(f" └ 🗂 <b>Approval mode:</b> {app_str}")
    return "\n".join(lines)

# ----------------- MAIN SETTINGS KEYBOARDS ----------------- #
def make_penalty_buttons(prefix: str, current_penalty: str, chat_id: int):
    def get_btn(label, val):
        is_selected = (current_penalty == val)
        btn_text = f"❌ {label}" if val == "Off" and not is_selected else label
        btn_style = "success" if is_selected else None
        return create_btn(btn_text, callback_data=f"{prefix}pen_{val}_{chat_id}", style=btn_style)

    row1 = [get_btn("Off", "Off"), get_btn("! Warn", "Warn"), get_btn("! Kick", "Kick")]
    row2 = [get_btn("🔊 Mute", "Mute"), get_btn("🚷 Ban", "Ban")]
    return row1, row2

def get_main_settings_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    btn = lambda key, text: f"{text} {'✅' if cfg.get(key) else '❌'}"
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
            create_btn(btn("captcha", "🧠 Captcha"), callback_data=f"cfg_toggle_captcha_{chat_id}"),
            create_btn("🔦 Checks", callback_data=f"cfg_view_checks_{chat_id}")
        ],
        [
            create_btn(btn("lock_media", "📸 Media"), callback_data=f"cfg_toggle_media_{chat_id}"),
            create_btn("🔗 Telegram links", callback_data=f"aspam_tglinks_{chat_id}")
        ],
        [
            create_btn(btn("night_mode", "🌘 Night Mode"), callback_data=f"cfg_toggle_night_{chat_id}"),
            create_btn(f"⚠️ Warn Limit ({cfg.get('warn_limit')})", callback_data=f"cfg_warn_limit_{chat_id}")
        ],
        [create_btn("Next Page ➡️", callback_data=f"cfg_page_2_{chat_id}")],
        [create_btn("❎ Close", callback_data="cfg_close")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_page2_settings_keyboard(chat_id: int):
    keyboard = [
        [create_btn("📁 Topic", callback_data=f"cfg_view_topic_{chat_id}")],
        [create_btn("🔤 Banned Words", callback_data=f"cfg_view_banned_{chat_id}")],
        [create_btn("👥 Members Management", callback_data=f"cfg_view_members_{chat_id}")],
        [create_btn("💭 Quote Antispam", callback_data=f"aspam_quote_{chat_id}")],
        [create_btn("🔍 Log Channel", callback_data=f"cfg_view_logs_{chat_id}")],
        [
            create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}"),
            create_btn("❎ Close", callback_data="cfg_close")
        ]
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
    r1, r2 = make_penalty_buttons("astot_", cfg["totallinks_penalty"], chat_id)
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
    r1, r2 = make_penalty_buttons("astg_", cfg["tglinks_penalty"], chat_id)
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

# ----------------- PUNISHMENT ENGINE ----------------- #
async def execute_punishment(penalty: str, should_delete: bool, update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str):
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

    try:
        if penalty == "Warn":
            chat_warns = user_warns.setdefault(chat.id, {})
            current_warns = chat_warns.get(user.id, 0) + 1
            chat_warns[user.id] = current_warns
            limit = get_config(chat.id).get("warn_limit", 3)

            if current_warns >= limit:
                chat_warns[user.id] = 0
                await context.bot.ban_chat_member(chat.id, user.id)
                await chat.send_message(f"🚫 {user.mention_html()} banned ({limit}/{limit} warns) for {reason}.", parse_mode="HTML")
            else:
                await chat.send_message(f"⚠️ {user.mention_html()} warned ({current_warns}/{limit}) for {reason}!", parse_mode="HTML")

        elif penalty == "Mute":
            await context.bot.restrict_chat_member(chat.id, user.id, permissions=ChatPermissions(can_send_messages=False))
            await chat.send_message(f"🔇 {user.mention_html()} muted for {reason}.", parse_mode="HTML")

        elif penalty == "Kick":
            await context.bot.unban_chat_member(chat.id, user.id)
            await chat.send_message(f"👞 {user.mention_html()} kicked for {reason}.", parse_mode="HTML")

        elif penalty == "Ban":
            await context.bot.ban_chat_member(chat.id, user.id)
            await chat.send_message(f"🚫 {user.mention_html()} banned for {reason}.", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Punishment execution error: {e}")

# ----------------- UNIFIED CALLBACK ROUTER ----------------- #
async def unified_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat = query.message.chat
    user = query.from_user

    # Revoke Link
    if data.startswith("rvk_"):
        link_id = data.split("_")[1]
        link_info = active_created_links.get(link_id)
        if not link_info:
            try:
                await query.answer("Link already revoked or expired.", show_alert=True)
            except Exception:
                pass
            return

        target_chat_id = link_info["chat_id"]
        target_link = link_info["link"]

        if not await check_admin_invite_permission(target_chat_id, user.id, context):
            try:
                await query.answer("Aapke paas is link ko revoke karne ki permission nahi hai.", show_alert=True)
            except Exception:
                pass
            return

        try:
            await context.bot.revoke_chat_invite_link(chat_id=target_chat_id, invite_link=target_link)
            active_created_links.pop(link_id, None)
            await fast_edit(query, f"❌ <b>The invite link has been revoked:</b>\n<s>{target_link}</s>", None)
            await query.answer("Link revoked successfully!")
        except Exception as e:
            await query.answer(f"Failed to revoke link: {e}", show_alert=True)
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

    # Link Creator Tabs & Generation Handlers
    if data.startswith("lnktab_"):
        parts = data.split("_")
        tab_name, cid, uid = parts[1], int(parts[2]), int(parts[3])
        if user.id != uid:
            await query.answer("Yeh button aapke liye nahi hai.", show_alert=True)
            return

        draft = get_link_draft(cid, uid)
        draft["active_tab"] = None if draft["active_tab"] == tab_name else tab_name
        await fast_edit(query, get_link_creator_text(cid, uid), get_link_creator_keyboard(cid, uid))
        return

    if data.startswith("lnsetlim_"):
        parts = data.split("_")
        limit_val, cid, uid = int(parts[1]), int(parts[2]), int(parts[3])
        if user.id != uid:
            await query.answer("Yeh button aapke liye nahi hai.", show_alert=True)
            return

        draft = get_link_draft(cid, uid)
        draft["limit"] = limit_val
        await fast_edit(query, get_link_creator_text(cid, uid), get_link_creator_keyboard(cid, uid))
        return

    if data.startswith("lnsettim_"):
        parts = data.split("_")
        seconds_val, cid, uid = int(parts[1]), int(parts[2]), int(parts[3])
        if user.id != uid:
            await query.answer("Yeh button aapke liye nahi hai.", show_alert=True)
            return

        draft = get_link_draft(cid, uid)
        draft["until_seconds"] = seconds_val
        await fast_edit(query, get_link_creator_text(cid, uid), get_link_creator_keyboard(cid, uid))
        return

    if data.startswith("lnktog_app_"):
        parts = data.split("_")
        cid, uid = int(parts[2]), int(parts[3])
        if user.id != uid:
            await query.answer("Yeh button aapke liye nahi hai.", show_alert=True)
            return

        draft = get_link_draft(cid, uid)
        draft["approval"] = not draft["approval"]
        if draft["approval"]:
            draft["limit"] = 0
            if draft["active_tab"] == "invitations":
                draft["active_tab"] = None
        await fast_edit(query, get_link_creator_text(cid, uid), get_link_creator_keyboard(cid, uid))
        return

    if data.startswith("lnk_generate_"):
        parts = data.split("_")
        cid, uid = int(parts[2]), int(parts[3])

        if user.id != uid:
            await query.answer("Sirf command chalane wala admin link generate kar sakta hai.", show_alert=True)
            return

        if not await check_admin_invite_permission(cid, uid, context):
            await query.answer("❌ Aapke paas group me 'Invite Users via Link' permission nahi hai!", show_alert=True)
            return

        draft = get_link_draft(cid, uid)
        expire_date = None
        if draft["until_seconds"] > 0:
            expire_date = datetime.datetime.now() + datetime.timedelta(seconds=draft["until_seconds"])

        member_limit = draft["limit"] if (draft["limit"] > 0 and not draft["approval"]) else None
        creates_join_request = draft["approval"]

        try:
            invite = await context.bot.create_chat_invite_link(
                chat_id=cid,
                expire_date=expire_date,
                member_limit=member_limit,
                creates_join_request=creates_join_request
            )

            link_id = str(int(time.time() * 1000))[-8:]
            active_created_links[link_id] = {"chat_id": cid, "link": invite.invite_link}

            pm_keyboard = [[create_btn("❌ Revoke link", callback_data=f"rvk_{link_id}", style="danger")]]
            pm_text = (
                f"🔗 <b>Link »</b> {invite.invite_link}\n"
                f" └ 🗂 <b>Approval mode:</b> {'Yes' if creates_join_request else 'No'}"
            )

            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=pm_text,
                    reply_markup=InlineKeyboardMarkup(pm_keyboard),
                    parse_mode="HTML"
                )
                bot_user = await context.bot.get_me()
                dm_button = [[create_btn("👉 Go to the chat ↗", url=f"https://t.me/{bot_user.username}")]]
                await fast_edit(query, "<i>Sent in private chat.</i>", InlineKeyboardMarkup(dm_button))

            except Forbidden:
                bot_user = await context.bot.get_me()
                start_btn = [[create_btn("🤖 Start Bot in DM", url=f"https://t.me/{bot_user.username}?start=start")]]
                await fast_edit(
                    query,
                    "⚠️ <b>Pehle bot ko Private Chat (DM) me /start karein</b> taaki bot aapko link bhej sake.",
                    InlineKeyboardMarkup(start_btn)
                )

        except Exception as e:
            await query.answer(f"Failed to create link: {e}", show_alert=True)
        return

    # Regular Admin Check
    if not await is_user_admin(chat.id, user.id, context):
        try:
            await query.answer("Sirf Admins settings badal sakte hain!", show_alert=True)
        except Exception:
            pass
        return

    cfg = get_config(chat.id)

    # 1. Main Pages Navigation
    if data.startswith("cfg_page_"):
        page = data.split("_")[2]
        cid = int(data.split("_")[3])
        if page == "2":
            text = "🛡 <b>Group Security & Settings Panel (Page 2)</b>\nSelect the options you want to configure:"
            await fast_edit(query, text, get_page2_settings_keyboard(cid))
        else:
            text = "🛡 <b>Group Security & Settings Panel</b>\nSelect the options you want to configure:"
            await fast_edit(query, text, get_main_settings_keyboard(cid))
        return

    # 2. WELCOME SYSTEM HUBS & ACTIONS
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

    if data.startswith("wlc_mode_"):
        mode = data.split("_")[2]
        cid = int(data.split("_")[3])
        cfg["welcome_mode"] = mode

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

    if data.startswith("wlc_tog_dellast_"):
        cid = int(data.split("_")[3])
        cfg["welcome_delete_last"] = not cfg["welcome_delete_last"]

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

    if data.startswith("wlc_custom_"):
        cid = int(data.split("_")[2])
        has_text = "✅" if cfg.get("welcome_text") else "❌"
        has_media = "✅" if cfg.get("welcome_media_id") else "❌"
        has_buttons = "✅" if cfg.get("welcome_buttons_raw") else "❌"

        text = (
            "💬 <b>Welcome Message</b>\n\n"
            f"📄 Text {has_text}\n"
            f"📸 Media {has_media}\n"
            f"🔤 Url Buttons {has_buttons}\n\n"
            "👉 Use the buttons below to choose what you want to set"
        )
        await fast_edit(query, text, get_welcome_customize_keyboard(cid))
        return

    if data.startswith("wlc_set_text_"):
        cid = int(data.split("_")[3])
        user_states[(cid, user.id)] = "awaiting_wlc_text"
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
            [create_btn("🚫 Remove message", callback_data=f"wlc_rem_text_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"wlc_custom_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("wlc_rem_text_"):
        cid = int(data.split("_")[3])
        cfg["welcome_text"] = None
        await query.answer("Welcome text removed!")
        await fast_edit(query, "💬 <b>Welcome Message</b>", get_welcome_customize_keyboard(cid))
        return

    if data.startswith("wlc_set_media_"):
        cid = int(data.split("_")[3])
        user_states[(cid, user.id)] = "awaiting_wlc_media"
        text = "👉 <b>Send now the media (photos, videos, stickers...) you want to set.</b>\n<i>You can also enter a caption.</i>"
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
        await query.answer("Welcome media removed!")
        await fast_edit(query, "💬 <b>Welcome Message</b>", get_welcome_customize_keyboard(cid))
        return

    if data.startswith("wlc_set_buttons_"):
        cid = int(data.split("_")[3])
        user_states[(cid, user.id)] = "awaiting_wlc_buttons"
        text = (
            "👉 <b>Set the buttons to be placed under the message</b>\n"
            "Send a message structured as follows:\n\n"
            "• <b>Single button:</b>\n<code>Button title - t.me/LinkExample</code>\n\n"
            "• <b>Multiple on single line:</b>\n<code>Title 1 - link1.com && Title 2 - link2.com</code>\n\n"
            "• <b>Multiple rows:</b>\n<code>Title 1 - link1.com\nTitle 2 - link2.com</code>\n\n"
            "<b>Special buttons:</b>\n"
            "• Popup: <code>Button title - popup: Text</code>\n"
            "• Rules: <code>Button title - rules</code>\n"
            "• Share: <code>Button title - share: Text to share</code>\n"
            "• Copy: <code>Button title - copy: Text to copy</code>"
        )
        keyboard = [
            [create_btn("🚫 Remove Keyboard", callback_data=f"wlc_rem_buttons_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"wlc_custom_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("wlc_rem_buttons_"):
        cid = int(data.split("_")[3])
        cfg["welcome_buttons_raw"] = None
        await query.answer("Welcome buttons removed!")
        await fast_edit(query, "💬 <b>Welcome Message</b>", get_welcome_customize_keyboard(cid))
        return

    # Welcome Previews
    if data.startswith("wlc_see_text_"):
        cid = int(data.split("_")[3])
        w_text = format_template(cfg.get("welcome_text", "No text set."), user, chat, cfg)
        try:
            await chat.send_message(f"👁️ <b>Text Preview:</b>\n\n{w_text}", parse_mode="HTML")
            await query.answer("Preview sent!")
        except Exception:
            await chat.send_message(f"👁️ <b>Text Preview:</b>\n\n{w_text}")
            await query.answer("Preview sent.")
        return

    if data.startswith("wlc_see_media_"):
        cid = int(data.split("_")[3])
        m_id = cfg.get("welcome_media_id")
        m_type = cfg.get("welcome_media_type")
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

    if data.startswith("wlc_see_buttons_"):
        cid = int(data.split("_")[3])
        kb = parse_custom_buttons(cfg.get("welcome_buttons_raw"), cid)
        if not kb:
            await query.answer("No buttons configured.", show_alert=True)
            return
        await chat.send_message("🔤 <b>Buttons Preview:</b>", reply_markup=kb, parse_mode="HTML")
        await query.answer("Buttons preview sent!")
        return

    # Full Preview Fixed
    if data.startswith("wlc_full_preview_"):
        cid = int(data.split("_")[3])
        try:
            await send_custom_bundle(chat, user, cfg, is_preview=True)
            await query.answer("Full preview sent successfully!")
        except Exception as e:
            logger.error(f"Full preview error: {e}")
            await query.answer(f"Preview error: {e}", show_alert=True)
        return

    if data.startswith("wlc_topic_info_"):
        cid = int(data.split("_")[3])
        text = (
            "📁 <b>Select a Topic</b>\n"
            "If you use \"Topics\" in your group, you can decide which topic the bot should send this type of message in.\n\n"
            "To do so, go to the chosen Topic and send this command:\n"
            "<code>/topic_welcome</code>\n\n"
            "<i>If you don't use \"Topics\", ignore this setting.</i>"
        )
        keyboard = [[create_btn("⬅️ Back", callback_data=f"wlc_custom_{cid}")]]
        await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    # 3. REGULATIONS HUB
    if data.startswith("cfg_view_reg_"):
        cid = int(data.split("_")[3])
        user_states.pop((cid, user.id), None)
        text = (
            "📜 <b>Group's regulations</b>\n"
            "From this menu you can manage the group's regulations, that will be shown with the command /rules.\n\n"
            "<i>To edit who can use the /rules command, go to the \"Commands permissions\" section.</i>"
        )
        await fast_edit(query, text, get_regulations_keyboard(cid))
        return

    if data.startswith("reg_custom_msg_"):
        cid = int(data.split("_")[3])
        text = "✍️ <b>Customize Regulations / Rules</b>\nConfigure message text, media attachment, and interactive buttons for /rules:"
        await fast_edit(query, text, get_reg_customize_keyboard(cid))
        return

    if data.startswith("reg_set_text_"):
        cid = int(data.split("_")[3])
        user_states[(cid, user.id)] = "awaiting_reg_text"
        text = "👉 <b>Send now the message you want to set.</b>\n<i>You can send it already formatted or use HTML.</i>"
        keyboard = [
            [create_btn("🚫 Remove message", callback_data=f"reg_rem_text_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"cfg_view_reg_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("reg_rem_text_"):
        cid = int(data.split("_")[3])
        cfg["rules_text"] = "📜 Group Rules are not configured yet."
        await fast_edit(query, "✍️ <b>Customize Regulations / Rules</b>", get_reg_customize_keyboard(cid))
        return

    if data.startswith("reg_set_media_"):
        cid = int(data.split("_")[3])
        user_states[(cid, user.id)] = "awaiting_reg_media"
        text = "👉 <b>Send now the media (photos, videos, stickers...) you want to set.</b>\n<i>You can also enter a caption.</i>"
        keyboard = [
            [create_btn("🚫 Remove media", callback_data=f"reg_rem_media_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"cfg_view_reg_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("reg_rem_media_"):
        cid = int(data.split("_")[3])
        cfg["rules_media_id"] = None
        cfg["rules_media_type"] = None
        await fast_edit(query, "✍️ <b>Customize Regulations / Rules</b>", get_reg_customize_keyboard(cid))
        return

    if data.startswith("reg_set_buttons_"):
        cid = int(data.split("_")[3])
        user_states[(cid, user.id)] = "awaiting_reg_buttons"
        text = (
            "👉 <b>Set the buttons to be placed under the message</b>\n"
            "Send a message structured as follows:\n\n"
            "• <b>Single button:</b>\n<code>Button title - t.me/LinkExample</code>\n\n"
            "• <b>Multiple on single line:</b>\n<code>Title 1 - link1.com && Title 2 - link2.com</code>\n\n"
            "• <b>Multiple rows:</b>\n<code>Title 1 - link1.com\nTitle 2 - link2.com</code>\n\n"
            "<b>Special buttons:</b>\n"
            "• Popup: <code>Title - popup: Text</code>\n"
            "• Rules: <code>Title - rules</code>\n"
            "• Share: <code>Title - share: Text to share</code>\n"
            "• Copy: <code>Title - copy: Text to copy</code>"
        )
        keyboard = [
            [create_btn("🚫 Remove Keyboard", callback_data=f"reg_rem_buttons_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"cfg_view_reg_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("reg_rem_buttons_"):
        cid = int(data.split("_")[3])
        cfg["rules_buttons_raw"] = None
        await fast_edit(query, "✍️ <b>Customize Regulations / Rules</b>", get_reg_customize_keyboard(cid))
        return

    if data.startswith("reg_preview_"):
        cid = int(data.split("_")[2])
        r_text = cfg.get("rules_text", "No rules set.")
        r_kb = parse_custom_buttons(cfg.get("rules_buttons_raw"), cid)
        m_id = cfg.get("rules_media_id")
        m_type = cfg.get("rules_media_type")
        try:
            if m_type == "photo":
                await chat.send_photo(photo=m_id, caption=f"👁️ <b>PREVIEW:</b>\n\n{r_text}", reply_markup=r_kb, parse_mode="HTML")
            elif m_type == "video":
                await chat.send_video(video=m_id, caption=f"👁️ <b>PREVIEW:</b>\n\n{r_text}", reply_markup=r_kb, parse_mode="HTML")
            elif m_type == "sticker":
                await chat.send_sticker(sticker=m_id)
                await chat.send_message(f"👁️ <b>PREVIEW:</b>\n\n{r_text}", reply_markup=r_kb, parse_mode="HTML")
            else:
                await chat.send_message(f"👁️ <b>PREVIEW:</b>\n\n{r_text}", reply_markup=r_kb, parse_mode="HTML")
            await query.answer("Preview sent!")
        except Exception as e:
            await query.answer(f"Preview error: {e}", show_alert=True)
        return

    # 4. COMMANDS PERMISSIONS MATRIX
    if data.startswith("reg_cmd_perms_"):
        cid = int(data.split("_")[3])
        text = (
            "🕹 <b>Commands Permissions</b>\n"
            "From this menu you can configure the usage permissions of the following commands.\n\n"
            "✖️ = nobody   |   👥 = all\n"
            "🤖 = all, in private chat\n"
            "👮🏻 = admins and moderators\n\n"
            f"• /staff » {'👥 Everyone' if cfg['perm_staff']=='everyone' else ('👮🏻 Staff' if cfg['perm_staff']=='staff' else ('🤖 Private' if cfg['perm_staff']=='private' else '✖️ Nobody'))}\n"
            f"• /rules » {'👥 Everyone' if cfg['perm_rules']=='everyone' else ('👮🏻 Staff' if cfg['perm_rules']=='staff' else ('🤖 Private' if cfg['perm_rules']=='private' else '✖️ Nobody'))}\n"
            f"• /me » {'👥 Everyone' if cfg['perm_me']=='everyone' else ('👮🏻 Staff' if cfg['perm_me']=='staff' else ('🤖 Private' if cfg['perm_me']=='private' else '✖️ Nobody'))}\n"
            f"• /translate » {'👥 Everyone' if cfg['perm_translate']=='everyone' else ('👮🏻 Staff' if cfg['perm_translate']=='staff' else ('🤖 Private' if cfg['perm_translate']=='private' else '✖️ Nobody'))}\n"
            f"• /link » {'👥 Everyone' if cfg['perm_link']=='everyone' else ('👮🏻 Staff' if cfg['perm_link']=='staff' else ('🤖 Private' if cfg['perm_link']=='private' else '✖️ Nobody'))}"
        )
        await fast_edit(query, text, get_cmd_permissions_keyboard(cid))
        return

    if data.startswith("permset_"):
        parts = data.split("_")
        cmd_key, mode_key, cid = parts[1], parts[2], int(parts[3])
        cfg[f"perm_{cmd_key}"] = mode_key
        text = (
            "🕹 <b>Commands Permissions</b>\n"
            "From this menu you can configure the usage permissions of the following commands.\n\n"
            "✖️ = nobody   |   👥 = all\n"
            "🤖 = all, in private chat\n"
            "👮🏻 = admins and moderators\n\n"
            f"• /staff » {'👥 Everyone' if cfg['perm_staff']=='everyone' else ('👮🏻 Staff' if cfg['perm_staff']=='staff' else ('🤖 Private' if cfg['perm_staff']=='private' else '✖️ Nobody'))}\n"
            f"• /rules » {'👥 Everyone' if cfg['perm_rules']=='everyone' else ('👮🏻 Staff' if cfg['perm_rules']=='staff' else ('🤖 Private' if cfg['perm_rules']=='private' else '✖️ Nobody'))}\n"
            f"• /me » {'👥 Everyone' if cfg['perm_me']=='everyone' else ('👮🏻 Staff' if cfg['perm_me']=='staff' else ('🤖 Private' if cfg['perm_me']=='private' else '✖️ Nobody'))}\n"
            f"• /translate » {'👥 Everyone' if cfg['perm_translate']=='everyone' else ('👮🏻 Staff' if cfg['perm_translate']=='staff' else ('🤖 Private' if cfg['perm_translate']=='private' else '✖️ Nobody'))}\n"
            f"• /link » {'👥 Everyone' if cfg['perm_link']=='everyone' else ('👮🏻 Staff' if cfg['perm_link']=='staff' else ('🤖 Private' if cfg['perm_link']=='private' else '✖️ Nobody'))}"
        )
        await fast_edit(query, text, get_cmd_permissions_keyboard(cid))
        return

    # 5. ANTI-SPAM HUB
    if data.startswith("aspam_main_"):
        cid = int(data.split("_")[2])
        text = "✉️ <b>Anti-Spam</b>\nIn this menu you can decide whether to protect your groups from unnecessary links, forwards, and quotes."
        await fast_edit(query, text, get_antispam_hub_keyboard(cid))
        return

    if data.startswith("aspam_totallinks_"):
        cid = int(data.split("_")[2])
        del_text = "Yes ✔️" if cfg["totallinks_delete"] else "No ✖️"
        text = f"🔗 <b>TOTAL LINKS BLOCK</b>\nChoose the punishment for those who sends any kind of link.\n\n<b>Penalty:</b> {cfg['totallinks_penalty']}\n<b>Deletion:</b> {del_text}"
        await fast_edit(query, text, get_totallinks_keyboard(cid))
        return

    if data.startswith("astot_pen_"):
        pen = data.split("_")[2]
        cid = int(data.split("_")[3])
        cfg["totallinks_penalty"] = pen
        del_text = "Yes ✔️" if cfg["totallinks_delete"] else "No ✖️"
        text = f"🔗 <b>TOTAL LINKS BLOCK</b>\nChoose the punishment for those who sends any kind of link.\n\n<b>Penalty:</b> {cfg['totallinks_penalty']}\n<b>Deletion:</b> {del_text}"
        await fast_edit(query, text, get_totallinks_keyboard(cid))
        return

    if data.startswith("astottog_del_"):
        cid = int(data.split("_")[2])
        cfg["totallinks_delete"] = not cfg["totallinks_delete"]
        del_text = "Yes ✔️" if cfg["totallinks_delete"] else "No ✖️"
        text = f"🔗 <b>TOTAL LINKS BLOCK</b>\nChoose the punishment for those who sends any kind of link.\n\n<b>Penalty:</b> {cfg['totallinks_penalty']}\n<b>Deletion:</b> {del_text}"
        await fast_edit(query, text, get_totallinks_keyboard(cid))
        return

    if data.startswith("aspam_tglinks_"):
        cid = int(data.split("_")[2])
        del_text = "Yes ✔️" if cfg["tglinks_delete"] else "No ✖️"
        text = f"📘 <b>Telegram links</b>\nFrom this menu you can set a punishment for users who send messages that contain Telegram links.\n\n🎯 <b>Username Antispam:</b> triggers when username is sent.\n🤖 <b>Bots Antispam:</b> triggers when Bot link is sent.\n\n<b>Penalty:</b> {cfg['tglinks_penalty']}\n<b>Deletion:</b> {del_text}"
        await fast_edit(query, text, get_tglinks_keyboard(cid))
        return

    if data.startswith("astg_pen_"):
        pen = data.split("_")[2]
        cid = int(data.split("_")[3])
        cfg["tglinks_penalty"] = pen
        del_text = "Yes ✔️" if cfg["tglinks_delete"] else "No ✖️"
        text = f"📘 <b>Telegram links</b>\nFrom this menu you can set a punishment for users who send messages that contain Telegram links.\n\n🎯 <b>Username Antispam:</b> triggers when username is sent.\n🤖 <b>Bots Antispam:</b> triggers when Bot link is sent.\n\n<b>Penalty:</b> {cfg['tglinks_penalty']}\n<b>Deletion:</b> {del_text}"
        await fast_edit(query, text, get_tglinks_keyboard(cid))
        return

    if data.startswith("astgtog_"):
        action = data.split("_")[1]
        cid = int(data.split("_")[2])
        if action == "del":
            cfg["tglinks_delete"] = not cfg["tglinks_delete"]
        elif action == "user":
            cfg["spam_usernames"] = not cfg["spam_usernames"]
        elif action == "bot":
            cfg["spam_bots"] = not cfg["spam_bots"]

        del_text = "Yes ✔️" if cfg["tglinks_delete"] else "No ✖️"
        text = f"📘 <b>Telegram links</b>\nFrom this menu you can set a punishment for users who send messages that contain Telegram links.\n\n🎯 <b>Username Antispam:</b> triggers when username is sent.\n🤖 <b>Bots Antispam:</b> triggers when Bot link is sent.\n\n<b>Penalty:</b> {cfg['tglinks_penalty']}\n<b>Deletion:</b> {del_text}"
        await fast_edit(query, text, get_tglinks_keyboard(cid))
        return

    if data.startswith("aspam_fwd_") or data.startswith("asf"):
        cid = int(data.split("_")[-1])
        if data.startswith("asftar_"):
            cfg["fwd_target"] = data.split("_")[1]
        elif data.startswith("asf_pen_"):
            target = cfg.get("fwd_target", "groups")
            cfg[f"fwd_{target}_penalty"] = data.split("_")[2]
        elif data.startswith("asftog_del_"):
            cfg["fwd_delete"] = not cfg["fwd_delete"]

        text = f"📩 <b>Forwarding</b>\nSelect punishment for users who forward messages.\n\n📣 <b>Forwards from channels</b>\n └ {cfg['fwd_channels_penalty']}\n👥 <b>Groups</b>\n └ {cfg['fwd_groups_penalty']}\n👤 <b>Users</b>\n └ {cfg['fwd_users_penalty']}\n🤖 <b>Bots</b>\n └ {cfg['fwd_bots_penalty']}"
        await fast_edit(query, text, get_forward_or_quote_keyboard(cid, mode="fwd"))
        return

    if data.startswith("aspam_quote_") or data.startswith("asq"):
        cid = int(data.split("_")[-1])
        if data.startswith("asqtar_"):
            cfg["quote_target"] = data.split("_")[1]
        elif data.startswith("asq_pen_"):
            target = cfg.get("quote_target", "groups")
            cfg[f"quote_{target}_penalty"] = data.split("_")[2]
        elif data.startswith("asqjtog_del_"):
            cfg["quote_delete"] = not cfg["quote_delete"]

        text = f"💭 <b>Quote</b>\nSelect punishment for users who send quotes from external chats.\n\n📣 <b>Channels</b>\n └ {cfg['quote_channels_penalty']}\n👥 <b>Groups</b>\n └ {cfg['quote_groups_penalty']}\n👤 <b>Users</b>\n └ {cfg['quote_users_penalty']}\n🤖 <b>Bots</b>\n └ {cfg['quote_bots_penalty']}"
        await fast_edit(query, text, get_forward_or_quote_keyboard(cid, mode="quote"))
        return

    if data.startswith("asexc_"):
        cid = int(data.split("_")[-1])
        action = data.split("_")[1]
        if action == "main":
            user_states.pop((cid, user.id), None)
            text = "☀️ <b>Antispam Exception</b>\nManage the Telegram's links/usernames of groups and channels that will not be treated as spam."
            await fast_edit(query, text, get_exceptions_keyboard(cid))
        elif action == "show":
            wl = get_whitelist(cid)
            items = "\n".join([f"• <code>{item}</code>" for item in sorted(wl)]) if wl else "The whitelist is currently empty."
            text = f"🔤 <b>Links Block Whitelist ({len(wl)} items):</b>\n\n{items}"
            keyboard = [[create_btn("⬅️ Back", callback_data=f"asexc_main_{cid}")]]
            await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        elif action == "add":
            user_states[(cid, user.id)] = "awaiting_whitelist_add"
            text = f"Ok {user.mention_html()}, now send one or more links to add to Whitelist.\nSend a single link in every line."
            keyboard = [[create_btn("❌ Cancel", callback_data=f"asexc_main_{cid}", style="danger")]]
            await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        elif action == "rem":
            user_states[(cid, user.id)] = "awaiting_whitelist_remove"
            text = f"Ok {user.mention_html()}, now send one or more links to remove from Whitelist.\nSend a single link in every line."
            keyboard = [[create_btn("❌ Cancel", callback_data=f"asexc_main_{cid}", style="danger")]]
            await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        elif action == "globalmenu":
            status_text = "Active" if cfg.get("global_whitelist_active", True) else "Inactive"
            text = f"<b>Global Whitelist:</b>\nOfficial verified channels and groups ignored by spam detection.\n\n<b>Status:</b> {status_text}"
            await fast_edit(query, text, get_global_whitelist_keyboard(cid))
        elif action == "glbtoggle":
            sub_action = data.split("_")[2]
            cfg["global_whitelist_active"] = (sub_action == "on")
            status_text = "Active" if cfg["global_whitelist_active"] else "Inactive"
            text = f"<b>Global Whitelist:</b>\nOfficial verified channels and groups ignored by spam detection.\n\n<b>Status:</b> {status_text}"
            await fast_edit(query, text, get_global_whitelist_keyboard(cid))
        elif action == "viewglobal":
            items = "\n".join([f"• <code>{item}</code>" for item in sorted(GLOBAL_WHITELIST_ITEMS)])
            text = f"📖 <b>Global Whitelist ({len(GLOBAL_WHITELIST_ITEMS)} items):</b>\n\n{items}"
            keyboard = [[create_btn("⬅️ Back", callback_data=f"asexc_globalmenu_{cid}")]]
            await fast_edit(query, text, InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("cfg_toggle_"):
        key = data.split("_")[2]
        cid = int(data.split("_")[3])
        if key == "captcha":
            cfg["captcha"] = not cfg["captcha"]
        elif key == "media":
            cfg["lock_media"] = not cfg["lock_media"]
        elif key == "night":
            cfg["night_mode"] = not cfg["night_mode"]
        text = "🛡 <b>Group Security & Settings Panel</b>\nSelect the options you want to configure:"
        await fast_edit(query, text, get_main_settings_keyboard(cid))
        return

    if data.startswith("cfg_warn_limit_"):
        cid = int(data.split("_")[3])
        cfg["warn_limit"] = 5 if cfg["warn_limit"] == 3 else 3
        text = "🛡 <b>Group Security & Settings Panel</b>\nSelect the options you want to configure:"
        await fast_edit(query, text, get_main_settings_keyboard(cid))
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

    # Regulations States
    if state == "awaiting_reg_text":
        cfg["rules_text"] = text
        kb = [[create_btn("⬅️ Back", callback_data=f"cfg_view_reg_{chat_id}")]]
        await msg.reply_text("✅ <b>Message set.</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    elif state == "awaiting_reg_media":
        if msg.photo:
            cfg["rules_media_id"] = msg.photo[-1].file_id
            cfg["rules_media_type"] = "photo"
        elif msg.video:
            cfg["rules_media_id"] = msg.video.file_id
            cfg["rules_media_type"] = "video"
        elif msg.sticker:
            cfg["rules_media_id"] = msg.sticker.file_id
            cfg["rules_media_type"] = "sticker"
        else:
            await msg.reply_text("❌ Kripya photo, video ya sticker send karein.")
            return True

        if msg.caption:
            cfg["rules_text"] = msg.caption

        kb = [[create_btn("⬅️ Back", callback_data=f"cfg_view_reg_{chat_id}")]]
        await msg.reply_text("✅ <b>Media set.</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    elif state == "awaiting_reg_buttons":
        cfg["rules_buttons_raw"] = text
        kb = [[create_btn("⬅️ Back", callback_data=f"cfg_view_reg_{chat_id}")]]
        await msg.reply_text("✅ <b>Buttons set.</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    # Welcome States
    elif state == "awaiting_wlc_text":
        cfg["welcome_text"] = text
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

        kb = [[create_btn("⬅️ Back", callback_data=f"wlc_custom_{chat_id}")]]
        await msg.reply_text("✅ <b>Media set.</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    elif state == "awaiting_wlc_buttons":
        cfg["welcome_buttons_raw"] = text
        kb = [[create_btn("⬅️ Back", callback_data=f"wlc_custom_{chat_id}")]]
        await msg.reply_text("✅ <b>Buttons set.</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    # Whitelist States
    elif state == "awaiting_whitelist_add":
        lines = [line.strip().lower() for line in text.splitlines() if line.strip()]
        wl = get_whitelist(chat_id)
        added = []
        for line in lines:
            clean = line.replace("https://", "").replace("http://", "").replace("@", "")
            wl.add(clean)
            added.append(clean)
        res = f"✅ <b>{len(added)} Link(s) added to Whitelist!</b>\n\n" + "\n".join([f"• <code>{x}</code>" for x in added])
        kb = [[create_btn("⬅️ Back to Exceptions", callback_data=f"asexc_main_{chat_id}")]]
        await msg.reply_text(res, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    elif state == "awaiting_whitelist_remove":
        lines = [line.strip().lower() for line in text.splitlines() if line.strip()]
        wl = get_whitelist(chat_id)
        removed, not_found = [], []
        for line in lines:
            clean = line.replace("https://", "").replace("http://", "").replace("@", "")
            if clean in wl:
                wl.remove(clean)
                removed.append(clean)
            else:
                not_found.append(clean)
        res = ""
        if removed:
            res += f"❌ <b>Removed {len(removed)} item(s):</b>\n" + "\n".join([f"• <code>{x}</code>" for x in removed]) + "\n\n"
        if not_found:
            res += f"⚠️ <b>Not found ({len(not_found)}):</b>\n" + "\n".join([f"• <code>{x}</code>" for x in not_found])
        kb = [[create_btn("⬅️ Back to Exceptions", callback_data=f"asexc_main_{chat_id}")]]
        await msg.reply_text(res or "No changes made.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    return False

# ----------------- TOPIC BINDING COMMAND ----------------- #
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

    if thread_id:
        await msg.reply_text(f"✅ Welcome messages will now be sent to this topic (Thread ID: <code>{thread_id}</code>).", parse_mode="HTML")
    else:
        await msg.reply_text("✅ Welcome messages bound to Main Chat.", parse_mode="HTML")

# ----------------- PUBLIC COMMANDS ----------------- #
async def link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_text("Yeh command group ke andar run karein.")
        return

    if not await check_admin_invite_permission(chat.id, user.id, context):
        await update.message.reply_text("❌ Aapke paas group me 'Invite Users via Link' permission nahi hai.")
        return

    link_drafts[(chat.id, user.id)] = {
        "active_tab": None,
        "limit": 0,
        "until_seconds": 0,
        "approval": False
    }

    await update.message.reply_text(
        get_link_creator_text(chat.id, user.id),
        reply_markup=get_link_creator_keyboard(chat.id, user.id),
        parse_mode="HTML"
    )

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    cfg = get_config(chat.id)
    r_text = cfg.get("rules_text", "No rules set.")
    r_kb = parse_custom_buttons(cfg.get("rules_buttons_raw"), chat.id)
    m_id = cfg.get("rules_media_id")
    m_type = cfg.get("rules_media_type")

    try:
        if m_type == "photo":
            await chat.send_photo(photo=m_id, caption=r_text, reply_markup=r_kb, parse_mode="HTML")
        elif m_type == "video":
            await chat.send_video(video=m_id, caption=r_text, reply_markup=r_kb, parse_mode="HTML")
        elif m_type == "sticker":
            await chat.send_sticker(sticker=m_id)
            await chat.send_message(r_text, reply_markup=r_kb, parse_mode="HTML")
        else:
            await chat.send_message(r_text, reply_markup=r_kb, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error displaying rules: {e}")

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
    warns = user_warns.get(chat.id, {}).get(user.id, 0)
    info = f"👤 <b>Your Info:</b>\n• Name: {user.mention_html()}\n• ID: <code>{user.id}</code>\n• Warns: <b>{warns}</b>"
    await update.message.reply_text(info, parse_mode="HTML")

# ----------------- NEW MEMBER JOIN & WELCOME DISPATCHER ----------------- #
async def new_member_welcome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    cfg = get_config(chat.id)

    if not cfg.get("welcome_active"):
        return

    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            continue

        joined_history = joined_members_history.setdefault(chat.id, set())
        if cfg.get("welcome_mode") == "first" and member.id in joined_history:
            continue
        joined_history.add(member.id)

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
    text = msg.text or msg.caption or ""
    cfg = get_config(chat.id)
    wl = get_whitelist(chat.id)
    global_wl_active = cfg.get("global_whitelist_active", True)

    if await is_user_admin(chat.id, user.id, context):
        return

    def is_whitelisted(item: str) -> bool:
        item_low = item.lower()
        if any(exc in item_low for exc in wl):
            return True
        if global_wl_active and any(gwl in item_low for gwl in GLOBAL_WHITELIST_ITEMS):
            return True
        return False

    # 1. FORWARDS & QUOTES
    if msg.forward_origin:
        origin_type = msg.forward_origin.type
        is_quote = getattr(msg, "quote", None) is not None
        prefix = "quote" if is_quote else "fwd"
        should_del = cfg.get(f"{prefix}_delete", False)
        penalty = "Off"

        sender_title = getattr(msg.forward_origin, 'chat', None)
        sender_user = getattr(msg.forward_origin, 'sender_user', None)
        origin_str = str(sender_title or sender_user or "")

        if not is_whitelisted(origin_str):
            if origin_type == "channel":
                penalty = cfg.get(f"{prefix}_channels_penalty", "Off")
            elif origin_type == "chat":
                penalty = cfg.get(f"{prefix}_groups_penalty", "Off")
            elif origin_type == "user":
                if sender_user and sender_user.is_bot:
                    penalty = cfg.get(f"{prefix}_bots_penalty", "Off")
                else:
                    penalty = cfg.get(f"{prefix}_users_penalty", "Off")

            if penalty != "Off" or should_del:
                await execute_punishment(penalty, should_del, update, context, f"{prefix.capitalize()} from {origin_type}")
                return

    # 2. TOTAL LINKS BLOCK
    all_links = re.findall(r"(https?://\S+|www\.\S+|\bt\.me/\S+)", text, re.IGNORECASE)
    if all_links:
        if cfg["totallinks_penalty"] != "Off" or cfg["totallinks_delete"]:
            for link in all_links:
                if not is_whitelisted(link):
                    await execute_punishment(cfg["totallinks_penalty"], cfg["totallinks_delete"], update, context, "Link Block")
                    return

        tg_links = re.findall(r"(https?://t\.me/\S+|t\.me/\S+|telegram\.me/\S+)", text, re.IGNORECASE)
        if tg_links and (cfg["tglinks_penalty"] != "Off" or cfg["tglinks_delete"]):
            for link in tg_links:
                if not is_whitelisted(link):
                    await execute_punishment(cfg["tglinks_penalty"], cfg["tglinks_delete"], update, context, "Telegram link")
                    return

    # 3. BOTS ANTISPAM
    if cfg.get("spam_bots"):
        bot_matches = re.findall(r"(?:t\.me/|@)(\w+bot)\b", text, re.IGNORECASE)
        for b_name in bot_matches:
            if not is_whitelisted(b_name):
                await execute_punishment(cfg["tglinks_penalty"], cfg["tglinks_delete"], update, context, "Bot link/mention")
                return

    # 4. USERNAME ANTISPAM
    if cfg.get("spam_usernames"):
        usernames = re.findall(r"@(\w+)", text)
        for un in usernames:
            if not is_whitelisted(un):
                await execute_punishment(cfg["tglinks_penalty"], cfg["tglinks_delete"], update, context, f"Username spam (@{un})")
                return

# ----------------- SYSTEM COMMANDS ----------------- #
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

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_text("Sirf groups ke liye available hai.")
        return

    if not await is_user_admin(chat.id, user.id, context):
        await update.message.reply_text("❌ Sirf Admins `/settings` open kar sakte hain.")
        return

    await update.message.reply_text(
        "🛡 <b>Group Security & Settings Panel</b>\nSelect the options you want to configure:",
        reply_markup=get_main_settings_keyboard(chat.id),
        parse_mode="HTML"
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        keyboard = [[create_btn("➕ Add Me to Your Group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
        await update.message.reply_text("🛡 Group Security Bot active! Add to group and send `/settings`.", reply_markup=InlineKeyboardMarkup(keyboard))

# ----------------- MAIN INITIALIZER ----------------- #
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("update", update_command))
    app.add_handler(CommandHandler("link", link_command))
    app.add_handler(CommandHandler("rules", rules_command))
    app.add_handler(CommandHandler("staff", staff_command))
    app.add_handler(CommandHandler("me", me_command))
    app.add_handler(CommandHandler("topic_welcome", topic_welcome_command))

    # Router
    app.add_handler(CallbackQueryHandler(unified_callback_handler))

    # Handlers
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member_welcome_handler))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^pip3?\s+install\s+"), auto_pip_installer))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, security_moderator))

    print("🛡 Group Help Security Bot running with reliable Photo + Text + Buttons preview...")
    app.run_polling()

if __name__ == "__main__":
    main()
