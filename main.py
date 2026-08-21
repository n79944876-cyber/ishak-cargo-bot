import os
import csv
import io
import requests
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")

SHEET_ID = "1xxG-pE2lsLsCp3VPFWwA-ZokeVZd_3xS"
SHEET_NAME = "Товарлар"

bot = telebot.TeleBot(TOKEN)


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


def main_menu():
    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )

    markup.add(
        types.KeyboardButton("👤 Профиль"),
        types.KeyboardButton("📦 Мои посылки")
    )

    markup.add(
        types.KeyboardButton("🔎 Отследить трек"),
        types.KeyboardButton("📍 Наши адреса")
    )

    markup.add(
        types.KeyboardButton("🚫 Запрещённые товары"),
        types.KeyboardButton("☎️ Поддержка")
    )

    return markup


@bot.message_handler(commands=["start"])
def start(message):
    text = (
        "👋 Добро пожаловать в ISHAK Cargo!\n\n"
        "Доставка товаров из Китая в Кыргызстан 🇨🇳➡️🇰🇬\n\n"
        "Выберите нужный раздел:"
    )

    bot.send_message(
        message.chat.id,
        text,
        reply_markup=main_menu()
    )


@bot.message_handler(func=lambda message: message.text == "👤 Профиль")
def profile(message):
    bot.send_message(
        message.chat.id,
        "👤 Профиль\n\n"
        "Чтобы посмотреть свои товары, "
        "отправьте свой код клиента.\n\n"
        "Пример: K001"
    )


@bot.message_handler(func=lambda message: message.text == "📍 Наши адреса")
def addresses(message):
    text = (
        "📍 Наши адреса\n\n"
        "🏢 Бишкек\n"
        "Склад ISHAK Cargo\n\n"
        "🏢 Ала-Бука район\n"
        "Склад ISHAK Cargo"
    )

    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda message: message.text == "🚫 Запрещённые товары")
def prohibited(message):
    text = (
        "🚫 Запрещённые товары\n\n"
        "❌ Компьютеры\n"
        "❌ Мобильные телефоны\n"
        "❌ Лекарства\n"
        "❌ Военные товары\n"
        "❌ Камуфляж\n\n"
        "Перед заказом сомнительного товара "
        "уточните у нас возможность доставки."
    )

    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda message: message.text == "☎️ Поддержка")
def support(message):
    bot.send_message(
        message.chat.id,
        "☎️ Поддержка ISHAK Cargo\n\n"
        "По всем вопросам напишите нам."
    )


@bot.message_handler(func=lambda message: message.text == "🔎 Отследить трек")
def track_instruction(message):
    msg = bot.send_message(
        message.chat.id,
        "🔎 Отправьте трек-код товара.\n\n"
        "Пример: TR123456"
    )

    bot.register_next_step_handler(msg, search_track)


def search_track(message):
    track_code = message.text.strip().upper()

    try:
        rows = get_products()

        found = []

        for row in rows:
            track = str(row.get("Трек-код", "")).strip().upper()

            if track == track_code:
                found.append(row)

        if not found:
            bot.send_message(
                message.chat.id,
                f"❌ Товар с трек-кодом {track_code} не найден.",
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
            "📦 Информация о товаре\n\n"
            f"🔎 Трек-код: {track_code}\n"
            f"🆔 Код клиента: {customer_code}\n"
            f"📦 Товар: {product}\n"
            f"🔢 Количество: {quantity}\n"
            f"⚖️ Вес: {weight} кг\n"
            f"📍 Статус: {status}\n"
        )

        if received.strip().lower() == "ооба":
            answer += "✅ Товар получен клиентом\n"
        elif received.strip().lower() == "жок":
            answer += "📦 Товар ожидает выдачи\n"

        bot.send_message(
            message.chat.id,
            answer,
            reply_markup=main_menu()
        )

    except Exception as error:
        print("TRACK ERROR:", error)
        bot.send_message(
            message.chat.id,
            "⚠️ Не удалось получить информацию из таблицы.",
            reply_markup=main_menu()
        )


@bot.message_handler(func=lambda message: message.text == "📦 Мои посылки")
def my_packages_instruction(message):
    msg = bot.send_message(
        message.chat.id,
        "📦 Отправьте свой код клиента.\n\nПример: K001"
    )
    bot.register_next_step_handler(msg, search_customer)


def search_customer(message):
    customer_code = message.text.strip().upper()

    try:
        rows = get_products()
        found = []

        for row in rows:
            code = str(row.get("Кардар коду", "")).strip().upper()
            if code == customer_code:
                found.append(row)

        if not found:
            bot.send_message(
                message.chat.id,
                f"❌ По коду {customer_code} товары не найдены.",
                reply_markup=main_menu()
            )
            return

        customer_name = found[0].get("Кардардын аты", "")

        answer = (
            f"👤 Клиент: {customer_name}\n"
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
                total_weight += float(str(weight).replace(",", "."))
            except:
                pass

            answer += (
                f"📦 {number}. {product}\n"
                f"🔎 Трек-код: {track}\n"
                f"🔢 Количество: {quantity}\n"
                f"⚖️ Вес: {weight} кг\n"
                f"📍 Статус: {status}\n"
            )

            if received.strip().lower() == "ооба":
                answer += "✅ Получено\n"
            elif received.strip().lower() == "жок":
                answer += "⏳ Ожидает выдачи\n"

            answer += "\n"

        answer += (
            f"📊 Всего товаров: {len(found)}\n"
            f"⚖️ Общий вес: {total_weight:.2f} кг"
        )

        bot.send_message(
            message.chat.id,
            answer,
            reply_markup=main_menu()
        )

    except Exception as error:
        print("CUSTOMER ERROR:", error)
        bot.send_message(
            message.chat.id,
            "⚠️ Не удалось получить данные из таблицы.",
            reply_markup=main_menu()
        )


@bot.message_handler(func=lambda message: True)
def other_messages(message):
    text = message.text.strip().upper()

    if text.startswith("K"):
        search_customer(message)
        return

    bot.send_message(
        message.chat.id,
        "Выберите нужный раздел в меню 👇",
        reply_markup=main_menu()
    )


print("ISHAK Cargo bot работает...")
bot.infinity_polling(skip_pending=True)        
