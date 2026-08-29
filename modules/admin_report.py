import html
import re
from telegram import Update, InlineKeyboardMarkup
from database import get_config, save_config
from utils import create_btn, fast_edit, is_user_admin

# --- 1. MAIN MENU ---
def get_report_main_keyboard(cid: int):
    cfg = get_config(cid)
    target = cfg.get("rep_target", "founder")  # nobody, founder, staff_group
    tag_founder = "✅" if cfg.get("rep_tag_founder", False) else "❌"
    tag_admins = "✅" if cfg.get("rep_tag_admins", False) else "❌"

    r1 = [
        create_btn("✖️ Nobody", callback_data=f"reptgt_nobody_{cid}", style="success" if target == "nobody" else None),
        create_btn("👑 Founder", callback_data=f"reptgt_founder_{cid}", style="success" if target == "founder" else None)
    ]
    r2 = [
        create_btn("👥 Staff Group", callback_data=f"reptgt_staff_{cid}", style="success" if target == "staff_group" else None)
    ]
    
    keyboard = [
        r1, r2,
        [create_btn(f"🔔 Tag Founder {tag_founder}", callback_data=f"reptog_tagfounder_{cid}")],
        [create_btn(f"🔔 Tag Admins {tag_admins}", callback_data=f"reptog_tagadmins_{cid}")]
    ]

    # Show "Select administrators" if Tag Admins is enabled
    if cfg.get("rep_tag_admins", False):
        keyboard.append([create_btn("🔔👮 Select administrators", callback_data=f"rep_seladmins_{cid}")])

    keyboard.extend([
        [create_btn("🛠 Advanced settings 🆕", callback_data=f"rep_adv_{cid}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]
    ])
    return InlineKeyboardMarkup(keyboard)

def get_report_main_text(cid: int):
    cfg = get_config(cid)
    target = cfg.get("rep_target", "founder")
    target_names = {
        "nobody": "Nobody ❌",
        "founder": "👑 Founder",
        "staff_group": "👥 Staff Group"
    }
    status = "Off ❌" if target == "nobody" else "Active"
    
    extra_warn = ""
    if target == "staff_group" and not cfg.get("staff_group_id"):
        extra_warn = "\n\n❗️ <b>If a Staff Group isn't set, the message will not be sent to anyone.</b>"

    return (
        "🆘 <b>@admin command</b>\n"
        "<b>@admin</b> (or /report) is a command available to users to attract the attention "
        "of the group's staff, for example if some other user is not respecting the group's rules.\n\n"
        "From this menu you can set where you want the reports made by users to be sent "
        "and/or whether to tag some staff members directly.\n\n"
        "⚠️ The <b>@admin</b> command <b>DOES NOT</b> work when used by Admins or Mods.\n\n"
        f"<b>Status:</b> {status}\n"
        f"<b>Send to:</b> {target_names.get(target, '👑 Founder')}"
        f"{extra_warn}"
    )

# --- 2. ADVANCED SETTINGS MENU ---
def get_report_adv_keyboard(cid: int):
    cfg = get_config(cid)
    only_reply = "✅" if cfg.get("rep_only_reply", False) else "❌"
    reason_req = "✅" if cfg.get("rep_reason_req", True) else "❌"
    del_res = "✅" if cfg.get("rep_del_resolved", False) else "❌"
    del_staff = "✅" if cfg.get("rep_del_staff_resolved", True) else "❌"

    keyboard = [
        [create_btn(f"↩️ Only in reply {only_reply}", callback_data=f"repadvtog_reply_{cid}")],
        [create_btn(f"📝 Reason required {reason_req}", callback_data=f"repadvtog_reason_{cid}")],
        [create_btn(f"🗑👥 Delete if resolved {del_res}", callback_data=f"repadvtog_delres_{cid}")],
        [create_btn(f"🗑👮🏻‍♂️ Delete in staff group if resolved {del_staff}", callback_data=f"repadvtog_delstaff_{cid}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_view_admincmd_{cid}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_report_adv_text(cid: int):
    cfg = get_config(cid)
    r_reply = "Active ✅" if cfg.get("rep_only_reply", False) else "Off ❌"
    r_reason = "Active ✅" if cfg.get("rep_reason_req", True) else "Off ❌"
    r_delres = "Active ✅" if cfg.get("rep_del_resolved", False) else "Off ❌"
    r_delstaff = "Active ✅" if cfg.get("rep_del_staff_resolved", True) else "Off ❌"

    return (
        "🆘 <b>@admin command</b>\n\n"
        "↩️ <b>Only in reply:</b> The command @admin will only be usable by users if sent in reply to another user's message.\n"
        f"- Status: <b>{r_reply}</b>\n\n"
        "📝 <b>Reason required:</b> The @admin command will only be usable by users if the message also includes a reason for the report.\n"
        f"- Status: <b>{r_reason}</b>\n\n"
        "🗑👥 <b>Delete if resolved:</b> If a report is marked as resolved, both the message from the user who made the report and the bot's message will be deleted from the group.\n"
        f"- Status: <b>{r_delres}</b>\n\n"
        "🗑👮🏻‍♂️ <b>Delete in staff group if resolved:</b> If a report is marked as resolved, the report message will be deleted in the staff group.\n"
        f"- Status: <b>{r_delstaff}</b>"
    )

# --- 3. SELECT ADMINS MENU ---
async def get_select_admins_keyboard(cid: int, context):
    cfg = get_config(cid)
    selected_admins = cfg.get("rep_selected_admins", [])
    
    keyboard = []
    try:
        admins = await context.bot.get_chat_administrators(cid)
        for adm in admins:
            if adm.user.is_bot:
                continue
            is_sel = adm.user.id in selected_admins
            icon = "✅ " if is_sel else ""
            name = adm.user.first_name[:15]
            keyboard.append([create_btn(f"{icon}{name}", callback_data=f"repadmtog_{adm.user.id}_{cid}", style="success" if is_sel else None)])
    except Exception:
        pass

    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_view_admincmd_{cid}")])
    return InlineKeyboardMarkup(keyboard)

def get_select_admins_text():
    return (
        "<b>Tagged Admins</b>\n"
        "Chose which admins of the group will be tagged when a user use the <b>@admin</b> command.\n\n"
        "<i>A maximum of 5 administrators can be tagged, among those who have permission to restrict users or delete messages.</i>"
    )

# --- 4. CALLBACK ROUTER ---
async def handle_admin_report_callbacks(query, data: str, cid: int, user, user_states, context):
    cfg = get_config(cid)

    # Main Report Dashboard
    if (
        data.startswith("cfg_view_admincmd_") 
        or data.startswith("cfg_view_admin_") 
        or data.startswith("cfg_view_report_") 
        or data.startswith("rep_main_")
    ):
        await fast_edit(query, get_report_main_text(cid), get_report_main_keyboard(cid))

    # Target Switchers
    elif data.startswith("reptgt_"):
        tgt = data.split("_")[1]
        cfg["rep_target"] = "staff_group" if tgt == "staff" else tgt
        save_config(cid, cfg)
        await fast_edit(query, get_report_main_text(cid), get_report_main_keyboard(cid))

    # Tags Toggles
    elif data.startswith("reptog_tagfounder_"):
        cfg["rep_tag_founder"] = not cfg.get("rep_tag_founder", False)
        save_config(cid, cfg)
        await fast_edit(query, get_report_main_text(cid), get_report_main_keyboard(cid))

    elif data.startswith("reptog_tagadmins_"):
        cfg["rep_tag_admins"] = not cfg.get("rep_tag_admins", False)
        save_config(cid, cfg)
        await fast_edit(query, get_report_main_text(cid), get_report_main_keyboard(cid))

    # Select Admins Menu
    elif data.startswith("rep_seladmins_"):
        kb = await get_select_admins_keyboard(cid, context)
        await fast_edit(query, get_select_admins_text(), kb)

    elif data.startswith("repadmtog_"):
        target_uid = int(data.split("_")[1])
        selected_admins = cfg.get("rep_selected_admins", [])
        
        if target_uid in selected_admins:
            selected_admins.remove(target_uid)
        else:
            if len(selected_admins) >= 5:
                await query.answer("You can select a maximum of 5 administrators!", show_alert=True)
                return
            selected_admins.append(target_uid)
            
        cfg["rep_selected_admins"] = selected_admins
        save_config(cid, cfg)
        kb = await get_select_admins_keyboard(cid, context)
        await fast_edit(query, get_select_admins_text(), kb)

    # Advanced Settings
    elif data.startswith("rep_adv_"):
        await fast_edit(query, get_report_adv_text(cid), get_report_adv_keyboard(cid))

    elif data.startswith("repadvtog_reply_"):
        cfg["rep_only_reply"] = not cfg.get("rep_only_reply", False)
        save_config(cid, cfg)
        await fast_edit(query, get_report_adv_text(cid), get_report_adv_keyboard(cid))

    elif data.startswith("repadvtog_reason_"):
        cfg["rep_reason_req"] = not cfg.get("rep_reason_req", True)
        save_config(cid, cfg)
        await fast_edit(query, get_report_adv_text(cid), get_report_adv_keyboard(cid))

    elif data.startswith("repadvtog_delres_"):
        cfg["rep_del_resolved"] = not cfg.get("rep_del_resolved", False)
        save_config(cid, cfg)
        await fast_edit(query, get_report_adv_text(cid), get_report_adv_keyboard(cid))

    elif data.startswith("repadvtog_delstaff_"):
        cfg["rep_del_staff_resolved"] = not cfg.get("rep_del_staff_resolved", True)
        save_config(cid, cfg)
        await fast_edit(query, get_report_adv_text(cid), get_report_adv_keyboard(cid))

    # Resolve Report Action
    elif data.startswith("represolve_"):
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

# --- 5. REPORT COMMAND EXECUTOR ---
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
