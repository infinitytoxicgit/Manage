import os
import sys
import subprocess
import logging
import re
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
OWNER_IDS = [8564072723, 7873324475]

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

# Default Security State
def get_default_config():
    return {
        "captcha": True,
        "warn_limit": 3,
        "night_mode": False,
        "lock_media": False,
        # Deep Anti-Spam
        "spam_penalty": "Off",  # Off, Warn, Kick, Mute, Ban
        "spam_delete": True,
        "spam_usernames": False,
        "spam_bots": False,
        # Quote Antispam Config
        "quote_target": "groups",  # channels, groups, users, bots
        "quote_channels_penalty": "Off",
        "quote_groups_penalty": "Off",
        "quote_users_penalty": "Off",
        "quote_bots_penalty": "Off",
        "quote_delete": True,
    }

def get_config(chat_id: int):
    if chat_id not in group_settings:
        group_settings[chat_id] = get_default_config()
    return group_settings[chat_id]

def get_whitelist(chat_id: int):
    if chat_id not in whitelist_storage:
        whitelist_storage[chat_id] = set()
    return whitelist_storage[chat_id]

# ----------------- SAFE CALLBACK & ADMIN CHECK ----------------- #
async def safe_answer(query, text=None, show_alert=False):
    try:
        if text:
            await query.answer(text=text, show_alert=show_alert)
        else:
            await query.answer()
    except BadRequest:
        pass
    except Exception as e:
        logger.error(f"Callback answer error: {e}")

async def is_user_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if user_id in OWNER_IDS:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in ["administrator", "creator"]:
            return True
        role = staff_roles.get(chat_id, {}).get(user_id)
        return role in ["admin", "mod"]
    except Exception:
        return False

# ----------------- INLINE KEYBOARDS ----------------- #
def get_main_settings_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    btn = lambda key, text: f"{text} {'✅' if cfg.get(key) else '❌'}"
    
    keyboard = [
        [
            InlineKeyboardButton("📜 Regulation", callback_data=f"cfg_view_reg_{chat_id}"),
            InlineKeyboardButton("✉️ Anti-Spam ⚙️", callback_data=f"aspam_main_{chat_id}")
        ],
        [
            InlineKeyboardButton("💬 Welcome", callback_data=f"cfg_view_welcome_{chat_id}"),
            InlineKeyboardButton("🗣 Anti-Flood", callback_data=f"cfg_view_flood_{chat_id}")
        ],
        [
            InlineKeyboardButton(btn("captcha", "🧠 Captcha"), callback_data=f"cfg_toggle_captcha_{chat_id}"),
            InlineKeyboardButton("🔦 Checks", callback_data=f"cfg_view_checks_{chat_id}")
        ],
        [
            InlineKeyboardButton(btn("lock_media", "📸 Media"), callback_data=f"cfg_toggle_media_{chat_id}"),
            InlineKeyboardButton("🔗 Telegram links", callback_data=f"aspam_tglinks_{chat_id}")
        ],
        [
            InlineKeyboardButton(btn("night_mode", "🌘 Night Mode"), callback_data=f"cfg_toggle_night_{chat_id}"),
            InlineKeyboardButton(f"⚠️ Warn Limit ({cfg.get('warn_limit')})", callback_data=f"cfg_warn_limit_{chat_id}")
        ],
        [InlineKeyboardButton("Next Page ➡️", callback_data=f"cfg_page_2_{chat_id}")],
        [InlineKeyboardButton("❎ Close", callback_data="cfg_close")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_page2_settings_keyboard(chat_id: int):
    keyboard = [
        [InlineKeyboardButton("📁 Topic", callback_data=f"cfg_view_topic_{chat_id}")],
        [InlineKeyboardButton("🔤 Banned Words", callback_data=f"cfg_view_banned_{chat_id}")],
        [InlineKeyboardButton("👥 Members Management", callback_data=f"cfg_view_members_{chat_id}")],
        [InlineKeyboardButton("💭 Quote Antispam", callback_data=f"aspam_quote_{chat_id}")],
        [InlineKeyboardButton("🔍 Log Channel", callback_data=f"cfg_view_logs_{chat_id}")],
        [
            InlineKeyboardButton("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}"),
            InlineKeyboardButton("❎ Close", callback_data="cfg_close")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# 1. Total Links & Telegram Links UI
def get_antispam_tglinks_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    p = cfg["spam_penalty"]
    
    p_btn = lambda name: f"✅ {name}" if p == name else name
    del_status = "Yes ✔️" if cfg["spam_delete"] else "No ✖️"
    user_status = "✔️" if cfg["spam_usernames"] else "✖️"
    bot_status = "✔️" if cfg["spam_bots"] else "✖️"

    keyboard = [
        [
            InlineKeyboardButton(p_btn("❌ Off"), callback_data=f"aspen_Off_{chat_id}"),
            InlineKeyboardButton(p_btn("! Warn"), callback_data=f"aspen_Warn_{chat_id}"),
            InlineKeyboardButton(p_btn("! Kick"), callback_data=f"aspen_Kick_{chat_id}")
        ],
        [
            InlineKeyboardButton(p_btn("🔇 Mute"), callback_data=f"aspen_Mute_{chat_id}"),
            InlineKeyboardButton(p_btn("🚷 Ban"), callback_data=f"aspen_Ban_{chat_id}")
        ],
        [InlineKeyboardButton(f"🗑 Delete Messages {del_status}", callback_data=f"astog_del_{chat_id}")],
        [InlineKeyboardButton(f"🎯 Username Antispam {user_status}", callback_data=f"astog_user_{chat_id}")],
        [InlineKeyboardButton(f"🤖 Bots Antispam {bot_status}", callback_data=f"astog_bot_{chat_id}")],
        [
            InlineKeyboardButton("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}"),
            InlineKeyboardButton("☀️ Exceptions", callback_data=f"asexc_main_{chat_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# 2. Quote Antispam UI
def get_antispam_quote_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    target = cfg.get("quote_target", "groups")
    p = cfg.get(f"quote_{target}_penalty", "Off")
    del_status = "✔️" if cfg["quote_delete"] else "✖️"

    t_btn = lambda name, key: f"» {name} «" if target == key else name
    p_btn = lambda name: f"✅ {name}" if p == name else name

    keyboard = [
        [
            InlineKeyboardButton(t_btn("📣 Channels", "channels"), callback_data=f"asqtar_channels_{chat_id}"),
            InlineKeyboardButton(t_btn("👥 Groups", "groups"), callback_data=f"asqtar_groups_{chat_id}")
        ],
        [
            InlineKeyboardButton(t_btn("👤 Users", "users"), callback_data=f"asqtar_users_{chat_id}"),
            InlineKeyboardButton(t_btn("🤖 Bots", "bots"), callback_data=f"asqtar_bots_{chat_id}")
        ],
        [InlineKeyboardButton("➖➖➖➖➖➖➖➖", callback_data="none")],
        [
            InlineKeyboardButton(p_btn("❌ Off"), callback_data=f"asqpen_Off_{chat_id}"),
            InlineKeyboardButton(p_btn("! Warn"), callback_data=f"asqpen_Warn_{chat_id}"),
            InlineKeyboardButton(p_btn("! Kick"), callback_data=f"asqpen_Kick_{chat_id}")
        ],
        [
            InlineKeyboardButton(p_btn("🔇 Mute"), callback_data=f"asqpen_Mute_{chat_id}"),
            InlineKeyboardButton(p_btn("🚷 Ban"), callback_data=f"asqpen_Ban_{chat_id}")
        ],
        [InlineKeyboardButton(f"🗑 Delete Messages {del_status}", callback_data=f"asqtog_del_{chat_id}")],
        [
            InlineKeyboardButton("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}"),
            InlineKeyboardButton("☀️ Exceptions", callback_data=f"asexc_main_{chat_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# 3. Exceptions & Whitelist UI
def get_exceptions_keyboard(chat_id: int):
    keyboard = [
        [InlineKeyboardButton("🔤 Show Whitelist", callback_data=f"asexc_show_{chat_id}")],
        [
            InlineKeyboardButton("➕ Add", callback_data=f"asexc_add_{chat_id}"),
            InlineKeyboardButton("➖ Remove", callback_data=f"asexc_rem_{chat_id}")
        ],
        [InlineKeyboardButton("🌐 Global Whitelist", callback_data=f"asexc_global_{chat_id}")],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"aspam_tglinks_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ----------------- PUNISHMENT DISPATCHER ----------------- #
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
                await chat.send_message(f"🚫 {user.mention_html()} banned for reaching maximum warns ({limit}/{limit}) due to {reason}.", parse_mode="HTML")
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
        logger.error(f"Punishment error: {e}")

# ----------------- ANTI-SPAM CALLBACK HANDLER ----------------- #
async def antispam_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = query.from_user
    chat = query.message.chat

    if not await is_user_admin(chat.id, user.id, context):
        await safe_answer(query, "Sirf Admins settings badal sakte hain!", show_alert=True)
        return

    cfg = get_config(chat.id)

    # 1. Open Menus
    if data.startswith("aspam_tglinks_"):
        cid = int(data.split("_")[2])
        text = (
            "📘 <b>Telegram links</b>\n"
            "From this menu you can set a punishment for users who send messages that contain Telegram links.\n\n"
            "🎯 <b>Username Antispam:</b> triggers when a username is sent.\n"
            "🤖 <b>Bots Antispam:</b> triggers when a bot link is sent.\n\n"
            f"<b>Penalty:</b> {cfg['spam_penalty']}\n"
            f"<b>Deletion:</b> {'Yes ✔️' if cfg['spam_delete'] else 'No ✖️'}"
        )
        await query.edit_message_text(text, reply_markup=get_antispam_tglinks_keyboard(cid), parse_mode="HTML")
        await safe_answer(query)
        return

    if data.startswith("aspam_quote_") or data.startswith("asqtar_"):
        cid = int(data.split("_")[2])
        if data.startswith("asqtar_"):
            cfg["quote_target"] = data.split("_")[1]
            
        text = (
            "💭 <b>Quote</b>\n"
            "Select punishment for users who send messages containing quotes/forwards from external chats.\n\n"
            f"📣 <b>Channels:</b> {cfg['quote_channels_penalty']}\n"
            f"👥 <b>Groups:</b> {cfg['quote_groups_penalty']}\n"
            f"👤 <b>Users:</b> {cfg['quote_users_penalty']}\n"
            f"🤖 <b>Bots:</b> {cfg['quote_bots_penalty']}\n"
        )
        await query.edit_message_text(text, reply_markup=get_antispam_quote_keyboard(cid), parse_mode="HTML")
        await safe_answer(query)
        return

    # 2. Exceptions Menu
    if data.startswith("asexc_"):
        cid = int(data.split("_")[2])
        sub = data.split("_")[1]
        
        if sub == "main":
            text = (
                "☀️ <b>Antispam Exception</b>\n"
                "Manage the Telegram's links/usernames of groups and channels that will not be treated as spam.\n\n"
                "<i>The group links are automatically in the antispam exception.</i>"
            )
            await query.edit_message_text(text, reply_markup=get_exceptions_keyboard(cid), parse_mode="HTML")
        elif sub == "show":
            wl = get_whitelist(cid)
            wl_text = "\n".join([f"• <code>{x}</code>" for x in wl]) if wl else "No whitelisted links/usernames."
            await safe_answer(query, f"Whitelist:\n{wl_text}", show_alert=True)
            return
        elif sub == "add":
            await safe_answer(query, "Whitelist me add karne ke liye chat me `/whitelist @username_ya_link` likhein.", show_alert=True)
            return
        elif sub == "rem":
            await safe_answer(query, "Remove karne ke liye `/unwhitelist @username_ya_link` likhein.", show_alert=True)
            return
        elif sub == "global":
            await safe_answer(query, "Global Whitelist active hai.", show_alert=True)
            return
            
        await safe_answer(query)
        return

    # 3. Penalties & Toggles for Links
    if data.startswith("aspen_"):
        pen = data.split("_")[1]
        cid = int(data.split("_")[2])
        cfg["spam_penalty"] = pen
        text = (
            "📘 <b>Telegram links</b>\n"
            "From this menu you can set a punishment for users who send messages that contain Telegram links.\n\n"
            f"<b>Penalty:</b> {cfg['spam_penalty']}\n"
            f"<b>Deletion:</b> {'Yes ✔️' if cfg['spam_delete'] else 'No ✖️'}"
        )
        await query.edit_message_text(text, reply_markup=get_antispam_tglinks_keyboard(cid), parse_mode="HTML")
        await safe_answer(query, f"Penalty set to {pen}")
        return

    if data.startswith("astog_"):
        tog = data.split("_")[1]
        cid = int(data.split("_")[2])
        if tog == "del":
            cfg["spam_delete"] = not cfg["spam_delete"]
        elif tog == "user":
            cfg["spam_usernames"] = not cfg["spam_usernames"]
        elif tog == "bot":
            cfg["spam_bots"] = not cfg["spam_bots"]

        text = (
            "📘 <b>Telegram links</b>\n"
            "From this menu you can set a punishment for users who send messages that contain Telegram links.\n\n"
            f"<b>Penalty:</b> {cfg['spam_penalty']}\n"
            f"<b>Deletion:</b> {'Yes ✔️' if cfg['spam_delete'] else 'No ✖️'}"
        )
        await query.edit_message_text(text, reply_markup=get_antispam_tglinks_keyboard(cid), parse_mode="HTML")
        await safe_answer(query, "Updated!")
        return

    # 4. Quote Penalties & Toggles
    if data.startswith("asqpen_"):
        pen = data.split("_")[1]
        cid = int(data.split("_")[2])
        target = cfg.get("quote_target", "groups")
        cfg[f"quote_{target}_penalty"] = pen

        text = (
            "💭 <b>Quote</b>\n"
            "Select punishment for users who send messages containing quotes from external chats.\n\n"
            f"📣 <b>Channels:</b> {cfg['quote_channels_penalty']}\n"
            f"👥 <b>Groups:</b> {cfg['quote_groups_penalty']}\n"
            f"👤 <b>Users:</b> {cfg['quote_users_penalty']}\n"
            f"🤖 <b>Bots:</b> {cfg['quote_bots_penalty']}\n"
        )
        await query.edit_message_text(text, reply_markup=get_antispam_quote_keyboard(cid), parse_mode="HTML")
        await safe_answer(query, f"{target.capitalize()} penalty set to {pen}")
        return

    if data.startswith("asqtog_del_"):
        cid = int(data.split("_")[2])
        cfg["quote_delete"] = not cfg["quote_delete"]
        text = (
            "💭 <b>Quote</b>\n"
            "Select punishment for users who send messages containing quotes from external chats.\n\n"
            f"📣 <b>Channels:</b> {cfg['quote_channels_penalty']}\n"
            f"👥 <b>Groups:</b> {cfg['quote_groups_penalty']}\n"
            f"👤 <b>Users:</b> {cfg['quote_users_penalty']}\n"
            f"🤖 <b>Bots:</b> {cfg['quote_bots_penalty']}\n"
        )
        await query.edit_message_text(text, reply_markup=get_antispam_quote_keyboard(cid), parse_mode="HTML")
        await safe_answer(query, "Quote deletion toggled!")
        return

# ----------------- WHITELIST MANAGEMENT ----------------- #
async def add_whitelist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not await is_user_admin(chat.id, user.id, context):
        return

    if not context.args:
        await update.message.reply_text("Usage: `/whitelist @username` ya `/whitelist t.me/joinchat`", parse_mode="Markdown")
        return

    target = context.args[0].lower().replace("@", "")
    wl = get_whitelist(chat.id)
    wl.add(target)
    await update.message.reply_text(f"✅ `@{target}` ko Antispam Whitelist me add kar diya gaya.", parse_mode="Markdown")

async def remove_whitelist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not await is_user_admin(chat.id, user.id, context):
        return

    if not context.args:
        await update.message.reply_text("Usage: `/unwhitelist @username`", parse_mode="Markdown")
        return

    target = context.args[0].lower().replace("@", "")
    wl = get_whitelist(chat.id)
    if target in wl:
        wl.remove(target)
        await update.message.reply_text(f"❌ `@{target}` ko Whitelist se hata diya gaya.", parse_mode="Markdown")
    else:
        await update.message.reply_text("Yeh entry whitelist me nahi hai.")

# ----------------- SECURITY & AUTO MODERATION FILTER ----------------- #
async def deep_antispam_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    chat = update.effective_chat
    user = update.effective_user
    msg = update.message
    text = msg.text or msg.caption or ""
    cfg = get_config(chat.id)
    wl = get_whitelist(chat.id)

    # Admins & Owners Bypass
    if await is_user_admin(chat.id, user.id, context):
        return

    # --- 1. QUOTE & FORWARD ANTISPAM ---
    if msg.forward_origin:
        origin_type = msg.forward_origin.type
        penalty = "Off"
        
        if origin_type == "channel":
            penalty = cfg.get("quote_channels_penalty", "Off")
        elif origin_type == "chat":
            penalty = cfg.get("quote_groups_penalty", "Off")
        elif origin_type == "user":
            sender_user = getattr(msg.forward_origin, 'sender_user', None)
            if sender_user and sender_user.is_bot:
                penalty = cfg.get("quote_bots_penalty", "Off")
            else:
                penalty = cfg.get("quote_users_penalty", "Off")

        if penalty != "Off" or cfg.get("quote_delete"):
            await execute_punishment(penalty, cfg.get("quote_delete", True), update, context, f"Forward/Quote from {origin_type}")
            return

    # --- 2. TELEGRAM LINK ANTISPAM ---
    link_pattern = r"(https?://t\.me/\S+|t\.me/\S+|telegram\.me/\S+)"
    found_links = re.findall(link_pattern, text, re.IGNORECASE)

    if found_links and cfg["spam_penalty"] != "Off":
        for link in found_links:
            clean_link = link.lower()
            # Whitelist verification
            if not any(exc in clean_link for exc in wl):
                await execute_punishment(cfg["spam_penalty"], cfg["spam_delete"], update, context, "Telegram link")
                return

    # --- 3. BOTS ANTISPAM ---
    if cfg.get("spam_bots"):
        if re.search(r"t\.me/\w+bot\b", text, re.IGNORECASE) or re.search(r"@\w+bot\b", text, re.IGNORECASE):
            await execute_punishment(cfg["spam_penalty"], cfg["spam_delete"], update, context, "Bot link/mention")
            return

    # --- 4. USERNAME ANTISPAM ---
    if cfg.get("spam_usernames"):
        usernames = re.findall(r"@(\w+)", text)
        for un in usernames:
            if un.lower() not in wl:
                await execute_punishment(cfg["spam_penalty"], cfg["spam_delete"], update, context, f"Username spam (@{un})")
                return

# ----------------- SYSTEM & SETTINGS COMMANDS ----------------- #
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
            process = subprocess.run(cmd, capture_output=True, text=True, check=True)
            await status_msg.edit_text(f"✅ Installed!\n\n⚙️ Restarting bot...", parse_mode="Markdown")
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
        "🛡 **Group Security & Settings Panel**\nSelect the options you want to configure:",
        reply_markup=get_main_settings_keyboard(chat.id),
        parse_mode="Markdown"
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        keyboard = [[InlineKeyboardButton("➕ Add Me to Your Group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
        await update.message.reply_text("🛡 Group Security Bot active! Add to group and send `/settings`.", reply_markup=InlineKeyboardMarkup(keyboard))

async def settings_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat = query.message.chat
    user = query.from_user

    if data == "cfg_close":
        try:
            await query.message.delete()
        except Exception:
            pass
        await safe_answer(query)
        return

    if not await is_user_admin(chat.id, user.id, context):
        await safe_answer(query, "Sirf admins change kar sakte hain.", show_alert=True)
        return

    if data.startswith("cfg_page_"):
        page = data.split("_")[2]
        cid = int(data.split("_")[3])
        kb = get_page2_settings_keyboard(cid) if page == "2" else get_main_settings_keyboard(cid)
        await query.edit_message_reply_markup(reply_markup=kb)
        await safe_answer(query)
        return

    if data.startswith("aspam_main_"):
        cid = int(data.split("_")[2])
        await antispam_callback_handler(update, context)
        return

# ----------------- MAIN APP ----------------- #
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("update", update_command))
    app.add_handler(CommandHandler("whitelist", add_whitelist_cmd))
    app.add_handler(CommandHandler("unwhitelist", remove_whitelist_cmd))

    # Dynamic Callback Handlers
    app.add_handler(CallbackQueryHandler(antispam_callback_handler, pattern="^(aspam_|aspen_|astog_|asqtar_|asqpen_|asqtog_|asexc_)"))
    app.add_handler(CallbackQueryHandler(settings_callback_handler, pattern="^cfg_"))

    # Security & Mod Message Handlers
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^pip3?\s+install\s+"), auto_pip_installer))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, deep_antispam_moderator))

    print("🛡 Group Help Security Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
