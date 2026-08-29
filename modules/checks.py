from database import get_config, save_config
from utils import create_btn, fast_edit, InlineKeyboardMarkup

def get_checks_text(chat_id: int):
    cfg = get_config(chat_id)
    p = cfg.get("checks_penalties", {})
    return (
        "<b>OBLIGATION OF...</b>\n"
        f" • Surname: {p.get('surname', 'Off')}\n"
        f" • Username: {p.get('username', 'Off')}\n"
        f" • Profile picture: {p.get('pfp', 'Off')}\n"
        f" • Channel obligation: {p.get('channel_ob', 'Off')}\n"
        f" • Obligation to add: {p.get('add_ob', 'Off')}\n\n"
        "<b>BLOCK...</b>\n"
        f" • Arabic name: {p.get('arabic', 'Off')}\n"
        f" • Chinese name: {p.get('chinese', 'Off')}\n"
        f" • Russian Name: {p.get('russian', 'Off')}\n"
        f" • Spam name: {p.get('spam', 'Off')}\n\n"
        "🚪 <b>Check at the join</b>\n"
        "If active, the bot will check for obligations and blocks even when users joins the group, as well as when sending a message.\n"
        f"<b>Status:</b> {'Active ✔️' if cfg.get('check_at_join', True) else 'Off ✖️'}\n\n"
        "🗑 <b>Delete Messages</b>\n"
        "If active, the bot will delete messages sent by users who do not comply with the obligations/blocks.\n"
        f"<b>Status:</b> {'Active ✔️' if cfg.get('checks_delete_messages', False) else 'Off ✖️'}"
    )

def get_checks_keyboard(chat_id: int):
    cfg = get_config(chat_id)
    main_tab = cfg.get("checks_main_tab", "obligations")
    sub_tab = cfg.get("checks_sub_tab")
    p = cfg.get("checks_penalties", {})

    t_ob = "» OBLIGATIONS «" if main_tab == "obligations" else "OBLIGATIONS"
    t_nb = "» NAME BLOCKS «" if main_tab == "nameblocks" else "NAME BLOCKS"

    keyboard = [[create_btn(t_ob, callback_data=f"chktab_main_obligations_{chat_id}", style="primary" if main_tab=="obligations" else None),
                 create_btn(t_nb, callback_data=f"chktab_main_nameblocks_{chat_id}", style="primary" if main_tab=="nameblocks" else None)]]

    def make_punishment_grid(current_val):
        def pbtn(name, val):
            return create_btn(name, callback_data=f"chkset_pen_{val}_{chat_id}", style="success" if current_val==val else None)
        return [pbtn("❌ Off", "Off"), pbtn("⚠️ Advise", "Advise"), pbtn("! Warn", "Warn")], [pbtn("! Kick", "Kick"), pbtn("🔊 Mute", "Mute"), pbtn("🚷 Ban", "Ban")]

    items = [
        ("surname", "🧑‍🤝‍🧑 Obligation Surname"), ("username", "🌐 Username Obligation"),
        ("pfp", "📸 Profile Picture Obligation 🔒"), ("add_ob", "➕ Obligation to add 🆕"),
        ("channel_ob", "📣 Channel obligation 🆕")
    ] if main_tab == "obligations" else [
        ("arabic", "☪️ Arabic name block"), ("chinese", "🇨🇳 Chinese name block"),
        ("russian", "🇷🇺 Russian name block"), ("spam", "📩 Spam name block")
    ]

    for k, lbl in items:
        is_active = (sub_tab == k)
        keyboard.append([create_btn(f"» {lbl} «" if is_active else lbl, callback_data=f"chktab_sub_{k}_{chat_id}", style="primary" if is_active else None)])
        if is_active:
            r1, r2 = make_punishment_grid(p.get(k, "Off"))
            keyboard.extend([r1, r2])

    if sub_tab is None:
        keyboard.append([create_btn(f"🚪 Check at the join {'✔️' if cfg.get('check_at_join', True) else '✖️'}", callback_data=f"chktog_join_{chat_id}")])
        keyboard.append([create_btn(f"🗑 Delete Messages {'✔️' if cfg.get('checks_delete_messages', False) else '✖️'}", callback_data=f"chktog_del_{chat_id}")])

    keyboard.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{chat_id}")])
    return InlineKeyboardMarkup(keyboard)

async def handle_checks_callbacks(query, data: str, cid: int):
    cfg = get_config(cid)
    if data.startswith("cfg_view_checks_"):
        cfg["checks_sub_tab"] = None
        save_config(cid, cfg)
        await fast_edit(query, get_checks_text(cid), get_checks_keyboard(cid))
    elif data.startswith("chktab_main_"):
        cfg["checks_main_tab"] = data.split("_")[2]
        cfg["checks_sub_tab"] = None
        save_config(cid, cfg)
        await fast_edit(query, get_checks_text(cid), get_checks_keyboard(cid))
    elif data.startswith("chktab_sub_"):
        s = data.split("_")[2]
        cfg["checks_sub_tab"] = None if cfg.get("checks_sub_tab") == s else s
        save_config(cid, cfg)
        await fast_edit(query, get_checks_text(cid), get_checks_keyboard(cid))
    elif data.startswith("chkset_pen_"):
        cur_sub = cfg.get("checks_sub_tab")
        if cur_sub:
            cfg.setdefault("checks_penalties", {})[cur_sub] = data.split("_")[2]
            save_config(cid, cfg)
        await fast_edit(query, get_checks_text(cid), get_checks_keyboard(cid))
    elif data.startswith("chktog_join_"):
        cfg["check_at_join"] = not cfg.get("check_at_join", True)
        save_config(cid, cfg)
        await fast_edit(query, get_checks_text(cid), get_checks_keyboard(cid))
    elif data.startswith("chktog_del_"):
        cfg["checks_delete_messages"] = not cfg.get("checks_delete_messages", False)
        save_config(cid, cfg)
        await fast_edit(query, get_checks_text(cid), get_checks_keyboard(cid))
