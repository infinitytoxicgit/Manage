import logging
import re
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ----------------- CONFIGURATION ----------------- #
BOT_TOKEN = ""  
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# In-Memory Settings & Security Storage
group_settings = {}
user_warns = {}
staff_roles = {}  # Format: {chat_id: {user_id: "role"}} (roles: admin, mod, cleaner, muter)

# Default Group Security Settings
DEFAULT_CONFIG = {
    "antilink": True,
    "antispam": True,
    "captcha": True,
    "warn_limit": 3,
    "night_mode": False,
    "lock_media": False
}

def get_config(chat_id: int):
    if chat_id not in group_settings:
        group_settings[chat_id] = DEFAULT_CONFIG.copy()
    return group_settings[chat_id]

# ----------------- PERMISSION CHECKERS ----------------- #
async def is_user_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in ["administrator", "creator"]:
            return True
        # Custom bot roles check
        role = staff_roles.get(chat_id, {}).get(user_id)
        return role in ["admin", "mod"]
    except Exception:
        return False

# ----------------- INLINE SETTINGS MENUS ----------------- #
def get_main_settings_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    btn = lambda key, text: f"{text} {'✅' if cfg.get(key) else '❌'}"
    
    keyboard = [
        [
            InlineKeyboardButton("📜 Regulation", callback_data=f"cfg_view_regulation_{chat_id}"),
            InlineKeyboardButton(btn("antispam", "✉️ Anti-Spam"), callback_data=f"cfg_toggle_antispam_{chat_id}")
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
            InlineKeyboardButton(btn("antilink", "🔗 Link Block"), callback_data=f"cfg_toggle_link_{chat_id}")
        ],
        [
            InlineKeyboardButton(btn("night_mode", "🌘 Night Mode"), callback_data=f"cfg_toggle_night_{chat_id}"),
            InlineKeyboardButton(f"⚠️ Warn Limit ({cfg.get('warn_limit')})", callback_data=f"cfg_warn_limit_{chat_id}")
        ],
        [
            InlineKeyboardButton("Next Page ➡️", callback_data=f"cfg_page_2_{chat_id}")
        ],
        [
            InlineKeyboardButton("❎ Close", callback_data="cfg_close")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_page2_settings_keyboard(chat_id: int):
    keyboard = [
        [InlineKeyboardButton("📁 Topic", callback_data=f"cfg_view_topic_{chat_id}")],
        [InlineKeyboardButton("🔤 Banned Words", callback_data=f"cfg_view_banned_{chat_id}")],
        [InlineKeyboardButton("👥 Members Management", callback_data=f"cfg_view_members_{chat_id}")],
        [InlineKeyboardButton("🎭 Magic Stickers & GIFs", callback_data=f"cfg_view_media_{chat_id}")],
        [InlineKeyboardButton("🔍 Log Channel", callback_data=f"cfg_view_logs_{chat_id}")],
        [
            InlineKeyboardButton("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}"),
            InlineKeyboardButton("❎ Close", callback_data="cfg_close")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ----------------- COMMANDS ----------------- #
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if chat.type == "private":
        keyboard = [
            [InlineKeyboardButton("➕ Add Me to Your Group", url=f"https://t.me/{context.bot.username}?startgroup=true")]
        ]
        await update.message.reply_text(
            f"Hello {user.first_name}!\n\n"
            "Main **Group Security & Moderation Bot** hoon.\n"
            "Mujhe apne group me add karein aur admin banayein, fir `/settings` command run karein security manage karne ke liye.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("Group Security Bot active hai. Type `/settings` for inline panel.")

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_text("Yeh command sirf groups ke andar chalegi.")
        return

    if not await is_user_admin(chat.id, user.id, context):
        await update.message.reply_text("❌ Sirf Admins `/settings` open kar sakte hain.")
        return

    await update.message.reply_text(
        "🛡 **Group Security & Settings Panel**\nSelect the options you want to configure:",
        reply_markup=get_main_settings_keyboard(chat.id),
        parse_mode="Markdown"
    )

# ----------------- MODERATION COMMANDS ----------------- #
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not await is_user_admin(chat.id, user.id, context):
        return

    target_user = update.message.reply_to_message.from_user if update.message.reply_to_message else None
    if not target_user:
        await update.message.reply_text("Command reply me use karein: Reply to a user with `/ban`")
        return

    try:
        await context.bot.ban_chat_member(chat.id, target_user.id)
        await update.message.reply_text(f"🚫 User {target_user.mention_html()} ko ban kar diya gaya.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not await is_user_admin(chat.id, user.id, context):
        return

    target_user = update.message.reply_to_message.from_user if update.message.reply_to_message else None
    if not target_user:
        await update.message.reply_text("Command reply me use karein: Reply to a user with `/mute`")
        return

    try:
        await context.bot.restrict_chat_member(
            chat.id,
            target_user.id,
            permissions=ChatPermissions(can_send_messages=False)
        )
        await update.message.reply_text(f"🔇 User {target_user.mention_html()} ko mute kar diya gaya.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not await is_user_admin(chat.id, user.id, context):
        return

    target_user = update.message.reply_to_message.from_user if update.message.reply_to_message else None
    if not target_user:
        await update.message.reply_text("Command reply me use karein: Reply to a user with `/unmute`")
        return

    try:
        await context.bot.restrict_chat_member(
            chat.id,
            target_user.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        await update.message.reply_text(f"🔊 User {target_user.mention_html()} ko unmute kar diya gaya.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not await is_user_admin(chat.id, user.id, context):
        return

    target_user = update.message.reply_to_message.from_user if update.message.reply_to_message else None
    if not target_user:
        await update.message.reply_text("Command reply me use karein: Reply to a user with `/warn`")
        return

    chat_warns = user_warns.setdefault(chat.id, {})
    current_warns = chat_warns.get(target_user.id, 0) + 1
    chat_warns[target_user.id] = current_warns

    limit = get_config(chat.id).get("warn_limit", 3)
    if current_warns >= limit:
        chat_warns[target_user.id] = 0
        try:
            await context.bot.ban_chat_member(chat.id, target_user.id)
            await update.message.reply_text(f"🚫 {target_user.mention_html()} reached maximum warns ({limit}/{limit}) and was banned.", parse_mode="HTML")
        except Exception as e:
            await update.message.reply_text(f"Error banning user: {e}")
    else:
        await update.message.reply_text(f"⚠️ {target_user.mention_html()} has been warned! ({current_warns}/{limit})", parse_mode="HTML")

async def delete_message_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not await is_user_admin(chat.id, user.id, context):
        return

    if update.message.reply_to_message:
        try:
            await update.message.reply_to_message.delete()
            await update.message.delete()
        except Exception:
            pass

# ----------------- INLINE BUTTON HANDLER ----------------- #
async def settings_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = query.from_user
    chat = query.message.chat

    if data == "cfg_close":
        await query.message.delete()
        return

    if not await is_user_admin(chat.id, user.id, context):
        await query.answer("Sirf admins yeh settings change kar sakte hain.", show_alert=True)
        return

    parts = data.split("_")
    action = parts[1]
    
    if action == "page":
        page_no = parts[2]
        chat_id = int(parts[3])
        if page_no == "2":
            await query.edit_message_reply_markup(reply_markup=get_page2_settings_keyboard(chat_id))
        else:
            await query.edit_message_reply_markup(reply_markup=get_main_settings_keyboard(chat_id))
        await query.answer()
        return

    if action == "toggle":
        setting_key = parts[2]
        chat_id = int(parts[3])
        cfg = get_config(chat_id)

        if setting_key == "link":
            cfg["antilink"] = not cfg["antilink"]
        elif setting_key == "antispam":
            cfg["antispam"] = not cfg["antispam"]
        elif setting_key == "captcha":
            cfg["captcha"] = not cfg["captcha"]
        elif setting_key == "media":
            cfg["lock_media"] = not cfg["lock_media"]
        elif setting_key == "night":
            cfg["night_mode"] = not cfg["night_mode"]

        await query.edit_message_reply_markup(reply_markup=get_main_settings_keyboard(chat_id))
        await query.answer("Setting updated!")
        return

    if action == "warn":
        chat_id = int(parts[3])
        cfg = get_config(chat_id)
        # Cycle warns 3 -> 5 -> 3
        cfg["warn_limit"] = 5 if cfg["warn_limit"] == 3 else 3
        await query.edit_message_reply_markup(reply_markup=get_main_settings_keyboard(chat_id))
        await query.answer(f"Warn limit set to {cfg['warn_limit']}")
        return

    await query.answer("Configuration module opened.")

# ----------------- SECURITY & AUTO MODERATION ----------------- #
async def auto_moderation_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    chat = update.effective_chat
    user = update.effective_user
    text = update.message.text or update.message.caption or ""
    cfg = get_config(chat.id)

    # Bypass checks for group admins
    if await is_user_admin(chat.id, user.id, context):
        return

    # 1. Anti-Link Security
    if cfg.get("antilink"):
        url_pattern = r"(https?://\S+|t\.me/\S+|telegram\.me/\S+)"
        if re.search(url_pattern, text):
            try:
                await update.message.delete()
                warn_msg = await chat.send_message(f"⚠️ {user.mention_html()}, links are not allowed here!", parse_mode="HTML")
                return
            except Exception:
                pass

    # 2. Media Lock Security
    if cfg.get("lock_media"):
        if update.message.photo or update.message.video or update.message.sticker or update.message.animation:
            try:
                await update.message.delete()
                return
            except Exception:
                pass

# ----------------- WELCOME & CAPTCHA ----------------- #
async def welcome_captcha_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    cfg = get_config(chat.id)

    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            await chat.send_message("Thanks for adding me! Make me Admin to enable full group protection.")
            continue

        if cfg.get("captcha"):
            # Restrict permissions until verified
            try:
                await context.bot.restrict_chat_member(
                    chat.id,
                    member.id,
                    permissions=ChatPermissions(can_send_messages=False)
                )
            except Exception:
                pass

            keyboard = [
                [InlineKeyboardButton("✅ I am human (Verify)", callback_data=f"captcha_verify_{member.id}")]
            ]
            await chat.send_message(
                f"Welcome {member.mention_html()}!\nPlease click the button below to verify yourself and start chatting.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )

async def captcha_verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    chat = query.message.chat
    data = query.data

    if data.startswith("captcha_verify_"):
        target_id = int(data.split("_")[2])
        if user.id != target_id:
            await query.answer("Yeh button aapke liye nahi hai!", show_alert=True)
            return

        # Restore permissions
        try:
            await context.bot.restrict_chat_member(
                chat.id,
                user.id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
            await query.message.delete()
            await chat.send_message(f"✅ {user.mention_html()} successfully verified!", parse_mode="HTML")
        except Exception as e:
            await query.answer("Permission error, ensure bot is admin.", show_alert=True)

# ----------------- MAIN INITIALIZER ----------------- #
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Basic Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("settings", settings_command))

    # Moderation Commands
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("mute", mute_user))
    app.add_handler(CommandHandler("unmute", unmute_user))
    app.add_handler(CommandHandler("warn", warn_user))
    app.add_handler(CommandHandler("del", delete_message_cmd))

    # Callback Query Handlers (Settings & Captcha)
    app.add_handler(CallbackQueryHandler(settings_callback_handler, pattern="^cfg_"))
    app.add_handler(CallbackQueryHandler(captcha_verify_callback, pattern="^captcha_verify_"))

    # Service & Chat Messages
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_captcha_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, auto_moderation_guard))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
