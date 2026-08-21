import os
import csv
import io
import requests
import telebot

TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = "1xxG-pE2lsLsCp3VPFWwA-ZokeVZd_3xS"

SHEET_NAME = "Товарлар"

bot = telebot.TeleBot(TOKEN)

def get_products():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq"
    response = requests.get(
        url,
        params={"tqx": "out:csv", "sheet": SHEET_NAME},
        timeout=20
    )
    response.raise_for_status()
    return list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))

@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "Салам! 👋\n"
        "ISHAK Cargo ботко кош келиңиз!\n\n"
        "Кардар кодуңузду жибериңиз.\n"
        "Мисалы: K001"
    )

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    code = message.text.strip().upper()

    try:
        rows = get_products()
        found = []

        for row in rows:
            customer_code = str(row.get("Кардар коду", "")).strip().upper()
            if customer_code == code:
                found.append(row)

        if not found:
            bot.reply_to(message, f"❌ {code} коду боюнча товар табылган жок.")
            return

        customer_name = found[0].get("Кардардын аты", "")

        answer = f"👤 Кардар: {customer_name}\n🆔 Код: {code}\n\n"
        total_weight = 0

        for i, item in enumerate(found, 1):
            track = item.get("Трек-номер", "")
            product = item.get("Товар", "")
            quantity = item.get("Саны", "")
            weight = item.get("Салмагы (кг)", "")
            status = item.get("Статус", "")

            try:
                total_weight += float(str(weight).replace(",", "."))
            except:
                pass

            answer += (
                f"📦 {i}. {product}\n"
                f"Трек-номер: {track}\n"
                f"Саны: {quantity}\n"
                f"Салмагы: {weight} кг\n"
                f"Статус: {status}\n\n"
            )

        answer += (
            f"📊 Жалпы посылка: {len(found)}\n"
            f"⚖️ Жалпы салмак: {total_weight:.2f} кг"
        )

        bot.reply_to(message, answer)

    except Exception as error:
        print("ERROR:", error)
        bot.reply_to(message, "⚠️ Таблицадан маалымат алуу мүмкүн болгон жок.")

print("ISHAK Cargo bot иштеп жатат...")
bot.infinity_polling(skip_pending=True)
