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
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "Global_matematika37maktab")
# ====================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable topilmadi! Railway sozlamalarida qo'shing.")

MENU_BUTTONS = [
    "📥 Ovoz berish", "➕ Loyiha qo'shish (Lider)",
    "⚙️ Mening Loyihalarim", "👤 Balansim",
    "🔗 Referal Link", "📊 Reyting", "ℹ️ Yo'riqnoma"
]


class CreateProjectState(StatesGroup):
    project_name = State()
    link = State()
    target_votes = State()
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
conn.commit()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def check_sub(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=f"@{CHANNEL_USERNAME}", user_id=user_id)
        return member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]
    except Exception:
        return False


def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📥 Ovoz berish"), KeyboardButton(text="➕ Loyiha qo'shish (Lider)")],
            [KeyboardButton(text="⚙️ Mening Loyihalarim"), KeyboardButton(text="👤 Balansim")],
            [KeyboardButton(text="🔗 Referal Link"), KeyboardButton(text="📊 Reyting")],
            [KeyboardButton(text="ℹ️ Yo'riqnoma")]
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


@dp.message(F.text == "/help")
async def cmd_help(message: Message, state: FSMContext):
    await state.clear()
    await show_guide(message)


# ---------- MENYU TUGMALARI — HAR DOIM HOLATNI TOZALAB, TO'G'RI BO'LIMGA O'TADI ----------
@dp.message(F.text.in_(MENU_BUTTONS))
async def global_menu_handler(message: Message, state: FSMContext):
    await state.clear()
    text = message.text
    if text == "📥 Ovoz berish":
        await vote_info(message)
    elif text == "➕ Loyiha qo'shish (Lider)":
        await create_project_start(message, state)
    elif text == "⚙️ Mening Loyihalarim":
        await my_projects(message)
    elif text == "👤 Balansim":
        await show_balance(message)
    elif text == "🔗 Referal Link":
        await get_ref_link(message)
    elif text == "📊 Reyting":
        await show_rating(message)
    elif text == "ℹ️ Yo'riqnoma":
        await show_guide(message)


# ---------- START VA REFERAL ----------
@dp.message(CommandStart())
async def start_cmd(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = (message.from_user.username or "").lower()

    if not await check_sub(user_id):
        sub_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me/{CHANNEL_USERNAME}")],
            [InlineKeyboardButton(text="✅ A'zolikni tekshirish", callback_data="check_sub_now")]
        ])
        await message.answer(
            "⚠️ Botdan foydalanish uchun rasmiy kanalimizga a'zo bo'ling!\n\n"
            "A'zo bo'lgach, «✅ A'zolikni tekshirish» tugmasini bosing.",
            reply_markup=sub_kb
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

    await message.answer(
        f"👋 Salom, {message.from_user.full_name}!\n\nOpen Budget botiga xush kelibsiz! 🚀",
        reply_markup=main_menu()
    )


@dp.callback_query(F.data == "check_sub_now")
async def check_sub_callback(call: CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.delete()
        await call.message.answer("🎉 A'zoligingiz tasdiqlandi! Bosh menyu ochildi:", reply_markup=main_menu())
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
    await state.set_state(CreateProjectState.verifier_username)
    my_uname = f"@{message.from_user.username}" if message.from_user.username else "sizda username yo'q, avval Telegram sozlamalaridan username o'rnating"
    await message.answer(
        f"👤 Skrinshotlarni kim tasdiqlaydi yoki rad etadi?\n\n"
        f"O'sha mas'ul shaxsning Telegram username'ini kiriting (masalan: @username).\n"
        f"Mas'ul shaxs botga kamida bir marta /start bosgan bo'lishi kerak, aks holda unga rasm yetib bormaydi.\n\n"
        f"(O'zingiz tasdiqlamoqchi bo'lsangiz: {my_uname})"
    )


@dp.message(CreateProjectState.verifier_username)
async def process_verifier_username(message: Message, state: FSMContext):
    raw_username = message.text.strip().replace("@", "").lower()
    data = await state.get_data()

    cursor.execute(
        "INSERT INTO projects (project_name, open_budget_link, leader_id, verifier_username, target_votes) VALUES (?, ?, ?, ?, ?)",
        (data['project_name'], data['link'], message.from_user.id, raw_username, data['target_votes'])
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


# ---------- OVOZ BERISH ----------
async def vote_info(message: Message):
    cursor.execute("SELECT id, project_name, open_budget_link, total_votes, target_votes FROM projects ORDER BY id DESC")
    projects = cursor.fetchall()

    if not projects:
        await message.answer("📥 Hozircha aktiv loyihalar yo'q.")
        return

    await message.answer("📥 Ovoz berish uchun loyihani tanlang:\n\nOpen Budget saytiga o'tib ovoz bering va chiqqan skrinshotni botga yuboring!")
    for p in projects:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗳 Saytda ovoz berish", url=p[2])],
            [InlineKeyboardButton(text="📸 Skrinshot yuborish", callback_data=f"send_photo_{p[0]}")]
        ])
        await message.answer(f"📌 Loyiha: {p[1]}\n📊 To'plangan ovozlar: {p[3]} / {p[4]} ta", reply_markup=kb)


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
    else:
        try:
            await bot.send_message(user_id, "❌ Ovozingiz rad etildi. Skrinshot talabga javob bermadi.")
        except Exception:
            pass
        await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n❌ Rad etildi")

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
    await message.answer(f"👤 Sizning Balansingiz:\n\n⭐ Ovozlar (Ball): {score}\n🎟 Chiptalar: {tickets}")


async def get_ref_link(message: Message):
    bot_info = await bot.get_me()
    await message.answer(
        f"📢 Referal havolangiz:\nhttps://t.me/{bot_info.username}?start={message.from_user.id}\n\n"
        f"Do'stingiz shu link orqali kirib /start bossa, sizga +1 ball beriladi!"
    )


async def show_rating(message: Message):
    cursor.execute("SELECT full_name, score FROM users ORDER BY score DESC LIMIT 10")
    top_users = cursor.fetchall()
    text = "🏆 Eng ko'p ovoz yig'gan Top-10 Foydalanuvchilar:\n\n"
    for i, u in enumerate(top_users, start=1):
        text += f"{i}. {u[0]} — {u[1]} ball\n"
    await message.answer(text if top_users else "📊 Hali aktiv foydalanuvchilar yo'q.")


async def show_guide(message: Message):
    await message.answer(
        "ℹ️ Botdan foydalanish yo'riqnomasi:\n\n"
        "1. «📥 Ovoz berish» bo'limidan loyihani tanlang.\n"
        "2. Open Budget saytida ovoz bering va skrinshot oling.\n"
        "3. «📸 Skrinshot yuborish» tugmasini bosib rasmni yuboring.\n"
        "4. Mas'ul shaxs rasmni tekshirib tasdiqlagach, sizga ball beriladi.\n"
        "5. Har 10 ta tasdiqlangan ovoz uchun +1 chipta olasiz."
    )


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
