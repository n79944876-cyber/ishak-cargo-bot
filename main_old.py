import os
import csv
import io
import json
import threading
import requests
import telebot
from telebot import types

# =========================
# SETTINGS
# =========================

TOKEN = os.getenv("BOT_TOKEN")

SHEET_ID = "1RlRU8VG-mqxsqtswXReeORcg-MOeeynzg-4wby5OpFU"
PRODUCTS_SHEET = "Товарлар"
CUSTOMERS_SHEET = "Кардарлар"

PHONE = "+996 556 050 995"
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
DATA_FILE = "bot_data.json"

if not TOKEN:
    raise RuntimeError("BOT_TOKEN табылган жок / BOT_TOKEN не найден")

bot = telebot.TeleBot(TOKEN)
data_lock = threading.Lock()


# =========================
# LOCAL DATA
# =========================
# Бул файл кардардын тилин жана Telegram ↔ кардар код байланышын сактайт.
# Railway кайра deploy болгондо файл өчүп калышы мүмкүн.
# Эгер кийин Google Sheets'ке түз жаздыруу кошулса, бул байланыш андан да туруктуу болот.

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"languages": {}, "bindings": {}, "channel_id": ""}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("languages", {})
        data.setdefault("bindings", {})
        data.setdefault("channel_id", "")
        return data
    except Exception:
        return {"languages": {}, "bindings": {}, "channel_id": ""}


BOT_DATA = load_data()


def save_data():
    with data_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(BOT_DATA, f, ensure_ascii=False, indent=2)


def get_lang(message):
    return BOT_DATA["languages"].get(str(message.from_user.id), "kg")


def set_lang(user_id, lang):
    BOT_DATA["languages"][str(user_id)] = lang
    save_data()


def get_bound_code(user_id):
    return BOT_DATA["bindings"].get(str(user_id), "")


def bind_code(user_id, customer_code):
    BOT_DATA["bindings"][str(user_id)] = customer_code
    save_data()


def get_channel_target():
    # Railway'деги CHANNEL_ID болсо ошону колдонот; болбосо бот өзү каналдан үйрөнгөн IDни алат.
    return CHANNEL_ID or str(BOT_DATA.get("channel_id", "")).strip()


def save_channel_id(channel_id):
    BOT_DATA["channel_id"] = str(channel_id)
    save_data()


def bound_to_other_user(customer_code, current_user_id):
    for uid, code in BOT_DATA["bindings"].items():
        if code == customer_code and uid != str(current_user_id):
            return True
    return False


# =========================
# GOOGLE SHEETS READ
# =========================

def read_sheet(sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq"
    response = requests.get(
        url,
        params={"tqx": "out:csv", "sheet": sheet_name},
        timeout=20
    )
    response.raise_for_status()
    text = response.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def get_products():
    return read_sheet(PRODUCTS_SHEET)


def get_customers():
    return read_sheet(CUSTOMERS_SHEET)


def cell(row, *names):
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def customer_by_code(code):
    code = (code or "").strip().upper()
    for row in get_customers():
        row_code = cell(row, "Кардар коду").upper()
        if row_code == code:
            return row
    return None


def customer_by_telegram_id(user_id):
    uid = str(user_id).strip()

    # 1) Алгач таблицадагы Telegram ID каралат
    for row in get_customers():
        saved = cell(row, "Telegram ID", "TelegramID", "Telegram id")
        if saved == uid:
            return row

    # 2) Андан кийин боттун бир жолку байланышы каралат
    code = get_bound_code(user_id)
    if code:
        return customer_by_code(code)

    return None


def bot_allowed(customer):
    value = cell(customer, "Ботко уруксат").lower()
    if not value:
        return True
    return value in {"ооба", "да", "yes", "1", "true"}


# =========================
# TEXTS
# =========================

TEXTS = {
    "kg": {
        "profile": "👤 Профиль",
        "parcels": "📦 Менин посылкаларым",
        "track": "🔎 Тректи текшерүү",
        "addresses": "📍 Биздин даректер",
        "forbidden": "🚫 Тыюу салынган товарлар",
        "support": "☎️ Колдоо",
        "language": "🌐 Тилди өзгөртүү",
        "welcome": "👋 ISHAK Cargo'го кош келиңиз!\n\n🇨🇳 Кытайдан Кыргызстанга товар жеткирүү 🇰🇬\n\nКеректүү бөлүмдү тандаңыз 👇",
    },
    "ru": {
        "profile": "👤 Профиль",
        "parcels": "📦 Мои посылки",
        "track": "🔎 Отследить трек",
        "addresses": "📍 Наши адреса",
        "forbidden": "🚫 Запрещённые товары",
        "support": "☎️ Поддержка",
        "language": "🌐 Изменить язык",
        "welcome": "👋 Добро пожаловать в ISHAK Cargo!\n\n🇨🇳 Доставка товаров из Китая в Кыргызстан 🇰🇬\n\nВыберите нужный раздел 👇",
    }
}


STATUS_RU = {
    "Кытайдан чыкты": "Выехал из Китая",
    "Жолго чыкты": "Выехал из Китая",
    "Кыргызстанга келди": "Прибыл в Кыргызстан",
    "Кардар алды": "Клиент получил",
}

STATUS_KG = {
    "Кытайдан чыкты": "Кытайдан чыкты",
    "Жолго чыкты": "Кытайдан чыкты",
    "Кыргызстанга келди": "Кыргызстанга келди",
    "Кардар алды": "Кардар алды",
}


def status_for_lang(status, lang):
    status = (status or "").strip()
    if lang == "ru":
        return STATUS_RU.get(status, status or "Не указан")
    return STATUS_KG.get(status, status or "Көрсөтүлгөн эмес")


# =========================
# KEYBOARDS
# =========================

def language_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.row(
        types.KeyboardButton("🇰🇬 Кыргызча"),
        types.KeyboardButton("🇷🇺 Русский")
    )
    return kb


def main_menu(lang):
    t = TEXTS[lang]
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        is_persistent=True,
        row_width=2
    )
    kb.row(
        types.KeyboardButton(t["profile"]),
        types.KeyboardButton(t["parcels"])
    )
    kb.row(
        types.KeyboardButton(t["track"]),
        types.KeyboardButton(t["addresses"])
    )
    kb.row(
        types.KeyboardButton(t["forbidden"]),
        types.KeyboardButton(t["support"])
    )
    kb.row(types.KeyboardButton(t["language"]))
    return kb


# =========================
# START / LANGUAGE
# =========================

@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "🌐 Тилди тандаңыз / Выберите язык",
        reply_markup=language_keyboard()
    )


@bot.message_handler(func=lambda m: m.text in ["🇰🇬 Кыргызча", "🇷🇺 Русский"])
def choose_language(message):
    lang = "kg" if message.text == "🇰🇬 Кыргызча" else "ru"
    set_lang(message.from_user.id, lang)
    bot.send_message(
        message.chat.id,
        TEXTS[lang]["welcome"],
        reply_markup=main_menu(lang)
    )


@bot.message_handler(commands=["menu"])
def menu_command(message):
    lang = get_lang(message)
    bot.send_message(
        message.chat.id,
        TEXTS[lang]["welcome"],
        reply_markup=main_menu(lang)
    )


@bot.message_handler(func=lambda m: m.text in ["🌐 Тилди өзгөртүү", "🌐 Изменить язык"])
def change_language(message):
    bot.send_message(
        message.chat.id,
        "🌐 Тилди тандаңыз / Выберите язык",
        reply_markup=language_keyboard()
    )


# =========================
# PROFILE + ONE-TIME CODE
# =========================

def show_profile(message, customer):
    lang = get_lang(message)

    name = cell(customer, "Аты-жөнү")
    code = cell(customer, "Кардар коду")
    phone = cell(customer, "Телефон", "Телефон-")
    address = cell(customer, "Кыргызстандагы дареги")

    china_address = (
        "墨涵 18078825935 广东省佛山市南海区 "
        "里水镇草场海南州工业区98号KFC87启那科技园E104-1墨 "
        f"(ISHAK) {code} ({phone})"
    )

    if lang == "ru":
        text = (
            "👤 ПРОФИЛЬ\n\n"
            f"👤 Имя: {name}\n"
            f"🆔 Код клиента: {code}\n"
            f"📱 Телефон: {phone}\n"
            f"📍 Пункт получения: {address}\n\n"
            "🇨🇳 АДРЕС СКЛАДА В КИТАЕ\n\n"
            f"{china_address}"
        )
    else:
        text = (
            "👤 ПРОФИЛЬ\n\n"
            f"👤 Аты-жөнү: {name}\n"
            f"🆔 Кардар коду: {code}\n"
            f"📱 Телефон: {phone}\n"
            f"📍 Алуу жери: {address}\n\n"
            "🇨🇳 КЫТАЙДАГЫ СКЛАДДЫН ДАРЕГИ\n\n"
            f"{china_address}"
        )

    bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))


@bot.message_handler(func=lambda m: m.text in ["👤 Профиль"])
def profile(message):
    lang = get_lang(message)
    try:
        customer = customer_by_telegram_id(message.from_user.id)

        if customer:
            if not bot_allowed(customer):
                text = "⛔ Ботко кирүүгө уруксат жок." if lang == "kg" else "⛔ Доступ к боту запрещён."
                bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))
                return
            show_profile(message, customer)
            return

        prompt = (
            "👤 Профилиңиз Telegram аккаунтуна байланыша элек.\n\n"
            "Кардар кодуңузду БИР ЖОЛУ жибериңиз.\n"
            "Мисалы: K001"
            if lang == "kg" else
            "👤 Ваш профиль пока не привязан к Telegram-аккаунту.\n\n"
            "Отправьте код клиента ОДИН РАЗ.\n"
            "Например: K001"
        )

        msg = bot.send_message(message.chat.id, prompt, reply_markup=main_menu(lang))
        bot.register_next_step_handler(msg, profile_by_customer_code)

    except Exception as e:
        print("PROFILE ERROR:", e)
        text = "⚠️ Профилди ачуу мүмкүн болгон жок." if lang == "kg" else "⚠️ Не удалось открыть профиль."
        bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))


def profile_by_customer_code(message):
    lang = get_lang(message)
    customer_code = (message.text or "").strip().upper()

    try:
        customer = customer_by_code(customer_code)

        if not customer:
            text = (
                f"❌ {customer_code} коду менен кардар табылган жок."
                if lang == "kg"
                else f"❌ Клиент с кодом {customer_code} не найден."
            )
            bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))
            return

        if not bot_allowed(customer):
            text = "⛔ Ботко кирүүгө уруксат жок." if lang == "kg" else "⛔ Доступ к боту запрещён."
            bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))
            return

        sheet_tid = cell(customer, "Telegram ID", "TelegramID", "Telegram id")
        if sheet_tid and sheet_tid != str(message.from_user.id):
            text = (
                "⛔ Бул кардар коду башка Telegram аккаунтуна байланыштырылган."
                if lang == "kg"
                else "⛔ Этот код клиента уже привязан к другому Telegram-аккаунту."
            )
            bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))
            return

        if bound_to_other_user(customer_code, message.from_user.id):
            text = (
                "⛔ Бул кардар коду башка Telegram аккаунтуна байланыштырылган."
                if lang == "kg"
                else "⛔ Этот код клиента уже привязан к другому Telegram-аккаунту."
            )
            bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))
            return

        # Кардар кодун бир жолу гана киргизет.
        bind_code(message.from_user.id, customer_code)

        show_profile(message, customer)

        text = (
            "✅ Профиль Telegram аккаунтуна байланыштырылды.\nЭми кардар кодун кайра киргизбейсиз."
            if lang == "kg"
            else "✅ Профиль привязан к Telegram-аккаунту.\nТеперь код клиента повторно вводить не нужно."
        )
        bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))

    except Exception as e:
        print("PROFILE CODE ERROR:", e)
        text = "⚠️ Кардар кодун текшерүү мүмкүн болгон жок." if lang == "kg" else "⚠️ Не удалось проверить код клиента."
        bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))


# =========================
# PARCELS
# =========================

def products_for_code(customer_code):
    result = []
    code = customer_code.strip().upper()
    for row in get_products():
        row_code = cell(row, "Кардар коду").upper()
        if row_code == code:
            result.append(row)
    return result


def _parse_number(value):
    """Google Sheets'тен келген санды коопсуз float кылып окуйт."""
    s = str(value or "").strip().replace("\xa0", "").replace(" ", "")
    if not s:
        return None

    try:
        # 1 312,50 / 1,312.50 / 1312,50 / 1312.50 форматтарын колдойт
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s:
            s = s.replace(",", ".")
        return float(s)
    except Exception:
        return None


def format_som(value):
    number = _parse_number(value)
    if number is None:
        return str(value).strip() if str(value or "").strip() else "—"
    return f"{number:,.2f}".replace(",", " ").replace(".", ",")


def show_parcels(message, customer):
    lang = get_lang(message)
    customer_code = cell(customer, "Кардар коду")
    name = cell(customer, "Аты-жөнү")
    rows = products_for_code(customer_code)

    if not rows:
        text = (
            "📦 Азырынча сиздин посылкаңыз табылган жок."
            if lang == "kg"
            else "📦 Пока посылки по вашему коду не найдены."
        )
        bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))
        return

    parts = []
    total_weight = 0.0

    for i, row in enumerate(rows, 1):
        track = cell(row, "Трек-номер", "Трек-код")
        qty = cell(row, "Саны")
        weight = cell(row, "Салмагы (кг)", "Салмагы(кг)")
        payment_som = cell(
            row,
            "Кардар төлөмү (сом)",
            "Кардар төлөмү(сом)",
            "Сумма (сом)",
            "Суммасы (сом)",
            "Төлөм (сом)"
        )
        status = status_for_lang(cell(row, "Статус"), lang)

        weight_number = _parse_number(weight)
        if weight_number is not None:
            total_weight += weight_number

        payment_text = format_som(payment_som)

        if lang == "ru":
            parts.append(
                f"📦 {i}.\n"
                f"🔎 Трек-код: {track or '—'}\n"
                f"🔢 Количество: {qty or '—'}\n"
                f"⚖️ Вес: {weight or '—'} кг\n"
                f"💰 Сумма: {payment_text} сом\n"
                f"📍 Статус: {status}"
            )
        else:
            parts.append(
                f"📦 {i}.\n"
                f"🔎 Трек-код: {track or '—'}\n"
                f"🔢 Саны: {qty or '—'}\n"
                f"⚖️ Салмагы: {weight or '—'} кг\n"
                f"💰 Суммасы: {payment_text} сом\n"
                f"📍 Статус: {status}"
            )

    if lang == "ru":
        header = f"👤 Клиент: {name}\n🆔 Код: {customer_code}\n\n"
        footer = f"\n\n📊 Всего позиций: {len(rows)}\n⚖️ Общий вес: {total_weight:.2f} кг"
    else:
        header = f"👤 Кардар: {name}\n🆔 Код: {customer_code}\n\n"
        footer = f"\n\n📊 Жалпы позиция: {len(rows)}\n⚖️ Жалпы салмак: {total_weight:.2f} кг"

    bot.send_message(
        message.chat.id,
        header + "\n\n".join(parts) + footer,
        reply_markup=main_menu(lang)
    )


@bot.message_handler(func=lambda m: m.text in ["📦 Менин посылкаларым", "📦 Мои посылки"])
def my_parcels(message):
    lang = get_lang(message)
    try:
        customer = customer_by_telegram_id(message.from_user.id)

        if not customer:
            text = (
                "👤 Адегенде «Профиль» бөлүмүнө кирип, кардар кодуңузду бир жолу жибериңиз."
                if lang == "kg"
                else "👤 Сначала откройте «Профиль» и один раз отправьте код клиента."
            )
            bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))
            return

        show_parcels(message, customer)

    except Exception as e:
        print("PARCELS ERROR:", e)
        text = "⚠️ Маалымат алуу мүмкүн болгон жок." if lang == "kg" else "⚠️ Не удалось получить информацию."
        bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))


# =========================
# TRACK
# =========================

@bot.message_handler(func=lambda m: m.text in ["🔎 Тректи текшерүү", "🔎 Отследить трек"])
def track_request(message):
    lang = get_lang(message)
    prompt = (
        "🔎 Товардын трек-кодун жибериңиз.\n\nМисалы: TR123456"
        if lang == "kg"
        else "🔎 Отправьте трек-код товара.\n\nНапример: TR123456"
    )
    msg = bot.send_message(message.chat.id, prompt)
    bot.register_next_step_handler(msg, track_lookup)


def track_lookup(message):
    lang = get_lang(message)
    track = (message.text or "").strip().upper()

    try:
        found = None
        for row in get_products():
            row_track = cell(row, "Трек-номер", "Трек-код").upper()
            if row_track == track:
                found = row
                break

        if not found:
            text = (
                f"❌ {track} трек-коду боюнча товар табылган жок."
                if lang == "kg"
                else f"❌ Товар по трек-коду {track} не найден."
            )
            bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))
            return

        status = status_for_lang(cell(found, "Статус"), lang)

        # «Товар» деген сап көрсөтүлбөйт — трек жана статус гана.
        text = f"🔎 Трек-код: {track}\n📍 Статус: {status}"

        bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))

    except Exception as e:
        print("TRACK ERROR:", e)
        text = "⚠️ Трек-кодду текшерүү мүмкүн болгон жок." if lang == "kg" else "⚠️ Не удалось проверить трек-код."
        bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))


# =========================
# ADDRESSES
# =========================

@bot.message_handler(func=lambda m: m.text in ["📍 Биздин даректер", "📍 Наши адреса"])
def addresses(message):
    lang = get_lang(message)

    if lang == "ru":
        text = (
            "📍 НАШИ АДРЕСА\n\n"
            "🏢 Бишкек\n"
            "Склад ISHAK Cargo\n"
            f"📞 {PHONE}\n\n"
            "🏢 Ала-Бука район\n"
            "Склад ISHAK Cargo\n"
            f"📞 {PHONE}"
        )
    else:
        text = (
            "📍 БИЗДИН ДАРЕКТЕР\n\n"
            "🏢 Бишкек\n"
            "ISHAK Cargo склады\n"
            f"📞 {PHONE}\n\n"
            "🏢 Ала-Бука району\n"
            "ISHAK Cargo склады\n"
            f"📞 {PHONE}"
        )

    bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))


# =========================
# FORBIDDEN
# =========================

@bot.message_handler(func=lambda m: m.text in ["🚫 Тыюу салынган товарлар", "🚫 Запрещённые товары"])
def forbidden(message):
    lang = get_lang(message)

    if lang == "ru":
        text = (
            "🚫 ЗАПРЕЩЁННЫЕ ТОВАРЫ\n\n"
            "❌ Компьютеры\n"
            "❌ Мобильные телефоны\n"
            "❌ Лекарства\n"
            "❌ Военные товары\n"
            "❌ Камуфляж\n\n"
            "Перед заказом сомнительного товара уточните возможность доставки."
        )
    else:
        text = (
            "🚫 ТЫЮУ САЛЫНГАН ТОВАРЛАР\n\n"
            "❌ Компьютерлер\n"
            "❌ Мобилдик телефондор\n"
            "❌ Дары-дармектер\n"
            "❌ Аскердик товарлар\n"
            "❌ Камуфляж\n\n"
            "Шектүү товарга заказ берерден мурун жеткирүү мүмкүнчүлүгүн тактаңыз."
        )

    bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))


# =========================
# SUPPORT
# =========================

@bot.message_handler(func=lambda m: m.text in ["☎️ Колдоо", "☎️ Поддержка"])
def support(message):
    lang = get_lang(message)

    if lang == "ru":
        text = f"☎️ Поддержка ISHAK Cargo\n\nПо всем вопросам пишите или звоните нам.\n📞 {PHONE}"
    else:
        text = f"☎️ ISHAK Cargo колдоо кызматы\n\nБардык суроолор боюнча бизге кайрылыңыз.\n📞 {PHONE}"

    bot.send_message(message.chat.id, text, reply_markup=main_menu(lang))



# =========================
# CHANNEL AUTO-LINK
# =========================

@bot.channel_post_handler(func=lambda m: True)
def learn_channel_id(message):
    try:
        current = get_channel_target()
        if not current:
            save_channel_id(message.chat.id)
            print(f"CHANNEL LINKED: {message.chat.id} / {getattr(message.chat, 'title', '')}")
            bot.send_message(
                message.chat.id,
                "✅ ISHAK CARGO бот каналга байланышты. Автоматтык билдирүү даяр."
            )
    except Exception as e:
        print("CHANNEL LINK ERROR:", e)


# =========================
# TELEGRAM CHANNEL AUTO POST
# =========================
# Каналга кг/сумма чыкпайт. Статус "Кыргызстанга келди" болгондо
# кардар коду + трек-код автоматтык түрдө бир топтом билдирүү болуп жөнөтүлөт.
# Жабык канал да болот: бот каналга админ болуп кошулгандан кийин биринчи тест посттон IDни өзү сактап алат.

ARRIVED_STATUS = "Кыргызстанга келди"
_channel_seen = set()
_channel_ready = False


def _channel_key(row):
    code = cell(row, "Кардар коду").upper()
    track = cell(row, "Трек-номер", "Трек-код").upper()
    if not code or not track:
        return None
    return f"{code}|{track}"


def _send_channel_batch(rows):
    target = get_channel_target()
    if not target or not rows:
        return

    grouped = {}
    for row in rows:
        code = cell(row, "Кардар коду").upper()
        track = cell(row, "Трек-номер", "Трек-код")
        if not code or not track:
            continue
        grouped.setdefault(code, []).append(track)

    if not grouped:
        return

    blocks = ["📦 ISHAK CARGO", "📍 Кыргызстанга келди / Прибыло в Кыргызстан", ""]
    for code, tracks in grouped.items():
        blocks.append(f"🆔 Код клиента: {code}")
        blocks.extend(f"🔎 {track}" for track in tracks)
        blocks.append("")

    text = "\n".join(blocks).strip()

    # Telegram билдирүүсүнүн лимитине жетпеш үчүн чоң постту бөлүп жөнөтөбүз.
    max_len = 3900
    if len(text) <= max_len:
        bot.send_message(target, text)
        return

    current = ""
    for line in text.splitlines():
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > max_len:
            if current:
                bot.send_message(target, current)
            current = line
        else:
            current = candidate
    if current:
        bot.send_message(target, current)


def channel_watcher():
    global _channel_ready

    while True:
        try:
            target = get_channel_target()
            if not target:
                print("CHANNEL: канал ID азырынча табыла элек — ботту каналга админ кылып, бир тест пост жазыңыз")
                threading.Event().wait(15)
                continue

            rows = get_products()
            current_arrived = set()
            newly_arrived = []

            for row in rows:
                key = _channel_key(row)
                if not key:
                    continue

                status = cell(row, "Статус")
                if status == ARRIVED_STATUS:
                    current_arrived.add(key)
                    if _channel_ready and key not in _channel_seen:
                        newly_arrived.append(row)

            # Биринчи окууда эски товарларды каналга кайра жибербейбиз.
            if not _channel_ready:
                _channel_seen.update(current_arrived)
                _channel_ready = True
                print(f"CHANNEL WATCHER READY: {len(current_arrived)} existing arrivals skipped")
            else:
                if newly_arrived:
                    _send_channel_batch(newly_arrived)
                    for row in newly_arrived:
                        key = _channel_key(row)
                        if key:
                            _channel_seen.add(key)
                    print(f"CHANNEL POSTED: {len(newly_arrived)} new arrivals")

            # Кардар алган же башка статус болуп калган товарларды seen ичинде калтырабыз,
            # ошентип бир эле трек кайра-кайра каналга чыкпайт.

        except Exception as e:
            print("CHANNEL WATCHER ERROR:", e)

        # Google таблицаны ар 60 секунд сайын текшерет.
        threading.Event().wait(60)

# =========================
# COMMANDS
# =========================

def setup_commands():
    try:
        bot.set_my_commands([
            types.BotCommand("start", "Запустить / Баштоо"),
            types.BotCommand("menu", "Меню"),
        ])
    except Exception as e:
        print("COMMAND ERROR:", e)


if __name__ == "__main__":
    setup_commands()

    # Каналга автоматтык билдирүү үчүн өзүнчө фондук текшерүү.
    watcher = threading.Thread(target=channel_watcher, daemon=True)
    watcher.start()

    print("ISHAK Cargo bot started")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
