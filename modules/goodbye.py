from database import get_config, save_config
from utils import create_btn, fast_edit, InlineKeyboardMarkup, send_custom_bundle

def get_goodbye_main_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    is_active = cfg.get("goodbye_active", False)
    in_pm = cfg.get("goodbye_in_pm", False)
    del_last = cfg.get("goodbye_delete_last", False)

    on_style = "success" if is_active else None
    off_style = "danger" if not is_active else None
    pm_icon = "✔️" if in_pm else "✖️"
    del_icon = "✔️" if del_last else "✖️"

    keyboard = [
        [create_btn("✖️ Turn off", callback_data=f"gby_toggle_off_{chat_id}", style=off_style), create_btn("✔️ Turn on", callback_data=f"gby_toggle_on_{chat_id}", style=on_style)],
        [create_btn("✍️ Customize message", callback_data=f"gby_custom_{chat_id}")],
        [create_btn(f"💌 Send in private chat {pm_icon}", callback_data=f"gby_tog_pm_{chat_id}")]
    ]
    if not in_pm:
        keyboard.append([create_btn(f"♻️ Delete last message {del_icon}", callback_data=f"gby_tog_dellast_{chat_id}")])
    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")])
    return InlineKeyboardMarkup(keyboard)

def get_goodbye_customize_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    has_text = "✅" if cfg.get("goodbye_text") else "❌"
    has_media = "✅" if cfg.get("goodbye_media_id") else "❌"
    has_buttons = "✅" if cfg.get("goodbye_buttons_raw") else "❌"

    keyboard = [
        [create_btn("📄 Text", callback_data=f"gby_set_text_{chat_id}"), create_btn("👀 See", callback_data=f"gby_see_text_{chat_id}")],
        [create_btn("📸 Media", callback_data=f"gby_set_media_{chat_id}"), create_btn("👀 See", callback_data=f"gby_see_media_{chat_id}")],
        [create_btn("🔤 Url Buttons", callback_data=f"gby_set_buttons_{chat_id}"), create_btn("👀 See", callback_data=f"gby_see_buttons_{chat_id}")],
        [create_btn("👀 Full preview", callback_data=f"gby_full_preview_{chat_id}")],
        [create_btn("📁 Select a Topic 🆕", callback_data=f"gby_topic_info_{chat_id}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_view_goodbye_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def handle_goodbye_callbacks(query, data: str, cid: int, user, chat, bot_username, user_states):
    cfg = get_config(cid)
    if data.startswith("cfg_view_goodbye_"):
        user_states.pop((cid, user.id), None)
        is_active = cfg.get("goodbye_active", False)
        in_pm = cfg.get("goodbye_in_pm", False)
        text = f"👋 <b>Goodbye</b>\nFrom this menu you can set a goodbye message that will be sent when someone leaves the group.\n\n"
        if in_pm:
            text += f"⚠️ The message will only be sent to users who started @{bot_username} in private chat.\n\n"
        text += f"<b>Status:</b> {'Active ✅' if is_active else 'Off ❌'}"
        await fast_edit(query, text, get_goodbye_main_keyboard(cid))
    elif data.startswith("gby_toggle_"):
        cfg["goodbye_active"] = (data.split("_")[2] == "on")
        save_config(cid, cfg)
        await handle_goodbye_callbacks(query, f"cfg_view_goodbye_{cid}", cid, user, chat, bot_username, user_states)
    elif data.startswith("gby_tog_pm_"):
        cfg["goodbye_in_pm"] = not cfg.get("goodbye_in_pm", False)
        save_config(cid, cfg)
        await handle_goodbye_callbacks(query, f"cfg_view_goodbye_{cid}", cid, user, chat, bot_username, user_states)
    elif data.startswith("gby_tog_dellast_"):
        cfg["goodbye_delete_last"] = not cfg.get("goodbye_delete_last", False)
        save_config(cid, cfg)
        await handle_goodbye_callbacks(query, f"cfg_view_goodbye_{cid}", cid, user, chat, bot_username, user_states)
    elif data.startswith("gby_custom_"):
        has_text = "✅" if cfg.get("goodbye_text") else "❌"
        has_media = "✅" if cfg.get("goodbye_media_id") else "❌"
        has_buttons = "✅" if cfg.get("goodbye_buttons_raw") else "❌"
        text = f"👋 <b>Goodbye</b>\n\n📄 Text {has_text}\n📸 Media {has_media}\n🔤 Url Buttons {has_buttons}\n\n👉 Use the buttons below to choose what you want to set"
        await fast_edit(query, text, get_goodbye_customize_keyboard(cid))
    elif data.startswith("gby_set_text_"):
        user_states[(cid, user.id)] = "awaiting_gby_text"
        text = f"{user.mention_html()}, send now the message you want to set!"
        kb = [[create_btn("🚫 Remove message", callback_data=f"gby_rem_text_{cid}")], [create_btn("❌ Cancel", callback_data=f"gby_custom_{cid}", style="danger")]]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
    elif data.startswith("gby_rem_text_"):
        cfg["goodbye_text"] = None
        save_config(cid, cfg)
        await query.answer("Goodbye text removed!")
        await handle_goodbye_callbacks(query, f"gby_custom_{cid}", cid, user, chat, bot_username, user_states)
    elif data.startswith("gby_full_preview_"):
        await send_custom_bundle(chat, user, cfg, mode="goodbye", is_preview=True)
        await query.answer("Full preview sent!")
