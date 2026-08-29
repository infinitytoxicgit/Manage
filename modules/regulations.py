from database import get_config
from utils import create_btn, fast_edit, InlineKeyboardMarkup

def get_regulations_keyboard(chat_id: int):
    keyboard = [
        [create_btn("✍️ Customize message", callback_data=f"reg_custom_msg_{chat_id}")],
        [create_btn("🕹 Commands Permissions", callback_data=f"reg_cmd_perms_{chat_id}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cmd_permissions_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    cmds = [("staff", "/staff"), ("rules", "/rules"), ("me", "/me"), ("translate", "/translate"), ("link", "/link")]
    modes = [("nobody", "✖️"), ("staff", "👮🏻"), ("everyone", "👥"), ("private", "🤖")]
    keyboard = []
    for cmd_key, label in cmds:
        row = [create_btn(label, callback_data=f"cmdlbl_{cmd_key}", style="primary")]
        cur_perm = cfg.get(f"perm_{cmd_key}", "everyone")
        for mode_key, icon in modes:
            style = "success" if cur_perm == mode_key else None
            row.append(create_btn(icon, callback_data=f"permset_{cmd_key}_{mode_key}_{chat_id}", style=style))
        keyboard.append(row)
    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_view_reg_{chat_id}")])
    return InlineKeyboardMarkup(keyboard)
