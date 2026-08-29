from database import get_config, save_config
from utils import create_btn, fast_edit, InlineKeyboardMarkup, send_custom_bundle

def get_welcome_main_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    is_active = cfg.get("welcome_active", False)
    mode = cfg.get("welcome_mode", "always")
    del_last = cfg.get("welcome_delete_last", False)

    on_style = "success" if is_active else None
    off_style = "danger" if not is_active else None
    del_icon = "✔️" if del_last else "✖️"

    keyboard = [
        [create_btn("✖️ Turn off", callback_data=f"wlc_toggle_off_{chat_id}", style=off_style), create_btn("✔️ Turn on", callback_data=f"wlc_toggle_on_{chat_id}", style=on_style)],
        [create_btn("✍️ Customize message", callback_data=f"wlc_custom_{chat_id}")],
        [create_btn("🔔 Always send", callback_data=f"wlc_mode_always_{chat_id}", style="primary" if mode=="always" else None), create_btn("1️⃣ Send 1st join", callback_data=f"wlc_mode_first_{chat_id}", style="primary" if mode=="first" else None)],
        [create_btn(f"♻️ Delete last message {del_icon}", callback_data=f"wlc_tog_dellast_{chat_id}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_welcome_customize_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    has_text = "✅" if cfg.get("welcome_text") else "❌"
    has_media = "✅" if cfg.get("welcome_media_id") else "❌"
    has_buttons = "✅" if cfg.get("welcome_buttons_raw") else "❌"

    keyboard = [
        [create_btn("📄 Text", callback_data=f"wlc_set_text_{chat_id}"), create_btn("👀 See", callback_data=f"wlc_see_text_{chat_id}")],
        [create_btn("📸 Media", callback_data=f"wlc_set_media_{chat_id}"), create_btn("👀 See", callback_data=f"wlc_see_media_{chat_id}")],
        [create_btn("🔤 Url Buttons", callback_data=f"wlc_set_buttons_{chat_id}"), create_btn("👀 See", callback_data=f"wlc_see_buttons_{chat_id}")],
        [create_btn("👀 Full preview", callback_data=f"wlc_full_preview_{chat_id}")],
        [create_btn("📁 Select a Topic 🆕", callback_data=f"wlc_topic_info_{chat_id}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_view_welcome_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def handle_welcome_callbacks(query, data: str, cid: int, user, chat, user_states):
    cfg = get_config(cid)
    if data.startswith("cfg_view_welcome_"):
        user_states.pop((cid, user.id), None)
        is_active = cfg.get("welcome_active", False)
        mode_desc = "Send the welcome message at every join" if cfg.get("welcome_mode") == "always" else "Send only at first join"
        text = f"💬 <b>Welcome Message</b>\nFrom this menu you can set a welcome message that will be sent when someone joins the group.\n\n<b>Status:</b> {'Active ✅' if is_active else 'Off ❌'}\n<b>Mode:</b> {mode_desc}"
        await fast_edit(query, text, get_welcome_main_keyboard(cid))
    elif data.startswith("wlc_toggle_"):
        cfg["welcome_active"] = (data.split("_")[2] == "on")
        save_config(cid, cfg)
        await handle_welcome_callbacks(query, f"cfg_view_welcome_{cid}", cid, user, chat, user_states)
    elif data.startswith("wlc_mode_"):
        cfg["welcome_mode"] = data.split("_")[2]
        save_config(cid, cfg)
        await handle_welcome_callbacks(query, f"cfg_view_welcome_{cid}", cid, user, chat, user_states)
    elif data.startswith("wlc_tog_dellast_"):
        cfg["welcome_delete_last"] = not cfg.get("welcome_delete_last", False)
        save_config(cid, cfg)
        await handle_welcome_callbacks(query, f"cfg_view_welcome_{cid}", cid, user, chat, user_states)
    elif data.startswith("wlc_custom_"):
        has_text = "✅" if cfg.get("welcome_text") else "❌"
        has_media = "✅" if cfg.get("welcome_media_id") else "❌"
        has_buttons = "✅" if cfg.get("welcome_buttons_raw") else "❌"
        text = f"💬 <b>Welcome Message</b>\n\n📄 Text {has_text}\n📸 Media {has_media}\n🔤 Url Buttons {has_buttons}\n\n👉 Use the buttons below to choose what you want to set"
        await fast_edit(query, text, get_welcome_customize_keyboard(cid))
    elif data.startswith("wlc_set_text_"):
        user_states[(cid, user.id)] = "awaiting_wlc_text"
        text = f"{user.mention_html()}, send now the message you want to set!\n\nYou can use HTML and:\n• {{ID}}, {{NAME}}, {{SURNAME}}, {{NAMESURNAME}}, {{LANG}}, {{DATE}}, {{TIME}}, {{WEEKDAY}}, {{MENTION}}, {{USERNAME}}, {{GROUPNAME}}, {{RULES}}"
        kb = [[create_btn("🚫 Remove message", callback_data=f"wlc_rem_text_{cid}")], [create_btn("❌ Cancel", callback_data=f"wlc_custom_{cid}", style="danger")]]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
    elif data.startswith("wlc_rem_text_"):
        cfg["welcome_text"] = None
        save_config(cid, cfg)
        await query.answer("Welcome text removed!")
        await handle_welcome_callbacks(query, f"wlc_custom_{cid}", cid, user, chat, user_states)
    elif data.startswith("wlc_set_media_"):
        user_states[(cid, user.id)] = "awaiting_wlc_media"
        text = "👉 <b>Send now the media (photos, videos, stickers...) you want to set.</b>"
        kb = [[create_btn("🚫 Remove message", callback_data=f"wlc_rem_media_{cid}")], [create_btn("❌ Cancel", callback_data=f"wlc_custom_{cid}", style="danger")]]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
    elif data.startswith("wlc_rem_media_"):
        cfg["welcome_media_id"] = None
        cfg["welcome_media_type"] = None
        save_config(cid, cfg)
        await query.answer("Welcome media removed!")
        await handle_welcome_callbacks(query, f"wlc_custom_{cid}", cid, user, chat, user_states)
    elif data.startswith("wlc_set_buttons_"):
        user_states[(cid, user.id)] = "awaiting_wlc_buttons"
        text = "👉 <b>Set the buttons to be placed under the message</b>\nFormat: <code>Button title - @username</code> or <code>Button title - t.me/example</code>"
        kb = [[create_btn("🚫 Remove Keyboard", callback_data=f"wlc_rem_buttons_{cid}")], [create_btn("❌ Cancel", callback_data=f"wlc_custom_{cid}", style="danger")]]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
    elif data.startswith("wlc_rem_buttons_"):
        cfg["welcome_buttons_raw"] = None
        save_config(cid, cfg)
        await query.answer("Buttons removed!")
        await handle_welcome_callbacks(query, f"wlc_custom_{cid}", cid, user, chat, user_states)
    elif data.startswith("wlc_full_preview_"):
        await send_custom_bundle(chat, user, cfg, mode="welcome", is_preview=True)
        await query.answer("Full preview sent!")
