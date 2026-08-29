from database import get_config, save_config
from utils import create_btn, make_penalty_buttons, fast_edit, InlineKeyboardMarkup

def get_totallinks_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    r1, r2 = make_penalty_buttons("astot_", cfg.get("totallinks_penalty", "Off"), chat_id)
    del_icon = "✔️" if cfg["totallinks_delete"] else "✖️"
    keyboard = [
        r1, r2,
        [create_btn(f"🗑 Delete Messages {del_icon}", callback_data=f"astottog_del_{chat_id}")],
        [create_btn("⬅️ Back", callback_data=f"aspam_main_{chat_id}"), create_btn("☀️ Exceptions", callback_data=f"asexc_main_{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)
