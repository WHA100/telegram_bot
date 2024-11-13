import logging
import random
import json
import os
from dotenv import load_dotenv
from aiogram import Bot, Router, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton
import asyncio
import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox
from threading import Thread
from aiogram.filters import CommandStart
import hashlib

# Загрузка переменных окружения из файла .env
load_dotenv()

# Настройки
API_TOKEN = os.getenv('API_TOKEN')
FILE_PATH = os.getenv('FILE_PATH')
SBERBANK_ACCOUNT = os.getenv('SBERBANK_ACCOUNT')
YMONEY_ACCOUNT = os.getenv('YMONEY_ACCOUNT')
PAYEER_ACCOUNT = os.getenv('PAYEER_ACCOUNT')
CRYPTO_ACCOUNT = os.getenv('CRYPTO_ACCOUNT')
PRICE = int(os.getenv('PRICE'))
SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME')
STORAGE_FILE = os.getenv('STORAGE_FILE')

storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
router = Router()

# Хранилище переписок и кодов подтверждения
chat_history = {}

# Загрузка истории чатов при запуске
def load_chat_history():
    global chat_history
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, 'r') as f:
            chat_history = json.load(f)

# Сохранение истории чатов
def save_chat_history():
    with open(STORAGE_FILE, 'w') as f:
        json.dump(chat_history, f)

load_chat_history()

# Генерация случайного кода подтверждения
def hash_code(code):
    return hashlib.sha256(code.encode()).hexdigest()
def generate_payment_code():
    return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))


# Команда для приветственного сообщения с кнопкой "Купить файлы"
@router.message(CommandStart())
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    user_name = message.from_user.full_name

    # Инициализация информации о пользователе
    if user_id not in chat_history:
        chat_history[user_id] = {
            "name": user_name, "messages": [], "payment_code": None,
            "support_access": False, "support_contacted": False,
            "purchase_stage": "Нажал /start", "last_payment_message_id": None
        }

    chat_history[user_id]["messages"].append(f"User: {message.text}")
    update_purchase_stage(user_id, "Нажал /start")

    # Показываем кнопку "Купить файлы" или "Техподдержка" в зависимости от статуса оплаты
    if chat_history[user_id].get("support_access"):
        keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Техподдержка")]], resize_keyboard=True)
    else:
        keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Купить файлы")]], resize_keyboard=True)

    welcome_text = (
        "*Добро пожаловать!*\n\n"
        "Все предлагаемые файлы предназначены _только для Windows_.\n"
        f"Стоимость файлов: *{PRICE} рублей*.\n\n"
        "Выберите действие ниже:"
    )
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="Markdown")
    save_chat_history()  # Сохраняем историю после добавления нового пользователя
    BotInterface.update_user_list_static()


# Обработка нажатий кнопок "Купить файлы" и "Техподдержка"
@router.message(lambda message: message.text in ["Купить файлы", "Техподдержка"])
async def handle_action(message: types.Message):
    user_id = message.from_user.id
    if message.text == "Купить файлы":
        if chat_history[user_id].get("payment_code") is not None:
            await message.answer("Вы уже запросили код оплаты. Пожалуйста, завершите оплату.")
            return
        update_purchase_stage(user_id, "Нажал 'Купить файлы'")
        # Способы оплаты
        payment_choice_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Из России"), KeyboardButton(text="Не из России")],
                [KeyboardButton(text="Криптовалютой")]
            ],
            resize_keyboard=True
        )
        await message.answer("Выберите способ оплаты:", reply_markup=payment_choice_keyboard)
    elif message.text == "Техподдержка":
        if chat_history[user_id].get("support_access") and not chat_history[user_id].get("support_contacted"):
            update_purchase_stage(user_id, "Нажал 'Техподдержка'")
            chat_history[user_id]["support_contacted"] = True  # Запретить повторное нажатие
            await message.answer(
                f"Для помощи свяжитесь с [техподдержкой]({SUPPORT_USERNAME})", parse_mode="Markdown"
            )
            save_chat_history()


# Обработка выбора способа оплаты
@router.message(lambda message: message.text in ["Из России", "Не из России", "Криптовалютой"])
async def handle_payment_choice(message: types.Message):
    user_id = message.from_user.id

    # Удаляем предыдущее сообщение с инструкциями, если оно есть
    last_message_id = chat_history[user_id].get("last_payment_message_id")
    if last_message_id:
        try:
            await bot.delete_message(chat_id=user_id, message_id=last_message_id)
        except Exception as e:
            logging.warning(f"Не удалось удалить сообщение: {e}")

    # Генерируем одноразовый код подтверждения
    payment_code = generate_payment_code()
    hashed_code = hash_code(payment_code)
    chat_history[user_id]["hashed_payment_code"] = hashed_code
    save_chat_history()

    if message.text == "Не из России":
        # Показ дополнительных вариантов для "Не из России"
        additional_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Для стран СНГ"), KeyboardButton(text="Из-за рубежа")],
                [KeyboardButton(text="Выбрать другой способ оплаты")]
            ],
            resize_keyboard=True
        )
        await message.answer("Выберите подходящий вариант:", reply_markup=additional_keyboard)
    else:
        # Отправляем инструкции для "Из России" или "Криптовалютой"
        await send_payment_instructions(message, user_id, payment_code, message.text)


@router.message(lambda message: message.text in ["Для стран СНГ", "Из-за рубежа", "Выбрать другой способ оплаты"])
async def handle_additional_payment_choice(message: types.Message):
    user_id = message.from_user.id

    # Удаляем предыдущее сообщение с инструкциями
    last_message_id = chat_history[user_id].get("last_payment_message_id")
    if last_message_id:
        try:
            await bot.delete_message(chat_id=user_id, message_id=last_message_id)
        except Exception as e:
            logging.warning(f"Не удалось удалить сообщение: {e}")

    # Генерируем одноразовый код подтверждения
    payment_code = generate_payment_code()
    hashed_code = hash_code(payment_code)
    chat_history[user_id]["hashed_payment_code"] = hashed_code
    save_chat_history()

    if message.text == "Выбрать другой способ оплаты":
        # Показываем выбор способов оплаты снова
        payment_choice_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Из России"), KeyboardButton(text="Не из России")],
                [KeyboardButton(text="Криптовалютой")]
            ],
            resize_keyboard=True
        )
        await message.answer("Выберите способ оплаты:", reply_markup=payment_choice_keyboard)
    else:
        # Отправляем инструкции для выбранного варианта
        await send_payment_instructions(message, user_id, payment_code, message.text)



async def send_payment_instructions(message, user_id, payment_code, payment_type):
    """Отправка инструкций в зависимости от выбранного типа оплаты."""
    instructions = ""

    if payment_type == "Из России":
        update_purchase_stage(user_id, "Выбрал способ 'Из России'")
        instructions = (
            f"Ваш код подтверждения оплаты: *{payment_code}*\n\n"
            "Переведите *800 рублей* на карту Сбербанка:\n"
            f"`{SBERBANK_ACCOUNT}`\n\n"
            "Укажите свой *Telegram-ник* и *код подтверждения*."
        )
    elif payment_type == "Криптовалютой":
        update_purchase_stage(user_id, "Выбрал способ 'Криптовалютой'")
        instructions = (
            f"Ваш код подтверждения оплаты: *{payment_code}*\n\n"
            "Переведите сумму *800 рублей* по курсу в криптовалюте на адрес:\n"
            f"`{CRYPTO_ACCOUNT}`\n\n"
            "Укажите свой *Telegram-ник* и *код подтверждения*."
        )
    elif payment_type == "Для стран СНГ":
        update_purchase_stage(user_id, "Выбрал 'Для стран СНГ'")
        instructions = (
            f"Ваш код подтверждения оплаты: *{payment_code}*\n\n"
            "Переведите *800 рублей* на счет ЮМани:\n"
            f"`{YMONEY_ACCOUNT}`\n\n"
            "[Регистрация в ЮМани](https://yoomoney.ru)\n\n"
            "Укажите свой *Telegram-ник* и *код подтверждения*."
        )
    elif payment_type == "Из-за рубежа":
        update_purchase_stage(user_id, "Выбрал 'Из-за рубежа'")
        instructions = (
            f"Ваш код подтверждения оплаты: *{payment_code}*\n\n"
            "Переведите *800 рублей* на кошелек Payeer:\n"
            f"`{PAYEER_ACCOUNT}`\n\n"
            "[Регистрация в Payeer](https://payeer.com)\n\n"
            "Укажите свой *Telegram-ник* и *код подтверждения*."
        )

    if instructions:
        sent_message = await message.answer(instructions, parse_mode="Markdown")
        chat_history[user_id]["last_payment_message_id"] = sent_message.message_id
        save_chat_history()



# Проверка подтверждения кода и отправка файла
async def send_file_on_confirmation(user_id, payment_code):
    """Проверка кода подтверждения и отправка файла пользователю."""
    hashed_code = hash_code(payment_code)

    if chat_history.get(user_id, {}).get("hashed_payment_code") == hashed_code:
        # Отправляем файл пользователю
        file = FSInputFile(FILE_PATH)
        await bot.send_document(user_id, file)

        # Сброс данных после успешной отправки файла
        chat_history[user_id]["hashed_payment_code"] = None
        chat_history[user_id]["support_access"] = True
        update_purchase_stage(user_id, "Файл отправлен")
        save_chat_history()

        # Отправляем сообщение без кнопок
        await bot.send_message(
            user_id,
            "Файл отправлен. Теперь вам доступна техподдержка @heew9",
            reply_markup=types.ReplyKeyboardRemove()  # Убираем кнопки
        )



# Обновление статуса покупки для пользователя
def update_purchase_stage(user_id, stage):
    chat_history[user_id]["purchase_stage"] = stage
    save_chat_history()
    BotInterface.update_user_list_static()


# Tkinter интерфейс
class BotInterface:
    instance = None

    def __init__(self, root, event_loop):
        BotInterface.instance = self
        self.root = root
        self.root.title("Telegram Bot Interface")
        self.event_loop = event_loop

        # Список пользователей
        self.user_list = tk.Listbox(root, width=30, height=20)
        self.user_list.grid(row=0, column=0, rowspan=5, padx=10, pady=10)
        self.user_list.bind("<<ListboxSelect>>", self.select_user)

        # Окно переписки
        self.chat_display = scrolledtext.ScrolledText(root, width=60, height=20, wrap=tk.WORD, state='disabled')
        self.chat_display.grid(row=0, column=1, columnspan=2, padx=10, pady=10)

        # Поле ввода сообщения
        self.message_entry = tk.Entry(root, width=50)
        self.message_entry.grid(row=1, column=1, padx=10, pady=5)

        # Поля и кнопки управления
        self.payment_code_entry = tk.Entry(root, width=20)
        self.payment_code_entry.grid(row=2, column=1, sticky="w", padx=10, pady=5)
        self.confirm_button = tk.Button(root, text="Подтвердить оплату", command=self.confirm_payment)
        self.confirm_button.grid(row=2, column=2, padx=5)
        self.send_button = tk.Button(root, text="Отправить", command=self.send_message_to_user)
        self.send_button.grid(row=3, column=1, sticky="e", padx=10, pady=5)
        self.broadcast_button = tk.Button(root, text="Отправить всем", command=self.send_broadcast)
        self.broadcast_button.grid(row=4, column=1, sticky="e", padx=10, pady=5)

        # Кнопка для завершения работы бота
        self.stop_button = tk.Button(root, text="Выключить бота", command=self.stop_bot)
        self.stop_button.grid(row=5, column=2, sticky="e", padx=10, pady=5)

        self.selected_user_id = None
        self.update_user_list()

    @classmethod
    def update_user_list_static(cls):
        if cls.instance:
            cls.instance.update_user_list()

    def update_user_list(self):
        self.user_list.delete(0, tk.END)
        for user_id, info in chat_history.items():
            display_text = f"{info['name']} ({user_id}) - {info['purchase_stage']}"
            if info.get("support_access"):
                self.user_list.insert(tk.END, display_text)
                self.user_list.itemconfig(tk.END, {'bg': 'lightgreen'})  # Зеленый цвет для подтвержденных оплат
            else:
                self.user_list.insert(tk.END, display_text)

    def select_user(self, event):
        selection = self.user_list.curselection()
        if selection:
            user_index = selection[0]
            user_id = list(chat_history.keys())[user_index]
            self.selected_user_id = user_id
            self.display_chat(user_id)

    def display_chat(self, user_id):
        self.chat_display.config(state='normal')
        self.chat_display.delete(1.0, tk.END)
        for msg in chat_history[user_id]["messages"]:
            self.chat_display.insert(tk.END, f"{msg}\n")
        self.chat_display.config(state='disabled')

    def send_message_to_user(self):
        if not self.selected_user_id:
            messagebox.showerror("Ошибка", "Выберите пользователя")
            return
        message = self.message_entry.get()
        if message:
            asyncio.run_coroutine_threadsafe(
                bot.send_message(self.selected_user_id, message),
                self.event_loop
            )
            chat_history[self.selected_user_id]["messages"].append(f"Admin: {message}")
            self.message_entry.delete(0, tk.END)
            self.display_chat(self.selected_user_id)
            save_chat_history()

    def confirm_payment(self):
        if not self.selected_user_id:
            messagebox.showerror("Ошибка", "Выберите пользователя для подтверждения оплаты")
            return
        payment_code = self.payment_code_entry.get()
        asyncio.run_coroutine_threadsafe(
            send_file_on_confirmation(self.selected_user_id, payment_code),
            self.event_loop
        )
        self.payment_code_entry.delete(0, tk.END)

    def send_broadcast(self):
        message = self.message_entry.get()
        if message:
            for user_id in chat_history.keys():
                asyncio.run_coroutine_threadsafe(
                    bot.send_message(user_id, message),
                    self.event_loop
                )
                chat_history[user_id]["messages"].append(f"Admin (broadcast): {message}")
            self.message_entry.delete(0, tk.END)
            if self.selected_user_id:
                self.display_chat(self.selected_user_id)
            save_chat_history()

    def stop_bot(self):
        """Завершение работы Telegram-бота и закрытие приложения Tkinter."""
        try:
            asyncio.run_coroutine_threadsafe(bot.session.close(), self.event_loop)
            asyncio.run_coroutine_threadsafe(bot.close(), self.event_loop)
            print("Бот успешно остановлен.")
        except Exception as e:
            print(f"Ошибка при остановке бота: {e}")
        self.root.quit()  # Закрытие окна Tkinter


# Основная функция запуска
async def main():
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


# Запуск Tkinter
def run_tkinter(event_loop):
    root = tk.Tk()
    app = BotInterface(root, event_loop)
    root.mainloop()



if __name__ == '__main__':
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tkinter_thread = Thread(target=run_tkinter, args=(loop,))
        tkinter_thread.start()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Shutting down bot...")
        loop.stop()
        tkinter_thread.join()
        print("Bot stopped.")
