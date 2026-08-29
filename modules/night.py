import datetime
import html
from telegram import (
    Update, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from database import get_config, save_config
from utils import create_btn, fast_edit, is_user_admin

def get_group_current_time_str(cid: int) -> str:
    cfg = get_config(cid)
    tz_offset_hours = cfg.get("night_tz_offset", 0)
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    target_time = utc_now + datetime.timedelta(hours=tz_offset_hours)
    return target_time.strftime("%d %b %Y, %H:%M")

def get_group_tz_name(cid: int) -> str:
    cfg = get_config(cid)
    return cfg.get("night_tz_name", "UTC")

def get_night_main_keyboard(cid: int):
    cfg = get_config(cid)
    mode = cfg.get("night_mode", "off")
    advise_icon = "✔️" if cfg.get("night_advise", True) else "✖️"

    if mode == "off":
        keyboard = [
            [create_btn("📸 Delete medias", callback_data=f"ngtset_mode_medias_{cid}"), create_btn("🤫 Global Silence", callback_data=f"ngtset_mode_silence_{cid}")],
            [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")]
        ]
        return InlineKeyboardMarkup(keyboard)

    r_mode = [
        create_btn("📸 Delete medias", callback_data=f"ngtset_mode_medias_{cid}", style="success" if mode == "medias" else None),
        create_btn("🤫 Global Silence", callback_data=f"ngtset_mode_silence_{cid}", style="success" if mode == "silence" else None)
    ]

    keyboard = [
        [create_btn("❌ Off", callback_data=f"ngtset_mode_off_{cid}", style="danger")],
        r_mode,
        [create_btn("⏰ Set time slot", callback_data=f"ngt_slot_start_{cid}")],
        [create_btn(f"📣 Start&End advises {advise_icon}", callback_data=f"ngttog_advise_{cid}")],
        [create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}"), create_btn("🌍 Time Zone", callback_data=f"ngt_tz_menu_{cid}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_night_main_text(cid: int):
    cfg = get_config(cid)
    mode = cfg.get("night_mode", "off")
    
    if mode == "off":
        return (
            "🌘 <b>Night mode</b>\n"
            "<b>Select the actions you want to limit every night.</b>\n\n"
            "<b>Status:</b> ❌ Off"
        )

    start_h = cfg.get("night_start_hour", 23)
    end_h = cfg.get("night_end_hour", 9)
    advise_str = "✔️" if cfg.get("night_advise", True) else "✖️"
    curr_time_str = get_group_current_time_str(cid)
    status_title = "📸 Delete medias" if mode == "medias" else "🤫 Global Silence"

    return (
        "🌘 <b>Night mode</b>\n"
        "<b>Select the actions you want to limit every night.</b>\n\n"
        f"<b>Status:</b> {status_title}\n"
        f" └ <b>Active from hour {start_h} to {end_h}</b>\n"
        f" └ <b>Start&End advises:</b> {advise_str}\n\n"
        f"<b>Current time:</b> {curr_time_str}"
    )

def get_timezone_keyboard(cid: int, in_pm: bool = False):
    if not in_pm:
        keyboard = [
            [create_btn("👤 Open in Private Chat", url=f"https://t.me/{{bot_username}}?start=tzset_{cid}")],
            [create_btn("⬅️ Back", callback_data=f"cfg_mod_night_{cid}")]
        ]
    else:
        keyboard = [
            [create_btn("✍️ Set", callback_data=f"ngt_tz_reqpos_{cid}")],
            [create_btn("⬅️ Back", callback_data=f"cfg_mod_night_{cid}")]
        ]
    return InlineKeyboardMarkup(keyboard)

def get_timezone_text(cid: int):
    tz_name = get_group_tz_name(cid)
    curr_time_str = get_group_current_time_str(cid)
    return (
        "🌍 <b>Time Zone</b>\n\n"
        "From this menu you can set the group Time Zone.\n"
        "Bot need it to send correctly the messages with dates.\n\n"
        f"<b>Actual:</b> {tz_name} ({curr_time_str})"
    )

async def handle_night_callbacks(query, data: str, cid: int, user, user_states, context):
    cfg = get_config(cid)
    bot_info = await context.bot.get_me()

    if data.startswith("cfg_mod_night_") or data.startswith("cfg_view_night_") or data.startswith("ngt_main_"):
        user_states.pop((cid, user.id), None)
        await fast_edit(query, get_night_main_text(cid), get_night_main_keyboard(cid))

    elif data.startswith("ngtset_mode_"):
        mode = data.split("_")[2]
        cfg["night_mode"] = mode
        save_config(cid, cfg)
        await fast_edit(query, get_night_main_text(cid), get_night_main_keyboard(cid))

    elif data.startswith("ngttog_advise_"):
        cfg["night_advise"] = not cfg.get("night_advise", True)
        save_config(cid, cfg)
        await fast_edit(query, get_night_main_text(cid), get_night_main_keyboard(cid))

    elif data.startswith("ngt_tz_menu_"):
        is_private = query.message.chat.type == "private"
        if not is_private:
            kb = [
                [create_btn("👤 Open in Private Chat", url=f"https://t.me/{bot_info.username}?start=tzset_{cid}")],
                [create_btn("⬅️ Back", callback_data=f"cfg_mod_night_{cid}")]
            ]
            await fast_edit(query, "Time Zone can be set only using settings in private chat with the Bot", InlineKeyboardMarkup(kb))
        else:
            await fast_edit(query, get_timezone_text(cid), get_timezone_keyboard(cid, in_pm=True))

    # Trigger Location Request in DM directly when ✍️ Set is clicked from Time Zone menu
    elif data.startswith("ngt_tz_reqpos_") or data.startswith("ngttz_reqpos_"):
        for k in list(user_states.keys()):
            if k[1] == user.id:
                user_states.pop(k, None)

        user_states[(cid, user.id)] = "awaiting_ngt_tz_loc"
        
        prompt_txt = (
            "🌍 <b>Time Zone</b>\n"
            "Now <b>send your position</b> in order to auto detect Time Zone to be set in the group.\n\n"
            "You can send it using the button in the keyboard or touching 📎 <u>Attach</u>, so 📍 <u>Position</u> "
            "(with this second way you can chose a specific position also different from yours).\n\n"
            "Alternatively you can <b>write the name of your city</b> directly.\n\n"
            "<i>Your position will not be saved, we will save only the Time Zone detected.</i>"
        )
        
        reply_kb = ReplyKeyboardMarkup(
            [
                [KeyboardButton("📍 Send the position", request_location=True)],
                [KeyboardButton("❌ Cancel")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )

        try:
            await query.message.delete()
        except Exception:
            pass

        await context.bot.send_message(
            chat_id=user.id,
            text=prompt_txt,
            reply_markup=reply_kb,
            parse_mode="HTML"
        )

async def handle_night_text_state(update: Update, context, user_states):
    msg = update.effective_message
    if not msg or not msg.from_user:
        return False

    user_id = msg.from_user.id
    state_key = None
    for k, v in list(user_states.items()):
        if k[1] == user_id and str(user_states[k]) == "awaiting_ngt_tz_loc":
            state_key = k
            break

    if not state_key:
        return False

    target_cid = state_key[0]
    cfg = get_config(target_cid)

    if msg.text and msg.text.strip() == "❌ Cancel":
        user_states.pop(state_key, None)
        await msg.reply_text("Time Zone setup cancelled.", reply_markup=ReplyKeyboardRemove())
        await msg.reply_text(
            get_timezone_text(target_cid),
            reply_markup=get_timezone_keyboard(target_cid, in_pm=True),
            parse_mode="HTML"
        )
        return True

    tz_name = "UTC"
    tz_offset = 0

    if msg.location:
        lat = msg.location.latitude
        lon = msg.location.longitude
        
        if 68 <= lon <= 97 and 8 <= lat <= 37:
            tz_name = "Asia/Kolkata"
            tz_offset = 5.5
        elif -20 <= lon <= 0 and 10 <= lat <= 28:
            tz_name = "Africa/Nouakchott"
            tz_offset = 0
        elif -10 <= lon <= 30 and 35 <= lat <= 60:
            tz_name = "Europe/Rome"
            tz_offset = 2
        else:
            tz_offset = round(lon / 15.0)
            tz_name = f"UTC{'+' if tz_offset >= 0 else ''}{tz_offset}" if tz_offset != 0 else "UTC"

    elif msg.text:
        city = msg.text.strip().title()
        if any(x in city for x in ["Delhi", "India", "Kolkata", "Mumbai"]):
            tz_name = "Asia/Kolkata"
            tz_offset = 5.5
        elif "Nouakchott" in city or "Mauritania" in city:
            tz_name = "Africa/Nouakchott"
            tz_offset = 0
        elif any(x in city for x in ["Rome", "Italy", "Europe", "Paris", "Berlin"]):
            tz_name = "Europe/Rome"
            tz_offset = 2
        elif "Utc" in city or "Gmt" in city:
            tz_name = "UTC"
            tz_offset = 0
        else:
            tz_name = city
            tz_offset = 0

    user_states.pop(state_key, None)
    cfg["night_tz_name"] = tz_name
    cfg["night_tz_offset"] = tz_offset
    save_config(target_cid, cfg)

    utc_now = datetime.datetime.now(datetime.timezone.utc)
    target_time = utc_now + datetime.timedelta(hours=tz_offset)
    curr_time_str = target_time.strftime("%d/%m/%Y %H:%M")

    confirm_text = (
        f"Time Zone set to <b>{tz_name}</b>\n"
        f"Current time: <b>{curr_time_str}</b>"
    )
    kb = [[create_btn("⬅️ Back", callback_data=f"ngt_tz_menu_{target_cid}")]]

    await msg.reply_text(confirm_text, reply_markup=ReplyKeyboardRemove())
    await msg.reply_text(confirm_text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return True
