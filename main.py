import os
import sys
import subprocess
import logging
import re
import shutil
import html
import asyncio
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
from modules.antiflood import handle_antiflood_callbacks, handle_antiflood_text_state
from modules.antispam import handle_antispam_callbacks, handle_antispam_text_state, inspect_antispam_message
from modules.admin_report import handle_admin_report_callbacks, handle_report_command
from modules.alphabets import handle_alphabets_callbacks
from modules.captcha import handle_captcha_callbacks
from modules.checks import handle_checks_callbacks
from modules.regulations import handle_regulations_callbacks, translate_command

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

    # Handle Translation Click Actions
    if data.startswith("trset_") or data.startswith("trcancel_"):
        await handle_regulations_callbacks(query, data, chat.id, user, chat, user_states, context)
        return

    # /settings open handler
    if data.startswith("set_open_"):
        mode = data.split("_")[2]
        cid = int(data.split("_")[3])
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
                bot_info = await context.bot.get_me()
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
        cid = int(data.split("_")[3])
        cfg = get_config(cid)
        try:
            await query.answer(cfg.get("rules_text", "No rules set.")[:200], show_alert=True)
        except Exception:
            pass
        return

    # Extract Chat ID safely
    match = re.search(r"(-?\d+)$", data)
    cid = int(match.group(1)) if match else chat.id

    if not await is_user_admin(cid, user.id, context):
        try:
            await query.answer("Sirf Admins settings badal sakte hain!", show_alert=True)
        except Exception:
            pass
        return

    bot_info = await context.bot.get_me()

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
    elif (
        data.startswith("as_") 
        or data.startswith("astg") 
        or data.startswith("astot") 
        or data.startswith("assub") 
        or data.startswith("asdel")
        or data.startswith("asexc") 
        or data.startswith("cfg_view_antispam_") 
        or data.startswith("cfg_view_spam_") 
        or data.startswith("cfg_view_aspam_") 
        or data.startswith("aspam_")
    ):
        await handle_antispam_callbacks(query, data, cid, user, user_states)
    elif (
        data.startswith("cfg_view_admincmd_") 
        or data.startswith("cfg_view_admin_") 
        or data.startswith("cfg_view_report_") 
        or data.startswith("rep_") 
        or data.startswith("reptgt_") 
        or data.startswith("reptog_") 
        or data.startswith("repadm") 
        or data.startswith("repadv")
        or data.startswith("represolve_")
    ):
        await handle_admin_report_callbacks(query, data, cid, user, user_states, context)
    elif data.startswith("alp") or data.startswith("cfg_view_alphabets_"):
        await handle_alphabets_callbacks(query, data, cid)
    elif data.startswith("cpt_") or data.startswith("cfg_view_captcha_"):
        await handle_captcha_callbacks(query, data, cid, user, user_states)
    elif data.startswith("chk") or data.startswith("cfg_view_checks_"):
        await handle_checks_callbacks(query, data, cid)

# Unified Message Receiver (Interactive States & Spam Scanning)
async def interactive_state_processor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message or not update.message.from_user:
        return False
    chat_id = update.effective_chat.id
    user_id = update.message.from_user.id
    state_key = (chat_id, user_id)
    text = update.message.text or update.message.caption or ""

    # 1. Trigger for @admin command
    if "@admin" in text.lower() or text.startswith("/report") or text.startswith("/admin"):
        await handle_report_command(update, context)
        return True

    # 2. State Input Handling
    if state_key in user_states:
        if not await is_user_admin(chat_id, user_id, context):
            user_states.pop(state_key, None)
            return False

        state = user_states.get(state_key)

        # Route to Antiflood Module
        if state and state.startswith("awaiting_flood_dur_"):
            return await handle_antiflood_text_state(update, context, user_states)

        # Route to Anti-Spam Module
        if state and (state.startswith("awaiting_as_tg_dur_") or state.startswith("awaiting_as_tot_dur_") or state.startswith("awaiting_as_wl_")):
            return await handle_antispam_text_state(update, context, user_states)

        cfg = get_config(chat_id)
        msg = update.message

        if state == "awaiting_reg_text":
            user_states.pop(state_key, None)
            cfg["rules_text"] = text
            save_config(chat_id, cfg)
            kb = [[create_btn("⬅️ Back", callback_data=f"reg_custom_msg_{chat_id}")]]
            await msg.reply_text("✅ <b>Regulations message set & permanently saved!</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
            return True

        elif state == "awaiting_reg_media":
            user_states.pop(state_key, None)
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
                user_states[state_key] = state
                return True
            if msg.caption:
                cfg["rules_text"] = msg.caption
            save_config(chat_id, cfg)
            kb = [[create_btn("⬅️ Back", callback_data=f"reg_custom_msg_{chat_id}")]]
            await msg.reply_text("✅ <b>Regulations media set & permanently saved!</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
            return True

        elif state == "awaiting_reg_buttons":
            user_states.pop(state_key, None)
            cfg["rules_buttons_raw"] = text
            save_config(chat_id, cfg)
            kb = parse_custom_buttons(text, chat_id)
            btn_list = kb.inline_keyboard if kb else []
            final_kb = list(btn_list) + [[create_btn("⬅️ Back", callback_data=f"reg_custom_msg_{chat_id}")]]
            await msg.reply_text(f"<code>{html.escape(text)}</code>", reply_markup=InlineKeyboardMarkup(final_kb), parse_mode="HTML")
            return True

    # 3. Inspect Group Messages for Anti-Spam
    await inspect_antispam_message(update, context)
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

# FULL ROBUST FORCE UPDATE COMMAND
async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in OWNER_IDS:
        return

    status_msg = await update.message.reply_text("🔄 **Syncing latest files from GitHub...**", parse_mode="Markdown")
    repo_dir = Path(__file__).resolve().parent

    try:
        subprocess.run(["git", "stash", "--include-untracked"], cwd=repo_dir, capture_output=True, text=True)

        branch_proc = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True)
        active_branch = branch_proc.stdout.strip() or "main"

        subprocess.run(["git", "fetch", "--all"], cwd=repo_dir, capture_output=True, text=True, check=True)
        subprocess.run(["git", "reset", "--hard", f"origin/{active_branch}"], cwd=repo_dir, capture_output=True, text=True, check=True)
        subprocess.run(["git", "clean", "-fd"], cwd=repo_dir, capture_output=True, text=True, check=True)

        log_proc = subprocess.run(["git", "log", "-1", "--pretty=format:%s (%h)"], cwd=repo_dir, capture_output=True, text=True, check=True)
        latest_commit_msg = log_proc.stdout.strip()

        for pyc_dir in repo_dir.rglob("__pycache__"):
            shutil.rmtree(pyc_dir, ignore_errors=True)

        await status_msg.edit_text(
            f"🚀 **Successfully Synced & Updated!**\n\n"
            f"📝 **Latest Commit:** `{latest_commit_msg}`\n"
            f"🔹 **Branch:** `{active_branch}`\n\n"
            f"⚙️ **Restarting bot instance now...**",
            parse_mode="Markdown"
        )

        async def restart_bot():
            await asyncio.sleep(1)
            os.execv(sys.executable, [sys.executable] + sys.argv)

        asyncio.create_task(restart_bot())

    except Exception as e:
        await status_msg.edit_text(f"❌ **Update Failed:**\n```\n{str(e)}\n```", parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("rules", rules_command))
    app.add_handler(CommandHandler("report", handle_report_command))
    app.add_handler(CommandHandler("admin", handle_report_command))
    app.add_handler(CommandHandler("translate", translate_command))
    app.add_handler(CommandHandler("staff", staff_command))
    app.add_handler(CommandHandler("me", me_command))
    app.add_handler(CommandHandler("update", update_command))
    app.add_handler(CallbackQueryHandler(unified_callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, interactive_state_processor))
    print("🛡 Group Security Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
