import os
import sys
import subprocess
import logging
import re
import shutil
from pathlib import Path
from telegram import Update, InlineKeyboardMarkup
from telegram.error import Forbidden
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
)

from config import BOT_TOKEN, OWNER_IDS
from database import get_config, save_config, get_user_warns
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
from modules.regulations import handle_regulations_callbacks

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
            await query.answer("❌ Sirf Group Owner aur Admins settings badal sakte hain!", show_alert=True)
        except Exception:
            pass
        return

    bot_info = await context.bot.get_me()

    # /settings opening selector
    if data.startswith("set_open_"):
        mode = data.split("_")[2]
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
                start_btn = [[create_btn("🤖 Start Bot in PM", url=f"https://t.me/{bot_info.username}?start=settings_{cid}")]]
                await fast_edit(query, "⚠️ Pehle bot ko PM me /start karein.", InlineKeyboardMarkup(start_btn))
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
        cfg = get_config(cid)
        try:
            await query.answer(cfg.get("rules_text", "No rules set.")[:200], show_alert=True)
        except Exception:
            pass
        return

    # 1. Page Navigation
    if data.startswith("cfg_page_"):
        page = data.split("_")[2]
        chat_title = chat.title if chat.type != "private" else "Group"
        header_text = f"<b>SETTINGS</b>\nGroup: {chat_title}\n\n<i>Select one of the settings that you want to change.</i>"
        if page == "2":
            await fast_edit(query, header_text, get_page2_settings_keyboard(cid))
        else:
            await fast_edit(query, header_text, get_page1_settings_keyboard(cid))
        return

    # 2. Module Handlers
    if data.startswith("cfg_view_reg_") or data.startswith("reg_") or data.startswith("permset_"):
        await handle_regulations_callbacks(query, data, cid, user, chat, user_states, context)
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

# Interactive Message Receiver
async def interactive_state_processor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message or not update.message.from_user:
        return False
    chat_id = update.effective_chat.id
    user_id = update.message.from_user.id
    state_key = (chat_id, user_id)

    if state_key not in user_states:
        return False

    if not await is_user_admin(chat_id, user_id, context):
        user_states.pop(state_key, None)
        await update.message.reply_text("❌ Aapke paas settings edit karne ka right nahi hai.")
        return True

    state = user_states.pop(state_key)
    cfg = get_config(chat_id)
    msg = update.message
    text = msg.text or msg.caption or ""

    if state == "awaiting_reg_text":
        cfg["rules_text"] = text
        save_config(chat_id, cfg)
        kb = [[create_btn("⬅️ Back", callback_data=f"reg_custom_msg_{chat_id}")]]
        await msg.reply_text("✅ <b>Regulations message permanently saved!</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
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
        save_config(chat_id, cfg)
        kb = [[create_btn("⬅️ Back", callback_data=f"reg_custom_msg_{chat_id}")]]
        await msg.reply_text("✅ <b>Regulations media permanently saved!</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    elif state == "awaiting_reg_buttons":
        cfg["rules_buttons_raw"] = text
        save_config(chat_id, cfg)
        kb = parse_custom_buttons(text, chat_id)
        btn_list = kb.inline_keyboard if kb else []
        final_kb = list(btn_list) + [[create_btn("⬅️ Back", callback_data=f"reg_custom_msg_{chat_id}")]]
        await msg.reply_text(f"<code>{html.escape(text)}</code>", reply_markup=InlineKeyboardMarkup(final_kb), parse_mode="HTML")
        return True

    elif state == "awaiting_wlc_text":
        cfg["welcome_text"] = text
        save_config(chat_id, cfg)
        kb = [[create_btn("⬅️ Back", callback_data=f"wlc_custom_{chat_id}")]]
        await msg.reply_text("✅ <b>Welcome message set.</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
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
        save_config(chat_id, cfg)
        kb = [[create_btn("⬅️ Back", callback_data=f"wlc_custom_{chat_id}")]]
        await msg.reply_text("✅ <b>Welcome media set.</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    elif state == "awaiting_wlc_buttons":
        cfg["welcome_buttons_raw"] = text
        save_config(chat_id, cfg)
        kb = parse_custom_buttons(text, chat_id)
        btn_list = kb.inline_keyboard if kb else []
        final_kb = list(btn_list) + [[create_btn("⬅️ Back", callback_data=f"wlc_custom_{chat_id}")]]
        await msg.reply_text(f"<code>{html.escape(text)}</code>", reply_markup=InlineKeyboardMarkup(final_kb), parse_mode="HTML")
        return True

    elif state == "awaiting_gby_text":
        cfg["goodbye_text"] = text
        save_config(chat_id, cfg)
        kb = [[create_btn("⬅️ Back", callback_data=f"gby_custom_{chat_id}")]]
        await msg.reply_text("✅ <b>Goodbye message set.</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    elif state.startswith("awaiting_flood_dur_"):
        ptype = state.split("_")[3]
        parsed_sec = parse_time_duration(text)
        cfg["flood_duration_sec"] = parsed_sec
        cfg["flood_duration_str"] = text.strip()
        save_config(chat_id, cfg)
        kb = [[create_btn("⬅️ Back to Antiflood", callback_data=f"cfg_view_flood_{chat_id}")]]
        await msg.reply_text(f"✅ <b>Antiflood {ptype} duration set to {text}!</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return True

    return False

# Commands
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

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
    await update.message.reply_text("Where do you want to open the settings menu?", reply_markup=InlineKeyboardMarkup(keyboard))

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.effective_chat.type == "private":
        if context.args and context.args[0].startswith("settings_"):
            target_cid = int(context.args[0].replace("settings_", ""))
            header_text = "<b>SETTINGS</b>\n\n<i>Select one of the settings that you want to change.</i>"
            await update.message.reply_text(header_text, reply_markup=get_page1_settings_keyboard(target_cid), parse_mode="HTML")
            return

        keyboard = [[create_btn("➕ Add Me to Your Group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
        await update.message.reply_text("🛡 Group Security Bot active! Add to group and send `/settings`.", reply_markup=InlineKeyboardMarkup(keyboard))

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    cfg = get_config(chat.id)
    perm = cfg.get("perm_rules", "staff")

    if perm == "nobody":
        return
    if perm == "staff" and not await is_user_admin(chat.id, user.id, context):
        return
    if perm == "private" and chat.type != "private":
        try:
            await send_custom_bundle(user, user, cfg, mode="rules")
            await update.message.reply_text("📜 Group regulations have been sent to your PM.")
        except Exception:
            bot_info = await context.bot.get_me()
            await update.message.reply_text(f"Please start @{bot_info.username} in PM to receive the regulations.")
        return

    await send_custom_bundle(chat, user, cfg, mode="rules")

async def staff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    cfg = get_config(chat.id)
    perm = cfg.get("perm_staff", "everyone")

    if perm == "nobody":
        return
    if perm == "staff" and not await is_user_admin(chat.id, user.id, context):
        return

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
    cfg = get_config(chat.id)
    perm = cfg.get("perm_me", "private")

    if perm == "nobody":
        return
    if perm == "staff" and not await is_user_admin(chat.id, user.id, context):
        return

    warns = get_user_warns(chat.id, user.id)
    info = f"👤 <b>Your Info:</b>\n• Name: {user.mention_html()}\n• ID: <code>{user.id}</code>\n• Warns: <b>{warns}</b>"

    if perm == "private" and chat.type != "private":
        try:
            await context.bot.send_message(chat_id=user.id, text=info, parse_mode="HTML")
        except Exception:
            pass
        return

    await update.message.reply_text(info, parse_mode="HTML")

async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in OWNER_IDS:
        return
    
    status_msg = await update.message.reply_text("🔄 **Syncing with GitHub and restarting...**", parse_mode="Markdown")
    repo_dir = Path(__file__).resolve().parent

    try:
        subprocess.run(["git", "stash"], cwd=repo_dir, capture_output=True, text=True, check=True)
        branch_proc = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True)
        current_branch = branch_proc.stdout.strip() or "main"

        subprocess.run(["git", "fetch", "--all"], cwd=repo_dir, capture_output=True, text=True, check=True)
        subprocess.run(["git", "reset", "--hard", f"origin/{current_branch}"], cwd=repo_dir, capture_output=True, text=True, check=True)
        
        pull_proc = subprocess.run(["git", "pull", "origin", current_branch], cwd=repo_dir, capture_output=True, text=True, check=True)
        pull_output = pull_proc.stdout.strip()

        for pyc_dir in repo_dir.rglob("__pycache__"):
            shutil.rmtree(pyc_dir, ignore_errors=True)

        await status_msg.edit_text(f"⚙️ **Update Complete!**\n`{pull_output}`\n\n🔄 Bot restarted.", parse_mode="Markdown")
        os.execv(sys.executable, [sys.executable, str(repo_dir / "main.py")])
    except Exception as e:
        await status_msg.edit_text(f"❌ **Update Failed:**\n`{str(e)}`", parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("rules", rules_command))
    app.add_handler(CommandHandler("staff", staff_command))
    app.add_handler(CommandHandler("me", me_command))
    app.add_handler(CommandHandler("update", update_command))
    app.add_handler(CallbackQueryHandler(unified_callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, interactive_state_processor))
    print("🛡 Group Security Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
