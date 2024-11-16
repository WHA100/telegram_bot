import os
import json
import random
import hashlib
import logging
import asyncio
from threading import Thread
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, Router
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.filters import CommandStart
from flask import Flask, request, jsonify

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
FILE_PATH = os.getenv("FILE_PATH")
SBERBANK_ACCOUNT = os.getenv("SBERBANK_ACCOUNT")
YMONEY_ACCOUNT = os.getenv("YMONEY_ACCOUNT")
PAYEER_ACCOUNT = os.getenv("PAYEER_ACCOUNT")
CRYPTO_ACCOUNT = os.getenv("CRYPTO_ACCOUNT")
PRICE = int(os.getenv("PRICE"))
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME")
STORAGE_FILE = os.getenv("STORAGE_FILE")

bot = Bot(token=API_TOKEN)
router = Router()
dp = Dispatcher(storage=MemoryStorage())
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
chat_history = {}

# Загрузка и сохранение истории чатов
def load_chat_history():
    global chat_history
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, 'r') as f:
            chat_history = json.load(f)

def save_chat_history():
    with open(STORAGE_FILE, 'w') as f:
        json.dump(chat_history, f)

load_chat_history()

# Генерация и хэширование кода
def generate_payment_code():
    return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))

def hash_code(code):
    return hashlib.sha256(code.encode()).hexdigest()

# Обработчик команды /start
@router.message(CommandStart())
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    user_name = message.from_user.full_name

    if user_id not in chat_history:
        chat_history[user_id] = {
            "name": user_name, "messages": [], "payment_code": None,
            "support_access": False, "support_contacted": False,
            "purchase_stage": "Нажал /start", "last_payment_message_id": None
        }

    chat_history[user_id]["messages"].append(f"User: {message.text}")
    update_purchase_stage(user_id, "Нажал /start")

    if chat_history[user_id].get("support_access"):
        keyboard = ReplyKeyboardMarkup([[KeyboardButton(text="Техподдержка")]], resize_keyboard=True)
    else:
        keyboard = ReplyKeyboardMarkup([[KeyboardButton(text="Купить файлы")]], resize_keyboard=True)

    welcome_text = (
        "*Добро пожаловать!*\n\n"
        "Все предлагаемые файлы предназначены _только для Windows_.\n"
        f"Стоимость файлов: *{PRICE} рублей*.\n\n"
        "Выберите действие ниже:"
    )
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="Markdown")
    save_chat_history()

# Обработка кнопок "Купить файлы" и "Техподдержка"
@router.message(lambda message: message.text in ["Купить файлы", "Техподдержка"])
async def handle_action(message: types.Message):
    user_id = message.from_user.id
    if message.text == "Купить файлы":
        if chat_history[user_id].get("payment_code") is not None:
            await message.answer("Вы уже запросили код оплаты. Пожалуйста, завершите оплату.")
            return
        update_purchase_stage(user_id, "Нажал 'Купить файлы'")
        payment_choice_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton(text="Из России")], [KeyboardButton(text="Не из России")], [KeyboardButton(text="Криптовалютой")]],
            resize_keyboard=True
        )
        await message.answer("Выберите способ оплаты:", reply_markup=payment_choice_keyboard)
    elif message.text == "Техподдержка":
        if chat_history[user_id].get("support_access") and not chat_history[user_id].get("support_contacted"):
            update_purchase_stage(user_id, "Нажал 'Техподдержка'")
            chat_history[user_id]["support_contacted"] = True
            await message.answer(f"Для помощи свяжитесь с [техподдержкой]({SUPPORT_USERNAME})", parse_mode="Markdown")
            save_chat_history()

# Обработка выбора способа оплаты и отправка инструкций
@router.message(lambda message: message.text in ["Из России", "Не из России", "Криптовалютой"])
async def handle_payment_choice(message: types.Message):
    user_id = message.from_user.id
    payment_code = generate_payment_code()
    hashed_code = hash_code(payment_code)
    chat_history[user_id]["hashed_payment_code"] = hashed_code
    save_chat_history()

    if message.text == "Из России":
        instructions = f"Ваш код: *{payment_code}*\nПереведите {PRICE} рублей на Сбербанк: `{SBERBANK_ACCOUNT}`"
    elif message.text == "Не из России":
        instructions = f"Ваш код: *{payment_code}*\nПереведите {PRICE} рублей на Payeer: `{PAYEER_ACCOUNT}`"
    elif message.text == "Криптовалютой":
        instructions = f"Ваш код: *{payment_code}*\nПереведите сумму в криптовалюте на адрес: `{CRYPTO_ACCOUNT}`"

    await message.answer(instructions, parse_mode="Markdown")

# Проверка оплаты и отправка файла
async def send_file_on_confirmation(user_id, payment_code):
    if chat_history[user_id]["hashed_payment_code"] == hash_code(payment_code):
        file = FSInputFile(FILE_PATH)
        await bot.send_document(user_id, file)
        chat_history[user_id]["hashed_payment_code"] = None
        chat_history[user_id]["support_access"] = True
        update_purchase_stage(user_id, "Файл отправлен")
        save_chat_history()
        return "Оплата подтверждена, файл отправлен."
    return "Неверный код."

def update_purchase_stage(user_id, stage):
    chat_history[user_id]["purchase_stage"] = stage
    save_chat_history()

# Flask API для админ-команд
@app.route("/send_command", methods=["POST"])
def send_command():
    data = request.json
    command = data.get("command", "").split()
    if command[0] == "confirm":
        user_id = int(command[1])
        payment_code = command[2]
        result = asyncio.run(send_file_on_confirmation(user_id, payment_code))
        return jsonify({"status": "success", "message": result})
    return jsonify({"status": "error", "message": "Неизвестная команда"})

def run_flask():
    app.run(host="0.0.0.0", port=3000)

async def main():
    Thread(target=run_flask).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
