import asyncio
import logging
import os
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatMemberStatus

# ==================== SOZLAMALAR ====================
# Tokenni endi kodga yozmaymiz — Railway'da Environment Variable sifatida beriladi
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
# CHANNEL_USERNAMES: vergul bilan ajratilgan kanal/chat username'lari
CHANNEL_USERNAMES = [c.strip() for c in os.environ.get(
    "CHANNEL_USERNAMES", "OpenBudjetBotChat,OpenBudjetBotYozmaChat"
).split(",") if c.strip()]
# ====================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable topilmadi! Railway sozlamalarida qo'shing.")

CALL_CENTER_PHONE = os.environ.get("CALL_CENTER_PHONE", "+998945120062")
CALL_CENTER_ADMIN = os.environ.get("CALL_CENTER_ADMIN", "Akramov_Erkin")
HELP_ADMIN = os.environ.get("HELP_ADMIN", "Akramov_Erkin")
# Tasdiqlangan/rad etilgan skrinshotlar avtomatik yuboriladigan guruhlar (ixtiyoriy)
APPROVED_GROUP_ID = os.environ.get("APPROVED_GROUP_ID", "")
REJECTED_GROUP_ID = os.environ.get("REJECTED_GROUP_ID", "")

LANGS = {
    "uz": "🇺🇿 O'zbek (lotin)",
    "uz_cyr": "🇺🇿 Ўзбек (кирилл)",
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
    "tj": "🇹🇯 Тоҷикӣ",
    "kk": "🇰🇿 Қазақша",
}

# Faqat asosiy menyu va start xabari tarjima qilingan; qolgan xabarlar o'zbek tilida qoladi
TR = {
    "uz": {
        "vote": "📥 Ovoz berish", "newproject": "➕ Loyiha qo'shish (Lider)",
        "myprojects": "⚙️ Mening Loyihalarim", "balance": "👤 Balansim",
        "referral": "🔗 Referal Link", "rating": "📊 Reyting", "stats": "📈 Statistika",
        "callcenter": "📞 Call-markaz", "help": "🆘 Yordam", "language": "🌐 Til",
        "guide": "ℹ️ Yo'riqnoma",
        "welcome": "🏛 ✨ OPEN BUDJET BOT ✨ 🏛\n━━━━━━━━━━━━━━━━━━━\n\n👋 Assalomu alaykum, {name}!\n\n🗳 Bu yerda siz:\n  • Jamoat loyihalariga ovoz berasiz\n  • Ball va chipta yutib olasiz\n  • Do'stlaringizni taklif qilib bonus olasiz\n  • Reytingda top o'ringa chiqasiz\n\n🚀 Boshlash uchun pastdagi menyudan foydalaning!",
        "choose_lang": "🌐 Tilni tanlang:",
        "lang_set": "✅ Til o'zbek tiliga o'rnatildi.",
    },
    "uz_cyr": {
        "vote": "📥 Овоз бериш", "newproject": "➕ Лойиҳа қўшиш (Лидер)",
        "myprojects": "⚙️ Менинг лойиҳаларим", "balance": "👤 Балансим",
        "referral": "🔗 Реферал линк", "rating": "📊 Рейтинг", "stats": "📈 Статистика",
        "callcenter": "📞 Колл-марказ", "help": "🆘 Ёрдам", "language": "🌐 Тил",
        "guide": "ℹ️ Йўриқнома",
        "welcome": "🏛 ✨ OPEN BUDJET BOT ✨ 🏛\n━━━━━━━━━━━━━━━━━━━\n\n👋 Ассалому алайкум, {name}!\n\n🗳 Бу ерда сиз:\n  • Жамоат лойиҳаларига овоз берасиз\n  • Балл ва чипта ютиб оласиз\n  • Дўстларингизни таклиф қилиб бонус оласиз\n  • Рейтингда топ ўринга чиқасиз\n\n🚀 Бошлаш учун пастдаги менюдан фойдаланинг!",
        "choose_lang": "🌐 Тилни танланг:",
        "lang_set": "✅ Тил ўзбек (кирилл) тилига ўрнатилди.",
    },
    "ru": {
        "vote": "📥 Голосовать", "newproject": "➕ Добавить проект (Лидер)",
        "myprojects": "⚙️ Мои проекты", "balance": "👤 Мой баланс",
        "referral": "🔗 Реферальная ссылка", "rating": "📊 Рейтинг", "stats": "📈 Статистика",
        "callcenter": "📞 Колл-центр", "help": "🆘 Помощь", "language": "🌐 Язык",
        "guide": "ℹ️ Инструкция",
        "welcome": "🏛 ✨ OPEN BUDJET BOT ✨ 🏛\n━━━━━━━━━━━━━━━━━━━\n\n👋 Здравствуйте, {name}!\n\n🗳 Здесь вы можете:\n  • Голосовать за общественные проекты\n  • Зарабатывать баллы и билеты\n  • Приглашать друзей и получать бонусы\n  • Занимать топ места в рейтинге\n\n🚀 Используйте меню ниже, чтобы начать!",
        "choose_lang": "🌐 Выберите язык:",
        "lang_set": "✅ Язык изменён на русский.",
    },
    "en": {
        "vote": "📥 Vote", "newproject": "➕ Add project (Leader)",
        "myprojects": "⚙️ My projects", "balance": "👤 My balance",
        "referral": "🔗 Referral link", "rating": "📊 Rating", "stats": "📈 Statistics",
        "callcenter": "📞 Call center", "help": "🆘 Help", "language": "🌐 Language",
        "guide": "ℹ️ Guide",
        "welcome": "🏛 ✨ OPEN BUDJET BOT ✨ 🏛\n━━━━━━━━━━━━━━━━━━━\n\n👋 Hello, {name}!\n\n🗳 Here you can:\n  • Vote for community projects\n  • Earn points and tickets\n  • Invite friends for bonuses\n  • Reach the top of the rating\n\n🚀 Use the menu below to get started!",
        "choose_lang": "🌐 Choose a language:",
        "lang_set": "✅ Language set to English.",
    },
    "tj": {
        "vote": "📥 Овоздиҳӣ", "newproject": "➕ Илова кардани лоиҳа (Лидер)",
        "myprojects": "⚙️ Лоиҳаҳои ман", "balance": "👤 Баланси ман",
        "referral": "🔗 Пайванди реферал", "rating": "📊 Рейтинг", "stats": "📈 Статистика",
        "callcenter": "📞 Маркази занг", "help": "🆘 Кӯмак", "language": "🌐 Забон",
        "guide": "ℹ️ Дастур",
        "welcome": "🏛 ✨ OPEN BUDJET BOT ✨ 🏛\n━━━━━━━━━━━━━━━━━━━\n\n👋 Салом, {name}!\n\n🗳 Дар ин ҷо шумо метавонед:\n  • Ба лоиҳаҳои ҷамъиятӣ овоз диҳед\n  • Балл ва чипта ба даст оред\n  • Дӯстонро даъват карда бонус гиред\n  • Дар рейтинг ҷои болоро ишғол кунед\n\n🚀 Барои сар кардан аз менюи поён истифода баред!",
        "choose_lang": "🌐 Забонро интихоб кунед:",
        "lang_set": "✅ Забон ба тоҷикӣ иваз шуд.",
    },
    "kk": {
        "vote": "📥 Дауыс беру", "newproject": "➕ Жоба қосу (Көшбасшы)",
        "myprojects": "⚙️ Менің жобаларым", "balance": "👤 Менің балансым",
        "referral": "🔗 Реферал сілтемесі", "rating": "📊 Рейтинг", "stats": "📈 Статистика",
        "callcenter": "📞 Байланыс орталығы", "help": "🆘 Көмек", "language": "🌐 Тіл",
        "guide": "ℹ️ Нұсқаулық",
        "welcome": "🏛 ✨ OPEN BUDJET BOT ✨ 🏛\n━━━━━━━━━━━━━━━━━━━\n\n👋 Сәлем, {name}!\n\n🗳 Мұнда сіз:\n  • Қоғамдық жобаларға дауыс бересіз\n  • Ұпай және билет жинайсыз\n  • Достарды шақырып бонус аласыз\n  • Рейтингте топ орынға шығасыз\n\n🚀 Бастау үшін төмендегі мәзірді пайдаланыңыз!",
        "choose_lang": "🌐 Тілді таңдаңыз:",
        "lang_set": "✅ Тіл қазақ тіліне өзгертілді.",
    },
}


def get_user_lang(user_id: int) -> str:
    cursor.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    lang = row[0] if row and row[0] else "uz"
    return lang if lang in TR else "uz"


def t(lang: str, key: str) -> str:
    return TR.get(lang, TR["uz"]).get(key, TR["uz"].get(key, key))


MENU_BUTTONS = [
    "📥 Ovoz berish", "➕ Loyiha qo'shish (Lider)",
    "⚙️ Mening Loyihalarim", "👤 Balansim",
    "🔗 Referal Link", "📊 Reyting", "📈 Statistika",
    "📞 Call-markaz", "🆘 Yordam", "🌐 Til", "ℹ️ Yo'riqnoma"
]
# Boshqa tillardagi menyu matnlari ham xuddi shu handler'larga tushishi uchun
ALL_MENU_TEXTS = set(MENU_BUTTONS)
for _lang_dict in TR.values():
    for _key in ["vote", "newproject", "myprojects", "balance", "referral", "rating", "stats", "callcenter", "help", "language", "guide"]:
        ALL_MENU_TEXTS.add(_lang_dict[_key])


class CreateProjectState(StatesGroup):
    project_name = State()
    link = State()
    target_votes = State()
    description = State()
    photo = State()
    verifier_username = State()


class UploadPhotoState(StatesGroup):
    waiting_for_photo = State()


conn = sqlite3.connect("bot_database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    referrer_id INTEGER,
    score INTEGER DEFAULT 0,
    tickets INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT,
    open_budget_link TEXT,
    leader_id INTEGER,
    verifier_username TEXT,
    target_votes INTEGER,
    total_votes INTEGER DEFAULT 0
)
""")

cursor.execute("CREATE TABLE IF NOT EXISTS sent_photos (photo_hash TEXT PRIMARY KEY)")

# Eski bazalarda yangi ustunlar bo'lmasligi mumkin — xavfsiz qo'shamiz
for col_def in ["description TEXT", "photo_file_id TEXT"]:
    try:
        cursor.execute(f"ALTER TABLE projects ADD COLUMN {col_def}")
    except sqlite3.OperationalError:
        pass

try:
    cursor.execute("ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'uz'")
except sqlite3.OperationalError:
    pass  # ustun allaqachon mavjud

conn.commit()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message.middleware()
async def subscription_message_middleware(handler, event: Message, data: dict):
    # /start har doim ruxsat etiladi — u o'zi tekshiruvni ko'rsatadi
    if event.text and event.text.startswith("/start"):
        return await handler(event, data)
    if not await check_sub(event.from_user.id):
        await event.answer(
            "⚠️ Botdan foydalanish uchun avval rasmiy kanal/chatlarimizga a'zo bo'ling!\n\n"
            "Barchasiga a'zo bo'lgach, «✅ A'zolikni tekshirish» tugmasini bosing.",
            reply_markup=build_sub_keyboard()
        )
        return
    return await handler(event, data)


@dp.callback_query.middleware()
async def subscription_callback_middleware(handler, event: CallbackQuery, data: dict):
    if event.data == "check_sub_now":
        return await handler(event, data)
    if not await check_sub(event.from_user.id):
        await event.answer("⚠️ Avval kanalga a'zo bo'ling!", show_alert=True)
        return
    return await handler(event, data)


async def check_sub(user_id: int) -> bool:
    """Barcha kanallar/chatlarga a'zo bo'lsagina True qaytaradi."""
    for channel in CHANNEL_USERNAMES:
        try:
            member = await bot.get_chat_member(chat_id=f"@{channel}", user_id=user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
                return False
        except Exception:
            return False
    return True


def build_sub_keyboard():
    buttons = [
        [InlineKeyboardButton(text=f"📢 {ch} ga a'zo bo'lish", url=f"https://t.me/{ch}")]
        for ch in CHANNEL_USERNAMES
    ]
    buttons.append([InlineKeyboardButton(text="✅ A'zolikni tekshirish", callback_data="check_sub_now")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def skip_keyboard(label: str = "⏭ O'tkazib yuborish"):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label)]],
        resize_keyboard=True
    )


def main_menu(lang: str = "uz"):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "vote")), KeyboardButton(text=t(lang, "newproject"))],
            [KeyboardButton(text=t(lang, "myprojects")), KeyboardButton(text=t(lang, "balance"))],
            [KeyboardButton(text=t(lang, "referral")), KeyboardButton(text=t(lang, "rating"))],
            [KeyboardButton(text=t(lang, "stats")), KeyboardButton(text=t(lang, "guide"))],
            [KeyboardButton(text=t(lang, "callcenter")), KeyboardButton(text=t(lang, "help"))],
            [KeyboardButton(text=t(lang, "language"))]
        ],
        resize_keyboard=True
    )


def esc(text: str) -> str:
    """Foydalanuvchi kiritgan matnni Markdown xato bermasligi uchun tozalash."""
    if not text:
        return ""
    for ch in ["_", "*", "[", "]", "`"]:
        text = text.replace(ch, "\\" + ch)
    return text


# ---------- DARAJA / MEDAL TIZIMI ----------
LEVELS = [
    (0, "🆕 Yangi ishtirokchi"),
    (10, "🥉 Bronza faol"),
    (30, "🥈 Kumush faol"),
    (60, "🥇 Oltin faol"),
    (100, "💎 Olmos faol"),
    (250, "👑 Afsonaviy faol"),
]


def get_level(score: int) -> str:
    level_name = LEVELS[0][1]
    for threshold, name in LEVELS:
        if score >= threshold:
            level_name = name
        else:
            break
    return level_name


def get_next_level_info(score: int) -> str:
    for threshold, name in LEVELS:
        if score < threshold:
            return f"\n📈 Keyingi daraja «{name}» gacha: {threshold - score} ball qoldi!"
    return "\n🏆 Siz eng yuqori darajadasiz!"


async def broadcast_new_project(project_name: str, target_votes: int):
    """Barcha foydalanuvchilarga yangi loyiha haqida xabar yuborish."""
    cursor.execute("SELECT user_id FROM users")
    user_ids = [row[0] for row in cursor.fetchall()]
    text = (
        f"🆕 Yangi loyiha e'lon qilindi!\n\n"
        f"📌 {project_name}\n"
        f"🎯 Maqsad: {target_votes} ta ovoz\n\n"
        f"«📥 Ovoz berish» bo'limidan qatnashing va ball/chipta yutib oling!"
    )
    for uid in user_ids:
        try:
            await bot.send_message(uid, text)
        except Exception:
            pass
        await asyncio.sleep(0.05)


# ---------- SLASH BUYRUQLAR (Menu tugmasi orqali) ----------
@dp.message(F.text == "/vote")
async def cmd_vote(message: Message, state: FSMContext):
    await state.clear()
    await vote_info(message)


@dp.message(F.text == "/newproject")
async def cmd_newproject(message: Message, state: FSMContext):
    await state.clear()
    await create_project_start(message, state)


@dp.message(F.text == "/myprojects")
async def cmd_myprojects(message: Message, state: FSMContext):
    await state.clear()
    await my_projects(message)


@dp.message(F.text == "/balance")
async def cmd_balance(message: Message, state: FSMContext):
    await state.clear()
    await show_balance(message)


@dp.message(F.text == "/referral")
async def cmd_referral(message: Message, state: FSMContext):
    await state.clear()
    await get_ref_link(message)


@dp.message(F.text == "/top")
async def cmd_top(message: Message, state: FSMContext):
    await state.clear()
    await show_rating(message)


@dp.message(F.text == "/stats")
async def cmd_stats(message: Message, state: FSMContext):
    await state.clear()
    await show_stats(message)


@dp.message(F.text == "/help")
async def cmd_help(message: Message, state: FSMContext):
    await state.clear()
    await show_guide(message)


# ---------- MENYU TUGMALARI — HAR DOIM HOLATNI TOZALAB, TO'G'RI BO'LIMGA O'TADI ----------
def find_menu_key(text: str):
    for lang_dict in TR.values():
        for key, val in lang_dict.items():
            if val == text:
                return key
    return None


@dp.message(F.text.in_(ALL_MENU_TEXTS))
async def global_menu_handler(message: Message, state: FSMContext):
    await state.clear()
    key = find_menu_key(message.text)
    lang = get_user_lang(message.from_user.id)
    if key == "vote":
        await vote_info(message)
    elif key == "newproject":
        await create_project_start(message, state)
    elif key == "myprojects":
        await my_projects(message)
    elif key == "balance":
        await show_balance(message)
    elif key == "referral":
        await get_ref_link(message)
    elif key == "rating":
        await show_rating(message)
    elif key == "stats":
        await show_stats(message)
    elif key == "guide":
        await show_guide(message)
    elif key == "callcenter":
        await show_call_center(message)
    elif key == "help":
        await show_help(message)
    elif key == "language":
        await show_language_menu(message, lang)


# ---------- START VA REFERAL ----------
@dp.message(CommandStart())
async def start_cmd(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = (message.from_user.username or "").lower()

    if not await check_sub(user_id):
        await message.answer(
            "⚠️ Botdan foydalanish uchun rasmiy kanal/chatlarimizga a'zo bo'ling!\n\n"
            "Barchasiga a'zo bo'lgach, «✅ A'zolikni tekshirish» tugmasini bosing.",
            reply_markup=build_sub_keyboard()
        )
        return

    referrer_id = None
    if command.args and command.args.isdigit() and int(command.args) != user_id:
        referrer_id = int(command.args)

    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    already_exists = cursor.fetchone()

    if not already_exists:
        cursor.execute(
            "INSERT INTO users (user_id, username, full_name, referrer_id) VALUES (?, ?, ?, ?)",
            (user_id, username, message.from_user.full_name, referrer_id)
        )
        conn.commit()
        if referrer_id:
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (referrer_id,))
            if cursor.fetchone():
                cursor.execute("UPDATE users SET score = score + 1 WHERE user_id = ?", (referrer_id,))
                conn.commit()
                try:
                    await bot.send_message(referrer_id, "🎉 Referal mukofoti: do'stingiz botga qo'shildi! Sizga +1 ball berildi.")
                except Exception:
                    pass
    else:
        cursor.execute("UPDATE users SET username = ?, full_name = ? WHERE user_id = ?",
                        (username, message.from_user.full_name, user_id))
        conn.commit()

    lang = get_user_lang(user_id)
    await message.answer(
        t(lang, "welcome").format(name=message.from_user.full_name),
        reply_markup=main_menu(lang)
    )


@dp.callback_query(F.data == "check_sub_now")
async def check_sub_callback(call: CallbackQuery):
    if await check_sub(call.from_user.id):
        lang = get_user_lang(call.from_user.id)
        await call.message.delete()
        await call.message.answer("🎉 A'zoligingiz tasdiqlandi! Bosh menyu ochildi:", reply_markup=main_menu(lang))
    else:
        await call.answer("❌ Siz hali kanalga a'zo bo'lmadingiz!", show_alert=True)


# ---------- LOYIHA QO'SHISH ----------
async def create_project_start(message: Message, state: FSMContext):
    await state.set_state(CreateProjectState.project_name)
    await message.answer("📝 Loyiha nomini kiriting\n(Masalan: 37-maktabni ta'mirlash):")


@dp.message(CreateProjectState.project_name)
async def process_pname(message: Message, state: FSMContext):
    await state.update_data(project_name=message.text.strip())
    await state.set_state(CreateProjectState.link)
    await message.answer("🔗 Endi Open Budget havolasini (linkini) yuboring:\n\nLink http:// yoki https:// bilan boshlanishi kerak!")


@dp.message(CreateProjectState.link)
async def process_link(message: Message, state: FSMContext):
    link = message.text.strip()
    if not (link.startswith("http://") or link.startswith("https://")):
        await message.answer("❌ Xato link! Iltimos, haqiqiy havola yuboring.\nMasalan: https://openbudget.uz/...")
        return
    await state.update_data(link=link)
    await state.set_state(CreateProjectState.target_votes)
    await message.answer("🎯 Nechta ovoz to'plashingiz kerak? (Faqat raqam kiriting, masalan: 100):")


@dp.message(CreateProjectState.target_votes)
async def process_target_votes(message: Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("⚠️ Iltimos, faqat musbat raqam kiriting (masalan: 50):")
        return
    await state.update_data(target_votes=int(message.text))
    await state.set_state(CreateProjectState.description)
    await message.answer(
        "📝 Loyiha haqida qo'shimcha tavsif yozing (ixtiyoriy).\n\n"
        "Masalan: \"Har bir ovoz uchun 5000 so'm\", \"Ovoz berib, ishni shunday bajaring\" va h.k.\n\n"
        "Agar tavsif yozmoqchi bo'lmasangiz, pastdagi tugmani bosing.",
        reply_markup=skip_keyboard()
    )


@dp.message(CreateProjectState.description)
async def process_description(message: Message, state: FSMContext):
    description = None if message.text == "⏭ O'tkazib yuborish" else (message.text or "").strip()
    await state.update_data(description=description)
    await state.set_state(CreateProjectState.photo)
    await message.answer(
        "🖼 Loyiha uchun rasm yuborishingiz mumkin (ixtiyoriy).\n\n"
        "Agar rasm qo'shmoqchi bo'lmasangiz, pastdagi tugmani bosing.",
        reply_markup=skip_keyboard()
    )


@dp.message(CreateProjectState.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await _ask_verifier(message, state)


@dp.message(CreateProjectState.photo, F.text == "⏭ O'tkazib yuborish")
async def process_photo_skip(message: Message, state: FSMContext):
    await state.update_data(photo_file_id=None)
    await _ask_verifier(message, state)


@dp.message(CreateProjectState.photo)
async def process_photo_invalid(message: Message, state: FSMContext):
    await message.answer("⚠️ Iltimos, rasm yuboring yoki «⏭ O'tkazib yuborish» tugmasini bosing.")


async def _ask_verifier(message: Message, state: FSMContext):
    await state.set_state(CreateProjectState.verifier_username)
    my_uname = f"@{message.from_user.username}" if message.from_user.username else "sizda username yo'q, avval Telegram sozlamalaridan username o'rnating"
    await message.answer(
        f"👤 Skrinshotlarni kim tasdiqlaydi yoki rad etadi?\n\n"
        f"O'sha mas'ul shaxsning Telegram username'ini kiriting (masalan: @username).\n"
        f"Mas'ul shaxs botga kamida bir marta /start bosgan bo'lishi kerak, aks holda unga rasm yetib bormaydi.\n\n"
        f"(O'zingiz tasdiqlamoqchi bo'lsangiz: {my_uname})",
        reply_markup=main_menu()
    )


@dp.message(CreateProjectState.verifier_username)
async def process_verifier_username(message: Message, state: FSMContext):
    raw_username = message.text.strip().replace("@", "").lower()
    data = await state.get_data()

    cursor.execute(
        "INSERT INTO projects (project_name, open_budget_link, leader_id, verifier_username, target_votes, description, photo_file_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (data['project_name'], data['link'], message.from_user.id, raw_username, data['target_votes'],
         data.get('description'), data.get('photo_file_id'))
    )
    conn.commit()
    await state.clear()

    cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = ?", (raw_username,))
    verifier_known = cursor.fetchone() is not None
    warn = "" if verifier_known else "\n\n⚠️ Diqqat: bu foydalanuvchi hali botga /start bosmagan. U /start bosmaguncha rasm sizga (liderga) yuboriladi."

    await message.answer(
        f"✅ Loyiha muvaffaqiyatli qo'shildi va mas'ul tayinlandi!\n\n"
        f"📌 Nom: {data['project_name']}\n"
        f"🔗 Link: {data['link']}\n"
        f"🎯 Ovoz maqsadi: {data['target_votes']} ta\n"
        f"👤 Mas'ul: @{raw_username}{warn}",
        reply_markup=main_menu()
    )

    asyncio.create_task(broadcast_new_project(data['project_name'], data['target_votes']))


# ---------- OVOZ BERISH ----------
async def vote_info(message: Message):
    cursor.execute("SELECT id, project_name, open_budget_link, total_votes, target_votes, description, photo_file_id FROM projects ORDER BY id DESC")
    projects = cursor.fetchall()

    if not projects:
        await message.answer("📥 Hozircha aktiv loyihalar yo'q.")
        return

    await message.answer("📥 Ovoz berish uchun loyihani tanlang:\n\nOpen Budget saytiga o'tib ovoz bering va chiqqan skrinshotni botga yuboring!")
    for p in projects:
        p_id, p_name, p_link, p_votes, p_target, p_desc, p_photo = p
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗳 Saytda ovoz berish", url=p_link)],
            [InlineKeyboardButton(text="📸 Skrinshot yuborish", callback_data=f"send_photo_{p_id}")]
        ])
        caption = f"📌 Loyiha: {p_name}\n📊 To'plangan ovozlar: {p_votes} / {p_target} ta"
        if p_desc:
            caption += f"\n\n📝 {p_desc}"
        if p_photo:
            await message.answer_photo(photo=p_photo, caption=caption, reply_markup=kb)
        else:
            await message.answer(caption, reply_markup=kb)


@dp.callback_query(F.data.startswith("send_photo_"))
async def prompt_photo_upload(call: CallbackQuery, state: FSMContext):
    project_id = int(call.data.split("_")[2])
    await state.set_state(UploadPhotoState.waiting_for_photo)
    await state.update_data(active_project_id=project_id)
    await call.message.answer("📸 Ushbu loyiha uchun ovoz berganingizni tasdiqlovchi skrinshotni yuboring:")
    await call.answer()


@dp.message(UploadPhotoState.waiting_for_photo, F.photo)
async def handle_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_unique_id

    cursor.execute("SELECT photo_hash FROM sent_photos WHERE photo_hash = ?", (photo_id,))
    if cursor.fetchone():
        await message.answer("⚠️ Bu skrinshot allaqachon botga yuborilgan! Takroriy rasmlar qabul qilinmaydi.")
        await state.clear()
        return

    data = await state.get_data()
    project_id = data.get("active_project_id")

    cursor.execute("SELECT id, verifier_username, project_name, leader_id FROM projects WHERE id = ?", (project_id,))
    project = cursor.fetchone()

    if not project:
        await message.answer("⚠️ Bu loyiha allaqachon o'chirilgan yoki topilmadi.")
        await state.clear()
        return

    p_id, verifier_username, p_name, leader_id = project

    cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = ?", (verifier_username.lower(),))
    v_row = cursor.fetchone()
    target_send_id = v_row[0] if v_row else leader_id

    verifier_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_{message.from_user.id}_{p_id}_{photo_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"rej_{message.from_user.id}_{photo_id}")
    ]])

    try:
        await bot.send_photo(
            chat_id=target_send_id,
            photo=message.photo[-1].file_id,
            caption=f"📥 Yangi ovoz skrinshoti!\n\n📌 Loyiha: {p_name}\n👤 Yubordi: {message.from_user.full_name}\n🆔 User ID: {message.from_user.id}",
            reply_markup=verifier_kb
        )
        await message.answer("✅ Skrinshot mas'ul shaxsga yuborildi. Tekshiruvdan o'tgach balansingizga ball beriladi!")
    except Exception:
        await message.answer("⚠️ Skrinshotni mas'ul shaxsga yuborib bo'lmadi (u botga /start bosmagan bo'lishi mumkin).")
    await state.clear()


# ---------- TASDIQLASH / RAD ETISH ----------
@dp.callback_query(F.data.startswith("app_") | F.data.startswith("rej_"))
async def process_verification(call: CallbackQuery):
    parts = call.data.split("_")
    action, user_id = parts[0], int(parts[1])

    if action == "app":
        p_id, photo_id = int(parts[2]), parts[3]
        cursor.execute("INSERT OR IGNORE INTO sent_photos (photo_hash) VALUES (?)", (photo_id,))
        cursor.execute("UPDATE users SET score = score + 1 WHERE user_id = ?", (user_id,))
        cursor.execute("UPDATE projects SET total_votes = total_votes + 1 WHERE id = ?", (p_id,))
        conn.commit()

        cursor.execute("SELECT score FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        score = row[0] if row else 0
        ticket_msg = ""
        if score > 0 and score % 10 == 0:
            cursor.execute("UPDATE users SET tickets = tickets + 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            ticket_msg = "\n🎟 10 ta ovoz yig'ganingiz uchun +1 ta chipta berildi!"

        cursor.execute("SELECT total_votes, target_votes, project_name, leader_id FROM projects WHERE id = ?", (p_id,))
        row = cursor.fetchone()
        if row and row[0] >= row[1]:
            cursor.execute("DELETE FROM projects WHERE id = ?", (p_id,))
            conn.commit()
            try:
                await bot.send_message(row[3], f"🎉 Tabriklaymiz! «{row[2]}» loyihangiz belgilangan {row[1]} ta ovoz yig'di va ro'yxatdan avtomatik olib tashlandi!")
            except Exception:
                pass

        try:
            await bot.send_message(user_id, f"🎉 Ovozingiz tasdiqlandi! +1 ball berildi.{ticket_msg}")
        except Exception:
            pass
        await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n✅ Tasdiqlandi va ball berildi")

        if APPROVED_GROUP_ID and call.message.photo:
            try:
                await bot.send_photo(
                    chat_id=APPROVED_GROUP_ID,
                    photo=call.message.photo[-1].file_id,
                    caption=(call.message.caption or "") + "\n\n✅ Tasdiqlangan"
                )
            except Exception:
                pass
    else:
        try:
            await bot.send_message(user_id, "❌ Ovozingiz rad etildi. Skrinshot talabga javob bermadi.")
        except Exception:
            pass
        await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n❌ Rad etildi")

        if REJECTED_GROUP_ID and call.message.photo:
            try:
                await bot.send_photo(
                    chat_id=REJECTED_GROUP_ID,
                    photo=call.message.photo[-1].file_id,
                    caption=(call.message.caption or "") + "\n\n❌ Rad etilgan"
                )
            except Exception:
                pass

    await call.answer()


# ---------- MENING LOYIHALARIM ----------
async def my_projects(message: Message):
    cursor.execute(
        "SELECT id, project_name, total_votes, target_votes, verifier_username FROM projects WHERE leader_id = ?",
        (message.from_user.id,)
    )
    projects = cursor.fetchall()

    if not projects:
        await message.answer("⚠️ Siz hali hech qanday loyiha yaratmagansiz.")
        return

    await message.answer("⚙️ Siz qo'shgan loyihalar ro'yxati:")
    for p in projects:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Loyihani bekor qilish (O'chirish)", callback_data=f"del_project_{p[0]}")]
        ])
        await message.answer(
            f"📌 Loyiha: {p[1]}\n📊 Yig'ildi: {p[2]} / {p[3]} ta ovoz\n👤 Mas'ul: @{p[4]}",
            reply_markup=kb
        )


@dp.callback_query(F.data.startswith("del_project_"))
async def delete_project_by_leader(call: CallbackQuery):
    p_id = int(call.data.split("_")[2])
    cursor.execute("SELECT leader_id FROM projects WHERE id = ?", (p_id,))
    row = cursor.fetchone()
    if not row or row[0] != call.from_user.id:
        await call.answer("Bu sizning loyihangiz emas!", show_alert=True)
        return
    cursor.execute("DELETE FROM projects WHERE id = ?", (p_id,))
    conn.commit()
    await call.message.edit_text("🗑 Loyiha bekor qilindi va botdan olib tashlandi.")
    await call.answer("O'chirildi!")


# ---------- BALANS / REFERAL / REYTING / YO'RIQNOMA ----------
async def show_balance(message: Message):
    cursor.execute("SELECT score, tickets FROM users WHERE user_id = ?", (message.from_user.id,))
    row = cursor.fetchone()
    score, tickets = (row[0], row[1]) if row else (0, 0)
    level = get_level(score)
    next_info = get_next_level_info(score)
    await message.answer(
        f"👤 Sizning Balansingiz:\n\n"
        f"⭐ Ovozlar (Ball): {score}\n"
        f"🎟 Chiptalar: {tickets}\n"
        f"🏅 Darajangiz: {level}"
        f"{next_info}"
    )


async def get_ref_link(message: Message):
    bot_info = await bot.get_me()
    await message.answer(
        f"📢 Referal havolangiz:\nhttps://t.me/{bot_info.username}?start={message.from_user.id}\n\n"
        f"Do'stingiz shu link orqali kirib /start bossa, sizga +1 ball beriladi!"
    )


async def show_rating(message: Message):
    cursor.execute("SELECT full_name, score FROM users ORDER BY score DESC LIMIT 10")
    top_users = cursor.fetchall()
    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 Eng ko'p ovoz yig'gan Top-10 Foydalanuvchilar:\n\n"
    for i, u in enumerate(top_users, start=1):
        prefix = medals[i - 1] if i <= 3 else f"{i}."
        text += f"{prefix} {u[0]} — {u[1]} ball ({get_level(u[1])})\n"
    await message.answer(text if top_users else "📊 Hali aktiv foydalanuvchilar yo'q.")


async def show_stats(message: Message):
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_votes), 0), COALESCE(SUM(target_votes), 0) FROM projects")
    active_projects, active_votes, active_target = cursor.fetchone()

    cursor.execute("SELECT COALESCE(SUM(score), 0) FROM users")
    total_score = cursor.fetchone()[0]

    cursor.execute("SELECT project_name, total_votes, target_votes FROM projects ORDER BY total_votes DESC LIMIT 1")
    top_project = cursor.fetchone()

    text = (
        "📈 Bot statistikasi\n\n"
        f"👥 Jami foydalanuvchilar: {total_users}\n"
        f"📌 Faol loyihalar: {active_projects}\n"
        f"🗳 Jami tasdiqlangan ovozlar: {total_score}\n"
    )
    if top_project:
        text += f"\n🔥 Eng faol loyiha: {top_project[0]} ({top_project[1]}/{top_project[2]} ovoz)"
    await message.answer(text)


async def show_guide(message: Message):
    await message.answer(
        "ℹ️ Botdan foydalanish yo'riqnomasi:\n\n"
        "1. «📥 Ovoz berish» bo'limidan loyihani tanlang.\n"
        "2. Open Budget saytida ovoz bering va skrinshot oling.\n"
        "3. «📸 Skrinshot yuborish» tugmasini bosib rasmni yuboring.\n"
        "4. Mas'ul shaxs rasmni tekshirib tasdiqlagach, sizga ball beriladi.\n"
        "5. Har 10 ta tasdiqlangan ovoz uchun +1 chipta olasiz."
    )


async def show_call_center(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Admin bilan yozishish", url=f"https://t.me/{CALL_CENTER_ADMIN}")]
    ])
    await message.answer(
        f"📞 Call-markaz\n\n"
        f"☎️ Telefon: {CALL_CENTER_PHONE}\n"
        f"👤 Admin: @{CALL_CENTER_ADMIN}\n\n"
        f"Savol yoki muammo bo'lsa, bemalol murojaat qiling!",
        reply_markup=kb
    )


async def show_help(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆘 Admin bilan bog'lanish", url=f"https://t.me/{HELP_ADMIN}")]
    ])
    await message.answer(
        "🆘 Yordam kerakmi?\n\n"
        "Botdan foydalanishda qiyinchilik bo'lsa yoki texnik muammo chiqsa, "
        "quyidagi tugma orqali admin bilan bog'laning.",
        reply_markup=kb
    )


def language_keyboard():
    buttons = []
    row = []
    for code, name in LANGS.items():
        row.append(InlineKeyboardButton(text=name, callback_data=f"setlang_{code}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def show_language_menu(message: Message, lang: str):
    await message.answer(t(lang, "choose_lang"), reply_markup=language_keyboard())


@dp.callback_query(F.data.startswith("setlang_"))
async def set_language_callback(call: CallbackQuery):
    lang_code = call.data.split("_", 1)[1]
    if lang_code not in LANGS:
        await call.answer()
        return
    cursor.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang_code, call.from_user.id))
    conn.commit()
    await call.message.answer(t(lang_code, "lang_set"), reply_markup=main_menu(lang_code))
    await call.answer()


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot ishlamoqda")

    def log_message(self, format, *args):
        pass  # keraksiz loglarni o'chirish


def _run_health_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    server.serve_forever()


async def _set_bot_commands():
    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="start", description="🏠 Botni qayta ishga tushirish"),
        BotCommand(command="vote", description="📥 Ovoz berish"),
        BotCommand(command="newproject", description="➕ Loyiha qo'shish (Lider)"),
        BotCommand(command="myprojects", description="⚙️ Mening loyihalarim"),
        BotCommand(command="balance", description="👤 Balansim"),
        BotCommand(command="referral", description="🔗 Referal link"),
        BotCommand(command="top", description="📊 Reyting"),
        BotCommand(command="stats", description="📈 Statistika"),
        BotCommand(command="help", description="ℹ️ Yo'riqnoma"),
    ])


async def main():
    logging.basicConfig(level=logging.INFO)
    threading.Thread(target=_run_health_server, daemon=True).start()
    await _set_bot_commands()
    print("🚀 Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
