from database import get_config, save_config
from config import ALPHABET_DATA
from utils import create_btn, make_penalty_buttons, fast_edit, InlineKeyboardMarkup

def get_alphabets_text(chat_id: int):
    cfg = get_config(chat_id)
    penalties = cfg.get("alpha_penalties", {})
    deletes = cfg.get("alpha_deletes", {})
    lines = ["🕉 <b>Alphabets</b>\nSelect punishment for any user who send messages written in certain alphabets.\n"]
    for key, data in ALPHABET_DATA.items():
        pen = penalties.get(key, "Off")
        del_on = deletes.get(key, False)
        status_str = "Deletion" if (pen == "Off" and del_on) else pen
        lines.append(f"{data['icon']} <b>{data['name']}</b> (<a href=\"{data['wiki']}\">?</a>)\n  └ Status: {status_str}\n")
    return "\n".join(lines)

def get_alphabets_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    cur_tab = cfg.get("alpha_active_tab", "chinese")
    cur_pen = cfg.get("alpha_penalties", {}).get(cur_tab, "Off")
    cur_del = cfg.get("alpha_deletes", {}).get(cur_tab, False)

    keyboard = []
    lang_keys = list(ALPHABET_DATA.keys())
    for i in range(0, len(lang_keys), 2):
        row = []
        for k in lang_keys[i:i+2]:
            d = ALPHABET_DATA[k]
            lbl = f"» {d['icon']} {d['name'].upper()} «" if cur_tab == k else f"{d['icon']} {d['name'].upper()}"
            row.append(create_btn(lbl, callback_data=f"alptab_{k}_{chat_id}", style="primary" if cur_tab==k else None))
        keyboard.append(row)

    keyboard.append([create_btn("➖➖➖➖➖➖➖➖", callback_data="none")])
    r1, r2 = make_penalty_buttons("alp", cur_pen, chat_id)
    keyboard.extend([r1, r2])
    keyboard.append([create_btn(f"🗑 Delete Messages {'✔️' if cur_del else '✖️'}", callback_data=f"alptog_del_{chat_id}")])
    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")])
    return InlineKeyboardMarkup(keyboard)

async def handle_alphabets_callbacks(query, data: str, cid: int):
    cfg = get_config(cid)
    if data.startswith("cfg_view_alphabets_"):
        await fast_edit(query, get_alphabets_text(cid), get_alphabets_keyboard(cid))
    elif data.startswith("alptab_"):
        cfg["alpha_active_tab"] = data.split("_")[1]
        save_config(cid, cfg)
        await fast_edit(query, get_alphabets_text(cid), get_alphabets_keyboard(cid))
    elif data.startswith("alppen_"):
        cur_tab = cfg.get("alpha_active_tab", "chinese")
        cfg.setdefault("alpha_penalties", {})[cur_tab] = data.split("_")[1]
        save_config(cid, cfg)
        await fast_edit(query, get_alphabets_text(cid), get_alphabets_keyboard(cid))
    elif data.startswith("alptog_del_"):
        cur_tab = cfg.get("alpha_active_tab", "chinese")
        cur_del = cfg.setdefault("alpha_deletes", {}).get(cur_tab, False)
        cfg["alpha_deletes"][cur_tab] = not cur_del
        save_config(cid, cfg)
        await fast_edit(query, get_alphabets_text(cid), get_alphabets_keyboard(cid))
