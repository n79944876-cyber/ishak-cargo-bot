import os
import csv
import io
import requests
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")

SHEET_ID = "1RlRU8YG-mqxsqtswXReeORcg-M0eeynzg-4Wby5OpFU"
SHEET_NAME = "Товарлар"

bot = telebot.TeleBot(TOKEN)


# =========================
# GOOGLE TABLE
# =========================

def get_products():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq"

    response = requests.get(
        url,
        params={
            "tqx": "out:csv",
            "sheet": SHEET_NAME
        },
        timeout=20
    )

    response.raise_for_status()

    text = response.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))
def get_customers():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq"

    response = requests.get(
        url,
        params={
            "tqx": "out:csv",
            "sheet": "Кардарлар"
        },
        timeout=20
    )

    response.raise_for_status()

    text = response.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))

# =========================
# TELEGRAM MENU
# =========================

def main_menu():
    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        is_persistent=True,
        row_width=2
    )

    markup.row(
        types.KeyboardButton("👤 Профиль"),
        types.KeyboardButton("📦 Мои посылки")
    )

    markup.row(
        types.KeyboardButton("🔎 Отследить трек"),
        types.KeyboardButton("📍 Наши адреса")
    )

    markup.row(
        types.KeyboardButton("🚫 Запрещённые товары"),
        types.KeyboardButton("☎️ Поддержка")
    )

    return markup


def setup_commands():
    commands = [
        types.BotCommand("start", "Запустить бот"),
        types.BotCommand("menu", "Главное меню"),
        types.BotCommand("profile", "Профиль"),
        types.BotCommand("parcels", "Мои посылки"),
        types.BotCommand("track", "Отследить трек"),
        types.BotCommand("addresses", "Наши адреса"),
        types.BotCommand("forbidden", "Запрещённые товары"),
        types.BotCommand("support", "Поддержка"),
    ]

    bot.set_my_commands(commands)

    try:
        bot.set_chat_menu_button(
            menu_button=types.MenuButtonCommands()
        )
    except Exception as error:
        print("MENU BUTTON ERROR:", error)


# =========================
# START / MENU
# =========================

@bot.message_handler(commands=["start", "menu"])
def start(message):
    text = (
        "👋 Добро пожаловать в ISHAK Cargo!\n\n"
        "🇨🇳 Доставка товаров из Китая в Кыргызстан 🇰🇬\n\n"
        "Выберите нужный раздел 👇"
    )

    bot.send_message(
        message.chat.id,
        text,
        reply_markup=main_menu()
    )


# =========================
# PROFILE
# =========================

def find_customer_by_telegram_id(telegram_id):
    rows = get_customers()

    result = []

    for row in rows:
        saved_id = str(row.get("Telegram ID", "")).strip()

        if saved_id == str(telegram_id):
            result.append(row)

    return result


def show_profile(message, found):
    customer = found[0]

    customer_name = customer.get("Аты-жөнү", "")
    customer_code = customer.get("Кардар коду", "")
    phone = customer.get("Телефон", "")
    kg_address = customer.get("Кыргызстандагы дареги", "")

    china_address = (
        "墨涵 18078825935 广东省佛山市南海区 "
        "里水镇草场海南州工业区98号KFC87启那科技园E104-1墨 "
        f"(ISHAK) {customer_code} ({phone})"
    )

    text = (
        "👤 ПРОФИЛЬ\n\n"
        f"👤 Аты-жөнү: {customer_name}\n"
        f"🆔 Кардар коду: {customer_code}\n"
        f"📱 Телефон: {phone}\n"
        f"📍 Алуу жери: {kg_address}\n\n"
        "🇨🇳 КЫТАЙДАГЫ СКЛАДДЫН ДАРЕГИ\n\n"
        f"{china_address}"
    )

    bot.send_message(
        message.chat.id,
        text,
        reply_markup=main_menu()
    )
@bot.message_handler(commands=["profile"])
@bot.message_handler(func=lambda message: message.text == "👤 Профиль")
def profile(message):
    try:
        found = find_customer_by_telegram_id(
            message.from_user.id
        )

        if found:
            show_profile(message, found)
            return

        msg = bot.send_message(
            message.chat.id,
            "👤 Ваш профиль пока не привязан к Telegram-аккаунту.\n\n"
            "Отправьте код клиента один раз.\n"
            "Например: K001",
            reply_markup=main_menu()
        )

        bot.register_next_step_handler(
            msg,
            profile_by_customer_code
        )

    except Exception as error:
        print("PROFILE ERROR:", error)
        bot.send_message(
            message.chat.id,
            "⚠️ Не удалось открыть профиль.",
            reply_markup=main_menu()
        )


def profile_by_customer_code(message):
    if message.text == "👤 Профиль":
        profile(message)
        return

    customer_code = message.text.strip().upper()

    try:
        rows = get_customers()
        found = []

        for row in rows:
            code = str(
                row.get("Кардар коду", "")
            ).strip().upper()

            if code == customer_code:
                found.append(row)

        if not found:
            bot.send_message(
                message.chat.id,
                f"❌ Клиент с кодом {customer_code} не найден.\n"
                "Проверьте код и попробуйте ещё раз.",
                reply_markup=main_menu()
            )
            return

        show_profile(message, found)

        bot.send_message(
            message.chat.id,
            "✅ Профиль успешно привязан к Telegram-аккаунту.",
            reply_markup=main_menu()
        )

    except Exception as error:
        print("PROFILE CODE ERROR:", error)
        bot.send_message(
            message.chat.id,
            "⚠️ Не удалось проверить код клиента.",
            reply_markup=main_menu()
        )        


# =========================
# MY PARCELS
# =========================

@bot.message_handler(
    commands=["parcels"]
)
@bot.message_handler(
    func=lambda message: message.text == "📦 Мои посылки"
)
def my_parcels(message):
    try:
        found = find_customer_by_telegram_id(
            message.from_user.id
        )

        if found:
            show_parcels(message, found)
            return

        msg = bot.send_message(
            message.chat.id,
            "📦 Кардар кодуңузду жибериңиз.\n\n"
            "Мисалы: K001"
        )

        bot.register_next_step_handler(
            msg,
            parcels_by_code
        )

    except Exception as error:
        print("PARCEL ERROR:", error)

        bot.send_message(
            message.chat.id,
            "⚠️ Маалымат алуу мүмкүн болгон жок.",
            reply_markup=main_menu()
        )


def parcels_by_code(message):
    customer_code = message.text.strip().upper()

    try:
        rows = get_products()

        found = []

        for row in rows:
            code = str(
                row.get("Кардар коду", "")
            ).strip().upper()

            if code == customer_code:
                found.append(row)

        if not found:
            bot.send_message(
                message.chat.id,
                f"❌ {customer_code} коду боюнча товар табылган жок.",
                reply_markup=main_menu()
            )
            return

        show_parcels(message, found)

    except Exception as error:
        print("PARCEL CODE ERROR:", error)

        bot.send_message(
            message.chat.id,
            "⚠️ Таблицадан маалымат алуу мүмкүн болгон жок.",
            reply_markup=main_menu()
        )


def show_parcels(message, found):
    customer_name = found[0].get("Кардардын аты", "")
    customer_code = found[0].get("Кардар коду", "")

    answer = (
        f"👤 Кардар: {customer_name}\n"
        f"🆔 Код: {customer_code}\n\n"
    )

    total_weight = 0

    for number, item in enumerate(found, 1):
        track = item.get("Трек-код", "")
        product = item.get("Товар", "")
        quantity = item.get("Саны", "")
        weight = item.get("Салмагы (кг)", "")
        status = item.get("Статус", "")
        received = item.get("Кардар алдыбы?", "")

        try:
            total_weight += float(
                str(weight).replace(",", ".")
            )
        except:
            pass

        answer += (
            f"📦 {number}. {product}\n"
            f"🔎 Трек-код: {track}\n"
            f"🔢 Саны: {quantity}\n"
            f"⚖️ Салмагы: {weight} кг\n"
            f"📍 Статус: {status}\n"
        )

        received_text = str(received).strip().lower()

        if received_text == "ооба":
            answer += "✅ Алынды\n"
        elif received_text == "жок":
            answer += "⏳ Берүүнү күтүп жатат\n"

        answer += "\n"

    answer += (
        f"📊 Жалпы товар: {len(found)}\n"
        f"⚖️ Жалпы салмак: {total_weight:.2f} кг"
    )

    bot.send_message(
        message.chat.id,
        answer,
        reply_markup=main_menu()
    )


# =========================
# TRACK
# =========================

@bot.message_handler(
    commands=["track"]
)
@bot.message_handler(
    func=lambda message: message.text == "🔎 Отследить трек"
)
def track_instruction(message):
    msg = bot.send_message(
        message.chat.id,
        "🔎 Товардын трек-кодун жибериңиз.\n\n"
        "Мисалы: TR123456"
    )

    bot.register_next_step_handler(
        msg,
        search_track
    )


def search_track(message):
    track_code = message.text.strip().upper()

    try:
        rows = get_products()

        found = []

        for row in rows:
            track = str(
                row.get("Трек-код", "")
            ).strip().upper()

            if track == track_code:
                found.append(row)

        if not found:
            bot.send_message(
                message.chat.id,
                f"❌ {track_code} трек-коду боюнча товар табылган жок.",
                reply_markup=main_menu()
            )
            return

        row = found[0]

        customer_code = row.get("Кардар коду", "")
        product = row.get("Товар", "")
        quantity = row.get("Саны", "")
        weight = row.get("Салмагы (кг)", "")
        status = row.get("Статус", "")
        received = row.get("Кардар алдыбы?", "")

        answer = (
            "📦 Товар тууралуу маалымат\n\n"
            f"🔎 Трек-код: {track_code}\n"
            f"🆔 Кардар коду: {customer_code}\n"
            f"📦 Товар: {product}\n"
            f"🔢 Саны: {quantity}\n"
            f"⚖️ Салмагы: {weight} кг\n"
            f"📍 Статус: {status}\n"
        )

        received_text = str(received).strip().lower()

        if received_text == "ооба":
            answer += "✅ Кардар алып кетти\n"
        elif received_text == "жок":
            answer += "⏳ Берүүнү күтүп жатат\n"

        bot.send_message(
            message.chat.id,
            answer,
            reply_markup=main_menu()
        )

    except Exception as error:
        print("TRACK ERROR:", error)

        bot.send_message(
            message.chat.id,
            "⚠️ Таблицадан маалымат алуу мүмкүн болгон жок.",
            reply_markup=main_menu()
        )


# =========================
# ADDRESSES
# =========================

@bot.message_handler(
    commands=["addresses"]
)
@bot.message_handler(
    func=lambda message: message.text == "📍 Наши адреса"
)
def addresses(message):
    text = (
        "📍 НАШИ АДРЕСА\n\n"
        "🏢 Бишкек\n"
        "Склад ISHAK Cargo\n\n"
        "🏢 Ала-Бука району\n"
        "Склад ISHAK Cargo"
    )

    bot.send_message(
        message.chat.id,
        text,
        reply_markup=main_menu()
    )


# =========================
# FORBIDDEN PRODUCTS
# =========================

@bot.message_handler(
    commands=["forbidden"]
)
@bot.message_handler(
    func=lambda message: message.text == "🚫 Запрещённые товары"
)
def prohibited(message):
    text = (
        "🚫 ЗАПРЕЩЁННЫЕ ТОВАРЫ\n\n"
        "❌ Компьютеры\n"
        "❌ Мобильные телефоны\n"
        "❌ Лекарства\n"
        "❌ Военные товары\n"
        "❌ Камуфляж\n\n"
        "Перед заказом сомнительного товара "
        "уточните возможность доставки."
    )

    bot.send_message(
        message.chat.id,
        text,
        reply_markup=main_menu()
    )


# =========================
# SUPPORT
# =========================

@bot.message_handler(
    commands=["support"]
)
@bot.message_handler(
    func=lambda message: message.text == "☎️ Поддержка"
)
def support(message):
    bot.send_message(
        message.chat.id,
        "☎️ Поддержка ISHAK Cargo\n\n"
        "По всем вопросам напишите нам.",
        reply_markup=main_menu()
    )


# =========================
# OTHER MESSAGES
# =========================

@bot.message_handler(func=lambda message: True)
def other_messages(message):
    bot.send_message(
        message.chat.id,
        "☰ Нужный разделды менюдан тандаңыз 👇",
        reply_markup=main_menu()
    )


# =========================
# START BOT
# =========================

setup_commands()

print("ISHAK Cargo bot работает...")

bot.infinity_polling(skip_pending=True)
