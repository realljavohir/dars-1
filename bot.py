import os
import random
import sqlite3
import bcrypt
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# O'yinlar sessiyasini xotirada saqlash
o_yinlar = {}

variantlar = {
    "tosh": "✊ Tosh",
    "qaychi": "✌️ Qaychi",
    "qogoz": "✋ Qog'oz"
}

# --- BAZA BILAN ISHLASH ---
def baza_ni_sozlash():
    conn = sqlite3.connect("foydalanuvchilar.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            login TEXT UNIQUE,
            password TEXT
        )
    """)
    conn.commit()
    conn.close()

baza_ni_sozlash()

def foydalanuvchi_mavjud(telegram_id):
    conn = sqlite3.connect("foydalanuvchilar.db")
    cursor = conn.cursor()
    cursor.execute("SELECT login FROM users WHERE telegram_id = ?", (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    return user is not None

def login_bandmi(login):
    conn = sqlite3.connect("foydalanuvchilar.db")
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM users WHERE login = ?", (login,))
    user = cursor.fetchone()
    conn.close()
    return user is not None

def ruyxatdan_utkazish(telegram_id, login, parol):
    hashed = bcrypt.hashpw(parol.encode('utf-8'), bcrypt.gensalt())
    conn = sqlite3.connect("foydalanuvchilar.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (telegram_id, login, password) VALUES (?, ?, ?)", (telegram_id, login, hashed))
        conn.commit()
        succeed = True
    except sqlite3.IntegrityError:
        succeed = False
    conn.close()
    return succeed

def login_tekshirish(telegram_id, login, parol):
    conn = sqlite3.connect("foydalanuvchilar.db")
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE telegram_id = ? AND login = ?", (telegram_id, login))
    user = cursor.fetchone()
    conn.close()
    if user:
        return bcrypt.checkpw(parol.encode('utf-8'), user)
    return False

# --- BUYRUQLAR ---
@bot.message_handler(commands=['start', 'help'])
def start_message(message):
    text = "🤖 Tosh, Qaychi, Qog'oz o'yin botiga xush kelibsiz!\n\n"
    if not foydalanuvchi_mavjud(message.from_user.id):
        text += "O'ynash uchun avval ro'yxatdan o'ting: /register"
    else:
        text += "Siz ro'yxatdan o'tgansiz.\n- Guruhda o'ynash uchun: /play\n- Kontaktlar bilan o'ynash uchun chatda bot nomini yozing!"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['register'])
def register_start(message):
    if message.chat.type != "private":
        bot.send_message(message.chat.id, "❌ Havfsizlik yuzasidan faqat botning o'zida ro'yxatdan o'tishingiz mumkin!")
        return
    if foydalanuvchi_mavjud(message.from_user.id):
        bot.send_message(message.chat.id, "✅ Siz allaqachon ro'yxatdan o'tgansiz!")
        return
    msg = bot.send_message(message.chat.id, "🔑 Yangi login kiriting:", reply_markup=ForceReply(selective=True))
    bot.register_next_step_handler(msg, register_login)

def register_login(message):
    login = message.text.strip()
    if login_bandmi(login):
        msg = bot.send_message(message.chat.id, "❌ Bu login band. Boshqa login kiriting:", reply_markup=ForceReply(selective=True))
        bot.register_next_step_handler(msg, register_login)
        return
    msg = bot.send_message(message.chat.id, f"Ajoyib! Endi '{login}' logini uchun parol kiriting:", reply_markup=ForceReply(selective=True))
    bot.register_next_step_handler(msg, register_password, login)

def register_password(message, login):
    parol = message.text.strip()
    if len(parol) < 4:
        msg = bot.send_message(message.chat.id, "❌ Parol juda qisqa (kamida 4 ta belgi). Qayta kiriting:", reply_markup=ForceReply(selective=True))
        bot.register_next_step_handler(msg, register_password, login)
        return
    if ruyxatdan_utkazish(message.from_user.id, login, parol):
        bot.send_message(message.chat.id, "🎉 Muvaffaqiyatli ro'yxatdan o'tdingiz! Endi o'yinlarda qatnashishingiz mumkin.")
    else:
        bot.send_message(message.chat.id, "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring: /register")

# --- GURUH REJIMI MANTIG'I ---
@bot.message_handler(commands=['play'])
def play_game(message):
    if message.chat.type == "private":
        bot.send_message(message.chat.id, "❌ O'yinni faqat guruhlarda o'ynash mumkin! Kontaktlar bilan o'ynash uchun esa inline rejimidan foydalaning.")
        return
    chat_id = message.chat.id
    o_yinlar[chat_id] = {
        "p1": None, "p2": None, "p1_name": "", "p2_name": "",
        "p1_choice": None, "p2_choice": None, "status": "kutish"
    }
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔐 LogIn va Qo'shilish", callback_data="login_and_join"))
    bot.send_message(
        chat_id,
        "⚔️ **Guruhda yangi o'yin boshlandi!**\n\nO'yinda qatnashish uchun 2 kishi shaxsiy xabarda ro'yxatdan o'tgan login va parolini kiritishi kerak.",
        parse_mode="Markdown", reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "login_and_join")
def login_and_join_callback(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    if chat_id not in o_yinlar or o_yinlar[chat_id]["status"] != "kutish":
        bot.answer_callback_query(call.id, "❌ O'yin topilmadi yoki boshlanib ketgan.")
        return
    if not foydalanuvchi_mavjud(user_id):
        bot.answer_callback_query(call.id, "❌ Siz hali ro'yxatdan o'tmagansiz! Botga kirib /register buyrug'ini bosing.", show_alert=True)
        return
    try:
        msg = bot.send_message(user_id, f"🎮 Guruhdagi o'yinga qo'shilish uchun loginingizni kiriting:\n(Guruh ID: `{chat_id}`)", parse_mode="Markdown", reply_markup=ForceReply(selective=True))
        bot.register_next_step_handler(msg, auth_login, chat_id, call.message.message_id)
        bot.answer_callback_query(call.id, "📩 Loginingizni kiritish uchun bot sizga shaxsiy xabar yuborishni boshladi.", show_alert=True)
    except Exception:
        bot.answer_callback_query(call.id, "❌ Bot sizga xabar yubora olmadi. Avval botga kirib /start bosing!", show_alert=True)

def auth_login(message, guruh_id, xabar_id):
    login = message.text.strip()
    msg = bot.send_message(message.chat.id, "Endi parolingizni kiriting:", reply_markup=ForceReply(selective=True))
    bot.register_next_step_handler(msg, auth_password, guruh_id, xabar_id, login)

def auth_password(message, guruh_id, xabar_id, login):
    parol = message.text.strip()
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    if login_tekshirish(user_id, login, parol):
        bot.send_message(user_id, "✅ Identifikatsiya muvaffaqiyatli! Guruhga qaytib o'yinni davom ettiring.")
        if guruh_id not in o_yinlar: return
        game = o_yinlar[guruh_id]
        if game["p1"] == user_id or game["p2"] == user_id:
            bot.send_message(user_id, "⚠️ Siz allaqachon qo'shilgansiz!")
            return
        if game["p1"] is None:
            game["p1"] = user_id
            game["p1_name"] = user_name
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔐 LogIn va Qo'shilish", callback_data="login_and_join"))
            bot.edit_message_text(
                f"⚔️ **O'yin kutish rejimida**\n\n1️⃣ O'yinchi: {user_name} (Tizimga kirdi)\n2️⃣ O'yinchi: ... kutilmoqda",
                chat_id=guruh_id, message_id=xabar_id, parse_mode="Markdown", reply_markup=markup
            )
        elif game["p2"] is None:
            game["p2"] = user_id
            game["p2_name"] = user_name
            game["status"] = "jarayon"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("✊ Tosh", callback_data="gtosh"), InlineKeyboardButton("✌️ Qaychi", callback_data="gqaychi"), InlineKeyboardButton("✋ Qog'oz", callback_data="gqogoz"))
            bot.edit_message_text(
                f"🎮 **O'yin boshlandi!**\n\nIkkala o'yinchi ham tizimga kirdi:\n👤 {game['p1_name']}\n👤 {game['p2_name']}\n\nVariantingizni tanlang:",
                chat_id=guruh_id, message_id=xabar_id, parse_mode="Markdown", reply_markup=markup
            )
    else:
        bot.send_message(user_id, "❌ Login yoki parol noto'g'ri! Guruhdagi tugmani bosib qaytadan urining.")

@bot.callback_query_handler(func=lambda call: call.data in ["gtosh", "gqaychi", "gqogoz"])
def guruh_game_logic(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    choice = call.data[1:]
    if chat_id not in o_yinlar or o_yinlar[chat_id]["status"] != "jarayon": return
    game = o_yinlar[chat_id]
    if user_id != game["p1"] and user_id != game["p2"]:
        bot.answer_callback_query(call.id, "⚠️ Siz bu o'yinda ishtirok etmayapsiz!")
        return
    if user_id == game["p1"]:
        if game["p1_choice"]: return
        game["p1_choice"] = choice
    elif user_id == game["p2"]:
        if game["p2_choice"]: return
        game["p2_choice"] = choice
    bot.answer_callback_query(call.id, f"Siz {variantlar[choice]} tanladingiz!")
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("✊ Tosh", callback_data="gtosh"), InlineKeyboardButton("✌️ Qaychi", callback_data="gqaychi"), InlineKeyboardButton("✋ Qog'oz", callback_data="gqogoz"))
    
    if game["p1_choice"] and game["p2_choice"]:
        game["status"] = "tugadi"
        p1_c, p2_c = game["p1_choice"], game["p2_choice"]
        natija = f"🏁 **O'YIN YAKUNLANDI!**\n\n👤 {game['p1_name']}: {variantlar[p1_c]}\n👤 {game['p2_name']}: {variantlar[p2_c]}\n\n"
        if p1_c == p2_c: natija += "🤝 **Durang!**"
        elif (p1_c == "tosh" and p2_c == "qaychi") or (p1_c == "qaychi" and p2_c == "qogoz") or (p1_c == "qogoz" and p2_c == "tosh"):
            natija += f"🏆 **G'olib:** {game['p1_name']} 🎉"
        else:
            natija += f"🏆 **G'olib:** {game['p2_name']} 🎉"
        bot.edit_message_text(natija, chat_id=chat_id, message_id=call.message.message_id, parse_mode="Markdown")
        del o_yinlar[chat_id]
    else:
        txt = f"🎮 **O'yin davom etmoqda...**\n\n👤 {game['p1_name']}: {'✅ Tanladi' if game['p1_choice'] else '⏳ Kutilmoqda'}\n👤 {game['p2_name']}: {'✅ Tanladi' if game['p2_choice'] else '⏳ Kutilmoqda'}"
        bot.edit_message_text(txt, chat_id=chat_id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=markup)


# --- INLINE REJIM MANTIG'I (KONTAKTLAR UCHUN) ---
@bot.inline_handler(func=lambda query: True)
def query_text(inline_query):
    try:
        user_id = inline_query.from_user.id
        if not foydalanuvchi_mavjud(user_id):
            r = telebot.types.InlineQueryResultArticle(
                id='1', title="❌ Avval ro'yxatdan o'ting!", description="O'yin boshlash uchun botga kirib /register buyrug'ini bosing.",
                input_message_content=telebot.types.InputTextMessageContent(text="🤖 Men hali botdan ro'yxatdan o'tmabman. Avval bot ichida /register bosishim kerak.")
            )
            bot.answer_inline_query(inline_query.id, [r], cache_time=1)
            return
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔐 LogIn va Qo'shilish", callback_data="login_and_join_inline"))
        r = telebot.types.InlineQueryResultArticle(
            id='2', title="⚔️ Tosh, Qaychi, Qog'oz (Ikki kishilik)", description="Ushbu xabarni do'stingizga yuborib o'yinni boshlang!",
            input_message_content=telebot.types.InputTextMessageContent(text="⚔️ **Tosh, Qaychi, Qog'oz o'yini boshlandi!**\n\nO'yinda qatnashish uchun 2 kishi shaxsiy xabarda ro'yxatdan o'tgan login va parolini kiritishi kerak."),
            reply_markup=markup
        )
        bot.answer_inline_query(inline_query.id, [r], cache_time=1)
    except Exception as e: print(f"Inline xatolik: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "login_and_join_inline")
def inline_join_callback(call):
    inline_id = call.inline_message_id
    user_id = call.from_user.id
    if not inline_id: return
    if not foydalanuvchi_mavjud(user_id):
        bot.answer_callback_query(call.id, "❌ Siz hali ro'yxatdan o'tmagansiz! Botga kirib /register buyrug'ini bosing.", show_alert=True)
        return
    if inline_id not in o_yinlar:
        o_yinlar[inline_id] = {
            "p1": None, "p2": None, "p1_name": "", "p2_name": "",
            "p1_choice": None, "p2_choice": None, "status": "kutish"
        }
    try:
        msg = bot.send_message(user_id, f"🎮 Kontaktdagi o'yinga qo'shilish uchun loginingizni kiriting:\n(O'yin ID: `{inline_id}`)", parse_mode="Markdown", reply_markup=ForceReply(selective=True))
        bot.register_next_step_handler(msg, auth_login_inline, inline_id)
        bot.answer_callback_query(call.id, "📩 Bot sizga shaxsiy xabar yubordi. Lichkaga o'tib login kiriting.", show_alert=True)
    except Exception:
        bot.answer_callback_query(call.id, "❌ Bot sizga xabar yubora olmadi. Avval botga kirib /start bosing!", show_alert=True)

def auth_login_inline(message, inline_id):
    login = message.text.strip()
    msg = bot.send_message(message.chat.id, "Endi parolingizni kiriting:", reply_markup=ForceReply(selective=True))
    bot.register_next_step_handler(msg, auth_password_inline, inline_id, login)

def auth_password_inline(message, inline_id, login):
    parol = message.text.strip()
    user_id, user_name = message.from_user.id, message.from_user.first_name
    if login_tekshirish(user_id, login, parol):
        bot.send_message(user_id, "✅ Identifikatsiya muvaffaqiyatli! Do'stingiz chatiga qaytib o'yinni davom ettiring.")
        if inline_id not in o_yinlar: return
        game = o_yinlar[inline_id]
        if game["p1"] == user_id or game["p2"] == user_id:
            bot.send_message(user_id, "⚠️ Siz allaqachon qo'shilgansiz!")
            return
        if game["p1"] is None:
            game["p1"] = user_id
            game["p1_name"] = user_name
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔐 LogIn va Qo'shilish", callback_data="login_and_join_inline"))
            bot.edit_message_text(f"⚔️ **O'yin kutish rejimida**\n\n1️⃣ O'yinchi: {user_name} (Tizimga kirdi)\n2️⃣ O'yinchi: ... kutilmoqda", inline_message_id=inline_id, parse_mode="Markdown", reply_markup=markup)
        elif game["p2"] is None:
            game["p2"] = user_id
            game["p2_name"] = user_name
            game["status"] = "jarayon"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("✊ Tosh", callback_data="itosh"), InlineKeyboardButton("✌️ Qaychi", callback_data="iqaychi"), InlineKeyboardButton("✋ Qog'oz", callback_data="iqogoz"))
            bot.edit_message_text(f"🎮 **O'yin boshlandi!**\n\nIkkala o'yinchi ham tizimga kirdi:\n👤 {game['p1_name']}\n👤 {game['p2_name']}\n\nVariantingizni tanlang:", inline_message_id=inline_id, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(user_id, "❌ Login yoki parol noto'g'ri! Chatdagi tugmani bosib qaytadan urining.")

@bot.callback_query_handler(func=lambda call: call.data in ["itosh", "iqaychi", "iqogoz"])
def inline_game_logic(call):
    inline_id = call.inline_message_id
    user_id = call.from_user.id
    choice = call.data[1:]
    if inline_id not in o_yinlar or o_yinlar[inline_id]["status"] != "jarayon": return
    game = o_yinlar[inline_id]
    if user_id != game["p1"] and user_id != game["p2"]:
        bot.answer_callback_query(call.id, "⚠️ Siz bu o'yinda ishtirok etmayapsiz!")
        return
    if user_id == game["p1"]:
        if game["p1_choice"]: return
        game["p1_choice"] = choice
    elif user_id == game["p2"]:
        if game["p2_choice"]: return
        game["p2_choice"] = choice
    bot.answer_callback_query(call.id, f"Siz {variantlar[choice]} tanladingiz!")
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("✊ Tosh", callback_data="itosh"), InlineKeyboardButton("✌️ Qaychi", callback_data="iqaychi"), InlineKeyboardButton("✋ Qog'oz", callback_data="iqogoz"))
    
    if game["p1_choice"] and game["p2_choice"]:
        game["status"] = "tugadi"
        p1_c, p2_c = game["p1_choice"], game["p2_choice"]
        natija = f"🏁 **O'YIN YAKUNLANDI!**\n\n👤 {game['p1_name']}: {variantlar[p1_c]}\n👤 {game['p2_name']}: {variantlar[p2_c]}\n\n"
        if p1_c == p2_c: natija += "🤝 **Durang!**"
        elif (p1_c == "tosh" and p2_c == "qaychi") or (p1_c == "qaychi" and p2_c == "qogoz") or (p1_c == "qogoz" and p2_c == "tosh"):
            natija += f"🏆 **G'olib:** {game['p1_name']} 🎉"
        else:
            natija += f"🏆 **G'olib:** {game['p2_name']} 🎉"
        bot.edit_message_text(natija, inline_message_id=inline_id, parse_mode="Markdown")
        del o_yinlar[inline_id]
    else:
        txt = f"🎮 **O'yin davom etmoqda...**\n\n👤 {game['p1_name']}: {'✅ Tanladi' if game['p1_choice'] else '⏳ Kutilmoqda'}\n👤 {game['p2_name']}: {'✅ Tanladi' if game['p2_choice'] else '⏳ Kutilmoqda'}"
        bot.edit_message_text(txt, inline_message_id=inline_id, parse_mode="Markdown", reply_markup=markup)

if __name__ == "__main__":
    print("Bot muvaffaqiyatli ishga tushdi...")
    bot.infinity_polling()
