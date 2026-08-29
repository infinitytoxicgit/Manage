import os
import sys
import subprocess
import logging
import re
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
)

from config import BOT_TOKEN, OWNER_IDS
from database import get_config, save_config, add_whitelist_item, remove_whitelist_item, get_whitelist
from utils import (
    create_btn, fast_edit, is_user_admin, send_custom_bundle, format_template,
    parse_custom_buttons, parse_time_duration
)

from modules.settings import get_page1_settings_keyboard, get_page2_settings_keyboard
from modules.welcome import handle_welcome_callbacks
from modules.goodbye import handle_goodbye_callbacks
from modules.antiflood import handle_antiflood_callbacks
from modules.alphabets import handle_alphabets_callbacks
from modules.captcha import handle_captcha_callbacks
from modules.checks import handle_checks_callbacks
from modules.regulations import get_regulations_keyboard, get_cmd_permissions_keyboard
from modules.settings import get_page1_settings_keyboard
from modules.antispam import get_totallinks_keyboard

user_states = {}

# Unified Router
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

    # Extract Chat ID
    match = re.search(r"(-?\d+)$", data)
    cid = int(match.group(1)) if match else chat.id

    if not await is_user_admin(cid, user.id, context):
        try:
            await query.answer("Sirf Admins settings badal sakte hain!", show_alert=True)
        except Exception:
            pass
        return

    bot_info = await context.bot.get_me()

    # Route to individual modules
    if data.startswith("set_open_"):
        mode = data.split("_")[2]
        header_text = f"<b>SETTINGS</b>\nGroup: {chat.title}\n\n<i>Select one of the settings that you want to change.</i>"
        if mode == "here":
            await fast_edit(query, header_text, get_page1_settings_keyboard(cid))
    elif data.startswith("cfg_page_"):
        page = data.split("_")[2]
        header_text = f"<b>SETTINGS</b>\nGroup: {chat.title}\n\n<i>Select one of the settings that you want to change.</i>"
        await fast_edit(query, header_text, get_page2_settings_keyboard(cid) if page=="2" else get_page1_settings_keyboard(cid))
    elif data.startswith("wlc_") or data.startswith("cfg_view_welcome_"):
        await handle_welcome_callbacks(query, data, cid, user, chat, user_states)
    elif data.startswith("gby_") or data.startswith("cfg_view_goodbye_"):
        await handle_goodbye_callbacks(query, data, cid, user, chat, bot_info.username, user_states)
    elif data.startswith("fl") or data.startswith("cfg_view_flood_"):
        await handle_antiflood_callbacks(query, data, cid, user, user_states)
    elif data.startswith("alp") or data.startswith("cfg_view_alphabets_"):
        await handle_alphabets_callbacks(query, data, cid)
    elif data.startswith("cpt_") or data.startswith("cfg_view_captcha_"):
        await handle_captcha_callbacks(query, data, cid, user, user_states)
    elif data.startswith("chk") or data.startswith("cfg_view_checks_"):
        await handle_checks_callbacks(query, data, cid)
    elif data.startswith("cfg_view_reg_") or data.startswith("reg_"):
        await fast_edit(query, "📜 <b>Group's regulations</b>", get_regulations_keyboard(cid))

# Interactive Message Receiver
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
    text = update.message.text or update.message.caption or ""

    if state == "awaiting_wlc_text":
        cfg["welcome_text"] = text
        save_config(chat_id, cfg)
        await update.message.reply_text("✅ <b>Welcome text updated!</b>", parse_mode="HTML")
        return True
    elif state == "awaiting_wlc_buttons":
        cfg["welcome_buttons_raw"] = text
        save_config(chat_id, cfg)
        await update.message.reply_text("✅ <b>Welcome buttons updated!</b>", parse_mode="HTML")
        return True
    return False

# Commands
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not await is_user_admin(chat.id, update.effective_user.id, context):
        await update.message.reply_text("❌ Sirf Admins `/settings` open kar sakte hain.")
        return
    bot_info = await context.bot.get_me()
    keyboard = [
        [create_btn("👥 Open here", callback_data=f"set_open_here_{chat.id}")],
        [create_btn("👤 Open in Private Chat", url=f"https://t.me/{bot_info.username}?start=settings_{chat.id}")]
    ]
    await update.message.reply_text("Where do you want to open the settings menu?", reply_markup=InlineKeyboardMarkup(keyboard))

async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in OWNER_IDS:
        return
    status_msg = await update.message.reply_text("🔄 Updating bot...", parse_mode="Markdown")
    try:
        subprocess.run(["git", "stash"], capture_output=True, text=True, check=True)
        subprocess.run(["git", "pull"], capture_output=True, text=True, check=True)
        await status_msg.edit_text("⚙️ Git pull complete. Restarting...", parse_mode="Markdown")
        os.execv(sys.executable, ["python3", "main.py"])
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: `{str(e)}`", parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("update", update_command))
    app.add_handler(CallbackQueryHandler(unified_callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, interactive_state_processor))
    print("🛡 Group Security Bot Modular Architecture Started...")
    app.run_polling()

if __name__ == "__main__":
    main()
