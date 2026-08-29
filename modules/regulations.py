from database import get_config, save_config
from utils import create_btn, fast_edit, InlineKeyboardMarkup, send_custom_bundle, format_template, parse_custom_buttons

def get_regulations_text(chat_id: int):
    return (
        "📜 <b>Group's regulations</b>\n"
        "From this menu you can manage the group's regulations, that will be shown with the command /rules.\n\n"
        "<i>To edit who can use the /rules command, go to the \"Commands permissions\" section.</i>"
    )

def get_regulations_keyboard(chat_id: int):
    keyboard = [
        [create_btn("✍️ Customize message", callback_data=f"reg_custom_msg_{chat_id}")],
        [create_btn("🕹 Commands Permissions", callback_data=f"reg_cmd_perms_{chat_id}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_reg_customize_text(chat_id: int):
    cfg = get_config(chat_id)
    has_text = "✅" if cfg.get("rules_text") else "❌"
    has_media = "✅" if cfg.get("rules_media_id") else "❌"
    has_buttons = "✅" if cfg.get("rules_buttons_raw") else "❌"

    return (
        "📜 <b>Regulation</b>\n\n"
        f"📄 Text {has_text}\n"
        f"📸 Media {has_media}\n"
        f"🔤 Url Buttons {has_buttons}\n\n"
        "👉 <i>Use the buttons below to choose what you want to set</i>"
    )

def get_reg_customize_keyboard(chat_id: int):
    keyboard = [
        [create_btn("📄 Text", callback_data=f"reg_set_text_{chat_id}"), create_btn("👀 See", callback_data=f"reg_see_text_{chat_id}")],
        [create_btn("📸 Media", callback_data=f"reg_set_media_{chat_id}"), create_btn("👀 See", callback_data=f"reg_see_media_{chat_id}")],
        [create_btn("🔤 Url Buttons", callback_data=f"reg_set_buttons_{chat_id}"), create_btn("👀 See", callback_data=f"reg_see_buttons_{chat_id}")],
        [create_btn("👀 Full preview", callback_data=f"reg_preview_{chat_id}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_view_reg_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cmd_permissions_text(chat_id: int):
    cfg = get_config(chat_id)
    def lbl(perm):
        if perm == "nobody": return "✖️ Nobody"
        if perm == "staff": return "👮🏻 Staff"
        if perm == "private": return "🤖 Private"
        return "👥 Everyone"

    return (
        "🕹 <b>Commands Permissions</b>\n"
        "From this menu you can configure the usage permissions of the following commands.\n\n"
        "✖️ = nobody   |   👥 = all\n"
        "🤖 = all, in private chat\n"
        "👮🏻 = admins and moderators\n\n"
        f"• /staff » {lbl(cfg.get('perm_staff', 'everyone'))}\n"
        f"• /rules » {lbl(cfg.get('perm_rules', 'staff'))}\n"
        f"• /me » {lbl(cfg.get('perm_me', 'private'))}\n"
        f"• /translate » {lbl(cfg.get('perm_translate', 'everyone'))}\n"
        f"• /link » {lbl(cfg.get('perm_link', 'everyone'))}"
    )

def get_cmd_permissions_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    cmds = [("staff", "/staff"), ("rules", "/rules"), ("me", "/me"), ("translate", "/translate"), ("link", "/link")]
    modes = [("nobody", "✖️"), ("staff", "👮🏻"), ("everyone", "👥"), ("private", "🤖")]
    keyboard = []
    for cmd_key, label in cmds:
        row = [create_btn(label, callback_data=f"cmdlbl_{cmd_key}", style="primary")]
        cur_perm = cfg.get(f"perm_{cmd_key}", "everyone" if cmd_key != "rules" else "staff")
        for mode_key, icon in modes:
            style = "success" if cur_perm == mode_key else None
            row.append(create_btn(icon, callback_data=f"permset_{cmd_key}_{mode_key}_{chat_id}", style=style))
        keyboard.append(row)
    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_view_reg_{chat_id}")])
    return InlineKeyboardMarkup(keyboard)

async def handle_regulations_callbacks(query, data: str, cid: int, user, chat, user_states):
    cfg = get_config(cid)

    if data.startswith("cfg_view_reg_"):
        user_states.pop((cid, user.id), None)
        await fast_edit(query, get_regulations_text(cid), get_regulations_keyboard(cid))

    elif data.startswith("reg_custom_msg_"):
        await fast_edit(query, get_reg_customize_text(cid), get_reg_customize_keyboard(cid))

    elif data.startswith("reg_see_text_"):
        r_text = cfg.get("rules_text") or "No rules configured yet."
        try:
            await chat.send_message(f"📜 <b>Rules Text Preview:</b>\n\n{r_text}", parse_mode="HTML")
            await query.answer("Preview sent!")
        except Exception:
            await chat.send_message(f"📜 <b>Rules Text Preview:</b>\n\n{r_text}")
            await query.answer("Preview sent.")

    elif data.startswith("reg_see_media_"):
        m_id = cfg.get("rules_media_id")
        m_type = cfg.get("rules_media_type")
        if not m_id:
            await query.answer("No media configured.", show_alert=True)
            return
        try:
            if m_type == "photo":
                await chat.send_photo(photo=m_id, caption="📸 Regulations Media Preview")
            elif m_type == "video":
                await chat.send_video(video=m_id, caption="📸 Regulations Media Preview")
            elif m_type == "sticker":
                await chat.send_sticker(sticker=m_id)
            await query.answer("Media preview sent!")
        except Exception as e:
            await query.answer(f"Error: {e}", show_alert=True)

    elif data.startswith("reg_see_buttons_"):
        kb = parse_custom_buttons(cfg.get("rules_buttons_raw"), cid)
        if not kb:
            await query.answer("No buttons configured.", show_alert=True)
            return
        await chat.send_message("🔤 <b>Regulations Buttons Preview:</b>", reply_markup=kb, parse_mode="HTML")
        await query.answer("Buttons preview sent!")

    elif data.startswith("reg_set_text_"):
        user_states[(cid, user.id)] = "awaiting_reg_text"
        text = "👉 <b>Send now the message you want to set.</b>\n<i>You can send it already formatted or use HTML.</i>"
        kb = [
            [create_btn("🚫 Remove message", callback_data=f"reg_rem_text_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"reg_custom_msg_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))

    elif data.startswith("reg_rem_text_"):
        cfg["rules_text"] = None
        save_config(cid, cfg)
        await query.answer("Regulations text removed!")
        await fast_edit(query, get_reg_customize_text(cid), get_reg_customize_keyboard(cid))

    elif data.startswith("reg_set_media_"):
        user_states[(cid, user.id)] = "awaiting_reg_media"
        text = "👉 <b>Send now the media (photos, videos, stickers...) you want to set.</b>\n<i>You can also enter a caption.</i>"
        kb = [
            [create_btn("🚫 Remove media", callback_data=f"reg_rem_media_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"reg_custom_msg_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))

    elif data.startswith("reg_rem_media_"):
        cfg["rules_media_id"] = None
        cfg["rules_media_type"] = None
        save_config(cid, cfg)
        await query.answer("Regulations media removed!")
        await fast_edit(query, get_reg_customize_text(cid), get_reg_customize_keyboard(cid))

    elif data.startswith("reg_set_buttons_"):
        user_states[(cid, user.id)] = "awaiting_reg_buttons"
        text = (
            "👉 <b>Set the buttons to be placed under the message</b>\n"
            "Send a message structured as follows:\n\n"
            "• <b>Single button:</b>\n<code>Button title - @username</code>\n\n"
            "• <b>Multiple on single line:</b>\n<code>Title 1 - @user1 && Title 2 - link2.com</code>\n\n"
            "• <b>Multiple rows:</b>\n<code>Title 1 - link1.com\nTitle 2 - @user2</code>\n\n"
            "<b>Special buttons:</b>\n"
            "• Popup: <code>Title - popup: Text</code>\n"
            "• Share: <code>Title - share: Text</code>\n"
            "• Copy: <code>Title - copy: Text</code>"
        )
        kb = [
            [create_btn("🚫 Remove Keyboard", callback_data=f"reg_rem_buttons_{cid}")],
            [create_btn("❌ Cancel", callback_data=f"reg_custom_msg_{cid}", style="danger")]
        ]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))

    elif data.startswith("reg_rem_buttons_"):
        cfg["rules_buttons_raw"] = None
        save_config(cid, cfg)
        await query.answer("Regulations buttons removed!")
        await fast_edit(query, get_reg_customize_text(cid), get_reg_customize_keyboard(cid))

    elif data.startswith("reg_preview_"):
        await send_custom_bundle(chat, user, cfg, mode="rules", is_preview=True)
        await query.answer("Preview sent!")

    elif data.startswith("reg_cmd_perms_"):
        await fast_edit(query, get_cmd_permissions_text(cid), get_cmd_permissions_keyboard(cid))

    elif data.startswith("permset_"):
        parts = data.split("_")
        cmd_key, mode_key = parts[1], parts[2]
        cfg[f"perm_{cmd_key}"] = mode_key
        save_config(cid, cfg)
        await fast_edit(query, get_cmd_permissions_text(cid), get_cmd_permissions_keyboard(cid))
