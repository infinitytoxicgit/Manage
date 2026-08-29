from utils import create_btn, InlineKeyboardMarkup

def get_page1_settings_keyboard(chat_id: int):
    keyboard = [
        [create_btn("📜 Regulation", callback_data=f"cfg_view_reg_{chat_id}"), create_btn("✉️ Anti-Spam", callback_data=f"aspam_main_{chat_id}")],
        [create_btn("💬 Welcome", callback_data=f"cfg_view_welcome_{chat_id}"), create_btn("🗣 Anti-Flood", callback_data=f"cfg_view_flood_{chat_id}")],
        [create_btn("👋 Goodbye", callback_data=f"cfg_view_goodbye_{chat_id}"), create_btn("🕉 Alphabets", callback_data=f"cfg_view_alphabets_{chat_id}")],
        [create_btn("🧠 Captcha", callback_data=f"cfg_view_captcha_{chat_id}"), create_btn("🔦 Checks", callback_data=f"cfg_view_checks_{chat_id}")],
        [create_btn("🆘 @Admin", callback_data=f"cfg_mod_admin_{chat_id}"), create_btn("🔐 Blocks", callback_data=f"cfg_mod_blocks_{chat_id}")],
        [create_btn("📸 Media", callback_data=f"cfg_mod_media_{chat_id}"), create_btn("🔞 Porn", callback_data=f"cfg_mod_porn_{chat_id}")],
        [create_btn("❗ Warns", callback_data=f"cfg_mod_warns_{chat_id}"), create_btn("🌘 Night", callback_data=f"cfg_mod_night_{chat_id}")],
        [create_btn("🔔 Tag", callback_data=f"cfg_mod_tag_{chat_id}"), create_btn("🔗 Link", callback_data=f"cfg_mod_link_{chat_id}")],
        [create_btn("🕵️ Guardian Bot 🆕", callback_data=f"cfg_mod_guardian_{chat_id}")],
        [create_btn("🗂 Approval mode", callback_data=f"cfg_mod_approval_{chat_id}")],
        [create_btn("🗑 Deleting Messages", callback_data=f"cfg_mod_delmsg_{chat_id}")],
        [create_btn("🇬🇧 Lang", callback_data=f"cfg_mod_lang_{chat_id}"), create_btn("✅ Close", callback_data="cfg_close"), create_btn("▶️ Other", callback_data=f"cfg_page_2_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_page2_settings_keyboard(chat_id: int):
    keyboard = [
        [create_btn("📁 Topic", callback_data=f"cfg_view_topic_{chat_id}")],
        [create_btn("🔤 Banned Words", callback_data=f"cfg_mod_bannedwords_{chat_id}")],
        [create_btn("🕒 Recurring messages", callback_data=f"cfg_mod_recurring_{chat_id}")],
        [create_btn("👥 Members Management", callback_data=f"cfg_mod_members_{chat_id}")],
        [create_btn("😷 Masked users", callback_data=f"cfg_mod_masked_{chat_id}")],
        [create_btn("📣 Discussion group 🆕", callback_data=f"cfg_mod_discussion_{chat_id}")],
        [create_btn("📱 Personal Commands", callback_data=f"cfg_mod_personalcmds_{chat_id}")],
        [create_btn("🎭 Magic Stickers&GIFs", callback_data=f"cfg_mod_magicstickers_{chat_id}")],
        [create_btn("📏 Message length", callback_data=f"cfg_mod_msglength_{chat_id}")],
        [create_btn("📢 Channels management 🆕", callback_data=f"cfg_mod_chanmgmt_{chat_id}")],
        [create_btn("📝 Permissions", callback_data=f"reg_cmd_perms_{chat_id}"), create_btn("🔍 Log Channel", callback_data=f"cfg_mod_logs_{chat_id}")],
        [create_btn("◀️ Back", callback_data=f"cfg_page_1_{chat_id}"), create_btn("✅ Close", callback_data="cfg_close"), create_btn("🇬🇧 Lang", callback_data=f"cfg_mod_lang_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)
