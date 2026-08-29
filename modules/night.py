import datetime
import html
from telegram import (
    Update, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from database import get_config, save_config
from utils import create_btn, fast_edit, is_user_admin

# Helper to get current formatted time in group's timezone
def get_group_current_time_str(cid: int) -> str:
    cfg = get_config(cid)
    tz_offset_hours = cfg.get("night_tz_offset", 0)
    
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    target_time = utc_now + datetime.timedelta(hours=tz_offset_hours)
    
    return target_time.strftime("%d %b %Y, %H:%M")

def get_group_tz_name(cid: int) -> str:
    cfg = get_config(cid)
    return cfg.get("night_tz_name", "UTC")

# --- 1. MAIN NIGHT MODE UI ---
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

# --- 2. TIME SLOT SELECTOR (0 TO 23 GRID) ---
def get_hour_grid_keyboard(cid: int, step: str):
    prefix = f"ngtval_{step}_"
    kb = []
    row = []
    for h in range(24):
        row.append(create_btn(str(h), callback_data=f"{prefix}{h}_{cid}"))
        if len(row) == 5:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    
    kb.append([create_btn("⬅️ Back", callback_data=f"cfg_mod_night_{cid}")])
    return InlineKeyboardMarkup(kb)

def get_hour_grid_text(step: str):
    label = "starting" if step == "start" else "ending"
    return (
        "<b>Night mode</b>\n"
        "In this menu you can set an interval of hour and every day, "
        "in that hours will be enabled the night mode.\n\n"
        f"👉 <b>Select the {label} time:</b>"
    )

# --- 3. TIMEZONE MENU UI ---
def get_timezone_keyboard(cid: int, in_pm: bool = False):
    if not in_pm:
        keyboard = [
            [create_btn("👤 Open in Private Chat", url=f"https://t.me/{{bot_username}}?start=tzset_{cid}")],
            [create_btn("⬅️ Back", callback_data=f"cfg_mod_night_{cid}")]
        ]
    else:
        keyboard = [
            [create_btn("✍️ Set", callback_data=f"lang_menu_{cid}")],
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

# --- 4. CALLBACK ROUTER ---
async def handle_night_callbacks(query, data: str, cid: int, user, user_states, context):
    cfg = get_config(cid)
    bot_info = await context.bot.get_me()

    # Main Dashboard
    if data.startswith("cfg_mod_night_") or data.startswith("cfg_view_night_") or data.startswith("ngt_main_"):
        user_states.pop((cid, user.id), None)
        await fast_edit(query, get_night_main_text(cid), get_night_main_keyboard(cid))

    # Mode Switches
    elif data.startswith("ngtset_mode_"):
        mode = data.split("_")[2]
        cfg["night_mode"] = mode
        save_config(cid, cfg)
        await fast_edit(query, get_night_main_text(cid), get_night_main_keyboard(cid))

    # Advise Toggle
    elif data.startswith("ngttog_advise_"):
        cfg["night_advise"] = not cfg.get("night_advise", True)
        save_config(cid, cfg)
        await fast_edit(query, get_night_main_text(cid), get_night_main_keyboard(cid))

    # Time Slot Grids
    elif data.startswith("ngt_slot_start_"):
        await fast_edit(query, get_hour_grid_text("start"), get_hour_grid_keyboard(cid, "start"))

    elif data.startswith("ngtval_start_"):
        parts = data.split("_")
        val = int(parts[2])
        cfg["night_start_hour"] = val
        save_config(cid, cfg)
        await fast_edit(query, get_hour_grid_text("end"), get_hour_grid_keyboard(cid, "end"))

    elif data.startswith("ngtval_end_"):
        parts = data.split("_")
        val = int(parts[2])
        cfg["night_end_hour"] = val
        save_config(cid, cfg)
        await fast_edit(query, get_night_main_text(cid), get_night_main_keyboard(cid))

    # Time Zone Menu
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

    # Request Position in DM with Native Location Button
    elif data.startswith("ngttz_reqpos_"):
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

# --- 5. TEXT & LOCATION STATE HANDLER ---
async def handle_night_text_state(update: Update, context, user_states):
    msg = update.effective_message
    if not msg or not msg.from_user:
        return False

    user_id = msg.from_user.id
    
    target_cid = None
    for k, v in list(user_states.items()):
        if k[1] == user_id and v == "awaiting_ngt_tz_loc":
            target_cid = k[0]
            break

    if not target_cid:
        return False

    cfg = get_config(target_cid)

    if msg.text and msg.text.strip() == "❌ Cancel":
        user_states.pop((target_cid, user_id), None)
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

    user_states.pop((target_cid, user_id), None)
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

# --- 6. LIVE NIGHT ENFORCER ---
async def inspect_night_message(update: Update, context) -> bool:
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not msg or not chat or not user or chat.type == "private":
        return False

    if await is_user_admin(chat.id, user.id, context):
        return False

    cfg = get_config(chat.id)
    mode = cfg.get("night_mode", "off")
    if mode == "off":
        return False

    start_h = cfg.get("night_start_hour", 23)
    end_h = cfg.get("night_end_hour", 9)
    tz_offset = cfg.get("night_tz_offset", 0)

    utc_now = datetime.datetime.now(datetime.timezone.utc)
    loc_now = utc_now + datetime.timedelta(hours=tz_offset)
    curr_hour = loc_now.hour

    is_night = False
    if start_h > end_h:
        if curr_hour >= start_h or curr_hour < end_h:
            is_night = True
    else:
        if start_h <= curr_hour < end_h:
            is_night = True

    if not is_night:
        return False

    if mode == "silence":
        try:
            await msg.delete()
        except Exception:
            pass
        return True

    elif mode == "medias":
        has_media = bool(msg.photo or msg.video or msg.audio or msg.voice or msg.video_note or msg.document or msg.sticker or msg.animation)
        if has_media:
            try:
                await msg.delete()
            except Exception:
                pass
            return True

    return False
