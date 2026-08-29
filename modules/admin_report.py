import html
import re
from telegram import Update, InlineKeyboardMarkup
from database import get_config
from utils import create_btn, is_user_admin

# --- 1. RESOLVE REPORT ACTION ---
async def handle_report_resolve_callback(query, data: str, user, context):
    parts = data.split("_")
    rep_chat_id = int(parts[1])
    rep_user_msg_id = int(parts[2])
    rep_bot_msg_id = int(parts[3])

    rcfg = get_config(rep_chat_id)

    # Delete in main group if configured
    if rcfg.get("rep_del_resolved", False):
        try:
            await context.bot.delete_message(chat_id=rep_chat_id, message_id=rep_user_msg_id)
        except Exception:
            pass
        try:
            await context.bot.delete_message(chat_id=rep_chat_id, message_id=rep_bot_msg_id)
        except Exception:
            pass

    # Delete in staff group if configured
    if rcfg.get("rep_del_staff_resolved", True):
        try:
            await query.message.delete()
        except Exception:
            pass
    else:
        await query.edit_message_text(f"✅ <b>Report Resolved by {user.mention_html()}</b>", parse_mode="HTML")

# --- 2. REPORT COMMAND EXECUTOR (@admin / /report) ---
async def handle_report_command(update: Update, context):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not msg or not chat or chat.type == "private":
        return

    # Admins / Mods cannot trigger the @admin command
    if await is_user_admin(chat.id, user.id, context):
        return

    cfg = get_config(chat.id)
    target = cfg.get("rep_target", "founder")
    if target == "nobody":
        return

    # Check "Only in reply"
    if cfg.get("rep_only_reply", False) and not msg.reply_to_message:
        return

    # Extract reason
    raw_text = msg.text or msg.caption or ""
    reason = re.sub(r'(@admin|/report|/admin)', '', raw_text, flags=re.IGNORECASE).strip()

    # Check "Reason required"
    if cfg.get("rep_reason_req", True) and not reason:
        await msg.reply_text("⚠️ <b>Please include a reason for your report.</b>\n<i>Example:</i> <code>@admin spamming in group</code>", parse_mode="HTML")
        return

    reported_user = msg.reply_to_message.from_user if msg.reply_to_message else None

    # Tag admins / founder in the group itself if configured
    tags = []
    if cfg.get("rep_tag_founder", False):
        try:
            admins = await context.bot.get_chat_administrators(chat.id)
            creator = next((a for a in admins if a.status == "creator"), None)
            if creator:
                tags.append(creator.user.mention_html())
        except Exception:
            pass

    if cfg.get("rep_tag_admins", False):
        sel_uids = cfg.get("rep_selected_admins", [])
        if sel_uids:
            for uid in sel_uids[:5]:
                tags.append(f"<a href='tg://user?id={uid}'>Admin</a>")

    tag_str = " ".join(tags)

    # Group confirmation notification
    confirm_text = f"🚨 <b>Report sent to group staff!</b>\n{tag_str}".strip()
    bot_conf_msg = await msg.reply_text(confirm_text, parse_mode="HTML")

    # Destination Delivery Message
    report_card = (
        f"🚨 <b>New Report in {html.escape(chat.title)}</b>\n\n"
        f"👤 <b>Reported by:</b> {user.mention_html()} (<code>{user.id}</code>)\n"
    )
    if reported_user:
        report_card += f"🎯 <b>Reported User:</b> {reported_user.mention_html()} (<code>{reported_user.id}</code>)\n"
    if reason:
        report_card += f"📝 <b>Reason:</b> <code>{html.escape(reason)}</code>\n"

    resolve_kb = InlineKeyboardMarkup([
        [create_btn("✅ Mark as Resolved", callback_data=f"represolve_{chat.id}_{msg.message_id}_{bot_conf_msg.message_id}")]
    ])

    if target == "founder":
        try:
            admins = await context.bot.get_chat_administrators(chat.id)
            creator = next((a for a in admins if a.status == "creator"), None)
            if creator:
                await context.bot.send_message(chat_id=creator.user.id, text=report_card, reply_markup=resolve_kb, parse_mode="HTML")
        except Exception:
            pass

    elif target == "staff_group":
        staff_gid = cfg.get("staff_group_id")
        if staff_gid:
            try:
                await context.bot.send_message(chat_id=staff_gid, text=report_card, reply_markup=resolve_kb, parse_mode="HTML")
            except Exception:
                pass
