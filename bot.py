import os
import sys
import subprocess
import logging
import re
import time
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions
)
from telegram.error import BadRequest
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

# Hardcoded Owner IDs
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

def get_default_config():
    return {
        "captcha": True,
        "warn_limit": 3,
        "night_mode": False,
        "lock_media": False,
        
        # Total Links Block
        "totallinks_penalty": "Off",
        "totallinks_delete": False,
        
        # Telegram Links Block
        "tglinks_penalty": "Off",
        "tglinks_delete": False,
        "spam_usernames": False,
        "spam_bots": False,
        
        # Forwarding Antispam
        "fwd_target": "groups",  # Active tab: channels, groups, users, bots
        "fwd_channels_penalty": "Off",
        "fwd_groups_penalty": "Off",
        "fwd_users_penalty": "Off",
        "fwd_bots_penalty": "Off",
        "fwd_delete": False,
        
        # Quote Antispam
        "quote_target": "groups",
        "quote_channels_penalty": "Off",
        "quote_groups_penalty": "Off",
        "quote_users_penalty": "Off",
        "quote_bots_penalty": "Off",
        "quote_delete": False
    }

def get_config(chat_id: int):
    if chat_id not in group_settings:
        group_settings[chat_id] = get_default_config()
    return group_settings[chat_id]

def get_whitelist(chat_id: int):
    if chat_id not in whitelist_storage:
        whitelist_storage[chat_id] = set()
    return whitelist_storage[chat_id]

# ----------------- COLOR BUTTON BUILDER (KURIGRAM / API COMPATIBLE) ----------------- #
def create_btn(text: str, callback_data: str, style: str = None):
    """
    Creates button with Native Style (primary/success/danger) 
    and fallback text icons for non-styled clients.
    """
    try:
        if style:
            return InlineKeyboardButton(text=text, callback_data=callback_data, style=style)
    except TypeError:
        # Fallback if standard python-telegram-bot without style parameter
        pass
    return InlineKeyboardButton(text=text, callback_data=callback_data)

# ----------------- FAST CACHED ADMIN CHECK ----------------- #
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

# ----------------- INLINE KEYBOARDS ----------------- #
def make_penalty_buttons(prefix: str, current_penalty: str, chat_id: int):
    def get_btn(label, val):
        is_selected = (current_penalty == val)
        btn_text = f"❌ {label}" if val == "Off" and not is_selected else label
        btn_style = "success" if is_selected else None
        return create_btn(btn_text, f"{prefix}pen_{val}_{chat_id}", style=btn_style)

    row1 = [
        get_btn("Off", "Off"),
        get_btn("! Warn", "Warn"),
        get_btn("! Kick", "Kick")
    ]
    row2 = [
        get_btn("🔊 Mute", "Mute"),
        get_btn("🚷 Ban", "Ban")
    ]
    return row1, row2

# 1. Main Settings Keyboard
def get_main_settings_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    btn = lambda key, text: f"{text} {'✅' if cfg.get(key) else '❌'}"
    
    keyboard = [
        [
            create_btn("📜 Regulation", f"cfg_view_reg_{chat_id}"),
            create_btn("✉️ Anti-Spam", f"aspam_main_{chat_id}")
        ],
        [
            create_btn("💬 Welcome", f"cfg_view_welcome_{chat_id}"),
            create_btn("🗣 Anti-Flood", f"cfg_view_flood_{chat_id}")
        ],
        [
            create_btn(btn("captcha", "🧠 Captcha"), f"cfg_toggle_captcha_{chat_id}"),
            create_btn("🔦 Checks", f"cfg_view_checks_{chat_id}")
        ],
        [
            create_btn(btn("lock_media", "📸 Media"), f"cfg_toggle_media_{chat_id}"),
            create_btn("🔗 Telegram links", f"aspam_tglinks_{chat_id}")
        ],
        [
            create_btn(btn("night_mode", "🌘 Night Mode"), f"cfg_toggle_night_{chat_id}"),
            create_btn(f"⚠️ Warn Limit ({cfg.get('warn_limit')})", f"cfg_warn_limit_{chat_id}")
        ],
        [create_btn("Next Page ➡️", f"cfg_page_2_{chat_id}")],
        [create_btn("❎ Close", "cfg_close")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_page2_settings_keyboard(chat_id: int):
    keyboard = [
        [create_btn("📁 Topic", f"cfg_view_topic_{chat_id}")],
        [create_btn("🔤 Banned Words", f"cfg_view_banned_{chat_id}")],
        [create_btn("👥 Members Management", f"cfg_view_members_{chat_id}")],
        [create_btn("💭 Quote Antispam", f"aspam_quote_{chat_id}")],
        [create_btn("🔍 Log Channel", f"cfg_view_logs_{chat_id}")],
        [
            create_btn("⬅️ Back", f"cfg_page_1_{chat_id}"),
            create_btn("❎ Close", "cfg_close")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# 2. Anti-Spam Hub
def get_antispam_hub_keyboard(chat_id: int):
    keyboard = [
        [create_btn("📘 Telegram links", f"aspam_tglinks_{chat_id}")],
        [
            create_btn("📩 Forwarding", f"aspam_fwd_{chat_id}"),
            create_btn("💭 Quote", f"aspam_quote_{chat_id}")
        ],
        [create_btn("🔗 Total links block", f"aspam_totallinks_{chat_id}")],
        [create_btn("⬅️ Back", f"cfg_page_1_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# 3. Total Links Block
def get_totallinks_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    r1, r2 = make_penalty_buttons("astot_", cfg["totallinks_penalty"], chat_id)
    del_icon = "✔️" if cfg["totallinks_delete"] else "✖️"

    keyboard = [
        r1,
        r2,
        [create_btn(f"🗑 Delete Messages {del_icon}", f"astottog_del_{chat_id}")],
        [
            create_btn("⬅️ Back", f"aspam_main_{chat_id}"),
            create_btn("☀️ Exceptions", f"asexc_main_{chat_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# 4. Telegram Links
def get_tglinks_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    r1, r2 = make_penalty_buttons("astg_", cfg["tglinks_penalty"], chat_id)
    del_icon = "Yes ✔️" if cfg["tglinks_delete"] else "No ✖️"
    user_status = "✔️" if cfg["spam_usernames"] else "✖️"
    bot_status = "✔️" if cfg["spam_bots"] else "✖️"

    keyboard = [
        r1,
        r2,
        [create_btn(f"🗑 Delete Messages {del_icon}", f"astgtog_del_{chat_id}")],
        [create_btn(f"🎯 Username Antispam {user_status}", f"astgtog_user_{chat_id}")],
        [create_btn(f"🤖 Bots Antispam {bot_status}", f"astgtog_bot_{chat_id}")],
        [
            create_btn("⬅️ Back", f"aspam_main_{chat_id}"),
            create_btn("☀️ Exceptions", f"asexc_main_{chat_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# 5. Forwarding & Quote with Dynamic Primary & Success Styles
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
        return create_btn(text, f"{prefix}tar_{key}_{chat_id}", style=style)

    row1, row2 = make_penalty_buttons(f"{prefix}_", current_penalty, chat_id)

    keyboard = [
        [tab("📣 Channels", "channels"), tab("👥 Groups", "groups")],
        [tab("👤 Users", "users"), tab("🤖 Bots", "bots")],
        [create_btn("➖➖➖➖➖➖➖➖", "none")],
        row1,
        row2,
        [create_btn(f"🗑 Delete Messages {del_icon}", f"{prefix}tog_del_{chat_id}")],
        [
            create_btn("⬅️ Back", f"aspam_main_{chat_id}"),
            create_btn("☀️ Exceptions", f"asexc_main_{chat_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# 6. Exceptions
def get_exceptions_keyboard(chat_id: int):
    keyboard = [
        [create_btn("🔤 Show Whitelist", f"asexc_show_{chat_id}")],
        [
            create_btn("➕ Add", f"asexc_add_{chat_id}"),
            create_btn("➖ Remove", f"asexc_rem_{chat_id}")
        ],
        [create_btn("🌐 Global Whitelist", f"asexc_global_{chat_id}")],
        [create_btn("⬅️ Back", f"aspam_main_{chat_id}")]
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

    if data == "none":
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
        if page == "2":
            text = "🛡 <b>Group Security & Settings Panel (Page 2)</b>\nSelect the options you want to configure:"
            await fast_edit(query, text, get_page2_settings_keyboard(cid))
        else:
            text = "🛡 <b>Group Security & Settings Panel</b>\nSelect the options you want to configure:"
            await fast_edit(query, text, get_main_settings_keyboard(cid))
        return

    # 2. Main Anti-Spam Hub
    if data.startswith("aspam_main_"):
        cid = int(data.split("_")[2])
        text = (
            "✉️ <b>Anti-Spam</b>\n"
            "In this menu you can decide whether to protect your groups from unnecessary links, forwards, and quotes."
        )
        await fast_edit(query, text, get_antispam_hub_keyboard(cid))
        return

    # 3. Total Links Block Menu
    if data.startswith("aspam_totallinks_"):
        cid = int(data.split("_")[2])
        del_text = "Yes ✔️" if cfg["totallinks_delete"] else "No ✖️"
        text = (
            "🔗 <b>TOTAL LINKS BLOCK</b>\n"
            "Choose the punishment for those who sends any kind of link.\n\n"
            f"<b>Penalty:</b> {cfg['totallinks_penalty']}\n"
            f"<b>Deletion:</b> {del_text}"
        )
        await fast_edit(query, text, get_totallinks_keyboard(cid))
        return

    if data.startswith("astot_pen_"):
        pen = data.split("_")[2]
        cid = int(data.split("_")[3])
        cfg["totallinks_penalty"] = pen
        del_text = "Yes ✔️" if cfg["totallinks_delete"] else "No ✖️"
        text = (
            "🔗 <b>TOTAL LINKS BLOCK</b>\n"
            "Choose the punishment for those who sends any kind of link.\n\n"
            f"<b>Penalty:</b> {cfg['totallinks_penalty']}\n"
            f"<b>Deletion:</b> {del_text}"
        )
        await fast_edit(query, text, get_totallinks_keyboard(cid))
        return

    if data.startswith("astottog_del_"):
        cid = int(data.split("_")[2])
        cfg["totallinks_delete"] = not cfg["totallinks_delete"]
        del_text = "Yes ✔️" if cfg["totallinks_delete"] else "No ✖️"
        text = (
            "🔗 <b>TOTAL LINKS BLOCK</b>\n"
            "Choose the punishment for those who sends any kind of link.\n\n"
            f"<b>Penalty:</b> {cfg['totallinks_penalty']}\n"
            f"<b>Deletion:</b> {del_text}"
        )
        await fast_edit(query, text, get_totallinks_keyboard(cid))
        return

    # 4. Telegram Links Menu
    if data.startswith("aspam_tglinks_"):
        cid = int(data.split("_")[2])
        del_text = "Yes ✔️" if cfg["tglinks_delete"] else "No ✖️"
        text = (
            "📘 <b>Telegram links</b>\n"
            "From this menu you can set a punishment for users who send messages that contain Telegram links.\n\n"
            "🎯 <b>Username Antispam:</b> this option triggers the antispam when a username considered spam is sent.\n\n"
            "🤖 <b>Bots Antispam:</b> this option triggers the antispam when a Bot link is sent.\n\n"
            f"<b>Penalty:</b> {cfg['tglinks_penalty']}\n"
            f"<b>Deletion:</b> {del_text}"
        )
        await fast_edit(query, text, get_tglinks_keyboard(cid))
        return

    if data.startswith("astg_pen_"):
        pen = data.split("_")[2]
        cid = int(data.split("_")[3])
        cfg["tglinks_penalty"] = pen
        del_text = "Yes ✔️" if cfg["tglinks_delete"] else "No ✖️"
        text = (
            "📘 <b>Telegram links</b>\n"
            "From this menu you can set a punishment for users who send messages that contain Telegram links.\n\n"
            "🎯 <b>Username Antispam:</b> this option triggers the antispam when a username considered spam is sent.\n\n"
            "🤖 <b>Bots Antispam:</b> this option triggers the antispam when a Bot link is sent.\n\n"
            f"<b>Penalty:</b> {cfg['tglinks_penalty']}\n"
            f"<b>Deletion:</b> {del_text}"
        )
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
        text = (
            "📘 <b>Telegram links</b>\n"
            "From this menu you can set a punishment for users who send messages that contain Telegram links.\n\n"
            "🎯 <b>Username Antispam:</b> this option triggers the antispam when a username considered spam is sent.\n\n"
            "🤖 <b>Bots Antispam:</b> this option triggers the antispam when a Bot link is sent.\n\n"
            f"<b>Penalty:</b> {cfg['tglinks_penalty']}\n"
            f"<b>Deletion:</b> {del_text}"
        )
        await fast_edit(query, text, get_tglinks_keyboard(cid))
        return

    # 5. Forwarding Menu
    if data.startswith("aspam_fwd_") or data.startswith("asf"):
        cid = int(data.split("_")[-1])
        if data.startswith("asftar_"):
            cfg["fwd_target"] = data.split("_")[1]
        elif data.startswith("asf_pen_"):
            target = cfg.get("fwd_target", "groups")
            cfg[f"fwd_{target}_penalty"] = data.split("_")[2]
        elif data.startswith("asftog_del_"):
            cfg["fwd_delete"] = not cfg["fwd_delete"]

        text = (
            "📩 <b>Forwarding</b>\n"
            "Select punishment for users who forward messages in the group.\n\n"
            "<i>Forward from groups option blocks messages written by an anonymous administrator of another group and forwarded to this group.</i>\n\n"
            f"📣 <b>Forwards from channels</b>\n └ {cfg['fwd_channels_penalty']}\n"
            f"👥 <b>Groups</b>\n └ {cfg['fwd_groups_penalty']}\n"
            f"👤 <b>Users</b>\n └ {cfg['fwd_users_penalty']}\n"
            f"🤖 <b>Bots</b>\n └ {cfg['fwd_bots_penalty']}"
        )
        await fast_edit(query, text, get_forward_or_quote_keyboard(cid, mode="fwd"))
        return

    # 6. Quote Menu
    if data.startswith("aspam_quote_") or data.startswith("asq"):
        cid = int(data.split("_")[-1])
        if data.startswith("asqtar_"):
            cfg["quote_target"] = data.split("_")[1]
        elif data.startswith("asq_pen_"):
            target = cfg.get("quote_target", "groups")
            cfg[f"quote_{target}_penalty"] = data.split("_")[2]
        elif data.startswith("asqtog_del_"):
            cfg["quote_delete"] = not cfg["quote_delete"]

        text = (
            "💭 <b>Quote</b>\n"
            "Select punishment for users who send messages containing quotes from external chats.\n\n"
            f"📣 <b>Channels</b>\n └ {cfg['quote_channels_penalty']}\n"
            f"👥 <b>Groups</b>\n └ {cfg['quote_groups_penalty']}\n"
            f"👤 <b>Users</b>\n └ {cfg['quote_users_penalty']}\n"
            f"🤖 <b>Bots</b>\n └ {cfg['quote_bots_penalty']}"
        )
        await fast_edit(query, text, get_forward_or_quote_keyboard(cid, mode="quote"))
        return

    # 7. Exceptions
    if data.startswith("asexc_"):
        cid = int(data.split("_")[2])
        action = data.split("_")[1]
        if action == "main":
            text = (
                "☀️ <b>Antispam Exception</b>\n"
                "Manage the Telegram's links/usernames of groups and channels that will not be treated as spam.\n\n"
                "<i>The group links are automatically in the antispam exception.</i>"
            )
            await fast_edit(query, text, get_exceptions_keyboard(cid))
        elif action == "show":
            wl = get_whitelist(cid)
            wl_text = "\n".join([f"• <code>{x}</code>" for x in wl]) if wl else "Whitelist empty hai."
            try:
                await query.answer(f"Whitelist:\n{wl_text}", show_alert=True)
            except Exception:
                pass
        elif action == "add":
            try:
                await query.answer("Whitelist add karne ke liye: /whitelist @username", show_alert=True)
            except Exception:
                pass
        elif action == "rem":
            try:
                await query.answer("Whitelist remove karne ke liye: /unwhitelist @username", show_alert=True)
            except Exception:
                pass
        elif action == "global":
            try:
                await query.answer("Global Whitelist is active.", show_alert=True)
            except Exception:
                pass
        return

    # 8. Main Settings Toggles
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

# ----------------- SECURITY & AUTO MODERATION FILTER ----------------- #
async def security_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    chat = update.effective_chat
    user = update.effective_user
    msg = update.message
    text = msg.text or msg.caption or ""
    cfg = get_config(chat.id)
    wl = get_whitelist(chat.id)

    if await is_user_admin(chat.id, user.id, context):
        return

    # 1. FORWARDS & QUOTES CHECK
    if msg.forward_origin:
        origin_type = msg.forward_origin.type
        is_quote = getattr(msg, "quote", None) is not None
        prefix = "quote" if is_quote else "fwd"
        should_del = cfg.get(f"{prefix}_delete", False)
        penalty = "Off"

        if origin_type == "channel":
            penalty = cfg.get(f"{prefix}_channels_penalty", "Off")
        elif origin_type == "chat":
            penalty = cfg.get(f"{prefix}_groups_penalty", "Off")
        elif origin_type == "user":
            sender_user = getattr(msg.forward_origin, 'sender_user', None)
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
                if not any(exc in link.lower() for exc in wl):
                    await execute_punishment(cfg["totallinks_penalty"], cfg["totallinks_delete"], update, context, "Link Block")
                    return

        tg_links = re.findall(r"(https?://t\.me/\S+|t\.me/\S+|telegram\.me/\S+)", text, re.IGNORECASE)
        if tg_links and (cfg["tglinks_penalty"] != "Off" or cfg["tglinks_delete"]):
            for link in tg_links:
                if not any(exc in link.lower() for exc in wl):
                    await execute_punishment(cfg["tglinks_penalty"], cfg["tglinks_delete"], update, context, "Telegram link")
                    return

    # 3. BOTS ANTISPAM
    if cfg.get("spam_bots"):
        if re.search(r"t\.me/\w+bot\b", text, re.IGNORECASE) or re.search(r"@\w+bot\b", text, re.IGNORECASE):
            await execute_punishment(cfg["tglinks_penalty"], cfg["tglinks_delete"], update, context, "Bot link/mention")
            return

    # 4. USERNAME ANTISPAM
    if cfg.get("spam_usernames"):
        usernames = re.findall(r"@(\w+)", text)
        for un in usernames:
            if un.lower() not in wl:
                await execute_punishment(cfg["tglinks_penalty"], cfg["tglinks_delete"], update, context, f"Username spam (@{un})")
                return

# ----------------- SYSTEM & COMMANDS ----------------- #
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
        keyboard = [[create_btn("➕ Add Me to Your Group", f"https://t.me/{context.bot.username}?startgroup=true")]]
        await update.message.reply_text("🛡 Group Security Bot active! Add to group and send `/settings`.", reply_markup=InlineKeyboardMarkup(keyboard))

async def add_whitelist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update.effective_chat.id, update.effective_user.id, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: `/whitelist @username`", parse_mode="Markdown")
        return
    target = context.args[0].lower().replace("@", "")
    get_whitelist(update.effective_chat.id).add(target)
    await update.message.reply_text(f"✅ `@{target}` whitelisted!", parse_mode="Markdown")

async def remove_whitelist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update.effective_chat.id, update.effective_user.id, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: `/unwhitelist @username`", parse_mode="Markdown")
        return
    target = context.args[0].lower().replace("@", "")
    wl = get_whitelist(update.effective_chat.id)
    if target in wl:
        wl.remove(target)
        await update.message.reply_text(f"❌ `@{target}` removed from whitelist.", parse_mode="Markdown")
    else:
        await update.message.reply_text("Entry not found in whitelist.")

# ----------------- APP INITIALIZATION ----------------- #
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("update", update_command))
    app.add_handler(CommandHandler("whitelist", add_whitelist_cmd))
    app.add_handler(CommandHandler("unwhitelist", remove_whitelist_cmd))

    # Fast Single Router
    app.add_handler(CallbackQueryHandler(unified_callback_handler))

    # Message Handlers
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^pip3?\s+install\s+"), auto_pip_installer))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, security_moderator))

    print("🛡 Group Help Security Bot running smoothly...")
    app.run_polling()

if __name__ == "__main__":
    main()
