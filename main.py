import os
import telebot

TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "Салам! 👋\n"
        "ISHAK Cargo ботко кош келиңиз!\n\n"
        "Кодду жибериңиз."
    )

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    code = message.text.strip()
    bot.reply_to(
        message,
        f"Кодуңуз кабыл алынды: {code}\n\n"
        "Товар келгенде ушул код аркылуу текшеребиз."
    )

print("ISHAK Cargo bot иштеп жатат...")
bot.infinity_polling()
