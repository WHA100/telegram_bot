import os
import json
import asyncio
import hashlib
import logging
import random
from fastapi import FastAPI, HTTPException
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from dotenv import load_dotenv


load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
FILE_PATH = os.getenv('FILE_PATH')
STORAGE_FILE = os.getenv('STORAGE_FILE')
PRICE = int(os.getenv('PRICE'))
SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME')

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
app = FastAPI()

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

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Купить файлы"), KeyboardButton("Техподдержка"))

    welcome_text = (
        "*Добро пожаловать!*\n"
        f"Стоимость файлов: *{PRICE} рублей*.\n"
        "Выберите действие ниже:"
    )
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="Markdown")
    save_chat_history()

# Обработка выбора действия
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

# FastAPI HTTP API для администратора
@app.post("/send_message")
async def send_message(user_id: int, text: str):
    if user_id not in chat_history:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    await bot.send_message(user_id, text)
    chat_history[user_id]["messages"].append(f"Admin: {text}")
    save_chat_history()
    return {"status": "success"}

@app.post("/confirm_payment")
async def confirm_payment(user_id: int, payment_code: str):
    hashed_code = hash_code(payment_code)

    if chat_history.get(user_id, {}).get("payment_code") == hashed_code:
        file = FSInputFile(FILE_PATH)
        await bot.send_document(user_id, file)
        chat_history[user_id]["payment_code"] = None
        chat_history[user_id]["support_access"] = True
        save_chat_history()
        return {"status": "success", "message": "Файл отправлен"}
    else:
        raise HTTPException(status_code=400, detail="Неверный код подтверждения")

# Запуск Telegram-бота и FastAPI
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import uvicorn
    load_chat_history()
    asyncio.run(main())
    uvicorn.run(app, host="0.0.0.0", port=8000)
