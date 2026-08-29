import html
from telegram import Update, InlineKeyboardMarkup
from database import get_config, save_config
from utils import create_btn, fast_edit

LANGUAGES = [
    ("en", "🇬🇧 English"),
    ("it", "🇮🇹 Italiano"),
    ("es", "🇪🇸 Español"),
    ("pt", "🇧🇷🇵🇹 Português"),
    ("de", "🇩🇪 Deutsch"),
    ("fr", "🇫🇷 Français"),
    ("ro", "🇷🇴 Română"),
    ("nl", "🇳🇱 Nederlands"),
    ("tr", "🇹🇷 Türkçe"),
    ("zh_cn", "🇨🇳 简体中文"),
    ("zh_tw", "🇨🇳 繁體中文"),
    ("uk", "🇺🇦 Українська"),
    ("ru", "🇷🇺 Русский"),
    ("kk", "🇰🇿 Қазақ"),
    ("id", "🇮🇩 Indonesia"),
    ("uz_lat", "🇺🇿 O'zbekcha"),
    ("uz_cyr", "🇺🇿 Ўзбекча"),
    ("az", "🇦🇿 Azərbaycanca"),
    ("ms", "🇲🇾 Melayu"),
    ("so", "🇸🇴 Soomaali"),
    ("sq", "🇦🇱 Shqipe"),
    ("sr", "🇷🇸 Srpski"),
    ("am", "🇪🇹 Amharic"),
    ("el", "🇬🇷 Ελληνικά"),
    ("ar", "🇸🇦 العربية"),
    ("ko", "🇰🇷 한국어"),
    ("fa", "🇮🇷 فارسی"),
    ("ku", "☀️ کوردی"),
    ("hi", "🇮🇳 हिंदी"),
    ("si", "🇱🇰 සිංහල"),
    ("bn", "🇧🇩 বাংলা"),
    ("ur", "🇵🇰 اردو"),
    ("he", "🇮🇱 עברית")
]

def get_language_keyboard(cid: int):
    kb = []
    
    # English full width
    kb.append([create_btn("🇬🇧 English", callback_data=f"setlang_en_{cid}")])
    
    # Rest in 2 columns
    row = []
    for code, label in LANGUAGES[1:]:
        row.append(create_btn(label, callback_data=f"setlang_{code}_{cid}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

    # Bottom Actions
    kb.append([create_btn("🌍 Time Zone", callback_data=f"ngt_tz_menu_{cid}")])
    kb.append([create_btn("⬅️ Back", callback_data=f"cfg_page_1_{cid}")])
    return InlineKeyboardMarkup(kb)

def get_language_text():
    return (
        "🇬🇧 Choose your language\n"
        "🇮🇹 Scegli la tua lingua"
    )

async def handle_language_callbacks(query, data: str, cid: int, user, user_states):
    cfg = get_config(cid)

    # Open Languages Menu
    if data.startswith("cfg_mod_lang_") or data.startswith("cfg_lang_") or data.startswith("lang_menu_"):
        await fast_edit(query, get_language_text(), get_language_keyboard(cid))

    # Set Language Action
    elif data.startswith("setlang_"):
        code = data.split("_")[1]
        cfg["bot_lang"] = code
        save_config(cid, cfg)

        selected_label = next((lbl for c, lbl in LANGUAGES if c == code), "English 🇬🇧")
        msg_text = f"Ok, from now on I'll speak {selected_label}"

        # Action Buttons after setting language (Screenshot 6)
        kb = [
            [create_btn("⚙️ Settings", callback_data=f"cfg_page_1_{cid}")],
            [create_btn("🌍 Time Zone", callback_data=f"ngt_tz_menu_{cid}")]
        ]
        await fast_edit(query, msg_text, InlineKeyboardMarkup(kb))
