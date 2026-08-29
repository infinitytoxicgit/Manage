from database import get_config, save_config
from utils import create_btn, fast_edit, InlineKeyboardMarkup

def get_captcha_text(chat_id: int):
    cfg = get_config(chat_id)
    is_active = cfg.get("captcha_active", False)
    base = "🧠 <b>Captcha</b>\nBy activating the captcha, when a user enters the group he will not be able to send messages until he has confirmed that he is not a robot.\n\n🕑 You can also decide to set a PUNISHMENT down below for those who will not resolve the captcha within the desired time and whether or not to clear the service message in case of failure.\n\n"
    if not is_active:
        return base + "<b>Status:</b> Off ❌"
    mode = cfg.get("captcha_mode", "button")
    mode_desc = "🗂 <b>Mode:</b> Button\n └ <i>The user will have to press a simple button to be unmuted.</i>" if mode == "button" else "🗂 <b>Mode:</b> Regulation\n └ <i>The group regulation is shown to the new user to accept.</i>"
    return base + f"<b>Status:</b> Active ✅\n🕒 <b>Time:</b> {cfg.get('captcha_time_label', '3 Minutes')}\n⛔️ <b>Penalty:</b> {cfg.get('captcha_penalty', 'Mute')}\n{mode_desc}\n🗑 <b>Delete service message:</b> {'Active' if cfg.get('captcha_delete_service') else 'Off'}"

def get_captcha_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    if not cfg.get("captcha_active", False):
        return InlineKeyboardMarkup([[create_btn("✅ Activate", callback_data=f"cpt_toggle_on_{chat_id}", style="success")], [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")]])
    
    tab = cfg.get("captcha_tab")
    cur_time_val = cfg.get("captcha_time_val", 180)
    cur_penalty = cfg.get("captcha_penalty", "Mute")
    del_icon = "✔️" if cfg.get("captcha_delete_service") else "✖️"

    keyboard = [
        [create_btn("❌ Turn off ❌", callback_data=f"cpt_toggle_off_{chat_id}", style="danger")],
        [create_btn("📦 Mode 📦", callback_data=f"cpt_switch_mode_{chat_id}")]
    ]

    if tab == "time":
        keyboard.append([create_btn("» 🕒 Time (Minutes) 🕒 «", callback_data=f"cpt_tab_time_{chat_id}", style="primary")])
        keyboard.extend([
            [create_btn(f"15 sec.{' ✅' if cur_time_val==15 else ''}", callback_data=f"cpt_set_t_15_{chat_id}"), create_btn(f"30 sec.{' ✅' if cur_time_val==30 else ''}", callback_data=f"cpt_set_t_30_{chat_id}")],
            [create_btn(f"1{' ✅' if cur_time_val==60 else ''}", callback_data=f"cpt_set_t_60_{chat_id}"), create_btn(f"2{' ✅' if cur_time_val==120 else ''}", callback_data=f"cpt_set_t_120_{chat_id}"), create_btn(f"3{' ✅' if cur_time_val==180 else ''}", callback_data=f"cpt_set_t_180_{chat_id}"), create_btn(f"5{' ✅' if cur_time_val==300 else ''}", callback_data=f"cpt_set_t_300_{chat_id}")],
            [create_btn(f"10{' ✅' if cur_time_val==600 else ''}", callback_data=f"cpt_set_t_600_{chat_id}"), create_btn(f"15{' ✅' if cur_time_val==900 else ''}", callback_data=f"cpt_set_t_900_{chat_id}"), create_btn(f"20{' ✅' if cur_time_val==1200 else ''}", callback_data=f"cpt_set_t_1200_{chat_id}"), create_btn(f"30{' ✅' if cur_time_val==1800 else ''}", callback_data=f"cpt_set_t_1800_{chat_id}")]
        ])
    else:
        keyboard.append([create_btn("🕒 Time 🕒", callback_data=f"cpt_tab_time_{chat_id}")])

    if tab == "penalty":
        keyboard.append([create_btn("» ⛔️ Penalty ⛔️ «", callback_data=f"cpt_tab_penalty_{chat_id}", style="primary")])
        keyboard.extend([
            [create_btn(f"🚷 Ban{' ✅' if cur_penalty=='Ban' else ''}", callback_data=f"cpt_set_p_Ban_{chat_id}")],
            [create_btn(f"🔊 Mute{' ✅' if cur_penalty=='Mute' else ''}", callback_data=f"cpt_set_p_Mute_{chat_id}"), create_btn(f"❗ Kick{' ✅' if cur_penalty=='Kick' else ''}", callback_data=f"cpt_set_p_Kick_{chat_id}")]
        ])
    else:
        keyboard.append([create_btn("⛔️ Penalty ⛔️", callback_data=f"cpt_tab_penalty_{chat_id}")])

    if tab == "custom":
        keyboard.append([create_btn("» ✍️ Customize message ✍️ «", callback_data=f"cpt_tab_custom_{chat_id}", style="primary")])
        keyboard.append([create_btn("📄 Text", callback_data=f"cpt_set_text_{chat_id}"), create_btn("👀 See", callback_data=f"cpt_see_text_{chat_id}")])
    else:
        keyboard.append([create_btn("✍️ Customize message ✍️", callback_data=f"cpt_tab_custom_{chat_id}")])

    keyboard.append([create_btn("📁 Select a Topic 🆕", callback_data=f"cpt_topic_info_{chat_id}")])
    keyboard.append([create_btn(f"🗑 Delete service message {del_icon}", callback_data=f"cpt_tog_delsvc_{chat_id}")])
    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")])
    return InlineKeyboardMarkup(keyboard)

async def handle_captcha_callbacks(query, data: str, cid: int, user, user_states):
    cfg = get_config(cid)
    if data.startswith("cfg_view_captcha_"):
        user_states.pop((cid, user.id), None)
        cfg["captcha_tab"] = None
        save_config(cid, cfg)
        await fast_edit(query, get_captcha_text(cid), get_captcha_keyboard(cid))
    elif data.startswith("cpt_toggle_"):
        cfg["captcha_active"] = (data.split("_")[2] == "on")
        cfg["captcha_tab"] = None
        save_config(cid, cfg)
        await fast_edit(query, get_captcha_text(cid), get_captcha_keyboard(cid))
    elif data.startswith("cpt_switch_mode_"):
        cfg["captcha_mode"] = "regulation" if cfg.get("captcha_mode") == "button" else "button"
        save_config(cid, cfg)
        await fast_edit(query, get_captcha_text(cid), get_captcha_keyboard(cid))
    elif data.startswith("cpt_tab_"):
        t_name = data.split("_")[2]
        cfg["captcha_tab"] = None if cfg.get("captcha_tab") == t_name else t_name
        save_config(cid, cfg)
        await fast_edit(query, get_captcha_text(cid), get_captcha_keyboard(cid))
    elif data.startswith("cpt_set_t_"):
        sec = int(data.split("_")[3])
        cfg["captcha_time_val"] = sec
        cfg["captcha_time_label"] = f"{sec} Seconds" if sec < 60 else f"{sec // 60} Minutes"
        save_config(cid, cfg)
        await fast_edit(query, get_captcha_text(cid), get_captcha_keyboard(cid))
    elif data.startswith("cpt_set_p_"):
        cfg["captcha_penalty"] = data.split("_")[3]
        save_config(cid, cfg)
        await fast_edit(query, get_captcha_text(cid), get_captcha_keyboard(cid))
    elif data.startswith("cpt_tog_delsvc_"):
        cfg["captcha_delete_service"] = not cfg.get("captcha_delete_service", False)
        save_config(cid, cfg)
        await fast_edit(query, get_captcha_text(cid), get_captcha_keyboard(cid))
    elif data.startswith("cpt_set_text_"):
        user_states[(cid, user.id)] = "awaiting_cpt_text"
        text = f"{user.mention_html()}, send now the custom message for Captcha!"
        kb = [[create_btn("🚫 Remove message", callback_data=f"cpt_rem_text_{cid}")], [create_btn("❌ Cancel", callback_data=f"cfg_view_captcha_{cid}", style="danger")]]
        await fast_edit(query, text, InlineKeyboardMarkup(kb))
    elif data.startswith("cpt_rem_text_"):
        cfg["captcha_custom_text"] = None
        save_config(cid, cfg)
        await query.answer("Custom Captcha text removed!")
        await fast_edit(query, get_captcha_text(cid), get_captcha_keyboard(cid))
