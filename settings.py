import html
from telegram import InlineKeyboardMarkup
from database import get_config, save_config
from utils import create_btn, fast_edit

# --- PAGE 1 SETTINGS KEYBOARD ---
def get_page1_settings_keyboard(chat_id: int):
    keyboard = [
        [create_btn("📜 Regulation", callback_data=f"cfg_view_reg_{chat_id}"), create_btn("📩 Anti-Spam", callback_data=f"as_main_{chat_id}")],
        [create_btn("💬 Welcome", callback_data=f"cfg_view_welcome_{chat_id}"), create_btn("🗣 Anti-Flood", callback_data=f"cfg_view_flood_{chat_id}")],
        [create_btn("👋 Goodbye", callback_data=f"cfg_view_goodbye_{chat_id}"), create_btn("🕉 Alphabets", callback_data=f"cfg_view_alphabets_{chat_id}")],
        [create_btn("🧠 Captcha", callback_data=f"cfg_view_captcha_{chat_id}"), create_btn("🔦 Checks", callback_data=f"cfg_view_checks_{chat_id}")],
        [create_btn("🆘 @Admin", callback_data=f"cfg_view_admincmd_{chat_id}"), create_btn("🔑 Blocks", callback_data=f"cfg_view_blocks_{chat_id}")],
        [create_btn("📸 Media", callback_data=f"cfg_view_media_{chat_id}"), create_btn("🔞 Porn", callback_data=f"cfg_view_porn_{chat_id}")],
        [create_btn("❗️ Warns", callback_data=f"cfg_view_warns_{chat_id}"), create_btn("🌘 Night", callback_data=f"cfg_view_night_{chat_id}")],
        [create_btn("🔔 Tag", callback_data=f"cfg_view_tag_{chat_id}"), create_btn("🔗 Link", callback_data=f"cfg_view_link_{chat_id}")],
        [create_btn("🕵️ Guardian Bot 🆕", callback_data=f"cfg_view_guardian_{chat_id}")],
        [create_btn("📦 Approval mode", callback_data=f"cfg_view_approval_{chat_id}")],
        [create_btn("🗑 Deleting Messages", callback_data=f"cfg_view_delmsg_{chat_id}")],
        [create_btn("🇬🇧 Lang", callback_data=f"cfg_lang_{chat_id}"), create_btn("✅ Close", callback_data="cfg_close"), create_btn("▶️ Other", callback_data=f"cfg_page_2_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- PAGE 2 SETTINGS KEYBOARD ---
def get_page2_settings_keyboard(chat_id: int):
    keyboard = [
        [create_btn("◀️ Back", callback_data=f"cfg_page_1_{chat_id}"), create_btn("✅ Close", callback_data="cfg_close")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- @ADMIN SETTINGS UI ---
def get_report_main_keyboard(cid: int):
    cfg = get_config(cid)
    target = cfg.get("rep_target", "founder")
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

# --- @ADMIN ADVANCED SETTINGS UI ---
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

# --- SELECT ADMINS UI ---
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

# --- SETTINGS CALLBACK ROUTER FOR @ADMIN ---
async def handle_admin_settings_callbacks(query, data: str, cid: int, user, user_states, context):
    cfg = get_config(cid)

    # 1. Main @Admin Dashboard
    if (
        data.startswith("cfg_view_admincmd_") 
        or data.startswith("cfg_view_admin_") 
        or data.startswith("cfg_view_report_") 
        or data.startswith("rep_main_")
    ):
        user_states.pop((cid, user.id), None)
        await fast_edit(query, get_report_main_text(cid), get_report_main_keyboard(cid))

    # 2. Target Switches
    elif data.startswith("reptgt_"):
        tgt = data.split("_")[1]
        cfg["rep_target"] = "staff_group" if tgt == "staff" else tgt
        save_config(cid, cfg)
        await fast_edit(query, get_report_main_text(cid), get_report_main_keyboard(cid))

    # 3. Tag Toggles
    elif data.startswith("reptog_tagfounder_"):
        cfg["rep_tag_founder"] = not cfg.get("rep_tag_founder", False)
        save_config(cid, cfg)
        await fast_edit(query, get_report_main_text(cid), get_report_main_keyboard(cid))

    elif data.startswith("reptog_tagadmins_"):
        cfg["rep_tag_admins"] = not cfg.get("rep_tag_admins", False)
        save_config(cid, cfg)
        await fast_edit(query, get_report_main_text(cid), get_report_main_keyboard(cid))

    # 4. Select Admins Menu
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

    # 5. Advanced Settings
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
