import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


# Укажи свой личный Telegram username без @.
# Например, если профиль @alex123, напиши: ADMIN_USERNAME = "alex123"
ADMIN_USERNAME = "Vizs2"

# Контакты по направлениям и поддержка
ADS_USERNAME = "sniskersik"
SITE_USERNAME = "Vizs2"
BOT_USERNAME = "Vizs22"
SUPPORT_USERNAME = "ASFSUPP"

# Цены можно менять отдельно для каждого варианта.
WARM_PRICES = {"1000": "40 TON", "5000": "45 TON", "10000": "50 TON"}
COLD_PRICE = "35 TON"
ORDER_COOLDOWN_SECONDS = 60
MESSAGE_COOLDOWN_SECONDS = 2
MINI_APP_URL = "https://cat277.github.io/qqq/miniapp.html"

# Токен можно один раз записать в bot_token.txt рядом с этим файлом.
TOKEN_FILE = Path(__file__).with_name("bot_token.txt")
TOKEN = os.environ.get("BOT_TOKEN", "").strip()
if not TOKEN:
    try:
        TOKEN = TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        TOKEN = ""

if not TOKEN:
    raise SystemExit('Токен не найден. Запиши его один раз в файл bot_token.txt рядом с bot.py.')

if not ADMIN_USERNAME or ADMIN_USERNAME == "ВПИШИ_СВОЙ_USERNAME":
    raise SystemExit('Замени ADMIN_USERNAME на свой Telegram username без @.')

API = f"https://api.telegram.org/bot{TOKEN}/"
ADMIN_ID_FILE = Path.home() / ".telegram_shop_admin_chat_id"


def load_admin_chat_id():
    try:
        return int(ADMIN_ID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


ADMIN_CHAT_ID = load_admin_chat_id()

BAN_FILE = Path(__file__).with_name("banned_users.json")


def load_bans():
    try:
        data = json.loads(BAN_FILE.read_text(encoding="utf-8"))
        return {
            "ids": {int(value) for value in data.get("ids", [])},
            "usernames": {str(value).lstrip("@").lower() for value in data.get("usernames", [])},
        }
    except FileNotFoundError:
        return {"ids": set(), "usernames": set()}
    except (OSError, ValueError, TypeError, AttributeError) as error:
        print(f"Не удалось прочитать список банов: {error}")
        return {"ids": set(), "usernames": set()}


BANS = load_bans()

ORDERS_FILE = Path(__file__).with_name("orders.json")
ORDER_SESSIONS_FILE = Path(__file__).with_name("order_sessions.json")
ADMIN_SESSIONS = {}
def load_order_sessions():
    try:
        data = json.loads(ORDER_SESSIONS_FILE.read_text(encoding="utf-8"))
        return {int(key): value for key, value in data.items()}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, TypeError, AttributeError) as error:
        print(f"Не удалось восстановить черновики заказов: {error}")
        return {}

def save_order_sessions():
    data = {str(key): value for key, value in ORDER_SESSIONS.items()}
    ORDER_SESSIONS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

ORDER_SESSIONS = load_order_sessions()

def clear_order_session(chat_id):
    ORDER_SESSIONS.pop(chat_id, None)
    try:
        save_order_sessions()
    except OSError as error:
        print(f"Не удалось удалить черновик заказа: {error}")
USER_MESSAGE_TIMES = {}
ORDER_STATUSES = {"new": "Новая", "work": "В работе", "paid": "Оплачена", "done": "Завершена", "rejected": "Отказано", "client_rejected": "Отказ клиента"}
MINI_APP_PRODUCTS = {
    "warm_1000": ("Аккаунт с прогревом 1000sub+", WARM_PRICES["1000"]),
    "warm_5000": ("Аккаунт с прогревом 5000sub+", WARM_PRICES["5000"]),
    "warm_10000": ("Аккаунт с прогревом 10000sub+", WARM_PRICES["10000"]),
    "cold": ("Аккаунт без прогрева", COLD_PRICE),
    "site": ("Создание сайта", "По договорённости"),
    "bot": ("Разработка Telegram-бота", "По договорённости"),
}

def load_orders():
    try:
        data = json.loads(ORDERS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except (OSError, ValueError, TypeError) as error:
        print(f"Не удалось загрузить заявки: {error}")
        return []

ORDERS = load_orders()


def save_bans():
    data = {"ids": sorted(BANS["ids"]), "usernames": sorted(BANS["usernames"])}
    BAN_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_banned(user):
    user_id = user.get("id")
    username = (user.get("username") or "").lstrip("@").lower()
    return user_id in BANS["ids"] or bool(username and username in BANS["usernames"])


def is_admin(user, chat):
    if chat.get("type") != "private":
        return False
    username = (user.get("username") or "").lower()
    return username == ADMIN_USERNAME.lower() or chat.get("id") == ADMIN_CHAT_ID


def admin_reply(chat_id, text):
    api_call("sendMessage", {"chat_id": chat_id, "text": text})


def handle_ban_command(message, command):
    chat_id = message.get("chat", {}).get("id")
    parts = (message.get("text") or "").split(maxsplit=1)
    argument = parts[1].strip() if len(parts) > 1 else ""

    if command == "/bans":
        ids = ", ".join(str(value) for value in sorted(BANS["ids"])) or "нет"
        usernames = ", ".join("@" + value for value in sorted(BANS["usernames"])) or "нет"
        admin_reply(chat_id, f"🚫 Заблокированные ID: {ids}\nЗаблокированные username: {usernames}")
        return

    if not argument:
        admin_reply(chat_id, f"Использование: {command} <Telegram ID или @username>")
        return

    target = argument.split()[0].strip().rstrip(",")
    if target.startswith("@"):
        username = target[1:].lower()
        if not (5 <= len(username) <= 32 and username.isascii() and all(char.isalnum() or char == "_" for char in username)):
            admin_reply(chat_id, "Укажи username в формате @username.")
            return
        key, value, display = "usernames", username, "@" + username
    elif target.isdecimal():
        key, value, display = "ids", int(target), target
    else:
        admin_reply(chat_id, "Укажи Telegram ID числом или username в формате @username.")
        return

    if command == "/ban":
        if (key == "ids" and value == message.get("from", {}).get("id")) or (
            key == "usernames" and value == ADMIN_USERNAME.lower()
        ):
            admin_reply(chat_id, "Нельзя заблокировать самого администратора.")
            return
        BANS[key].add(value)
        try:
            save_bans()
        except OSError as error:
            BANS[key].discard(value)
            admin_reply(chat_id, f"Не удалось сохранить бан: {error}")
            return
        admin_reply(chat_id, f"✅ Заблокирован: {display}")
    else:
        if value not in BANS[key]:
            admin_reply(chat_id, f"{display} не найден в списке банов.")
            return
        BANS[key].remove(value)
        try:
            save_bans()
        except OSError as error:
            BANS[key].add(value)
            admin_reply(chat_id, f"Не удалось сохранить изменения: {error}")
            return
        admin_reply(chat_id, f"✅ Разблокирован: {display}")


def show_user_orders(chat_id, user, message_id=None):
    user_id = user.get("id")
    user_orders = sorted(
        (item for item in ORDERS if item.get("user_id") == user_id),
        key=lambda item: int(item.get("id", 0)),
        reverse=True,
    )[:10]
    rows = []
    if not user_orders:
        text = "📋 У вас пока нет оформленных заказов."
    else:
        lines = ["📋 Ваши последние заказы:"]
        for order in user_orders:
            status_key = order.get("status", "new")
            status = ORDER_STATUSES.get(status_key, status_key)
            lines.append(f"\n#{order['id']} · {order['product']}\nЦена: {order['price']}\nСтатус: {status}")
            rows.append([button(f"📜 История #{order['id']}", callback=f"order_history:{order['id']}")])
            if status_key in ("new", "work"):
                rows.append([button(f"❌ Отказаться от заказа #{order['id']}", callback=f"confirm_cancel:{order['id']}")])
        text = "".join(lines)
    rows.extend([
        [button("💬 Поддержка", callback="support")],
        [button("🏠 В главное меню", callback="home")],
    ])
    show_message(chat_id, text, keyboard(rows), message_id)


def show_order_history(chat_id, order, message_id=None):
    history = order.get("history") or [{
        "status": order.get("status", "new"),
        "at": order.get("created_at", "Время не указано"),
        "by": "system",
    }]
    lines = [f"📜 История заявки #{order['id']} · {order['product']}"]
    for entry in history:
        status = ORDER_STATUSES.get(entry.get("status"), entry.get("status", "Неизвестен"))
        lines.append(f"\n• {status}\n  {entry.get('at', 'Время не указано')} · {entry.get('by', 'system')}")
    show_message(chat_id, "".join(lines), keyboard([
        [button("⬅️ К моим заказам", callback="my_orders")],
        [button("💬 Поддержка", callback="support")],
        [button("🏠 В главное меню", callback="home")],
    ]), message_id)

def save_orders():
    ORDERS_FILE.write_text(json.dumps(ORDERS, ensure_ascii=False, indent=2), encoding="utf-8")


def order_step_keyboard(session_id, can_skip=False):
    rows = []
    if can_skip:
        rows.append([button("Пропустить пожелания", callback=f"skip_details:{session_id}")])
    rows.extend([
        [button("✖️ Отменить заказ", callback=f"cancel_order:{session_id}")],
        [button("🏠 В главное меню", callback="home")],
    ])
    return keyboard(rows)


def order_status_keyboard(order):
    order_id = order["id"]
    username = order.get("username")
    contact_url = f"https://t.me/{username}" if username else f"tg://user?id={order['user_id']}"
    return keyboard([
        [button("🆕 Новая", callback=f"order_status:{order_id}:new"),
         button("🛠 В работе", callback=f"order_status:{order_id}:work")],
        [button("💳 Оплачена", callback=f"order_status:{order_id}:paid"),
         button("✅ Завершена", callback=f"order_status:{order_id}:done")],
        [button("❌ Отказать", callback=f"order_status:{order_id}:rejected")],
        [button("✉️ Написать клиенту", url=contact_url)],
    ])


def start_order(chat_id, user, product, price, message_id=None):
    if chat_id in ORDER_SESSIONS:
        session = ORDER_SESSIONS[chat_id]
        if session.get("step") == "details":
            prompt = "Черновик заказа восстановлен. Контакт сохранён. Напишите пожелания или пропустите этот шаг."
        else:
            prompt = f"Черновик заказа восстановлен. Услуга: {session.get('product')}. Напишите контакт для связи."
        show_message(chat_id, prompt, order_step_keyboard(session["session_id"], session.get("step") == "details"), message_id)
        return

    now = datetime.now(timezone.utc)
    latest_order = next(
        (order for order in reversed(ORDERS) if order.get("user_id") == user.get("id")),
        None,
    )
    if latest_order:
        try:
            last_order_at = datetime.fromisoformat(latest_order["created_at"])
            seconds_left = ORDER_COOLDOWN_SECONDS - (now - last_order_at).total_seconds()
            if seconds_left > 0:
                show_message(chat_id, f"Для защиты от спама подождите ещё {int(seconds_left) + 1} сек. перед новой заявкой.", main_menu(), message_id)
                return
        except (KeyError, TypeError, ValueError):
            pass

    ORDER_SESSIONS[chat_id] = {
        "session_id": str(int(now.timestamp() * 1000000)),
        "user_id": user.get("id"),
        "username": user.get("username"),
        "first_name": user.get("first_name", "Пользователь"),
        "product": product,
        "price": price,
        "step": "contact",
    }
    save_order_sessions()
    show_message(
        chat_id,
        f"📝 Оформление заказа\nУслуга: {product}\nЦена: {price}\n\nШаг 1 из 2. Напишите ваш контакт для связи (например, @username или телефон).",
        order_step_keyboard(ORDER_SESSIONS[chat_id]["session_id"]),
        message_id,
    )


def create_order(chat_id, details=""):
    session = ORDER_SESSIONS.get(chat_id)
    if not session:
        return
    order = {
        "id": max((int(item.get("id", 0)) for item in ORDERS), default=0) + 1,
        "chat_id": chat_id,
        "user_id": session["user_id"],
        "username": session.get("username"),
        "first_name": session.get("first_name", "Пользователь"),
        "product": session["product"],
        "price": session["price"],
        "contact": session["contact"],
        "details": details.strip() or "Не указаны",
        "status": "new",
        "history": [{"status": "new", "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "by": "system"}],
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    ORDERS.append(order)
    try:
        save_orders()
    except OSError as error:
        ORDERS.pop()
        admin_reply(chat_id, f"Не удалось сохранить заказ. Попробуйте позже. ({error})")
        return

    clear_order_session(chat_id)
    notify_admin_order(order)
    show_message(chat_id, f"✅ Заявка #{order['id']} создана. Мы свяжемся с вами. Статус: Новая.", main_menu())


def notify_admin_order(order):
    username = "@" + order["username"] if order.get("username") else "не указан"
    text = (
        f"📦 Новая заявка #{order['id']}\n"
        f"Услуга: {order['product']}\nЦена: {order['price']}\n"
        f"Клиент: {order['first_name']} ({username}, ID {order['user_id']})\n"
        f"Контакт: {order['contact']}\nПожелания: {order['details']}\n"
        f"Статус: {ORDER_STATUSES['new']}"
    )
    if ADMIN_CHAT_ID is None:
        print(text)
        return
    try:
        api_call("sendMessage", {
            "chat_id": ADMIN_CHAT_ID,
            "text": text,
            "reply_markup": order_status_keyboard(order),
        })
    except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
        print(f"Не удалось отправить заявку администратору: {error}")
        print(text)


def process_mini_app_message(message):
    web_data = message.get("web_app_data")
    if not web_data:
        return False
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    user = message.get("from", {})
    if chat.get("type") != "private" or chat_id is None:
        return True
    try:
        payload = json.loads(web_data.get("data", "{}"))
    except (TypeError, ValueError):
        show_message(chat_id, "Не удалось прочитать данные Mini App. Откройте её ещё раз и повторите.", main_menu())
        return True
    if payload.get("action") == "my_orders":
        show_user_orders(chat_id, user)
        return True
    if payload.get("action") != "submit_order":
        show_message(chat_id, "Неизвестное действие Mini App.", main_menu())
        return True
    product_key = payload.get("product")
    if product_key not in MINI_APP_PRODUCTS:
        show_message(chat_id, "Выбранная услуга не найдена. Обновите Mini App и попробуйте ещё раз.", main_menu())
        return True
    if chat_id in ORDER_SESSIONS:
        show_message(chat_id, "Сначала завершите или отмените незаконченный заказ в чате с ботом.", main_menu())
        return True
    contact = str(payload.get("contact", "")).strip()
    details = str(payload.get("details", "")).strip()
    if not contact or len(contact) > 200 or len(details) > 1000:
        show_message(chat_id, "Проверьте контакт (обязательное поле, до 200 символов) и пожелания (до 1000 символов).", main_menu())
        return True
    now = datetime.now(timezone.utc)
    latest_order = next((item for item in reversed(ORDERS) if item.get("user_id") == user.get("id")), None)
    if latest_order:
        try:
            last_order_at = datetime.fromisoformat(latest_order["created_at"])
            seconds_left = ORDER_COOLDOWN_SECONDS - (now - last_order_at).total_seconds()
            if seconds_left > 0:
                show_message(chat_id, f"Для защиты от спама подождите ещё {int(seconds_left) + 1} сек. перед новой заявкой.", main_menu())
                return True
        except (KeyError, TypeError, ValueError):
            pass
    product, price = MINI_APP_PRODUCTS[product_key]
    session_id = str(int(now.timestamp() * 1000000))
    ORDER_SESSIONS[chat_id] = {
        "session_id": session_id,
        "user_id": user.get("id"),
        "username": user.get("username"),
        "first_name": user.get("first_name", "Пользователь"),
        "product": product,
        "price": price,
        "contact": contact,
        "step": "details",
    }
    try:
        save_order_sessions()
    except OSError as error:
        ORDER_SESSIONS.pop(chat_id, None)
        show_message(chat_id, f"Не удалось сохранить заявку. Попробуйте позже. ({error})", main_menu())
        return True
    create_order(chat_id, details)
    return True


def show_admin_panel(chat_id, message_id=None):
    show_message(chat_id, "🛠 Панель администратора\nВыберите действие:", keyboard([
        [button("📋 Последние заявки", callback="admin_orders")],
        [button("🔎 Найти по Telegram ID", callback="admin_find_user")],
        [button("🏠 В главное меню", callback="home")],
    ]), message_id)


def show_admin_orders(chat_id, message_id=None, target_id=None):
    if target_id is None:
        orders = sorted(ORDERS, key=lambda item: int(item.get("id", 0)), reverse=True)[:15]
        title = "📋 Последние заявки"
    else:
        orders = sorted((item for item in ORDERS if item.get("user_id") == target_id), key=lambda item: int(item.get("id", 0)), reverse=True)[:15]
        title = f"🔎 Заявки пользователя ID {target_id}"
    rows = [[button(f"#{item['id']} · {ORDER_STATUSES.get(item.get('status'), item.get('status'))} · {item['product']}", callback=f"admin_view:{item['id']}")] for item in orders]
    if not orders:
        title += "\nЗаявок не найдено."
    rows.append([button("🔎 Найти по Telegram ID", callback="admin_find_user")])
    rows.append([button("⬅️ В панель администратора", callback="admin_panel")])
    show_message(chat_id, title, keyboard(rows), message_id)


def show_admin_order(chat_id, order, message_id=None):
    username = "@" + order["username"] if order.get("username") else "не указан"
    status = ORDER_STATUSES.get(order.get("status"), order.get("status"))
    text = (
        f"📦 Заявка #{order['id']}\nСтатус: {status}\nУслуга: {order['product']}\nЦена: {order['price']}\n"
        f"Клиент: {order['first_name']} ({username}, ID {order['user_id']})\nКонтакт: {order['contact']}\nПожелания: {order['details']}"
    )
    rows = order_status_keyboard(order)["inline_keyboard"]
    rows.extend([
        [button("📜 История статусов", callback=f"admin_history:{order['id']}")],
        [button("⬅️ К списку заявок", callback="admin_orders")],
    ])
    show_message(chat_id, text, keyboard(rows), message_id)


def process_order_message(message):
    chat_id = message.get("chat", {}).get("id")
    session = ORDER_SESSIONS.get(chat_id)
    if not session:
        return False
    text = (message.get("text") or "").strip()
    if text.lower() in ("/cancel", "/start"):
        clear_order_session(chat_id)
        show_message(chat_id, "Оформление заказа отменено.", main_menu())
        return True
    if session["step"] == "contact":
        if not text or len(text) > 200:
            show_message(chat_id, "Укажите контакт текстом (до 200 символов) или отмените заказ.", order_step_keyboard(session["session_id"]))
            return True
        session["contact"] = text
        session["step"] = "details"
        save_order_sessions()
        show_message(
            chat_id,
            "Шаг 2 из 2. Напишите пожелания к заказу. Если пожеланий нет, нажмите «Пропустить пожелания».",
            order_step_keyboard(session["session_id"], can_skip=True),
        )
        return True
    if session["step"] == "details":
        if text.lower() == "/skip":
            text = ""
        if len(text) > 1000:
            show_message(chat_id, "Пожелания должны быть не длиннее 1000 символов. Попробуйте ещё раз.", order_step_keyboard(session["session_id"], can_skip=True))
            return True
        create_order(chat_id, text)
        return True
    return False


def set_order_status(order_id, status, changed_by="Администратор"):
    order = next((item for item in ORDERS if item.get("id") == order_id), None)
    if not order or status not in ORDER_STATUSES:
        return False
    previous_status = order.get("status", "new")
    if previous_status == status:
        return True
    old_history = list(order.get("history", []))
    if not old_history:
        old_history.append({"status": previous_status, "at": order.get("created_at", "Время не указано"), "by": "system"})
    order["status"] = status
    order["history"] = old_history + [{
        "status": status,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "by": changed_by,
    }]
    try:
        save_orders()
    except OSError as error:
        order["status"] = previous_status
        order["history"] = old_history
        print(f"Не удалось сохранить статус заявки: {error}")
        return False
    try:
        api_call("sendMessage", {
            "chat_id": order["chat_id"],
            "text": f"ℹ️ Статус вашей заявки #{order_id} обновлён: {ORDER_STATUSES[status]}.",
        })
    except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
        print(f"Не удалось сообщить клиенту о статусе заявки #{order_id}: {error}")
    return True

def handle_order_admin_command(message, command):
    chat_id = message.get("chat", {}).get("id")
    parts = (message.get("text") or "").split(maxsplit=2)
    if command == "/orders":
        if len(parts) > 1:
            if not parts[1].isdecimal():
                admin_reply(chat_id, "Использование: /orders <Telegram ID>")
                return
            target_id = int(parts[1])
            recent = sorted(
                (item for item in ORDERS if item.get("user_id") == target_id),
                key=lambda item: int(item.get("id", 0)),
                reverse=True,
            )[:15]
            if not recent:
                admin_reply(chat_id, f"У пользователя ID {target_id} заявок нет.")
                return
        else:
            recent = sorted(ORDERS, key=lambda item: int(item.get("id", 0)), reverse=True)[:15]
        if not recent:
            admin_reply(chat_id, "Заявок пока нет.")
            return
        lines = [f"#{item['id']} · {ORDER_STATUSES.get(item.get('status'), item.get('status'))} · {item['product']} · ID {item['user_id']}" for item in recent]
        admin_reply(chat_id, "📋 Последние заявки:\n" + "\n".join(lines))
        return
    if command == "/order":
        if len(parts) < 2 or not parts[1].isdecimal():
            admin_reply(chat_id, "Использование: /order <номер>")
            return
        order_id = int(parts[1])
        order = next((item for item in ORDERS if item.get("id") == order_id), None)
        if not order:
            admin_reply(chat_id, f"Заявка #{order_id} не найдена.")
            return
        username = "@" + order["username"] if order.get("username") else "не указан"
        admin_reply(chat_id, f"Заявка #{order_id}\nСтатус: {ORDER_STATUSES.get(order.get('status'), order.get('status'))}\nУслуга: {order['product']}\nЦена: {order['price']}\nКлиент: {order['first_name']} ({username}, ID {order['user_id']})\nКонтакт: {order['contact']}\nПожелания: {order['details']}")
        return
    if command == "/status":
        if len(parts) < 3 or not parts[1].isdecimal():
            admin_reply(chat_id, "Использование: /status <номер> <новая|в работе|оплачена|завершена|отказано|отказ клиента>")
            return
        status_text = parts[2].strip().lower()
        aliases = {"новая": "new", "new": "new", "в работе": "work", "работа": "work", "work": "work", "оплачена": "paid", "paid": "paid", "завершена": "done", "done": "done", "отказано": "rejected", "rejected": "rejected", "отказ клиента": "client_rejected", "client_rejected": "client_rejected"}
        status = aliases.get(status_text)
        order_id = int(parts[1])
        if not status:
            admin_reply(chat_id, "Статус должен быть: новая, в работе, оплачена, завершена, отказано или отказ клиента.")
        elif not set_order_status(order_id, status):
            admin_reply(chat_id, f"Не удалось обновить заявку #{order_id}.")
        else:
            admin_reply(chat_id, f"✅ Заявка #{order_id}: {ORDER_STATUSES[status]}.")

def api_call(method, data):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        API + method,
        data=body,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(request, timeout=40) as response:
        result = json.loads(response.read().decode("utf-8"))

    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Ошибка Telegram API"))

    return result["result"]


def telegram_link(username, message):
    encoded_message = urllib.parse.quote(message, safe="")
    return f"https://t.me/{username}?text={encoded_message}"


def button(text, callback=None, url=None):
    item = {"text": text}

    if callback is not None:
        item["callback_data"] = callback

    if url is not None:
        item["url"] = url

    return item


def keyboard(rows):
    return {"inline_keyboard": rows}


def main_menu():
    return keyboard([
        [button("🛍 Главный магазин", callback="shop")],
        [button("📱 Открыть Mini App", callback="mini_app")],
        [button("📋 Мои заказы", callback="my_orders")],
        [button("💬 Поддержка", callback="support")],
        [button("ℹ️ Помощь", callback="help")],
    ])

def shop_menu():
    return keyboard([
        [button("📣 Реклама", callback="ads")],
        [button("🌐 Сайт", callback="site")],
        [button("🤖 Telegram-бот", callback="bot")],
        [button("💬 Поддержка", callback="support")],
        [button("⬅️ В главное меню", callback="home")],
    ])


def show_message(chat_id, text, markup, message_id=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": markup,
    }

    if message_id is None:
        api_call("sendMessage", data)
    else:
        data["message_id"] = message_id
        api_call("editMessageText", data)


def user_description(user):
    username = user.get("username")
    name = user.get("first_name", "Пользователь")
    identity = f"@{username}" if username else "без username"
    user_id = user.get("id", "неизвестен")
    return f"{name} ({identity}, ID {user_id})"


def log_activity(text):
    log_message = f"📋 Активность магазина\n{text}"

    if ADMIN_CHAT_ID is None:
        print(log_message)
        return

    try:
        api_call(
            "sendMessage",
            {"chat_id": ADMIN_CHAT_ID, "text": log_message},
        )
    except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
        print(f"Не удалось отправить журнал администратору: {error}")


def log_incoming_message(message, edited=False):
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    sender = message.get("from") or message.get("sender_chat") or {}

    if chat_id is None or message_id is None:
        return

    metadata_fields = {
        "message_id",
        "message_thread_id",
        "from",
        "sender_chat",
        "sender_boost_count",
        "sender_business_bot",
        "business_connection_id",
        "chat",
        "date",
        "edit_date",
        "forward_origin",
        "is_topic_message",
        "is_automatic_forward",
        "reply_to_message",
        "external_reply",
        "quote",
        "via_bot",
        "has_protected_content",
        "is_paid_post",
        "author_signature",
        "reply_to_story",
    }
    content = {
        key: value
        for key, value in message.items()
        if key not in metadata_fields
    }
    content_types = ", ".join(content) or "тип не определён"
    kind = "Изменённое сообщение" if edited else "Входящее сообщение"
    details = (
        f"📥 {kind}\n"
        f"От: {user_description(sender)}\n"
        f"Чат ID: {chat_id}\n"
        f"Сообщение ID: {message_id}\n"
        f"Тип: {content_types}"
    )

    if ADMIN_CHAT_ID is None:
        print(details)
        if content:
            print(json.dumps(content, ensure_ascii=False))
        return

    try:
        api_call(
            "sendMessage",
            {"chat_id": ADMIN_CHAT_ID, "text": details},
        )
        api_call(
            "copyMessage",
            {
                "chat_id": ADMIN_CHAT_ID,
                "from_chat_id": chat_id,
                "message_id": message_id,
            },
        )
    except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
        print(
            "Не удалось полностью передать сообщение администратору: "
            f"{type(error).__name__}"
        )
        fallback_content = json.dumps(content, ensure_ascii=False)
        fallback_text = (
            "⚠️ Telegram не дал скопировать исходное сообщение.\n"
            f"{details}\n\n{fallback_content}"
        )[:3900]
        try:
            api_call(
                "sendMessage",
                {"chat_id": ADMIN_CHAT_ID, "text": fallback_text},
            )
        except (urllib.error.URLError, TimeoutError, RuntimeError) as fallback_error:
            print(
                "Не удалось отправить резервную запись сообщения: "
                f"{type(fallback_error).__name__}"
            )


def enable_admin_log(message):
    global ADMIN_CHAT_ID

    chat = message.get("chat", {})
    chat_id = chat.get("id")

    if chat.get("type") != "private" or chat_id is None:
        return False

    ADMIN_CHAT_ID = chat_id

    try:
        ADMIN_ID_FILE.write_text(str(chat_id), encoding="utf-8")
    except OSError as error:
        print(f"Не удалось сохранить ID администратора: {error}")

    api_call(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": "✅ Журнал подключён. Сюда будут приходить сообщения, вложения и нажатия кнопок.",
        },
    )

    print(f"Журнал подключён для @{ADMIN_USERNAME}.")
    return True


def show_ads(chat_id, message_id):
    text = (
        "📣 Реклама\n"
        "Прайс-лист:\n"
        f"• Прогрев, 1000sub+ — {WARM_PRICES['1000']}\n"
        f"• Прогрев, 5000sub+ — {WARM_PRICES['5000']}\n"
        f"• Прогрев, 10000sub+ — {WARM_PRICES['10000']}\n"
        f"• Без прогрева — {COLD_PRICE}\n\n"
        "Выберите вариант:"
    )
    markup = keyboard([
        [button("Аккаунты с прогревом", callback="warm")],
        [button(f"Аккаунт без прогрева · {COLD_PRICE}", callback="cold")],
        [button("💬 Поддержка", callback="support")],
        [button("⬅️ В магазин", callback="shop")],
        [button("🏠 В главное меню", callback="home")],
    ])
    show_message(chat_id, text, markup, message_id)

def warm_accounts_menu():
    return keyboard([
        [button(f"Аккаунт 1000sub+ · {WARM_PRICES['1000']}", callback="warm_1000")],
        [button(f"Аккаунт 5000sub+ · {WARM_PRICES['5000']}", callback="warm_5000")],
        [button(f"Аккаунт 10000sub+ · {WARM_PRICES['10000']}", callback="warm_10000")],
        [button("💬 Поддержка", callback="support")],
        [button("⬅️ Назад", callback="ads")],
        [button("🏠 В главное меню", callback="home")],
    ])


def show_contact(
    chat_id,
    message_id,
    text,
    username,
    message_to_seller,
    back="shop",
    show_support_button=True,
):
    rows = [[button(
        "Открыть чат и написать",
        url=telegram_link(username, message_to_seller),
    )]]
    if show_support_button:
        rows.append([button("💬 Поддержка", callback="support")])
    rows.extend([
        [button("⬅️ Назад", callback=back)],
        [button("🏠 В главное меню", callback="home")],
    ])
    markup = {"inline_keyboard": rows}

    show_message(chat_id, text, markup, message_id)


def show_help(chat_id, message_id=None):
    text = (
        "ℹ️ Как пользоваться ботом\n\n"
        "1. Выберите услугу в магазине или откройте Mini App.\n"
        "2. Укажите контакт для связи и пожелания.\n"
        "3. Статус заявки смотрите в разделе «Мои заказы».\n"
        "4. Оплата и сроки согласуются с менеджером.\n\n"
        f"Если нужна помощь, напишите @{SUPPORT_USERNAME}."
    )
    show_message(chat_id, text, keyboard([
        [button("💬 Поддержка", callback="support")],
        [button("🏠 В главное меню", callback="home")],
    ]), message_id)


def open_mini_app(chat_id, chat_type):
    if chat_type != "private":
        admin_reply(chat_id, "Mini App можно открыть только в личном чате с ботом.")
        return
    if not MINI_APP_URL.startswith("https://") or "YOUR_DOMAIN" in MINI_APP_URL:
        admin_reply(chat_id, "Mini App подготовлен, но ещё не подключён: укажи его HTTPS-адрес в MINI_APP_URL в bot.py после публикации miniapp.html.")
        return
    api_call("sendMessage", {
        "chat_id": chat_id,
        "text": "Нажмите кнопку ниже, чтобы открыть каталог и оформить заказ:",
        "reply_markup": {
            "keyboard": [[{"text": "🛍 Открыть ASF Mini App", "web_app": {"url": MINI_APP_URL}}]],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        },
    })


def handle_button(query):
    user = query.get("from", {})
    if is_banned(user):
        api_call("answerCallbackQuery", {"callback_query_id": query["id"], "text": "⛔ Доступ к боту ограничен. Если считаете, что это ошибка, обратитесь в поддержку: @ASFSUPP.", "show_alert": True})
        return

    api_call("answerCallbackQuery", {"callback_query_id": query["id"]})
    action = query.get("data", "")
    message = query.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    if chat_id is None:
        return

    admin_action = action in ("admin_panel", "admin_orders", "admin_find_user", "admin_cancel_find") or action.startswith(("admin_view:", "admin_history:"))
    if admin_action:
        if not is_admin(user, chat):
            return
        if action == "admin_panel":
            show_admin_panel(chat_id, message_id)
        elif action == "admin_orders":
            show_admin_orders(chat_id, message_id)
        elif action == "admin_find_user":
            ADMIN_SESSIONS[chat_id] = "find_user_id"
            show_message(chat_id, "Отправьте Telegram ID пользователя, чтобы найти его заявки.", keyboard([
                [button("✖️ Отмена", callback="admin_cancel_find")],
                [button("⬅️ В панель администратора", callback="admin_panel")],
            ]), message_id)
        elif action == "admin_cancel_find":
            ADMIN_SESSIONS.pop(chat_id, None)
            show_admin_panel(chat_id, message_id)
        elif action.startswith("admin_view:"):
            try:
                order_id = int(action.split(":", 1)[1])
            except ValueError:
                return
            order = next((item for item in ORDERS if item.get("id") == order_id), None)
            if order:
                show_admin_order(chat_id, order, message_id)
        elif action.startswith("admin_history:"):
            try:
                order_id = int(action.split(":", 1)[1])
            except ValueError:
                return
            order = next((item for item in ORDERS if item.get("id") == order_id), None)
            if order:
                history = order.get("history") or [{"status": order.get("status", "new"), "at": order.get("created_at", "Время не указано"), "by": "system"}]
                lines = [f"📜 История заявки #{order_id}"]
                for entry in history:
                    lines.append(f"\n• {ORDER_STATUSES.get(entry.get('status'), entry.get('status'))}\n  {entry.get('at', 'Время не указано')} · {entry.get('by', 'system')}")
                show_message(chat_id, "".join(lines), keyboard([
                    [button("⬅️ К заявке", callback=f"admin_view:{order_id}")],
                    [button("⬅️ В панель администратора", callback="admin_panel")],
                ]), message_id)
        return

    if action.startswith("order_status:"):
        parts = action.split(":")
        if len(parts) == 3 and is_admin(user, chat):
            try:
                order_id = int(parts[1])
            except ValueError:
                return
            if set_order_status(order_id, parts[2], changed_by="Администратор"):
                admin_reply(chat_id, f"✅ Заявка #{order_id}: {ORDER_STATUSES[parts[2]]}.")
            else:
                admin_reply(chat_id, f"Не удалось обновить заявку #{order_id}.")
        return

    if action.startswith("order_history:"):
        try:
            order_id = int(action.split(":", 1)[1])
        except ValueError:
            return
        order = next((item for item in ORDERS if item.get("id") == order_id), None)
        if order and order.get("user_id") == user.get("id"):
            show_order_history(chat_id, order, message_id)
        return

    if action.startswith("confirm_cancel:"):
        try:
            order_id = int(action.split(":", 1)[1])
        except ValueError:
            return
        order = next((item for item in ORDERS if item.get("id") == order_id), None)
        if order and order.get("user_id") == user.get("id") and order.get("status") in ("new", "work"):
            show_message(chat_id, f"Отказаться от заявки #{order_id} «{order['product']}»? Это действие изменит её статус.", keyboard([
                [button("Да, отказаться", callback=f"confirm_client_cancel:{order_id}")],
                [button("Нет, оставить заявку", callback="my_orders")],
            ]), message_id)
        return

    if action.startswith("confirm_client_cancel:"):
        try:
            order_id = int(action.split(":", 1)[1])
        except ValueError:
            return
        order = next((item for item in ORDERS if item.get("id") == order_id), None)
        if not order or order.get("user_id") != user.get("id") or order.get("status") not in ("new", "work"):
            return
        if not set_order_status(order_id, "client_rejected", changed_by="Клиент"):
            show_message(chat_id, "Не удалось отменить заявку. Попробуйте ещё раз или обратитесь в поддержку.", main_menu(), message_id)
            return
        notice = f"↩️ Клиент отказался от заявки #{order_id}. Клиент ID {order.get('user_id')}"
        if ADMIN_CHAT_ID is not None:
            try:
                admin_reply(ADMIN_CHAT_ID, notice)
            except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
                print(f"Не удалось сообщить администратору об отказе клиента: {error}")
        else:
            print(notice)
        show_user_orders(chat_id, user, message_id)
        return

    if action.startswith("cancel_order:"):
        session = ORDER_SESSIONS.get(chat_id)
        if session and action.split(":", 1)[1] == session.get("session_id"):
            clear_order_session(chat_id)
            show_message(chat_id, "Оформление заказа отменено.", main_menu(), message_id)
        return
    if action.startswith("skip_details:"):
        session = ORDER_SESSIONS.get(chat_id)
        if session and session.get("step") == "details" and action.split(":", 1)[1] == session.get("session_id"):
            create_order(chat_id)
        return

    action_names = {
        "home": "нажал «В главное меню»",
        "shop": "открыл магазин",
        "ads": "открыл раздел «Реклама»",
        "site": "начал заказ сайта",
        "bot": "начал заказ Telegram-бота",
        "support": "нажал «Поддержка»",
        "warm": "открыл варианты аккаунта с прогревом",
        "warm_1000": "выбрал аккаунт с прогревом 1000sub+",
        "warm_5000": "выбрал аккаунт с прогревом 5000sub+",
        "warm_10000": "выбрал аккаунт с прогревом 10000sub+",
        "cold": "выбрал аккаунт без прогрева",
    }
    event = action_names.get(action)
    if event:
        log_activity(f"{user_description(user)} {event}.")

    if action == "home":
        clear_order_session(chat_id)
        show_message(chat_id, "Добро пожаловать в магазин! Выберите раздел:\n\nℹ️ Сообщения и вложения, отправленные боту, видны администратору.", main_menu(), message_id)
    elif action == "mini_app":
        open_mini_app(chat_id, chat.get("type"))
    elif action == "help":
        show_help(chat_id, message_id)
    elif action == "my_orders":
        show_user_orders(chat_id, user, message_id)
    elif action == "shop":
        clear_order_session(chat_id)
        show_message(chat_id, "🛍 Магазин\nВыберите категорию:", shop_menu(), message_id)
    elif action == "ads":
        show_ads(chat_id, message_id)
    elif action == "support":
        clear_order_session(chat_id)
        show_contact(chat_id, message_id, "💬 Поддержка\nНажмите кнопку, чтобы открыть чат поддержки.", SUPPORT_USERNAME, "Здравствуйте! Нужна поддержка.", back="home", show_support_button=False)
    elif action == "warm":
        show_message(chat_id, "🔥 Аккаунт с прогревом\nВыберите количество подписчиков:", warm_accounts_menu(), message_id)
    elif action in ("warm_1000", "warm_5000", "warm_10000"):
        subscribers = action.removeprefix("warm_")
        start_order(chat_id, user, f"Аккаунт с прогревом {subscribers}sub+", WARM_PRICES[subscribers], message_id)
    elif action == "cold":
        start_order(chat_id, user, "Аккаунт без прогрева", COLD_PRICE, message_id)
    elif action == "site":
        start_order(chat_id, user, "Создание сайта", "По договорённости", message_id)
    elif action == "bot":
        start_order(chat_id, user, "Разработка Telegram-бота", "По договорённости", message_id)

def handle_message(message, edited=False):
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    user = message.get("from", {})
    text = message.get("text", "")
    if chat_id is None:
        return

    command = text.split()[0].split("@", 1)[0].lower() if text else ""
    admin = is_admin(user, chat)
    if admin:
        if ADMIN_SESSIONS.get(chat_id) == "find_user_id":
            if command in ("/cancel", "/start"):
                ADMIN_SESSIONS.pop(chat_id, None)
                show_admin_panel(chat_id)
            elif text.strip().isdecimal():
                target_id = int(text.strip())
                ADMIN_SESSIONS.pop(chat_id, None)
                show_admin_orders(chat_id, target_id=target_id)
            else:
                admin_reply(chat_id, "Отправьте числовой Telegram ID или нажмите «Отмена».")
            return
        if command == "/setadmin":
            if enable_admin_log(message):
                log_incoming_message(message)
                return
        elif command == "/admin":
            show_admin_panel(chat_id)
            return
        elif command == "/help":
            admin_reply(chat_id, "Команды: /admin — панель; /orders [Telegram ID] — заявки; /order <номер> — карточка; /status <номер> <статус>; /ban, /unban, /bans.")
            return
        elif command in ("/ban", "/unban", "/bans"):
            handle_ban_command(message, command)
            return
        elif command in ("/orders", "/order", "/status"):
            handle_order_admin_command(message, command)
            return

    if is_banned(user):
        return
    if process_mini_app_message(message):
        return

    if not admin and chat_id not in ORDER_SESSIONS:
        now = time.monotonic()
        previous = USER_MESSAGE_TIMES.get(user.get("id"))
        if previous is not None and now - previous < MESSAGE_COOLDOWN_SECONDS:
            return
        USER_MESSAGE_TIMES[user.get("id")] = now

    if edited:
        log_incoming_message(message, edited=True)
        return
    if process_order_message(message):
        return
    if command == "/help":
        show_help(chat_id)
        return

    log_incoming_message(message)
    show_message(
        chat_id,
        "Добро пожаловать в магазин! Выберите раздел:\n\nℹ️ Сообщения и вложения, отправленные боту, видны администратору.",
        main_menu(),
    )

def main():
    try:
        bot_info = api_call("getMe", {})
    except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
        raise SystemExit(
            f"Не удалось подключиться к Telegram или проверить токен: {error}"
        )

    print(f"Подключение успешно: @{bot_info.get('username')}")

    if ADMIN_CHAT_ID is None:
        print(
            f"Открой бота с аккаунта @{ADMIN_USERNAME} "
            "и отправь ему /setadmin для включения журнала."
        )

    print("Бот запущен. Остановить: Ctrl+C")
    offset = None

    try:
        while True:
            params = {"timeout": 25}

            if offset is not None:
                params["offset"] = offset

            try:
                updates = api_call("getUpdates", params)

                for update in updates:
                    offset = update["update_id"] + 1

                    if "callback_query" in update:
                        handle_button(update["callback_query"])
                    elif "message" in update:
                        handle_message(update["message"])
                    elif "edited_message" in update:
                        handle_message(update["edited_message"], edited=True)

            except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
                print(f"Ошибка Telegram API: {error}. Повтор через 5 секунд.")
                time.sleep(5)

    except KeyboardInterrupt:
        print("\nБот остановлен.")


if __name__ == "__main__":
    main()










































