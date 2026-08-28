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

# In-Memory Settings & Security Storage
group_settings = {}
user_warns = {}
staff_roles = {}

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

# ----------------- SAFE CALLBACK ANSWER ----------------- #
async def safe_answer(query, text=None, show_alert=False):
    """Prevents crash when query is too old or already answered."""
    try:
        if text:
            await query.answer(text=text, show_alert=show_alert)
        else:
            await query.answer()
    except BadRequest as e:
        if "Query is too old" in str(e) or "query id is invalid" in str(e):
            logger.warning("Ignored expired callback query.")
        else:
            logger.error(f"Callback answer error: {e}")
    except Exception as e:
        logger.error(f"Unexpected callback error: {e}")

# ----------------- PERMISSION CHECKERS ----------------- #
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

# ----------------- AUTO PIP INSTALL & RESTART ----------------- #
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
            await update.message.reply_text("❌ Kripya package ka naam bhi dein (e.g. `pip install aiohttp`)")
            return

        status_msg = await update.message.reply_text(
            f"📦 **VPS Installation Started...**\nInstalling: `{' '.join(packages)}`",
            parse_mode="Markdown"
        )

        try:
            cmd = [sys.executable, "-m", "pip", "install"] + packages
            process = subprocess.run(cmd, capture_output=True, text=True, check=True)

            log_output = process.stdout[-800:] if len(process.stdout) > 800 else process.stdout
            await status_msg.edit_text(
                f"✅ **Installation Successful!**\n```\n{log_output.strip()}\n```\n\n⚙️ **Restarting bot via `python3 bot.py`...**",
                parse_mode="Markdown"
            )

            os.execv(sys.executable, ["python3", "bot.py"])

        except subprocess.CalledProcessError as e:
            err = e.stderr or e.stdout
            await status_msg.edit_text(f"❌ **Installation Failed:**\n```\n{err[-800:]}\n```", parse_mode="Markdown")
        except Exception as e:
            await status_msg.edit_text(f"❌ **Error:** `{str(e)}`", parse_mode="Markdown")

# ----------------- AUTO UPDATE SYSTEM ----------------- #
async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in OWNER_IDS:
        await update.message.reply_text("⛔ Sirf authorized bot owners hi is command ko use kar sakte hain.")
        return

    status_msg = await update.message.reply_text("🔄 **Update Process Started...**\nRunning `git stash` & `git pull`...", parse_mode="Markdown")

    try:
        subprocess.run(["git", "stash"], capture_output=True, text=True, check=True)
        pull_res = subprocess.run(["git", "pull"], capture_output=True, text=True, check=True)
        
        output_log = f"**Git Output:**\n```\n{pull_res.stdout.strip()}\n```"
        await status_msg.edit_text(f"{output_log}\n\n⚙️ **Restarting bot via `python3 bot.py`...**", parse_mode="Markdown")

        os.execv(sys.executable, ["python3", "bot.py"])

    except subprocess.CalledProcessError as e:
        err_msg = e.stderr or e.stdout
        await status_msg.edit_text(f"❌ **Git Error Failed:**\n```\n{err_msg}\n```", parse_mode="Markdown")
    except Exception as e:
        await status_msg.edit_text(f"❌ **Error during update/restart:**\n`{str(e)}`", parse_mode="Markdown")

# ----------------- INLINE SETTINGS MENUS ----------------- #
def get_main_settings_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    btn = lambda key, text: f"{text} {'✅' if cfg.get(key) else '❌'}"
    
    keyboard = [
        [
            InlineKeyboardButton("📜 Regulation", callback_data=f"cfg_view_reg_{chat_id}"),
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

# ----------------- BASIC COMMANDS ----------------- #
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
            "Mujhe group me add karein aur admin banayein, fir `/settings` command run karein.",
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

# ----------------- INLINE CALLBACK HANDLER ----------------- #
async def settings_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = query.from_user
    chat = query.message.chat

    if data == "cfg_close":
        try:
            await query.message.delete()
        except Exception:
            pass
        await safe_answer(query)
        return

    if not await is_user_admin(chat.id, user.id, context):
        await safe_answer(query, "Sirf admins settings change kar sakte hain.", show_alert=True)
        return

    parts = data.split("_")
    action = parts[1]
    
    if action == "page":
        page_no = parts[2]
        chat_id = int(parts[3])
        try:
            if page_no == "2":
                await query.edit_message_reply_markup(reply_markup=get_page2_settings_keyboard(chat_id))
            else:
                await query.edit_message_reply_markup(reply_markup=get_main_settings_keyboard(chat_id))
        except Exception:
            pass
        await safe_answer(query)
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

        try:
            await query.edit_message_reply_markup(reply_markup=get_main_settings_keyboard(chat_id))
        except Exception:
            pass
        await safe_answer(query, "Setting updated!")
        return

    if action == "warn":
        chat_id = int(parts[3])
        cfg = get_config(chat_id)
        cfg["warn_limit"] = 5 if cfg["warn_limit"] == 3 else 3
        try:
            await query.edit_message_reply_markup(reply_markup=get_main_settings_keyboard(chat_id))
        except Exception:
            pass
        await safe_answer(query, f"Warn limit set to {cfg['warn_limit']}")
        return

    await safe_answer(query, "Module opened.")

# ----------------- SECURITY & AUTO MODERATION ----------------- #
async def auto_moderation_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    chat = update.effective_chat
    user = update.effective_user
    text = update.message.text or update.message.caption or ""
    cfg = get_config(chat.id)

    if await is_user_admin(chat.id, user.id, context):
        return

    # Anti-Link Filter
    if cfg.get("antilink"):
        url_pattern = r"(https?://\S+|t\.me/\S+|telegram\.me/\S+)"
        if re.search(url_pattern, text):
            try:
                await update.message.delete()
                await chat.send_message(f"⚠️ {user.mention_html()}, links are not allowed here!", parse_mode="HTML")
                return
            except Exception:
                pass

    # Media Lock Filter
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
                f"Welcome {member.mention_html()}!\nPlease click the button below to verify yourself.",
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
            await safe_answer(query, "Yeh button aapke liye nahi hai!", show_alert=True)
            return

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
            await chat.send_message(f"✅ {user.mention_html()} verified successfully!", parse_mode="HTML")
        except Exception:
            await safe_answer(query, "Permission error, ensure bot is admin.", show_alert=True)

# ----------------- GLOBAL ERROR HANDLER ----------------- #
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log exceptions caused by Updates."""
    if isinstance(context.error, BadRequest) and ("Query is too old" in str(context.error) or "query id is invalid" in str(context.error)):
        logger.warning("Captured and handled expired callback query gracefully.")
        return
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

# ----------------- MAIN RUNNER ----------------- #
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register Global Error Handler
    app.add_error_handler(error_handler)

    # Core & Owner Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("update", update_command))
    app.add_handler(CommandHandler("settings", settings_command))

    # Moderation Commands
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("mute", mute_user))
    app.add_handler(CommandHandler("unmute", unmute_user))
    app.add_handler(CommandHandler("warn", warn_user))
    app.add_handler(CommandHandler("del", delete_message_cmd))

    # Callbacks
    app.add_handler(CallbackQueryHandler(settings_callback_handler, pattern="^cfg_"))
    app.add_handler(CallbackQueryHandler(captcha_verify_callback, pattern="^captcha_verify_"))

    # Event Handlers
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_captcha_handler))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^pip3?\s+install\s+"), auto_pip_installer))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, auto_moderation_guard))

    print("Bot is up and running...")
    app.run_polling()

if __name__ == "__main__":
    main()
