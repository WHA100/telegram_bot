import os
import json
import hashlib
import random
import asyncio
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
FILE_PATH = os.getenv('FILE_PATH')
STORAGE_FILE = 'chat_history.json'
PRICE = int(os.getenv('PRICE'))
SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
app = Flask(__name__)
chat_history = {}

# Загрузка и сохранение истории чатов
def load_chat_history():
    global chat_history
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, 'r') as f:
                chat_history = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            chat_history = {}
    else:
        chat_history = {}

def save_chat_history():
    with open(STORAGE_FILE, 'w') as f:
        json.dump(chat_history, f)

load_chat_history()

# Генерация случайного кода подтверждения
def hash_code(code):
    return hashlib.sha256(code.encode()).hexdigest()

def generate_payment_code():
    return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))

# Обработка команды /start
@dp.message(CommandStart())
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    user_name = message.from_user.full_name

    if user_id not in chat_history:
        chat_history[user_id] = {
            "name": user_name, "messages": [], "payment_code": None,
            "support_access": False, "support_contacted": False,
            "purchase_stage": "Нажал /start", "last_payment_message_id": None
        }

    # Клавиатура с кнопками
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Купить файлы"), KeyboardButton("Техподдержка"))

    welcome_text = (
        "*Добро пожаловать!*\n"
        f"Стоимость файлов: *{PRICE} рублей*.\n"
        "Выберите действие ниже:"
    )
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="Markdown")
    save_chat_history()

# Обработка кнопок "Купить файлы" и "Техподдержка"
@dp.message(lambda message: message.text in ["Купить файлы", "Техподдержка"])
async def handle_action(message: types.Message):
    user_id = message.from_user.id
    if message.text == "Купить файлы":
        payment_code = generate_payment_code()
        hashed_code = hash_code(payment_code)
        chat_history[user_id]["payment_code"] = hashed_code
        save_chat_history()
        await message.answer(f"Ваш код оплаты: {payment_code}")
    elif message.text == "Техподдержка":
        await message.answer(f"Свяжитесь с техподдержкой: {SUPPORT_USERNAME}")

# Главная страница Flask API
@app.route('/')
def index():
    return "Telegram Bot API is running!"

# Запуск Telegram-бота
async def start_bot():
    await dp.start_polling(bot)

# Запуск Flask и Telegram-бота
if __name__ == '__main__':
    port = int(os.getenv("PORT", 10000))
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    app.run(host='0.0.0.0', port=port)
